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
from ptn.boozebot.constants import server_council_role_ids, server_sommelier_role_id, server_mod_role_id, bot, get_steve_says_channel, bot_guild_id

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
        self.ctx_menu = app_commands.ContextMenu(
            name="Reply as Steve",
            callback=self.reply_as_steve
        )
        self.bot.tree.add_command(self.ctx_menu)

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
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    async def reply_as_steve(self, interaction: discord.Interaction, reply_message: discord.Message):
        class ReplyModal(discord.ui.Modal, title="Reply as PirateSteve"):
            message = discord.ui.TextInput(label="Message", style=discord.TextStyle.long)

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.send_message("Replying as PirateSteve...", ephemeral=True)
                await MimicSteve._steve_speak(interaction, self.message.value, reply_message=reply_message)

        print(f"User {interaction.user.name} has requested to reply as PirateSteve to: {reply_message.jump_url}.")
        await interaction.response.send_modal(ReplyModal())

    """
    This class implements functionality for a user to send commands as PirateSteve
    """
    @app_commands.command(name="steve_says", description="Send a message as PirateSteve.")
    @app_commands.describe(message="The message to send",
                           send_channel="The channel to send the message in",
                            )
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    async def mimic_steve(self, interaction: discord.Interaction, message: str, send_channel: discord.TextChannel = None):
        """
        Command to send a message as pirate steve. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :param str message: The message for the bot to send.
        :param TextChannel send_channel: The channel for the bot to send the message to.
        :returns: 2 discord messages, 1 in the channel it is run and 1 as the output.
        """
        if send_channel == None:
            send_channel = interaction.channel
        
        print(f"User {interaction.user.name} has requested to send the message {message} as PirateSteve in: {send_channel.name}.")
        
        await interaction.response.send_message("Replying as PirateSteve...", ephemeral=True)
        await self._steve_speak(interaction, message, send_channel=send_channel)


    @staticmethod
    async def _steve_speak(interaction: discord.Interaction, message: str, send_channel: discord.TextChannel = None, reply_message: discord.Message = None):
        guild = bot.get_guild(bot_guild_id())
        steve_says_channel = guild.get_channel(get_steve_says_channel())
        try:
            if reply_message:
                send_channel = reply_message.channel
                msg = await reply_message.reply(content=message)
            elif send_channel:
                msg = await send_channel.send(content=message)
            else:
                await interaction.edit_original_response(content=f"No channel specified")
                print("No channel specified")
                return
            
            await interaction.edit_original_response(content=f"Pirate Steve said: `{message}` in: {send_channel} successfully")
            await steve_says_channel.send(f"User {interaction.user.name} sent the message `{message}` as PirateSteve in: {send_channel.name}. {msg.jump_url}")
            print("Message was impersonated successfully.")
        except discord.DiscordException:
            print(f"Error sending message in {message} channel: {send_channel}")
            await interaction.edit_original_response(content=f"Pirate Steve failed to say: `{message}` in: {send_channel}.")