"""
Cog for unloading related commands

"""

# libraries
import re
import time

# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands, tasks
from discord import app_commands, NotFound

# local constants
from ptn.boozebot.constants import bot, server_admin_role_id, server_sommelier_role_id, \
    server_wine_carrier_role_id, server_mod_role_id, wine_carrier_command_channel, \
    server_hitchhiker_role_id, get_departure_announcement_channel, server_connoisseur_role_id, \
    get_thoon_emoji_id, bot_guild_id, get_wine_carrier_channel

# local classes
from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_lock

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
    
    # On ready check for any completed departure messages and remove them.
    @commands.Cog.listener()
    async def on_ready(self):
        guild = bot.get_guild(bot_guild_id())
        departure_channel = guild.get_channel(get_departure_announcement_channel())
        
        print("Checking for completed departure messages.")
        
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
        
    @tasks.loop(minutes = 10)
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
                
                if int(time.time()) > departure_time:
                    print("Departure time has passed.")
                    author_id = self.get_departure_author_id(message)
                    if author_id:
                        print(f"Responding to departure message from {author_id}.")
                        await message.add_reaction("⏲️")
                        await wine_carrier_chat.send(f"<@{author_id}> your scheduled departure time of <t:{departure_time}:F> has passed. If your carrier has entered lockdown or completed its jump, please use the ✅ reaction under your notice to remove it. {message.jump_url}")
            
            except Exception as e:
                print(f"Failed to process departure message while checking for time passed. message: {message.id}. Error: {e}")
    
    
    async def location_autocomplete(self, interaction: discord.Interaction, current:str) -> list[app_commands.Choice[str]]:
        locations = ["N0 Star", "N0 Planet 1", "N0 Planet 2", "N0 Planet 3", "N0 Planet 4", "N0 Planet 5", "N0 Planet 6",
                     "N0", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "N10", "N11", "N12", "N13", "N14", "N15","Gali"]
        return [
            app_commands.Choice(name=location, value=location)
            for location in locations if current.lower() in location.lower()
        ]
    
    
    @app_commands.command(name="wine_carrier_departure",
                          description="Post a departure message for a wine carrier.")
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles([server_admin_role_id(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id(), server_wine_carrier_role_id()])
    @check_command_channel(wine_carrier_command_channel())
    @app_commands.autocomplete(departure_location=location_autocomplete, arrival_location=location_autocomplete)
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
        await interaction.response.defer()

        # Convert carrier ID to uppercase
        carrier_id = carrier_id.upper().strip()

        # Validate the carrier ID format
        if not re.fullmatch(r"\w{3}-\w{3}", carrier_id):
            print(f'{interaction.user.name}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')
            return await interaction.edit_original_response(content=f'{interaction.user.name}, the carrier ID was invalid during tanker unload, '
                                        f'XXX-XXX expected received, {carrier_id}.')

        # Acquire the database lock and fetch carrier data
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )
        carrier_data = pirate_steve_db.fetchone()
        
        # Check if carrier data was found
        if not carrier_data:
            print(f'We failed to find the carrier: {carrier_id} in the database.')
            return await interaction.edit_original_response(content=f'Sorry, during unload we could not find a carrier for the data: {carrier_id}.')

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
        arrival_location = sanitize_input(arrival_location)
        departure_location = sanitize_input(departure_location)
        
        departure_time_text = ""
        
        # Handle departure time if provided as a timestamp
        if departing_at:
            try:
                departure_timestamp = departing_at
                if departure_timestamp.startswith("<t:") and departure_timestamp.endswith(">"):
                    departure_timestamp = departure_timestamp.split(":")[1]
                departure_timestamp = int(departure_timestamp)
            except ValueError:
                print(f"Departure time was not an integer: {departing_at}")
                return await interaction.edit_original_response(content=f"Departure time was not a valid timestamp: {departing_at}. You can use <https://hammertime.cyou> to generate them.")
            
            # Validate the timestamp range
            now = int(time.time())
            min_timestamp = now - 60*60*24*14 # 14 days ago
            max_timestamp = now + 60*60*24*14 # 14 days in the future
            if not (departure_timestamp > min_timestamp and departure_timestamp < max_timestamp):
                print(f"Departure time was outside 32bit range: {departing_at}")
                return await interaction.edit_original_response(content=f"Departure time was not a valid timestamp: {departing_at}. You can use <https://hammertime.cyou> to generate them.")
            departure_time_text = f" <t:{departure_timestamp}> (<t:{departure_timestamp}:R>) |"
            
        # Handle departure time if provided as a duration in minutes
        elif departing_in:
            try:
                departure_timestamp = float(departing_in)
            except ValueError:
                print(f"Departure time was not a float: {departing_in}")
                return await interaction.edit_original_response(content=f"Departing in was not a valid number: {departing_in}. It should be the number of minutes until your carrier departs.")
            
            departure_timestamp = int(departure_timestamp * 60 + int(time.time()))
            departure_time_text = f" <t:{departure_timestamp}:F> (<t:{departure_timestamp}:R>) |"
            
        # Check if the departure needs a hitchhiker ping
        if departure_location in ["N1", "N2"] and arrival_location in ["N1", "N0", "N0 Star", "N0 Planet 1", "N0 Planet 2", "N0 Planet 3", "N0 Planet 4", "N0 Planet 5", "N0 Planet 6"]:
            print("Departure needs hitchhiker ping.")
            hitchhiker_ping_text = f"| <@&{str(server_hitchhiker_role_id())}>"
            departure_time_text = f" {bot.get_emoji(get_thoon_emoji_id())} |"
        else:
            hitchhiker_ping_text = ""
            
        # Construct the departure message text
        departure_message_text = f"**{departure_location} > {arrival_location}** |{departure_time_text} **{carrier_name} ({carrier_id})** | <@{interaction.user.id}> {hitchhiker_ping_text}"
                    
        # Send the departure message to the departure announcement channel
        departure_channel = bot.get_channel(get_departure_announcement_channel())
        departure_message = await departure_channel.send(departure_message_text)
        await departure_message.add_reaction("🛬")
        await departure_message.add_reaction("✅")
        print(f"Departure message sent.")
        
        # Edit the original interaction response with the jump URL of the departure message
        return await interaction.edit_original_response(content=f"Departure message sent to {departure_message.jump_url}.")
    

    def get_departure_author_id(self, message):
        try:
            return int(message.content.split("<@")[1].split(">")[0])
        except IndexError:
            return None

    async def handle_reaction(self, message, user):
        print(f"User {user.name} reacted to their departure in {message.channel.name} removing.")
        await message.delete()