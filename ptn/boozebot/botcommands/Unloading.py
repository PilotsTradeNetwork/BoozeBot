"""
Cog for unloading related commands

"""

# libraries
import re
from datetime import datetime, timedelta

# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands, tasks
from discord import app_commands, NotFound

# local constants
from ptn.boozebot.constants import get_custom_assassin_id, bot, get_discord_booze_unload_channel, \
    server_council_role_ids, server_sommelier_role_id, server_wine_carrier_role_id, \
    server_mod_role_id, get_primary_booze_discussions_channel, get_fc_complete_id, server_wine_tanker_role_id, \
    get_discord_tanker_unload_channel, wine_carrier_command_channel, server_hitchhiker_role_id, \
    get_departure_announcement_channel, server_connoisseur_role_id, get_thoon_emoji_id, bot_guild_id, \
    get_wine_carrier_channel, get_steve_says_channel

# local classes
from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier

# local modules
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, GenericError, CustomError, on_generic_error
from ptn.boozebot.modules.helpers import bot_exit, check_roles, check_command_channel
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_lock, pirate_steve_conn
from ptn.boozebot.modules.PHcheck import ph_check

"""
UNLOADING COMMANDS
/wine_helper_market_open - wine carrier/conn/somm/mod/admin
/wine_helper_market_closed - wine carrier/conn/somm/mod/admin
/wine_unload  - wine carrier/conn/somm/mod/admin
/wine_unload_complete  - wine carrier/wine tanker/conn/somm/mod/admin
/tanker_unload  - wine tanker/conn/somm/mod/admin
"""

# initialise the Cog and attach our global error handler
class Unloading(commands.Cog):
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
    This class is a collection functionality for tracking a booze cruise unload operations
    """
    timed_unloads_allowed: bool = False
    last_unload_time: datetime = None
    
    # On reaction check if its in the unloading channel and if the reaction is fc complete,
    # If it is and there are 5 reactions ping the poster
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction_event):
        try:
            user = reaction_event.member

            if user.bot:
                return

            if reaction_event.channel_id != get_discord_booze_unload_channel():
                return

            channel = await bot.fetch_channel(reaction_event.channel_id)
            message = await channel.fetch_message(reaction_event.message_id)

            if message.pinned:
                return

            if message.author.id != bot.user.id:
                return

            if reaction_event.emoji.id != get_fc_complete_id():
                return

            # Check if the FC complete reaction count meets the threshold
            for message_reaction in message.reactions:
                if message_reaction.emoji.id == get_fc_complete_id() and message_reaction.count >= 5:
                    
                    # Find carrier data for this message from the database
                    pirate_steve_lock.acquire() 
                    try:
                        # Get the carrier data based on the message ID
                        pirate_steve_db.execute(
                            "SELECT * FROM boozecarriers WHERE discord_unload_in_progress = ?", 
                            (message.id,)
                        )
                        carrier_data = pirate_steve_db.fetchone()
                        
                        carrier_data = BoozeCarrier(carrier_data)
                        
                        if carrier_data and carrier_data.discord_unload_poster_id:
                            wine_carrier_channel = bot.get_channel(wine_carrier_command_channel())
                            await wine_carrier_channel.send(
                                f"<@{carrier_data.discord_unload_poster_id}> "
                                f"Your unload for {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) "
                                f"has been marked completed, Please check and run /wine_unload_complete in <#{get_steve_says_channel()}> "
                                "if it is correct."
                            )
                            
                            # Set the poster ID to None to indicate they have already been notified
                            pirate_steve_db.execute(
                                "UPDATE boozecarriers SET discord_unload_poster_id = NULL WHERE discord_unload_in_progress = ?",
                                (message.id,)  
                            )
                            pirate_steve_conn.commit()
                    finally:
                        pirate_steve_lock.release()
                break

        except Exception as e:
            print(f"Failed to process reaction: {reaction_event}. Error: {e}")

    """
    Market helper commands
    """
    
    @commands.Cog.listener()
    async def on_ready(self):           
        print("Starting the last unload time loop")
        if not self.last_unload_time_loop.is_running():
            self.last_unload_time_loop.start()
    
    @tasks.loop(seconds=60.0)
    async def last_unload_time_loop(self):
        """
        Checks if the last unload time was more than 20 minutes ago and sends a reminder message to the RSTC channel.
        """
        
        print("Running last unload time loop.")
        
        if self.last_unload_time is None:
            print("Last unload time is not set, skipping reminder check.")
            return
        
        if not ph_check():
            print("PH is not currently active, skipping reminder check.")
            return

        if datetime.now() - self.last_unload_time  >= timedelta(minutes=20):
            print("Last unload time was more than 20 minutes ago, sending reminder message.")
            try:
                rstc_channel = bot.get_channel(wine_carrier_command_channel())
                timestamp = int(self.last_unload_time.timestamp())
                content = f"Arrr, ye scurvy dogs! Our last booze unload was <t:{timestamp}:R>. Might be time to open another vessel to the people, ye think?"
                message = await rstc_channel.send(content)
                await message.edit(content=f"<@&{server_connoisseur_role_id()}> {content}")
                await message.add_reaction("🏴‍☠️")
                # Set the flag back to None so we don't keep sending messages
                self.last_unload_time = None
            except:
                print("Failed to notify RSTC channel about the last unload time.")
        else:
            print("Last unload time was less than 20 minutes ago, skipping reminder.")
            

    @app_commands.command(name="wine_helper_market_open", description="Creates a new unloading helper operation in this channel.")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()])
    async def booze_unload_market(self, interaction: discord.Interaction):
        print(f'User {interaction.user.name} requested a new booze unload in channel: {interaction.channel.name}.')

        embed = discord.Embed(title='Avast Ye!')
        embed.add_field(name='If you are INTENDING TO BUY, please react with: :airplane_arriving:.\n'
                             f'Once you are DOCKED react with: <:Assassin:{str(get_custom_assassin_id())}>\n'
                             f'Once you PURCHASE WINE, react with: :wine_glass:',
                        value='Market will be opened once we have aligned the number of commanders.',
                        inline=True)
        embed.set_footer(text='All 3 emoji counts should match by the end or Pirate Steve will be unhappy. 🏴‍☠')

        await interaction.response.send_message(embed=embed)
        # Retrieve the message object
        message = await interaction.original_response()
        await message.add_reaction('🛬')
        await message.add_reaction(f'<:Assassin:{str(get_custom_assassin_id())}>')
        await message.add_reaction('🍷')

    @app_commands.command(name="wine_helper_market_closed", description="Sends a message to indicate you have closed your market. Command sent in active channel.")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()])
    async def booze_market_closed(self, interaction: discord.Interaction):
        print(f'User {interaction.user.name} requested a to close the market in channel: {interaction.channel.name}.')
        embed = discord.Embed(title='Batten Down The Hatches! This sale is currently done!')
        embed.add_field(name='Go fight the sidewinder for the landing pad.',
                        value='Hopefully you got some booty, now go get your doubloons!')
        embed.set_footer(text='Notified by your friendly neighborhood pirate bot.')
        await interaction.response.send_message(embed=embed)
        # Retrieve the message object
        message = await interaction.original_response()
        await message.add_reaction('🏴‍☠️')


    """
    carrier unload commands
    """

    PLANETARY_CHOICES = [
        Choice(name="Star", value="Star"),
        Choice(name="Planet 1", value="Planet 1"),
        Choice(name="Planet 2", value="Planet 2"),
        Choice(name="Planet 3", value="Planet 3"),
        Choice(name="Planet 4", value="Planet 4"),
        Choice(name="Planet 5", value="Planet 5"),
        Choice(name="Planet 6", value="Planet 6")
    ]

    @app_commands.command(name="wine_unload", description="Posts a new unload notice for a carrier. Admin/Sommelier/WineCarrier role required.")
    @describe(
        carrier_id="The XXX-XXX ID string for the carrier",
        planetary_body="A string representing the location of the carrier, ie Star, P1, P2",
    )
    @app_commands.choices(planetary_body=PLANETARY_CHOICES)
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()])
    @check_command_channel(wine_carrier_command_channel())
    async def wine_carrier_unload(self, interaction: discord.Interaction, carrier_id: str, planetary_body: str):
        """
        Posts a wine unload request to the unloading channel.

        :param SlashContext ctx: The discord slash context.
        :param str carrier_id: The carrier ID string
        :param str planetary_body: Where is the carrier? Star, P1 etc?
        :returns: A message to the user
        :rtype: Union[discord.Message, dict]
        """
        
        print(f'User {interaction.user.name} has requested a new wine unload operation for carrier: {carrier_id} around the '
              f'body: {planetary_body}.')

        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            msg = f'{interaction.user.name}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.'
            print(msg)
            return await interaction.response.send_message(msg)


        pirate_steve_lock.acquire()
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )

        # We will only get a single entry back here as the carrierid is a unique field.
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())
        pirate_steve_lock.release()

        if not carrier_data:
            print(f'We failed to find the carrier: {carrier_id} in the database.')
            return await interaction.response.send_message(f'Sorry, during unload we could not find a carrier for the data: {carrier_id}.')

        wine_alert_channel = bot.get_channel(get_discord_booze_unload_channel())
        
        if carrier_data.discord_unload_notification:
            print(f'Sorry, carrier {carrier_data.carrier_identifier} is already on a wine unload.')
            return await interaction.response.send_message(f'Carrier: {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) is '
                                  f'already unloading wine. Check the notification in <#{wine_alert_channel.id}>.')
            
        if carrier_data.total_unloads >= carrier_data.run_count:
            print(f'Sorry, carrier {carrier_data.carrier_identifier} has already run all of its unloads.')
            return await interaction.response.send_message(f'Carrier: {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) has '
                                  f'already completed all of its unloads. No further unloads are possible.')

        print(f'Starting to post un-load operation for carrier: {carrier_data}')
        message_send = await interaction.channel.send("**Sending to Discord...**")

        market_conditions = 'Open for all'

        wine_load_embed = discord.Embed(
            title='Wine unload notification.',
            description=f'Carrier **{carrier_data.carrier_name} ({carrier_data.carrier_identifier})** is currently '
                        f'unloading **{carrier_data.wine_total // carrier_data.run_count}** tonnes of wine from *'
                        f'*{planetary_body}**.\n Market Conditions: **{market_conditions}**.'
        )

        wine_load_embed.set_footer(text='Please react with this emoji once completed.',
                                   icon_url=f'https://cdn.discordapp.com/emojis/{get_fc_complete_id()}.png?v=1')
        wine_unload_alert = await wine_alert_channel.send(embed=wine_load_embed)
        await message_send.delete()
        
        self.last_unload_time = None
        
        # Get the discord alert ID and drop it into the database
        discord_alert_id = wine_unload_alert.id

        print(f'Posted the wine unload alert for {carrier_data.carrier_name} ({carrier_data.carrier_identifier})')

        try:
            pirate_steve_lock.acquire()
            data = (
                discord_alert_id,
                interaction.user.id,
                f'%{carrier_id}%'
            )

            pirate_steve_db.execute('''
                UPDATE boozecarriers
                SET discord_unload_in_progress=?, totalunloads=totalunloads+1, discord_unload_poster_id=?
                WHERE carrierid LIKE (?)
            ''', data)
            pirate_steve_conn.commit()
        finally:
            pirate_steve_lock.release()
        print(f'Discord alert ID written to database for {carrier_data.carrier_identifier}')

        # Also post a note into the primary channel to go read the announcements.
        booze_cruise_chat = bot.get_channel(get_primary_booze_discussions_channel())
        await booze_cruise_chat.send(f"A new wine unload is in progress. See <#{wine_unload_alert.channel.id}>")

        return await interaction.response.send_message(
            f'Wine unload requested by {interaction.user.name} for **{carrier_data.carrier_name} ({carrier_id})** '
            f'processed successfully. Market: **{market_conditions}**.'
        )


    @app_commands.command(name="wine_timed_unload", description="Posts a new timed unload notice for a carrier. Admin/Sommelier/WineCarrier role required.")
    @describe(carrier_id="The XXX-XXX ID string for the carrier",
              planetary_body="A string representing the location of the carrier, ie Star, P1, P2",
              unload_channel="The discord channel #xxx which the carrier will run timed unloads in")
    @app_commands.choices(planetary_body=PLANETARY_CHOICES)
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()])
    @check_command_channel(wine_carrier_command_channel())
    async def wine_carrier_timed_unload(self, interaction: discord.Interaction, carrier_id: str, planetary_body: str,
                                        unload_channel: discord.TextChannel):
        """
        Posts a wine unload request to the unloading channel.

        :param SlashContext ctx: The discord slash context.
        :param str carrier_id: The carrier ID string
        :param str planetary_body: Where is the carrier? Star, P1 etc?
        :param str unload_channel: The discord unload channel.
        :returns: A message to the user
        :rtype: Union[discord.Message, dict]
        """
        await interaction.response.defer()
        print(f'User {interaction.user.name} has requested a new wine timed unload operation for carrier: {carrier_id} '
              f'around the body: {planetary_body} using unload channel: "{unload_channel}".')

        if self.timed_unloads_allowed is False:
            msg = "Timed unloads are not allowed at this time."
            print(msg)
            await interaction.followup.send(msg)
            return

        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            msg = f'{interaction.user.name}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.'
            print(msg)
            return await interaction.followup.send(msg)

        pirate_steve_lock.acquire()
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )

        # We will only get a single entry back here as the carrierid is a unique field.
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())
        pirate_steve_lock.release()

        if not carrier_data:
            print(f'We failed to find the carrier: {carrier_id} in the database.')
            return await interaction.followup.send(f'Sorry, during unload we could not find a carrier for the data: {carrier_id}.')

        wine_alert_channel = bot.get_channel(get_discord_booze_unload_channel())

        if unload_channel == wine_alert_channel:
            print('Unload channel for timed market is the same as the wine alert channel. Problem!')
            return await interaction.followup.send('You cannot use the alert channel for timed unloads. Talk with a sommelier to '
                                  'arrange a channel for this activity.')

        if carrier_data.discord_unload_notification:
            print(f'Sorry, carrier {carrier_data.carrier_identifier} is already on a wine unload.')
            return await interaction.followup.send(f'Carrier: {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) is '
                                  f'already unloading wine. Check the notification in <#{wine_alert_channel.id}>.')

        if carrier_data.total_unloads >= carrier_data.run_count:
            print(f'Sorry, carrier {carrier_data.carrier_identifier} has already run all of its unloads.')
            return await interaction.followup.send(f'Carrier: {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) has '
                                  f'already completed all of its unloads. No further unloads are possible.')

        print(f'Starting to post un-load operation for carrier: {carrier_data}')
        message_send = await interaction.channel.send("**Sending to Discord...**")

        market_conditions = 'Timed Openings'

        # Only in the case of timed openings does a channel make sense.
        unload_tracking = f' Tracked in <#{unload_channel.id}>.'

        wine_load_embed = discord.Embed(
            title='Wine unload notification.',
            description=f'Carrier **{carrier_data.carrier_name} ({carrier_data.carrier_identifier})** is currently '
                        f'unloading **{carrier_data.wine_total // carrier_data.run_count}** tonnes of wine from *'
                        f'*{planetary_body}**.'
                        f'\n Market Conditions: **{market_conditions}**.{unload_tracking}'
        )

        wine_load_embed.set_footer(text='Please react with this emoji once completed.',
                                   icon_url=f'https://cdn.discordapp.com/emojis/{get_fc_complete_id()}.png?v=1')
        wine_unload_alert = await wine_alert_channel.send(embed=wine_load_embed)
        await message_send.delete()
        
        self.last_unload_time = None
        
        # Get the discord alert ID and drop it into the database
        discord_alert_id = wine_unload_alert.id

        print(f'Posted the wine unload alert for {carrier_data.carrier_name} ({carrier_data.carrier_identifier})')

        try:
            pirate_steve_lock.acquire()
            data = (
                discord_alert_id,
                interaction.user.id,
                f'%{carrier_id}%'
            )

            pirate_steve_db.execute('''
                UPDATE boozecarriers
                SET discord_unload_in_progress=?, totalunloads=totalunloads+1, discord_unload_poster_id=?
                WHERE carrierid LIKE (?)
            ''', data)
            pirate_steve_conn.commit()
        finally:
            pirate_steve_lock.release()
        print(f'Discord alert ID written to database for {carrier_data.carrier_identifier}')

        embed = discord.Embed(title='Wine unloading starting shortly')
        # If we have an unload channel ID, go write a message there also.
        embed.add_field(
            name=f'Carrier {carrier_data.carrier_name} ({carrier_data.carrier_identifier}).\n'
                 f'Unloading {carrier_data.wine_total // carrier_data.run_count} tonnes of wine with timed '
                 f'openings.\nLocation: {planetary_body}',
            value='Market unloads will begin shortly.',
            inline=True
        )
        embed.set_footer(text='C/O: Try the commands /wine_helper_market_open and /wine_helper_market_closed.')
        await unload_channel.send(embed=embed)

        # Also post a note into the primary channel to go read the announcements.
        booze_cruise_chat = bot.get_channel(get_primary_booze_discussions_channel())
        await booze_cruise_chat.send(f"A new wine unload is in progress. See <#{wine_unload_alert.channel.id}>")

        return await interaction.followup.send(
            f'Wine unload requested by {interaction.user.name} for **{carrier_data.carrier_name} ({carrier_id})** '
            f'processed successfully. Market: **{market_conditions}**.{unload_tracking}'
        )


    @app_commands.command(name="wine_unload_complete", description="Removes any trade channel notification for unloading wine. Somm/Conn/Wine Carrier role required.")
    @describe(carrier_id="the XXX-XXX ID string for the carrier")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id(), server_wine_tanker_role_id()])
    @check_command_channel(wine_carrier_command_channel())
    async def wine_unloading_complete(self, interaction: discord.Interaction, carrier_id: str):
        print(f'Wine unloading complete for {carrier_id} flagged by {interaction.user.name}.')
        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            msg = f'{interaction.user.name}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.'
            print(msg)
            return await interaction.response.send_message(msg)

        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )

        # We will only get a single entry back here as the carrierid is a unique field.
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())
        if not carrier_data:
            print(f'No carrier found while searching the DB for: {carrier_id}')
            return await interaction.response.send_message(f'Sorry, could not find a carrier for the ID data in DB: {carrier_id}.')

        if carrier_data.discord_unload_notification and carrier_data.discord_unload_notification != 'NULL':
            # If we have a notification, remove it.
            print(f'Deleting the wine carrier unload notification for: {carrier_id}.')
            wine_alert_channel = bot.get_channel(get_discord_booze_unload_channel())
            message = await wine_alert_channel.fetch_message(carrier_data.discord_unload_notification)
            # Now delete it in the database

            try:
                pirate_steve_lock.acquire()
                data = (f'%{carrier_id}%',)
                pirate_steve_db.execute('''
                    UPDATE boozecarriers
                    SET discord_unload_in_progress=NULL, discord_unload_poster_id=NULL
                    WHERE carrierid LIKE (?)
                ''', data)
                pirate_steve_conn.commit()
            finally:
                pirate_steve_lock.release()
                
            self.last_unload_time = datetime.now()

            await message.delete()
            print(f'Deleted the carrier discord notification for carrier: {carrier_id}')
            response = f'Removed the unload notification for {carrier_data.carrier_name} ({carrier_id})'
            allowed_mentions = discord.AllowedMentions.none()
            guild = bot.get_guild(bot_guild_id())
            conn_role = guild.get_role(server_connoisseur_role_id())
            allowed_mentions.roles = [conn_role]

            await interaction.response.send_message(response, allowed_mentions=allowed_mentions)
            await interaction.edit_original_response(content=f"<@&{server_connoisseur_role_id()}> {response}", allowed_mentions=allowed_mentions)
            
        else:
            print(f'No discord alert found for carrier, {carrier_id}. It likely ran an untracked market.')
            return await interaction.response.send_message(
                f'Sorry {interaction.user.name}, we have no carrier unload notification found in the database for '
                f'{carrier_id}.'
            )


    @app_commands.command(name="tanker_unload", description="Posts a new tanker unload notice for a carrier. Admin/Sommelier/WineTanker role required.")
    @describe(carrier_id="The XXX-XXX ID string for the carrier",
              system_name="The system the carrier is present in.",
              planetary_body="A string representing the location of the carrier, ie Star, P1, P2")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_tanker_role_id()])
    @check_command_channel(wine_carrier_command_channel())
    async def wine_tanker_unload(self, interaction: discord.Interaction, carrier_id: str, system_name: str, planetary_body: str):
        """
        Tanker unload command.

        :param SlashContext ctx: The discord message context.
        :param str carrier_id: The carrier ID as a string (XXX-XXX).
        :param str system_name: The system the unload is in.
        :param str planetary_body: The planetary body the carrier is located at.
        :returns: None
        """
        print(f'User {interaction.user.name} has requested a new tanker unload operation for carrier: {carrier_id} around the '
              f'body: {planetary_body} in system: "{system_name}".')

        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            msg = f'{interaction.user.name}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.'
            print(msg)
            return await interaction.response.send_message(msg)

        pirate_steve_lock.acquire()
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )

        # We will only get a single entry back here as the carrierid is a unique field.
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())
        pirate_steve_lock.release()

        if not carrier_data:
            print(f'We failed to find the carrier: {carrier_id} in the database.')
            return await interaction.response.send_message(f'Sorry, during unload we could not find a carrier for the data: {carrier_id}.')

        tanker_unload_channel = bot.get_channel(get_discord_tanker_unload_channel())
        if carrier_data.discord_unload_notification:
            print(f'Sorry, carrier {carrier_data.carrier_identifier} is already on a wine unload.')
            return await interaction.response.send_message(f'Carrier: {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) is '
                                  f'already unloading wine. No second notification posted.')

        tanker_embed = discord.Embed(
            title='Wine unload notification.',
            description=f'Tanker {carrier_data.carrier_name} (**{carrier_data.carrier_identifier}**) is currently '
                        f'unloading **{carrier_data.wine_total // carrier_data.run_count}** tonnes of wine in '
                        f'**system: {system_name}** from **{planetary_body}**.'
        )
        tanker_embed.set_footer(text=f'Please react with this emoji once completed.',
                                icon_url=f'https://cdn.discordapp.com/emojis/{get_fc_complete_id()}.png?v=1')
        tanker_unload_alert = await tanker_unload_channel.send(embed=tanker_embed)
        
        self.last_unload_time = None

        # Get the discord alert ID and drop it into the database
        discord_alert_id = tanker_unload_alert.id

        print(f'Posted the tanker unload alert for {carrier_data.carrier_name} ({carrier_data.carrier_identifier})')

        try:
            pirate_steve_lock.acquire()
            data = (
                discord_alert_id,
                interaction.user.id,
                f'%{carrier_id}%'
            )

            pirate_steve_db.execute('''
                UPDATE boozecarriers
                SET discord_unload_in_progress=?, totalunloads=totalunloads+1, discord_unload_poster_id=?
                WHERE carrierid LIKE (?)
            ''', data)
            pirate_steve_conn.commit()
        finally:
            pirate_steve_lock.release()
        print(f'Discord alert ID written to database for {carrier_data.carrier_identifier}')

        # Also post a note into the primary channel to go read the announcements.
        booze_cruise_chat = bot.get_channel(get_primary_booze_discussions_channel())
        await booze_cruise_chat.send(f"A new wine unload is in progress. See <#{tanker_unload_alert.channel.id}>")

        return await interaction.response.send_message(
            f'Wine unload requested by {interaction.user.name} for **{carrier_data.carrier_name}** ({carrier_id}) '
            f'processed successfully. Unloading in **system: {system_name}** at **position: {planetary_body}**.'
        )


    @app_commands.command(name="toggle_timed_unloads", description="Toggle the status of timed unloads.")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    async def toggle_timed_unloads(self, interaction: discord.Interaction):
        """
        Toggle allowing timed unloads.

        Args:
            interaction (discord.Interaction): The discord interaction context.
        """

        await interaction.response.defer(ephemeral=True)

        # Log the request
        guild = bot.get_guild(bot_guild_id())
        steve_says_channel = guild.get_channel(get_steve_says_channel())
        new_status = "Disabled" if self.timed_unloads_allowed else "Enabled"
        msg = f"requested to toggle the timed unloads status to: '{new_status}'."
        print(f'{interaction.user.name} {msg}')
        await steve_says_channel.send(f'{interaction.user.mention} {msg}', silent=True)
        self.timed_unloads_allowed = not self.timed_unloads_allowed
        # Send the response message
        await interaction.edit_original_response(content=f"Timed unloads are now '{new_status}'.")