# pyright: reportPrivateUsage=false
"""
Cog for wine loading related commands
"""

import re
from typing import Any, TypedDict

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands
from ptn_utils.global_constants import (
    CHANNEL_BC_WINE_CARRIER,
    CHANNEL_BC_WINE_CELLAR_LOADING,
    EMOJI_CARRIER_DONE,
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
from ptn.boozebot.modules.Views import DynamicButton

"""
LOADING COMMANDS
/wine_load        - wine carrier/conn/somm/mod/admin
/wine_load_delete - wine carrier/conn/somm/mod/admin
"""

logger = get_logger("boozebot.commands.loading")

# Matches the carrier name and ID inside the load message format:
# **<carrier_name> (<carrier_id>)** | <@owner_id> | ...
_LOAD_MESSAGE_RE = re.compile(
    r"\*\*(?P<carrier_name>.+?) \((?P<carrier_id>[A-Z0-9]{3}-[A-Z0-9]{3})\)\*\* \| <@(?P<owner_id>\d+)> \|"
)


class LoadCacheEntry(TypedDict):
    message_id: int
    owner_id: int
    carrier_name: str


class LoadOperationError(Exception):
    """Raised when a load announcement cannot be posted or deleted."""

    def __init__(self, message: str):
        super().__init__(message)


# ---------------------------------------------------------------------------
# In-memory cache
#
# Structure:
#   _load_cache[carrier_id] = LoadCacheEntry(message_id=..., owner_id=..., carrier_name=...)
#
# Keyed by carrier_id (upper-case XXX-XXX) for O(1) lookups on post/delete.
# owner_id and carrier_name are stored so the autocomplete can filter and
# display results without hitting the API.
# ---------------------------------------------------------------------------
_load_cache: dict[str, LoadCacheEntry] = {}


def _cache_add(carrier_id: str, message_id: int, owner_id: int, carrier_name: str) -> None:
    _load_cache[carrier_id] = LoadCacheEntry(message_id=message_id, owner_id=owner_id, carrier_name=carrier_name)
    logger.debug(
        f"Load cache ADD: {carrier_id} → message_id={message_id}, owner_id={owner_id}, carrier_name={carrier_name!r}"
    )


async def _build_cache_from_history() -> None:
    """Rebuild _load_cache by reading the full loading channel history."""
    logger.info("Building load message cache from channel history…")
    _load_cache.clear()
    try:
        loading_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CELLAR_LOADING)
        async for message in loading_channel.history(limit=None):
            if message.author.id != bot.user.id:
                continue
            match = _LOAD_MESSAGE_RE.search(message.content)
            if match:
                _cache_add(
                    match.group("carrier_id"), message.id, int(match.group("owner_id")), match.group("carrier_name")
                )
        logger.info(f"Load cache built: {len(_load_cache)} entries.")
    except Exception as e:
        logger.exception(f"Failed to build load cache from history: {e}")


def _carrier_in_cache(carrier_id: str) -> bool:
    """Return True if *carrier_id* has an active load message in the cache."""
    return carrier_id in _load_cache


def _find_carrier_in_cache(message_id: int) -> tuple[str, str, int] | None:
    """
    Return ``(carrier_id, carrier_name, owner_id)`` for the given *message_id*,
    or None if not found.
    """
    for carrier_id, entry in _load_cache.items():
        if entry["message_id"] == message_id:
            return carrier_id, entry["carrier_name"], entry["owner_id"]
    return None


async def _lookup_load_message(carrier_id: str) -> LoadCacheEntry | None:
    """
    Return the cache entry for *carrier_id*, rebuilding from history on a miss.
    Returns None if the carrier has no active load message.
    """
    if carrier_id in _load_cache:
        return _load_cache[carrier_id]

    logger.info(f"Cache miss for {carrier_id}. Rebuilding from history…")
    await _build_cache_from_history()
    return _load_cache.get(carrier_id)


class Loading(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await _build_cache_from_history()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

        Raises LoadOperationError if a load order for this carrier already exists
        or if the message could not be posted.

        Returns the posted Discord message.
        """
        # Sanitise user-supplied text to prevent ping/formatting abuse
        carrier_name = carrier_name.replace("<", "").replace(">", "").replace("@", "").replace("|", "")
        clean_carrier_id = carrier_id.replace("<", "").replace(">", "").replace("@", "").replace("|", "")

        # Duplicate check via cache only — on startup the cache is populated
        # from history, so a miss here means no existing load order.
        if _carrier_in_cache(clean_carrier_id):
            raise LoadOperationError(f"A load order for carrier **{clean_carrier_id}** already exists.")

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
            message = await loading_channel.send(message_text)
        except Exception as e:
            logger.exception(f"Failed to post load message for carrier {carrier_id}: {e}")
            raise LoadOperationError(f"Failed to post load message for carrier {carrier_id}: {e}") from e

        _cache_add(clean_carrier_id, message.id, int(owner_discord_id), carrier_name)
        return message

    async def _delete_load_message(self, carrier_id: str) -> None:
        """
        Delete the loading channel message for *carrier_id* and remove it from
        the cache.

        Raises LoadOperationError if no load message is found or deletion fails.
        """
        entry = await _lookup_load_message(carrier_id)
        if entry is None:
            raise LoadOperationError(f"No active load order found for carrier **{carrier_id}**.")

        try:
            loading_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CELLAR_LOADING)
            message = await loading_channel.fetch_message(entry["message_id"])
            await message.delete()
        except discord.NotFound:
            # Message was already deleted externally — treat as success
            logger.warning(f"Load message for {carrier_id} (id={entry['message_id']}) was already deleted.")
        except Exception as e:
            logger.exception(f"Failed to delete load message for carrier {carrier_id}: {e}")
            raise LoadOperationError(f"Failed to delete load message for carrier {carrier_id}: {e}") from e
        finally:
            _load_cache.pop(carrier_id, None)
            logger.debug(f"Load cache REMOVE: {carrier_id}")

        try:
            await booze_sheets_api.update_carrier_info(carrier_id, {"wine_status": "Full"})
            logger.info(f"Marked wine_status=Full for carrier {carrier_id} via BoozeSheets API.")
        except Exception as e:
            logger.warning(f"Failed to mark wine_status=Full for carrier {carrier_id}: {e}")

    # ------------------------------------------------------------------
    # Autocomplete
    # ------------------------------------------------------------------

    async def _load_delete_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """
        Autocomplete for /wine_load_delete.
        Shows only the caller's active load messages (or all for staff).
        """
        user_id = interaction.user.id
        staff = is_staff(interaction.user)

        choices: list[app_commands.Choice[str]] = []
        for carrier_id, entry in _load_cache.items():
            if not staff and entry["owner_id"] != user_id:
                continue
            display_name = f"{entry['carrier_name']} ({carrier_id})"
            if current.lower() not in display_name.lower():
                continue
            choices.append(app_commands.Choice(name=display_name, value=carrier_id))
            if len(choices) >= 25:
                break

        return choices

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @app_commands.command(name="wine_load", description="Posts a wine loading notice for a carrier.")
    @describe(
        carrier_id="The XXX-XXX ID string for the carrier",
        tritium="Amount of Tritium to request in tonnes (optional)",
        note="[Staff Only] Optional note to include in the loading announcement",
    )
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM, ROLE_CONN, ROLE_WINE_CARRIER])
    @check_command_channel(CHANNEL_BC_WINE_CARRIER)
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

        carrier_id = carrier_id.upper()

        if not CARRIER_ID_RE.fullmatch(carrier_id):
            msg = (
                f"The carrier ID was invalid, XXX-XXX expected received, {carrier_id}.\n"
                "Carrier IDs cannot contain `'O'`s or `'I'`s, only `'0'`s and `'1'`s respectively."
            )
            logger.info(msg)
            await interaction.edit_original_response(content=msg)
            return

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
        logger.info(f"Wine load announcement for {carrier_str} by {interaction.user.name} posted successfully.")
        await interaction.edit_original_response(
            content=f"Wine load announcement for {carrier_str} by {interaction.user.mention} posted successfully."
        )

    @app_commands.command(name="wine_load_delete", description="Deletes an active wine loading notice for a carrier.")
    @describe(carrier_id="The XXX-XXX ID string for the carrier whose load notice should be removed")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM, ROLE_CONN, ROLE_WINE_CARRIER])
    @check_command_channel(CHANNEL_BC_WINE_CARRIER)
    @app_commands.autocomplete(carrier_id=_load_delete_autocomplete)
    async def wine_load_complete(self, interaction: discord.Interaction, carrier_id: str):
        """
        Deletes the active wine loading notice for the given carrier.

        :param interaction: the interaction from discord
        :param str carrier_id: The carrier ID string
        """
        await interaction.response.defer()
        logger.info(
            f"User {interaction.user.name} has requested deletion of wine load announcement for carrier: {carrier_id}."
        )

        carrier_id = carrier_id.upper()
        # Verify ownership (staff may delete any)
        entry = await _lookup_load_message(carrier_id)
        if entry is not None and entry["owner_id"] != interaction.user.id and not is_staff(interaction.user):
            await interaction.edit_original_response(
                content=f"The load order for **{carrier_id}** does not belong to you.",
            )
            return

        try:
            await self._delete_load_message(carrier_id)
        except LoadOperationError as e:
            logger.info(str(e))
            await interaction.edit_original_response(content=str(e))
            return

        logger.info(f"Wine load announcement for {carrier_id} deleted by {interaction.user.name}.")
        await interaction.edit_original_response(
            content=f"Wine load announcement for **{carrier_id}** deleted by {interaction.user.name}.",
        )

    # ------------------------------------------------------------------
    # WebSocket event
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Reaction → DynamicButton confirm-delete flow
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction_event: discord.RawReactionActionEvent):
        """
        When a single EMOJI_CARRIER_DONE reaction is added to a message in the
        loading channel, post a DynamicButton to CHANNEL_BC_WINE_CARRIER pinging
        the owner so they can confirm deletion.
        """
        if reaction_event.emoji.id != EMOJI_CARRIER_DONE:
            return

        if reaction_event.channel_id != CHANNEL_BC_WINE_CELLAR_LOADING:
            return

        # Ignore bot reactions
        if reaction_event.member is None or reaction_event.member.bot:
            return

        # Look up the carrier this message belongs to
        found = _find_carrier_in_cache(reaction_event.message_id)

        if found is None:
            # Cache miss — rebuild and retry
            logger.info(f"Reaction on unknown message {reaction_event.message_id}. Rebuilding load cache and retrying.")
            await _build_cache_from_history()
            found = _find_carrier_in_cache(reaction_event.message_id)

        if found is None:
            logger.debug(
                f"Message {reaction_event.message_id} not found in load cache after rebuild. Ignoring reaction."
            )
            return

        carrier_id, carrier_name, owner_id = found

        carrier_str = f"{carrier_name} ({carrier_id})"
        logger.info(
            f"EMOJI_CARRIER_DONE reacted on load message for {carrier_str} by {reaction_event.member}. "
            + f"Posting confirm-delete button for owner {owner_id}."
        )

        try:
            wine_carrier_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CARRIER)
            delete_button = DynamicButton(
                label="Delete load order",
                action="delete_load",
                user_id=owner_id,
                payload=carrier_id,
            )
            view = discord.ui.View()
            view.add_item(delete_button)
            await wine_carrier_channel.send(
                content=f"<@{owner_id}> — your load order for **{carrier_str}** has been flagged as complete. "
                + "Verify, then click the button below to delete it.",
                view=view,
            )
        except Exception as e:
            logger.exception(f"Failed to post confirm-delete button for {carrier_id}: {e}")

    @commands.Cog.listener()
    async def on_dynamic_button_delete_load(self, interaction: discord.Interaction, button: DynamicButton):
        """
        Handles the DynamicButton confirm-delete click.
        Verifies the clicker is the load order owner, then deletes the message.
        """
        carrier_id = button.payload
        owner_id = button.user_id

        logger.info(
            f"delete_load button clicked for {carrier_id} by {interaction.user} ({interaction.user.id}). Expected owner_id={owner_id}."
        )

        if interaction.user.id != owner_id and not is_staff(interaction.user):
            await interaction.response.send_message(
                "Only the carrier owner may delete this load order.", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await self._delete_load_message(carrier_id)
        except LoadOperationError as e:
            logger.info(str(e))
            await interaction.followup.send(str(e), ephemeral=True)
            return

        logger.info(f"Load order for {carrier_id} deleted via DynamicButton by {interaction.user.name}.")

        # Edit the button message to reflect completion
        if interaction.message:
            try:
                await interaction.message.edit(
                    content=f"✅ Load order for **{carrier_id}** deleted by {interaction.user.mention}.",
                    view=None,
                )
            except Exception as e:
                logger.warning(f"Could not edit confirm-delete message after deletion: {e}")
