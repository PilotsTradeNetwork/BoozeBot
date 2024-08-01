"""
Cog for PH check commands and loop

"""

# libraries
import random
from datetime import datetime, timedelta

# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands, tasks
from discord import app_commands, NotFound

# local constants
from ptn.boozebot.constants import rackhams_holiday_channel, bot, bot_guild_id, server_admin_role_id, \
    server_sommelier_role_id, server_mod_role_id, server_connoisseur_role_id, holiday_query_not_started_gifs, \
    holiday_query_started_gifs, holiday_start_gif, holiday_ended_gif, get_steve_says_channel

# local modules
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, GenericError, CustomError, on_generic_error
from ptn.boozebot.modules.helpers import bot_exit, check_roles, check_command_channel
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_conn
from ptn.boozebot.modules.PHcheck import ph_check

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

    # custom global error handler
    # attaching the handler when the cog is loaded
    # and storing the old handler
    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    # detaching the handler when the cog is unloaded
    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error
        
    """
    The public holiday state checker mechanism for booze bot.
    """

    admin_override_state = False
    rackhams_holiday_active = False

    @classmethod
    @tasks.loop(minutes=15)
    async def public_holiday_loop(cls):
        """
        Command triggers periodically to check the state at Rackhams Peak. Right now this triggers every 15 minutes.

        :return: None
        """
        print("Rackham's holiday loop running.")
        if ph_check():
            print('PH detected, triggering the notifications.')
            holiday_announce_channel = bot.get_channel(rackhams_holiday_channel())
            if PublicHoliday.admin_override_state:
                print('Turning off the admin override state for holiday check.')
                PublicHoliday.admin_override_state = False

            # Check if we had a holiday flagged already
            pirate_steve_db.execute(
                '''SELECT state FROM holidaystate'''
            )
            holiday_sqlite3 = pirate_steve_db.fetchone()
            holiday_ongoing = bool(dict(holiday_sqlite3).get('state'))
            print(f'Holiday state from database: {holiday_ongoing}')
            if not holiday_ongoing:

                pirate_steve_db.execute(
                    '''UPDATE holidaystate SET state=TRUE, timestamp=CURRENT_TIMESTAMP'''
                )
                pirate_steve_conn.commit()
                print('Holiday was not ongoing, started now - flag it accordingly')
                await holiday_announce_channel.send(holiday_start_gif)
                await holiday_announce_channel.send(
                    f'Pirate Steve thinks the folks at Rackhams are partying again. '
                    f'<@&{server_admin_role_id()}>, <@&{server_sommelier_role_id()}> please take note.'
                )
            else:
                print('Holiday already flagged - no need to set it again')
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
            print('No PH detected, next check in 15 mins.')

            if current_time_utc > end_time:
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
                if holiday_ongoing:
                    pirate_steve_db.execute(
                        '''UPDATE holidaystate SET state=False, timestamp=CURRENT_TIMESTAMP'''
                    )
                    pirate_steve_conn.commit()
                    # Only post it if it is a state change.
                    print('Holiday was ongoing, no longer ongoing - flag it accordingly')
                    await holiday_announce_channel.send(holiday_ended_gif)
            else:
                print(f'Holiday has not yet expired, due at: {end_time}. Ignoring the check result for now.')

    
    @app_commands.command(name="booze_started", description="Returns a GIF for whether the holiday has started.")
    @check_roles([server_connoisseur_role_id(), server_sommelier_role_id(), server_mod_role_id(), server_admin_role_id()])
    async def holiday_query(self, interaction: discord.Interaction):
        print(f'User {interaction.user.name} wanted to know if the holiday has started.')
        gif = None

        if ph_check() or PublicHoliday.admin_override_state:
            if PublicHoliday.admin_override_state:
                print('Admin override was detected - forcefully returning True.')
            else:
                print('Rackhams holiday check says yep.')
            try:
                gif = random.choice(holiday_query_started_gifs)
                await interaction.response.send_message(gif)
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await interaction.response.send_message('Pirate Steve could not parse the gif. Try again and tell Kutu to check the log.')
        else:
            try:
                gif = random.choice(holiday_query_not_started_gifs)
                print('Rackhams holiday check says no.')
                await interaction.response.send_message(gif)
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await interaction.response.send_message('Pirate Steve could not parse the gif. Try again and tell Kutu to check the log.')


    @app_commands.command(name="booze_started_admin_override",
                          description="Overrides the holiday admin flag."
                                      "Used to set the holiday state before the polling API catches it.")
    @check_roles([server_sommelier_role_id(), server_mod_role_id(), server_admin_role_id()])
    @describe(state="True or False to override the holiday check flag.")
    @check_command_channel([get_steve_says_channel()])
    async def admin_override_holiday_state(self, interaction: discord.Interaction, state: bool):
        print(f'{interaction.user.name} requested to override the admin holiday state too: {state}.')
        PublicHoliday.admin_override_state = state
        await interaction.response.send_message(f'Set the admin holiday flag to: {state}. Check with /booze_started.')


    @app_commands.command(name="booze_duration_remaining", description="Returns roughly how long the holiday has remaining.")
    @check_roles([server_connoisseur_role_id(), server_sommelier_role_id(), server_mod_role_id(), server_admin_role_id()])
    async def remaining_time(self, interaction: discord. Interaction):
        print(f'User {interaction.user.name} wanted to know if the remaining time of the holiday.')
        if not ph_check():
            await interaction.response.send_message("Pirate Steve has not detected the holiday state yet, or it is already over.", ephemeral=True)
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

        print(f'End time calculated as: {end_time}. Which is epoch of: {end_time.strftime("%s")}')

        await interaction.response.send_message(f"Pirate Steve thinks the holiday will end around <t:{end_time.strftime('%s')}> [local"
                                                 "timezone].")
        return