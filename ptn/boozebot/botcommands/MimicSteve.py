"""
Cog for the commands related to opening and closing the cruise channels and roles

"""

# libraries
import re

# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands
from discord import app_commands

# local constants
from ptn.boozebot.constants import server_admin_role_id, server_sommelier_role_id, server_mod_role_id, bot, get_steve_says_channel

# local modules
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, GenericError, CustomError, on_generic_error
from ptn.boozebot.modules.helpers import bot_exit, check_roles, check_command_channel


"""
MIMIC STEVE COMMAND

/steve_says - somm/mod/admin
"""

class MimicSteve(commands.Cog):
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
    This class implements functionality for a user to send commands as PirateSteve
    """

    @app_commands.command(name="steve_says", description="Send a message as PirateSteve.")
    @app_commands.describe(message="The message to send",
                           send_channel="The channel to send the message in",
                            )
    @check_roles([server_admin_role_id(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel(get_steve_says_channel())
    async def mimic_steve(self, interaction: discord.Interaction, message: str, send_channel: discord.TextChannel):
        """
        Command to send a message as pirate steve. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :param str message: The message for the bot to send.
        :param TextChannel send_channel: The channel for the bot to send the message to.
        :returns: 2 discord messages, 1 in the channel it is run and 1 as the output.
        """
        print(f"User {interaction.user.name} has requested to send the message {message} as PirateSteve in: {send_channel}.")
 
        print(f"Channel resolved into: {send_channel.name}. Checking for any potential use names to be resolved.")

        possible_id = None
        # Try to resolve any @<int> to a user
        for word in message.split():
            if word.startswith("@"):
                try:
                    print(f"Potential user id found: {word}.")
                    # this might be a user ID, int convert it
                    possible_id = int(re.search(r"\d+", word).group())

                    # Ok this was in fact an int, try to see if it resolves to a discord user
                    member = await bot.fetch_user(possible_id)
                    print(f"Member determined as: {member}")

                    message = message.replace(word, f"<@{member.id}>")
                    print(f"New message is: {message}")
                except discord.errors.NotFound as ex:
                    print(
                        f'Potential user string "{possible_id if possible_id else word}" is invalid: {ex}. Continuing '
                        f"on as-is"
                    )
                except ValueError as ex:
                    # Ok continue on anyway and send it as-is
                    print(f"Error converting the word: {word}. {ex}")

        response = f"{message}"
        
        await interaction.response.defer(ephemeral=True)
        
        msg = await send_channel.send(content=response)

        if msg:
            print("Message was impersonated successfully.")
            await interaction.edit_original_response(content=f"Pirate Steve said: {message} in: {send_channel} successfully")
            return

        # Error case
        print(f"Error sending message in {message} channel: {send_channel}")
        await interaction.edit_original_response(content=f"Pirate Steve failed to say: {message} in: {send_channel}.")

        return