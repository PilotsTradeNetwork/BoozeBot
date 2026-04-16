# pyright: reportPrivateUsage=false
"""
Cog for wine loading related commands
"""

from typing import Any

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands
from ptn_utils.global_constants import (
    CHANNEL_BC_WINE_CARRIER_COMMAND,
    CHANNEL_BC_WINE_CELLAR_LOADING,
    ROLE_CONN,
    ROLE_SOMM,
    ROLE_WINE_CARRIER,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import CARRIER_ID_RE, bot
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, is_staff

"""
LOADING COMMANDS
/wine_load  - wine carrier/conn/somm/mod/admin
"""

logger = get_logger("boozebot.commands.loading")


class LoadOperationError(Exception):
    """Raised when a load announcement cannot be posted."""

    def __init__(self, message: str):
        super().__init__(message)


class Loading(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _post_wine_load(
        self,
        *,
        carrier_id: str,
        carrier_name: str,
        owner_discord_id: str,
        wine_total: int,
        tritium: int | None,
        note: str | None,
    ) -> discord.Message:
        """
        Post a wine loading notice in the loading channel.

        Returns the posted Discord message.
        """
        # Sanitise user-supplied text to prevent ping/formatting abuse
        carrier_name = carrier_name.replace("<", "").replace(">", "").replace("@", "").replace("|", "")
        clean_carrier_id = carrier_id.replace("<", "").replace(">", "").replace("@", "").replace("|", "")

        wine_text = f"**{wine_total / 1000:.1f}k** :wine_glass:"

        tritium_text = ""
        if tritium:
            tritium_text = f" + **{tritium / 1000:.1f}k** :oil:"

        note_text = ""
        if note:
            note_text = f"\n-# {note}"

        message_text = (
            f"**{carrier_name} ({clean_carrier_id})** | <@{owner_discord_id}> | {wine_text}{tritium_text}{note_text}"
        )

        try:
            loading_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CELLAR_LOADING)

            # Check if a load order for this carrier has already been posted
            search_pattern = f"({clean_carrier_id})** | <@{owner_discord_id}> |"
            async for hist_message in loading_channel.history(limit=None):
                if search_pattern in hist_message.content:
                    raise LoadOperationError(f"A load order for carrier **{clean_carrier_id}** already exists")

            message = await loading_channel.send(message_text)
        except LoadOperationError:
            raise
        except Exception as e:
            logger.exception(f"Failed to post load message for carrier {carrier_id}: {e}")
            raise LoadOperationError(f"Failed to post load message for carrier {carrier_id}: {e}") from e

        return message

    @app_commands.command(name="wine_load", description="Posts a wine loading notice for a carrier.")
    @describe(
        carrier_id="The XXX-XXX ID string for the carrier",
        tritium="Amount of Tritium to request in tonnes (optional)",
        note="[Staff Only] Optional note to include in the loading announcement",
    )
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM, ROLE_CONN, ROLE_WINE_CARRIER])
    @check_command_channel(CHANNEL_BC_WINE_CARRIER_COMMAND)
    @app_commands.autocomplete(carrier_id=booze_sheets_api.carrier_autocomplete(state="empty"))
    async def wine_load(
        self, interaction: discord.Interaction, carrier_id: str, tritium: int | None = None, note: str | None = None
    ):
        """
        Posts a wine loading notice to the loading channel.

        :param interaction: the interaction from discord
        :param str carrier_id: The carrier ID string
        :param int tritium: Optional tritium amount in tonnes
        :param str note: Optional note for staff members
        """
        await interaction.response.defer()
        logger.info(f"User {interaction.user.name} has requested a wine load announcement for carrier: {carrier_id}.")

        # Cast to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not CARRIER_ID_RE.fullmatch(carrier_id):
            msg = (
                f"The carrier ID was invalid, XXX-XXX expected received, {carrier_id}.\n"
                "Carrier IDs cannot contain `'O'`s or `'I'`s, only `'0'`s and `'1'`s respectively."
            )
            logger.info(msg)
            await interaction.edit_original_response(content=msg)
            return

        # Only staff can include a note via the slash command
        if note and not is_staff(interaction.user):
            await interaction.edit_original_response(content="Only staff members can include a note.")
            return

        logger.debug(f"Fetching carrier data for ID: {carrier_id}")
        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

        if not carrier_data:
            error_msg = f"Carrier {carrier_id} was not found."
            logger.info(error_msg)
            await interaction.followup.send(error_msg)
            return

        logger.debug(f"Fetched carrier data: {carrier_data.to_dictionary()}")
        if not carrier_data.is_owned_by(interaction.user) and not is_staff(interaction.user):
            await interaction.edit_original_response(content=f"Carrier {carrier_id} is not owned by you.")
            return

        await interaction.edit_original_response(content="**Sending to Discord...**")

        try:
            await self._post_wine_load(
                carrier_id=carrier_data.carrier_identifier,
                carrier_name=carrier_data.carrier_name,
                owner_discord_id=str(interaction.user.id),
                wine_total=carrier_data.wine_total,
                tritium=tritium,
                note=note,
            )
        except LoadOperationError as e:
            logger.info(str(e))
            await interaction.edit_original_response(content=str(e))
            return

        carrier_str = f"{carrier_data.carrier_name} ({carrier_id})"
        logger.info(f"Wine load announcement posted by {interaction.user.name} for {carrier_str} successfully.")
        await interaction.edit_original_response(
            content=f"Wine load announcement posted by {interaction.user.name} for **{carrier_str}** successfully."
        )

    @commands.Cog.listener()
    async def on_boozesheets_load_request(self, data: dict[str, Any]):
        carrier_id = data.get("fcCallsign")
        carrier_name = data.get("fcName")
        owner_discord_id = data.get("ownerDiscordId")
        wine_total = data.get("wineTotal")
        tritium = data.get("tritium")
        note = data.get("note")
        action_id = data.get("actionId")

        logger.info(f"Received load_request for carrier_id={carrier_id}, action_id={action_id}")

        if not carrier_id:
            logger.error(f"load_request missing fcCallsign: {data}")
            return

        success: bool = False
        error: str | None = None

        try:
            await self._post_wine_load(
                carrier_id=carrier_id,
                carrier_name=carrier_name or "",
                owner_discord_id=owner_discord_id or "",
                wine_total=int(wine_total) if wine_total is not None else 0,
                tritium=int(tritium) if tritium is not None else None,
                note=note,
            )
            logger.info(f"Successfully posted load announcement for carrier {carrier_id} from load_request event.")
            success = True
        except LoadOperationError as e:
            logger.warning(f"Failed to post load announcement for carrier {carrier_id} from load_request event: {e}")
            error = str(e)

        if action_id:
            logger.debug(f"Sending load_request ack for event: {action_id=}, {success=}, {error=}")
            await booze_sheets_api.send_action_ack(action_id, success=success, error=error)
