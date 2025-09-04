"""
Cog for PH check commands and loop

"""

import random
from datetime import datetime, timedelta

import discord
from discord import NotFound, app_commands
from discord.app_commands import describe
from discord.ext import commands, tasks

from ptn.boozebot.botcommands.Cleaner import Cleaner
from ptn.boozebot.constants import (
    bot, get_primary_booze_discussions_channel, get_steve_says_channel, get_wine_carrier_channel, holiday_ended_gif,
    holiday_query_not_started_gifs, holiday_query_started_gifs, holiday_start_gif, rackhams_holiday_channel,
    server_council_role_ids, server_sommelier_role_id, wine_carrier_command_channel
)
from ptn.boozebot.database.database import pirate_steve_conn, pirate_steve_db, pirate_steve_db_lock
from ptn.boozebot.modules.helpers import check_command_channel, track_last_run
from ptn.boozebot.modules.PHcheck import ph_check, api_ph_check
from ptn.boozebot.modules.CommandGroups import somm_command_group, conn_command_group, everyone_command_group

"""
PUBLIC HOLIDAY TASK LOOP

Checks every 15 minutes if the PH at rackhams peak is happening and pings somm and updates the db if it is.


PUBLIC HOLIDAY COMMANDS

/booze_started - conn/somm/mod/admin
/booze_started_admin_override - somm/mod/admin
/booze_duration_remaining - conn/somm/mod/admin
"""

class PublicHoliday(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    """
    The public holiday state checker mechanism for booze bot.
    """

    rackhams_holiday_active = False
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("Starting the public holiday state checker")
        if not self.public_holiday_loop.is_running():
            self.public_holiday_loop.start()
        
        
    @staticmethod
    async def _set_public_holiday_state(state: bool, force_update: bool = False) -> tuple[bool, str]:
        if state:
            print('PH detected, triggering the notifications.')
            holiday_announce_channel = bot.get_channel(rackhams_holiday_channel())

            # Check if we had a holiday flagged already
            pirate_steve_db.execute(
                '''SELECT state FROM holidaystate'''
            )
            holiday_sqlite3 = pirate_steve_db.fetchone()
            holiday_ongoing = bool(dict(holiday_sqlite3).get('state'))
            print(f'Holiday state from database: {holiday_ongoing}')
            if not holiday_ongoing or force_update:
                async with pirate_steve_db_lock:
                    pirate_steve_db.execute(
                        '''UPDATE holidaystate SET state=TRUE, timestamp=CURRENT_TIMESTAMP'''
                    )
                    pirate_steve_conn.commit()
                
                print('Holiday was not ongoing, started now - flag it accordingly')
                await holiday_announce_channel.send(holiday_start_gif)
                await holiday_announce_channel.send(
                    f'Pirate Steve thinks the folks at Rackhams are partying again. '
                    f'<@&{server_council_role_ids()[0]}>, <@&{server_sommelier_role_id()}> please take note.'
                )
                await Cleaner.update_status_embed("bc_start")
                return True, "Holiday started and flagged in the database"
            else:
                print('Holiday already flagged - no need to set it again')
                return False, "Holiday already ongoing, no need to set it again"
        else:
            # Check if the 48 hours have expired first, to avoid scenarios of the HTTP request failing and turning
            # off an ongoing holiday.

            pirate_steve_db.execute(
                '''SELECT timestamp FROM holidaystate'''
            )
            timestamp = pirate_steve_db.fetchone()

            start_time = datetime.strptime(dict(timestamp).get('timestamp'), '%Y-%m-%d %H:%M:%S')
            end_time = start_time + timedelta(hours=48)

            current_time_utc = datetime.strptime(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
            print('No PH detected, next check in 10 mins.')

            if current_time_utc > end_time or force_update:
                # Current time is after the end time, go turn the checks off.
                print('Holiday duration expired, turning the check off.')
                holiday_announce_channel = bot.get_channel(rackhams_holiday_channel())

                # Check if we had a holiday flagged already
                pirate_steve_db.execute(
                    '''SELECT state FROM holidaystate'''
                )
                holiday_sqlite3 = pirate_steve_db.fetchone()
                holiday_ongoing = bool(dict(holiday_sqlite3).get('state'))

                print(f'Holiday state from database: {holiday_ongoing}')
                if holiday_ongoing or force_update:
                    async with pirate_steve_db_lock:
                        pirate_steve_db.execute(
                            '''UPDATE holidaystate SET state=False, timestamp=CURRENT_TIMESTAMP'''
                        )
                        pirate_steve_conn.commit()
                    
                    # Only post it if it is a state change.
                    print('Holiday was ongoing, no longer ongoing - flag it accordingly')
                    await holiday_announce_channel.send(holiday_ended_gif)
                    await Cleaner.update_status_embed("bc_end")
                    return True, "Holiday ended and flagged in the database"
                return False, "Holiday was not ongoing, no need to turn it off"
            else:
                print(f'Holiday has not yet expired, due at: {end_time}. Ignoring the check result for now.')
                return False, "Holiday has not yet expired, no need to turn it off"
                   

    @classmethod
    @tasks.loop(minutes=10)
    @track_last_run()
    async def public_holiday_loop(cls):
        """
        Command triggers periodically to check the state at Rackhams Peak. Right now this triggers every 15 minutes.

        :return: None
        """
        try:
            print("Rackham's holiday loop running.")
            await cls._set_public_holiday_state(await api_ph_check())
                
        except Exception as e:
            print(f'Error in the public holiday loop: {e}')

    
    @conn_command_group.command(name="booze_started", description="Returns a GIF for whether the holiday has started.")
    async def holiday_query(self, interaction: discord.Interaction):
        await interaction.response.defer()
        print(f'User {interaction.user.name} wanted to know if the holiday has started.')
        gif = None

        if ph_check():
            print('Rackhams holiday check says yep.')
            try:
                gif = random.choice(holiday_query_started_gifs)
                await interaction.followup.send(gif)
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await interaction.followup.send('Pirate Steve could not parse the gif. Try again and tell Council to check the log.')
        else:
            try:
                gif = random.choice(holiday_query_not_started_gifs)
                print('Rackhams holiday check says no.')
                await interaction.followup.send(gif)
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await interaction.followup.send('Pirate Steve could not parse the gif. Try again and tell Council to check the log.')


    @somm_command_group.command(name="started__override",
                          description="Overrides the holiday admin flag."
                                      "Used to set the holiday state before the polling API catches it.")
    @describe(state="True or False to override the holiday check flag.",
              force_update="Force the update of the holiday state, even if it is already set.")
    @check_command_channel([get_steve_says_channel()])
    async def admin_override_holiday_state(self, interaction: discord.Interaction, state: bool, force_update: bool = False):
        print(f'{interaction.user.name} requested to override the admin holiday state too: {state}, forced: {force_update}.')
        success, message = await self._set_public_holiday_state(state, force_update)
        await interaction.response.send_message(f'{message}. Check with /booze_started.')
        
    @somm_command_group.command(name="timestamp_override",
                          description="Overrides the holiday start time."
                                      "Used to set the cruise start time used to get the duration")
    @describe(timestamp="Date time of the the cruise starting in the format YYYY-MM-DD HH:MI:SS")
    @check_command_channel([get_steve_says_channel()])
    async def admin_override_start_timestamp(self, interaction: discord.Interaction, timestamp: str):
        print(f'{interaction.user.name} requested to override the start time to: {timestamp}.')
        
        try:
            datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            await interaction.response.send_message(f'Invalid timestamp format. Please use YYYY-MM-DD HH:MI:SS.', ephemeral=True)
            return

        # Check if we had a holiday flagged already
        pirate_steve_db.execute(
            '''SELECT state FROM holidaystate'''
        )
        holiday_sqlite3 = pirate_steve_db.fetchone()
        holiday_ongoing = bool(dict(holiday_sqlite3).get('state'))
        print(f'Holiday state from database: {holiday_ongoing}')
        if holiday_ongoing:
            print('Holiday ongoing - updating timestamp')

            pirate_steve_db.execute(
                f'''UPDATE holidaystate SET state=TRUE, timestamp=\'{timestamp}\''''
            )
            pirate_steve_conn.commit()
            
            await interaction.response.send_message(f'Set the cruise start time to: {timestamp}. Check with /booze_duration_remaining.')
            
        else:
            print('Holiday was not ongoing')
            await interaction.response.send_message(f'No holiday has been detected yet, Wait until steve detects the holiday before using this command.')
        

    @everyone_command_group.command(name="duration_remaining", description="Returns roughly how long the holiday has remaining.")
    @check_command_channel([get_wine_carrier_channel(), get_steve_says_channel(), wine_carrier_command_channel(), get_primary_booze_discussions_channel()])
    async def remaining_time(self, interaction: discord. Interaction):
        print(f'User {interaction.user.name} wanted to know if the remaining time of the holiday.')
        await interaction.response.defer()
        if not ph_check():
            await interaction.edit_original_response(content="Pirate Steve has not detected the holiday state yet, or it is already over.")
            return
        print('Holiday ongoing, go figure out how long is left.')
        # Ok the holiday is ongoing
        duration_hours = 48

        # Get the starting timestamp

        pirate_steve_db.execute(
            '''SELECT timestamp FROM holidaystate'''
        )
        timestamp = pirate_steve_db.fetchone()

        start_time = datetime.strptime(dict(timestamp).get('timestamp'), '%Y-%m-%d %H:%M:%S')
        end_time = start_time + timedelta(hours=duration_hours)
        end_timestamp = int(end_time.timestamp())
        print(f'End time calculated as: {end_time}. Which is epoch of: {end_timestamp}')

        await interaction.edit_original_response(
            content=f"Pirate Steve thinks the holiday will end around <t:{end_timestamp}> (<t:{end_timestamp}:R>) [local timezone]."
        )
