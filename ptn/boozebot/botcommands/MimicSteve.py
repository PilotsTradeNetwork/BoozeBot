from loguru import logger

# discord.py
import discord
from discord import app_commands
from discord.ext import commands

# local constants
from ptn.boozebot.constants import (
    get_steve_says_channel, server_council_role_ids, server_mod_role_id, server_sommelier_role_id
)
# local modules
from ptn.boozebot.modules.helpers import check_roles, get_channel

"""
MIMIC STEVE COMMAND

/steve_says - somm/mod/admin
"""


class MimicSteve(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(name="Reply as Steve", callback=self.reply_as_steve)
        logger.debug("Adding context menu command: Reply as Steve")
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    async def reply_as_steve(self, interaction: discord.Interaction, reply_message: discord.Message):
        class ReplyModal(discord.ui.Modal, title="Reply as PirateSteve"):
            message = discord.ui.TextInput(label="Message", style=discord.TextStyle.long)
            
            logger.debug(f"Modal for {interaction.user.name} to reply as PirateSteve opened.")

            async def on_submit(self, interaction: discord.Interaction):
                
                logger.debug(f"User {interaction.user.name} submitted a reply as PirateSteve: {self.message.value}.")
                
                await interaction.response.send_message("Replying as PirateSteve...", ephemeral=True)
                await MimicSteve._steve_speak(interaction, self.message.value, reply_message=reply_message)

        logger.info(
            f"User {interaction.user.name} has requested to reply as PirateSteve to: {reply_message.jump_url}."
        )
        await interaction.response.send_modal(ReplyModal())

    """
    This class implements functionality for a user to send commands as PirateSteve
    """

    @app_commands.command(name="steve_says", description="Send a message as PirateSteve.")
    @app_commands.describe(
        message="The message to send",
        send_channel="The channel to send the message in",
    )
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    async def mimic_steve(
        self, interaction: discord.Interaction, message: str, send_channel: discord.TextChannel = None
    ):
        """
        Command to send a message as pirate steve. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :param str message: The message for the bot to send.
        :param TextChannel send_channel: The channel for the bot to send the message to.
        :returns: 2 discord messages, 1 in the channel it is run and 1 as the output.
        """
        
        logger.info(
            f"User {interaction.user.name} has requested to send the message {message} as PirateSteve "
            f"in: {send_channel}."
        )
        
        if not send_channel:
            logger.debug("No send_channel provided, using the interaction channel.")
            send_channel = interaction.channel

        logger.debug(f"Sending message as PirateSteve in channel: {send_channel}.")

        await interaction.response.send_message("Replying as PirateSteve...", ephemeral=True)
        await self._steve_speak(interaction, message, send_channel=send_channel)

    @staticmethod
    async def _steve_speak(
        interaction: discord.Interaction,
        message: str,
        send_channel: discord.TextChannel = None,
        reply_message: discord.Message = None,
    ):
        logger.info(
            f"User {interaction.user.name} is sending the message {message} as PirateSteve "
            f"in: {send_channel if send_channel else reply_message.channel}."
        )
        steve_says_channel = await get_channel(get_steve_says_channel())
        try:
            if reply_message:
                send_channel = reply_message.channel
                msg = await reply_message.reply(content=message)
                logger.debug("Sent reply message as PirateSteve.")
            elif send_channel:
                msg = await send_channel.send(content=message)
                logger.debug("Sent message as PirateSteve.")
            else:
                await interaction.edit_original_response(content="No channel specified")
                logger.error("No channel specified for PirateSteve to send message.")
                return

            message = message.replace("`", "\u200b`")

            await interaction.edit_original_response(
                content=f"Pirate Steve said: ``{message}\u200b`` in: {send_channel} successfully"
            )
            await steve_says_channel.send(
                f"User {interaction.user.name} sent the message ``{message}\u200b`` as PirateSteve in: {send_channel.name}. {msg.jump_url}"
            )
            logger.info(
                f"User {interaction.user.name} successfully sent the message {message} as PirateSteve "
                f"in: {send_channel}."
            )
        except discord.DiscordException:
            logger.exception(f"Failed to send the message {message} as PirateSteve in: {send_channel}.")
            await interaction.edit_original_response(
                content=f"Pirate Steve failed to say: ``{message}\u200b`` in: {send_channel}."
            )
