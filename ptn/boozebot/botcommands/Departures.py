"""
Cog for unloading related commands

"""

# libraries
import re
import time
from datetime import datetime, timedelta
from typing import Literal
import logging
 
# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands, tasks
from discord import app_commands, NotFound

# local constants
from ptn.boozebot.constants import bot, server_council_role_ids, server_sommelier_role_id, \
    server_wine_carrier_role_id, server_mod_role_id, wine_carrier_command_channel, \
    server_hitchhiker_role_id, get_departure_announcement_channel, server_connoisseur_role_id, \
    get_thoon_emoji_id, bot_guild_id, get_wine_carrier_channel, get_steve_says_channel, N_SYSTEMS

# local classes
from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier
from ptn.boozebot.database.database import pirate_steve_db

# local modules
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, GenericError, CustomError, on_generic_error
from ptn.boozebot.modules.helpers import bot_exit, check_roles, check_command_channel

"""
UNLOADING COMMANDS
/wine_carrier_departure - wine carrier/somm/mod/admin
"""

# initialise the Cog and attach our global error handler
class Departures(commands.Cog):
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
    This class is a collection functionality for posting departure messages for carriers.
    """

    system_choices = [Choice(name=f"{system_id} ({system_name})", value=system_id) for system_id, system_name in N_SYSTEMS.items()]

    departure_announcement_status: Literal["Disabled", "Upwards", "All"] = "Disabled"
    # On ready check for any completed departure messages and remove them.
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            guild = bot.get_guild(bot_guild_id())
        except Exception as e:
            logging.exception(f"Failed to get guild: {e}")
        try:
            departure_channel = guild.get_channel(get_departure_announcement_channel())
        except Exception as e:
            logging.exception(f"Failed to get departure_channel: {e}")

        print("Checking for completed departure messages.")
        try:
            async for message in departure_channel.history(limit=100):
                try:
                    if message.pinned:
                        continue

                    if message.author.id != bot.user.id:
                        continue

                    for reaction in message.reactions:
                        if reaction.emoji == "✅":
                            async for user in reaction.users():
                                if self.get_departure_author_id(message) == user.id:
                                    await self.handle_reaction(reaction.message, user)
                except Exception as e:
                    print(f"Failed to process departure message while checking for closing. message: {message.id}. Error: {e}")
        except Exception as e:
            logging.exception(f"Failed to get departure_channel history: {e}")

        print("Starting the departure message checker")
        if not self.check_departure_messages_loop.is_running():
            self.check_departure_messages_loop.start()

    # On reaction check if its in the departures channel and if it was from who posted the departure, if it is remove it.
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction_event):
        try:
            user = reaction_event.member

            if user.bot:
                return

            if reaction_event.channel_id != get_departure_announcement_channel():
                return

            channel = await bot.fetch_channel(reaction_event.channel_id)
            message = await channel.fetch_message(reaction_event.message_id)

            if message.pinned:
                return

            if message.author.id != bot.user.id:
                return

            if reaction_event.emoji.name != "✅":
                return

            if not self.get_departure_author_id(message) == user.id:
                return

            await self.handle_reaction(message, user)
        except Exception as e:
            print(f"Failed to process reaction: {reaction_event}. Error: {e}")

    @tasks.loop(minutes = 5)
    async def check_departure_messages_loop(self):
        guild = bot.get_guild(bot_guild_id())
        departure_channel = guild.get_channel(get_departure_announcement_channel())
        wine_carrier_chat = guild.get_channel(get_wine_carrier_channel())

        print("Checking for passed departure messages.")
        async for message in departure_channel.history(limit=100):

            try:
                if message.pinned:
                    continue

                if message.author.id != bot.user.id:
                    continue
                
                if len(message.embeds) > 0:
                    continue

                print("Departure message found.")

                has_reacted = False
                for reaction in message.reactions:
                    if reaction.emoji == "⏲️":
                        async for user in reaction.users():
                            if user.id == bot.user.id:
                                has_reacted = True
                                break

                if has_reacted:
                    print("Departure message has been responded to.")
                    continue

                content = message.content
                departure_time = content.split("|")[1].replace(" ", "")

                if departure_time.startswith("<t:"):
                    departure_time = departure_time.split(":")[1]
                elif departure_time == f"{bot.get_emoji(get_thoon_emoji_id())}":
                    departure_time = message.created_at.timestamp() + 25 * 60

                try:
                    departure_time = int(departure_time)
                except ValueError:
                    print(f"Departure time was not an integer: {departure_time}, Probably means they never set a departure time.")
                    continue

                print(f"Departure time: {departure_time}")

                if int(time.time()) > departure_time + 10 * 60:  # Allow a 10-minute grace period
                    print("Departure time has passed.")
                    author_id = self.get_departure_author_id(message)
                    if author_id:
                        print(f"Responding to departure message from {author_id}.")
                        await message.add_reaction("⏲️")
                        await wine_carrier_chat.send(f"<@{author_id}> your scheduled departure time of <t:{departure_time}:F> has passed. If your carrier has entered lockdown or completed its jump, please use the ✅ reaction under your notice to remove it. {message.jump_url}")

            except Exception as e:
                print(f"Failed to process departure message while checking for time passed. message: {message.id}. Error: {e}")

    @app_commands.command(name="wine_carrier_departure",
                          description="Post a departure message for a wine carrier.")
    @describe(carrier_id="The XXX-XXX ID string for the carrier",
              departure_location="The location the carrier is departing from.",
              arrival_location="The location the carrier is arriving at.",
              departing_at="The unix timestamp, or discord timestamp of the carrier departure.",
              departing_in="The time in minutes until the carrier departs."
              )
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()])
    @check_command_channel(wine_carrier_command_channel())
    @app_commands.choices(arrival_location=system_choices, departure_location=system_choices)
    async def wine_carrier_departure(self, interaction: discord.Interaction, carrier_id: str, departure_location: str, arrival_location: str, departing_at: str = None, departing_in: str = None):
        """
        Handles the wine carrier departure operation.

        Args:
            interaction (discord.Interaction): The discord interaction context.
            carrier_id (str): The carrier ID string.
            departure_location (str): The location the carrier is departing from.
            arrival_location (str): The location the carrier is arriving at.
            departing_at (str, optional): The unix timestamp of when the carrier is departing. Defaults to None.
            departing_in (str, optional): The time in minutes until the carrier departs. Defaults to None.
        """

        # Log the request
        print(f'User {interaction.user.name} has requested a new wine carrier departure operation for carrier: {carrier_id} from the '
              f'location: {departure_location} to {arrival_location}.')

        # Defer the interaction response to allow more time for processing
        await interaction.response.defer(ephemeral=True)

        # Convert carrier ID to uppercase
        carrier_id = carrier_id.upper().strip()

        guild = bot.get_guild(bot_guild_id())
        steve_says_channel = guild.get_channel(get_steve_says_channel())
        # Validate the carrier ID format
        if not re.fullmatch(r"\w{3}-\w{3}", carrier_id):
            msg = f'{interaction.user.name}, the carrier ID was invalid, "XXX-XXX" expected, received "{carrier_id}".'
            print(msg)
            await interaction.edit_original_response(content=msg)
            await steve_says_channel.send(f"Error for {interaction.user.name} during `/wine_carrier_departure` command: {msg}")
            return

        # Acquire the database lock and fetch carrier data
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )
        carrier_data = pirate_steve_db.fetchone()

        # Check if carrier data was found
        if not carrier_data:
            msg = f'could not find a carrier for the data: "{carrier_id}".'
            print(msg)
            await interaction.edit_original_response(content=f"Sorry, we {msg}")
            await steve_says_channel.send(f"Error for {interaction.user.name} during `/wine_carrier_departure` command: {msg}")
            return

        # Create a BoozeCarrier object from the fetched data
        carrier_data = BoozeCarrier(carrier_data)

        carrier_name = carrier_data.carrier_name
        carrier_id = carrier_data.carrier_identifier

        # Function to sanitize input by removing certain characters
        def sanitize_input(text):
            return text.replace("<", "").replace(">", "").replace("@", "").replace("|", "")

        # Sanitize the input data
        carrier_name = sanitize_input(carrier_name)
        carrier_id = sanitize_input(carrier_id)

        departure_timestamp = None

        thoon_inputs = [f"<:thoon:{get_thoon_emoji_id()}>", "thoon"]
        # Handle thoon
        if (departing_at and departing_at.lower() in thoon_inputs) or (departing_in and departing_in.lower() in thoon_inputs):
            print("Thoon given as departure time")
        # Handle departure time if provided as a timestamp
        elif departing_at:
            try:
                departure_timestamp = departing_at
                if departure_timestamp.startswith("<t:") and departure_timestamp.endswith(">"):
                    departure_timestamp = departure_timestamp.rstrip(">").split(":")[1]
                departure_timestamp = int(departure_timestamp)
            except ValueError:
                msg = f"Departure time was not a valid timestamp: {departing_at}"
                print(msg)
                await interaction.edit_original_response(content=f"{msg}. You can use <https://hammertime.cyou> to generate them.")
                await steve_says_channel.send(f"Error for {interaction.user.name} during `/wine_carrier_departure` command: {msg}")
                return

            # Validate the timestamp range
            now = int(time.time())
            min_timestamp = now - 60*60*24*14 # 14 days ago
            max_timestamp = now + 60*60*24*14 # 14 days in the future
            if not (min_timestamp < departure_timestamp < max_timestamp):
                msg = f"Departure time must be within 2 weeks of now: {departing_at}"
                print(msg)
                await interaction.edit_original_response(content=msg)
                await steve_says_channel.send(f"Error for {interaction.user.name} during `/wine_carrier_departure` command: {msg}")
                return

        # Handle departure time if provided as a duration in minutes
        elif departing_in:
            try:
                departure_timestamp = float(departing_in)
            except ValueError:
                msg = f"Departing in was not a valid number: {departing_in}"
                print(msg)
                await interaction.edit_original_response(content=f"{msg}. It should be the number of minutes until your carrier departs.")
                await steve_says_channel.send(f"Error for {interaction.user.name} during `/wine_carrier_departure` command: {msg}")
                return

            departure_timestamp = int(departure_timestamp * 60 + int(time.time()))

        departing_thoon = False
        if departure_timestamp:
            departure_time_text = f" <t:{departure_timestamp}:f> (<t:{departure_timestamp}:R>) |"
            departing_thoon = datetime.fromtimestamp(departure_timestamp) < datetime.now() + timedelta(hours=2)
        else:
            departure_time_text = f" {bot.get_emoji(get_thoon_emoji_id())} |"

        # Check if the departure needs a hitchhiker ping
        hitchhiker_systems = [0, 1, 2, 3]
        thoon_systems = [0, 1]

        try:
            departure_system_index = int(departure_location.split(" ")[0][1:])
        except ValueError:
            departure_system_index = 16

        try:
            arrival_system_index = int(arrival_location.split(" ")[0][1:])
        except ValueError:
            arrival_system_index = 16
            
        departure_location = f"{departure_location} ({N_SYSTEMS[departure_location]})"
        arrival_location = f"{arrival_location} ({N_SYSTEMS[arrival_location]})"
            

        is_hitchhiking_trip = departure_system_index in hitchhiker_systems and arrival_system_index in hitchhiker_systems
        is_thoon_trip = departure_system_index in thoon_systems or arrival_system_index in thoon_systems
        if is_thoon_trip and departing_thoon:
            departure_time_text = f" {bot.get_emoji(get_thoon_emoji_id())} |"

        hitchhiker_ping_text = ""
        # Set the direction arrow text and determine if hitchhiker ping is needed
        if departure_system_index == arrival_system_index:
            msg = "Departure and arrival are the same system."
            print(msg)
            await interaction.edit_original_response(content=msg)
            await steve_says_channel.send(f"Error for {interaction.user.name} during `/wine_carrier_departure` command: {msg}")
            return
        elif departure_system_index < arrival_system_index:
            print("Departure system is above arrival system.")
            direction_arrow = "⬇️"
        elif departure_system_index > arrival_system_index:
            print("Departure system is below arrival system.")
            direction_arrow = "⬆️"
            if is_hitchhiking_trip:
                print("Departure needs hitchhiker ping.")
                hitchhiker_ping_text = f"| <@&{str(server_hitchhiker_role_id())}>"
        else:
            print("Failed to determine direction arrow.")
            direction_arrow = ""

        # Check if departure announcements are enabled
        msg = ""
        if self.departure_announcement_status  == "Disabled":
            msg = "Departure announcements are currently disabled."
        elif self.departure_announcement_status == "Upwards" and direction_arrow == "⬇️":
            msg = "Departure announcements are currently only enabled for jumps moving up towards N0"
        if msg:
            print(msg)
            await interaction.edit_original_response(content=msg)
            await steve_says_channel.send(f"Error for {interaction.user.name} during `/wine_carrier_departure` command: {msg}")
            return

        # Construct the departure message text
        departure_message_text = f"**{direction_arrow} {departure_location} > {arrival_location}** |{departure_time_text} **{carrier_name} ({carrier_id})** | <@{interaction.user.id}> {hitchhiker_ping_text}"

        # Send the departure message to the departure announcement channel
        departure_channel = bot.get_channel(get_departure_announcement_channel())
        departure_message = await departure_channel.send(departure_message_text)
        await departure_message.add_reaction("🛬")
        await departure_message.add_reaction("✅")
        print("Departure message sent.")

        # Edit the original interaction response with the jump URL of the departure message
        await interaction.edit_original_response(content=f"Departure message sent to {departure_message.jump_url}.")

    @app_commands.command(name="set_allowed_departures", description="Set the status of departure announcements.")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @describe(status="The status to set for departure announcements.")
    async def set_allowed_departures(self, interaction: discord.Interaction, status: Literal["Disabled", "Upwards", "All"]):
        """
        Set the status of departure announcements.

        Args:
            interaction (discord.Interaction): The discord interaction context.
            status (Literal["Disabled", "Upwards", "All"]): The status of departure announcements.
        """

        await interaction.response.defer(ephemeral=True)

        # Log the request
        guild = bot.get_guild(bot_guild_id())
        steve_says_channel = guild.get_channel(get_steve_says_channel())
        msg = f"requested to set the departure announcement status to: '{status}'."
        print(f'{interaction.user.name} {msg}')
        await steve_says_channel.send(f'{interaction.user.mention} {msg}', silent=True)
        # Set the departure announcement status
        self.departure_announcement_status = status
        # Send the response message
        await interaction.edit_original_response(content=f"Departure announcements are now '{status}'.")
    
    @app_commands.command(name="official_carrier_departure", description="Post an official carrier departure message.")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    @describe(carrier_id="The XXX-XXX ID string for the carrier",
              operated_by="The user who is operating the carrier.",
              departure_location="The location the carrier is departing from.",
              arrival_location="The location the carrier is arriving at.",
              departure_time_type="The type of departure time to use. Start/End of PH or a specific time.",
              departure_timestamp="The unix timestamp, or discord timestamp of the carrier departure.")
    @app_commands.choices(arrival_location=system_choices, departure_location=system_choices, departure_time_type=[
        Choice(name="Start Of Cruise", value="Start Of Cruise"),
        Choice(name="End of Cruise", value="End of Cruise"),
        Choice(name="Custom (requires timestamp)", value="Custom (requires timestamp)"),
    ])
    async def official_carrier_departure(self, interaction: discord.Interaction, carrier_id: str, operated_by: discord.Member, departure_location: str, arrival_location: str, departure_time_type: str, departure_timestamp: str = ""):
        print(f"User {interaction.user.name} has requested an official carrier departure for carrier: {carrier_id} from {departure_location} to {arrival_location} with type: {departure_time_type}.")
        await interaction.response.defer()
        
        # Convert carrier ID to uppercase
        carrier_id = carrier_id.upper().strip()
        guild = bot.get_guild(bot_guild_id())
        
        # Validate the carrier ID format
        if not re.fullmatch(r"\w{3}-\w{3}", carrier_id):
            msg = f'{interaction.user.name}, the carrier ID was invalid, "XXX-XXX" expected, received "{carrier_id}".'
            print(msg)
            await interaction.edit_original_response(content=msg)
            return
        
        # Acquire the database lock and fetch carrier data
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )
        carrier_data = pirate_steve_db.fetchone()
        
        # Check if carrier data was found
        if not carrier_data:
            msg = f'could not find a carrier for the data: "{carrier_id}".'
            print(msg)
            await interaction.edit_original_response(content=f"Sorry, we {msg}")
            return
        
        # Create a BoozeCarrier object from the fetched data
        carrier_data = BoozeCarrier(carrier_data)
        
        carrier_name = carrier_data.carrier_name
        carrier_id = carrier_data.carrier_identifier
        
        departure_location = f"{departure_location} ({N_SYSTEMS[departure_location]})"
        arrival_location = f"{arrival_location} ({N_SYSTEMS[arrival_location]})"
        
        if departure_time_type == "Start Of Cruise":
            departure_time_text = "Departs when the public holiday is announced at Rackham's Peak"
        elif departure_time_type == "End of Cruise":
            departure_time_text = "Departs when the public holiday ends at Rackham's Peak"
        elif departure_time_type == "Custom (requires timestamp)":
            if not departure_timestamp:
                msg = "You must provide a departure timestamp when using the 'Custom' departure time type."
                print(msg)
                await interaction.edit_original_response(content=msg)
                return
            
            try:
                if departure_timestamp.startswith("<t:") and departure_timestamp.endswith(">"):
                    departure_timestamp = departure_timestamp.rstrip(">").split(":")[1]
                departure_timestamp = int(departure_timestamp)
            except ValueError:
                msg = f"Departure timestamp was not a valid integer: {departure_timestamp}"
                print(msg)
                await interaction.edit_original_response(content=msg)
                return
            
            departure_time_text = f"Departing at <t:{departure_timestamp}:f> (<t:{departure_timestamp}:R>)"
        
        embed = discord.Embed(
            description=f"## {carrier_name} ({carrier_id})\n"
                        f"## {departure_location} > {arrival_location}\n"
                        f"{departure_time_text}\n"
                        f"Operated by {operated_by.mention}",
            color=15611236
        )
        
        departure_channel = bot.get_channel(get_departure_announcement_channel())
        departure_message = await departure_channel.send(embed=embed)
        await departure_message.add_reaction("🛬")
        await interaction.edit_original_response(content=f"Official carrier departure message sent: {departure_message.jump_url}")
    


    def get_departure_author_id(self, message):
        try:
            return int(message.content.split("<@")[1].split(">")[0])
        except IndexError:
            return None

    async def handle_reaction(self, message, user):
        print(f"User {user.name} reacted to their departure in {message.channel.name} removing.")
        await message.delete()
