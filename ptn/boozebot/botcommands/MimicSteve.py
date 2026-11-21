import re
from typing import cast, override

import discord
from discord import app_commands
from discord.app_commands import ContextMenu
from discord.ext import commands
from discord.ext.commands import Bot
from discord.ui import TextInput
from discord.ui.view import BaseView
from ptn_utils.global_constants import CHANNEL_BC_STEVE_SAYS, ROLE_SOMM, any_council_role, any_moderation_role
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import bot
from ptn.boozebot.modules.helpers import check_roles

"""
MIMIC STEVE COMMAND
/steve_says - somm/mod/admin
/steve_says_edit - somm/mod/admin
"""

logger = get_logger("boozebot.commands.mimicsteve")

MESSAGE_LINK_RE = re.compile(r"discord(?:app)?\.com/channels/\d+/(\d+)/(\d+)")


class MimicSteve(commands.Cog):
    ctx_menu: ContextMenu
    ctx_menu_edit: ContextMenu
    bot: Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(name="Reply as Steve", callback=self.reply_as_steve)
        logger.debug("Adding context menu command: Reply as Steve")
        self.bot.tree.add_command(self.ctx_menu)
        self.ctx_menu_edit = app_commands.ContextMenu(name="Edit Steve message", callback=self.edit_steve_message)
        logger.debug("Adding context menu command: Edit Steve message")
        self.bot.tree.add_command(self.ctx_menu_edit)

    @override
    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)
        self.bot.tree.remove_command(self.ctx_menu_edit.name, type=self.ctx_menu_edit.type)

    @check_roles([*any_council_role, ROLE_SOMM, *any_moderation_role])
    async def edit_steve_message(self, interaction: discord.Interaction, edit_message: discord.Message):
        logger.info(f"User {interaction.user.name} has requested to edit PirateSteve message: {edit_message.jump_url}.")

        if error := MimicSteve._validate_editable(edit_message):
            await interaction.response.send_message(error, ephemeral=True)
            return

        class EditModal(discord.ui.Modal, title="Edit PirateSteve message"):
            message: TextInput[BaseView] = discord.ui.TextInput(
                label="Message", style=discord.TextStyle.long, default=edit_message.content, max_length=2000
            )

            @override
            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.send_message("Editing PirateSteve message...", ephemeral=True)
                await MimicSteve._steve_edit(interaction, edit_message, self.message.value)

        await interaction.response.send_modal(EditModal())

    @check_roles([*any_council_role, ROLE_SOMM, *any_moderation_role])
    async def reply_as_steve(self, interaction: discord.Interaction, reply_message: discord.Message):
        class ReplyModal(discord.ui.Modal, title="Reply as PirateSteve"):
            message: TextInput[BaseView] = discord.ui.TextInput(label="Message", style=discord.TextStyle.long)

            logger.debug(f"Modal for {interaction.user.name} to reply as PirateSteve opened.")

            @override
            async def on_submit(self, interaction: discord.Interaction):
                logger.debug(f"User {interaction.user.name} submitted a reply as PirateSteve: {self.message.value}.")

                await interaction.response.send_message("Replying as PirateSteve...", ephemeral=True)
                await MimicSteve._steve_speak(interaction, self.message.value, reply_message=reply_message)

        logger.info(f"User {interaction.user.name} has requested to reply as PirateSteve to: {reply_message.jump_url}.")
        await interaction.response.send_modal(ReplyModal())

    """
    This class implements functionality for a user to send commands as PirateSteve
    """

    @app_commands.command(name="steve_says", description="Send a message as PirateSteve.")
    @app_commands.describe(
        message="The message to send",
        send_channel="The channel to send the message in",
    )
    @check_roles([*any_council_role, ROLE_SOMM, *any_moderation_role])
    async def mimic_steve(
        self, interaction: discord.Interaction, message: str, send_channel: discord.TextChannel | None = None
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
            + f"in: {send_channel}."
        )

        if not send_channel:
            logger.debug("No send_channel provided, using the interaction channel.")
            send_channel = cast("discord.TextChannel", interaction.channel)

        logger.debug(f"Sending message as PirateSteve in channel: {send_channel}.")

        await interaction.response.send_message("Replying as PirateSteve...", ephemeral=True)
        await self._steve_speak(interaction, message, send_channel=send_channel)

    @app_commands.command(name="steve_says_edit", description="Edit a message previously sent as PirateSteve.")
    @app_commands.describe(
        message_id="The ID or link of the message to edit",
        message="The new message content",
    )
    @check_roles([*any_council_role, ROLE_SOMM, *any_moderation_role])
    async def mimic_steve_edit(self, interaction: discord.Interaction, message_id: str, message: str):
        """
        Edit a plaintext message previously sent by PirateSteve.

        :param Interaction interaction: The discord interaction context.
        :param str message_id: Message ID (looked up in the current channel) or message link.
        :param str message: The new message content.
        """
        logger.info(
            f"User {interaction.user.name} has requested to edit message {message_id} as PirateSteve to: {message}."
        )
        await interaction.response.send_message("Editing PirateSteve message...", ephemeral=True)

        message_id = message_id.strip()
        if match := MESSAGE_LINK_RE.search(message_id):
            channel_id, msg_id = int(match.group(1)), int(match.group(2))
        elif message_id.isdigit() and interaction.channel_id:
            channel_id, msg_id = interaction.channel_id, int(message_id)
        else:
            await interaction.edit_original_response(content="Invalid message ID or link.")
            return

        try:
            channel = cast("discord.abc.Messageable", await bot.get_or_fetch.channel(channel_id))
            edit_message = await channel.fetch_message(msg_id)
        except (discord.DiscordException, AttributeError):
            logger.warning(f"Could not find message {msg_id} in channel {channel_id}.")
            await interaction.edit_original_response(content="Message not found.")
            return

        if error := self._validate_editable(edit_message):
            await interaction.edit_original_response(content=error)
            return

        await self._steve_edit(interaction, edit_message, message)

    @staticmethod
    def _validate_editable(edit_message: discord.Message) -> str | None:
        """Return an error string if the message can't be edited as Steve, else None."""
        if not bot.user or edit_message.author.id != bot.user.id:
            return "That message was not sent by PirateSteve."
        if edit_message.embeds or edit_message.attachments or edit_message.components or edit_message.stickers:
            return "That message is not a plaintext message."
        if not edit_message.content:
            return "That message has no text content."
        return None

    @staticmethod
    async def _steve_edit(interaction: discord.Interaction, edit_message: discord.Message, message: str):
        steve_says_channel = cast("discord.TextChannel", await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS))
        old_content = edit_message.content.replace("`", "\u200b`")
        try:
            await edit_message.edit(content=message)
        except discord.DiscordException:
            logger.exception(f"Failed to edit PirateSteve message {edit_message.jump_url}.")
            await interaction.edit_original_response(content="Pirate Steve failed to edit the message.")
            return

        safe_message = message.replace("`", "\u200b`")
        await interaction.edit_original_response(
            content=f"Pirate Steve message edited to: ``{safe_message}\u200b`` {edit_message.jump_url}"
        )
        await steve_says_channel.send(
            f"User {interaction.user.name} edited a PirateSteve message from ``{old_content}\u200b`` "
            + f"to ``{safe_message}\u200b``. {edit_message.jump_url}"
        )
        logger.info(f"User {interaction.user.name} edited PirateSteve message {edit_message.jump_url}.")

    @staticmethod
    async def _steve_speak(
        interaction: discord.Interaction,
        message: str,
        send_channel: discord.TextChannel | None = None,
        reply_message: discord.Message | None = None,
    ):
        logger.info(
            f"User {interaction.user.name} is sending the message {message} as PirateSteve "
            + f"in: {send_channel or reply_message.channel}."
        )
        steve_says_channel = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)
        try:
            if reply_message:
                send_channel = cast("discord.TextChannel", reply_message.channel)
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
                + f"in: {send_channel}."
            )
        except discord.DiscordException:
            logger.exception(f"Failed to send the message {message} as PirateSteve in: {send_channel}.")
            await interaction.edit_original_response(
                content=f"Pirate Steve failed to say: ``{message}\u200b`` in: {send_channel}."
            )
