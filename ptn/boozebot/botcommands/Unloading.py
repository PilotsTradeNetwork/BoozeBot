# pyright: reportPrivateUsage=false
"""
Cog for unloading related commands
"""

import random
from asyncio import Lock
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, override

import discord
from discord import Interaction, app_commands
from discord.app_commands import describe
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from ptn_utils.enums.booze_enums import CruiseSystemState
from ptn_utils.global_constants import (
    CHANNEL_BC_BOOZE_CRUISE_CHAT,
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER_COMMAND,
    CHANNEL_BC_WINE_CELLAR_UNLOADING,
    EMOJI_ASSASSIN,
    EMOJI_CARRIER_DONE,
    ROLE_CONN,
    ROLE_SOMM,
    ROLE_WINE_CARRIER,
    _production,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier
from ptn.boozebot.constants import CARRIER_ID_RE, bot, unload_opened_gifs
from ptn.boozebot.database.database import database
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, is_staff, track_last_run
from ptn.boozebot.modules.PHcheck import ph_check
from ptn.boozebot.modules.Settings import settings
from ptn.boozebot.modules.Views import DynamicButton

"""
UNLOADING COMMANDS
/wine_helper_market_open - wine carrier/conn/somm/mod/admin
/wine_helper_market_closed - wine carrier/conn/somm/mod/admin
/wine_unload  - wine carrier/conn/somm/mod/admin
/wine_unload_complete  - wine carrier/wine conn/somm/mod/admin
"""

logger = get_logger("boozebot.commands.unloading")


class UnloadOperationError(Exception):
    """Raised when an unload operation cannot be started or completed."""

    def __init__(self, message: str):
        super().__init__(message)


@dataclass(slots=True)
class UnloadStartResult:
    alert_message_id: int
    alert_channel_id: int
    open_time_str: str | None = None


@dataclass(slots=True)
class UnloadCompleteResult:
    unload_duration: float | None


# initialise the Cog and attach our global error handler
class Unloading(commands.Cog):
    bot: Bot
    reaction_lock: Lock
    unload_lock: Lock
    REACTION_THRESHOLD: Literal[5, 1] = 5 if _production else 1
    ctx_menu_close_unload_command: app_commands.ContextMenu

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reaction_lock = Lock()
        self.unload_lock = Lock()
        self.ctx_menu_close_unload_command = app_commands.ContextMenu(
            name="Close Unload", callback=self.ctx_menu_close_unload
        )
        logger.debug("Adding context menu command: Close Unload")
        self.bot.tree.add_command(self.ctx_menu_close_unload_command)

    @override
    async def cog_unload(self):
        self.bot.tree.remove_command(
            self.ctx_menu_close_unload_command.name, type=self.ctx_menu_close_unload_command.type
        )

    async def _unload(
        self,
        *,
        carrier_id: str,
        carrier_name: str,
        carrier_db_id: int,
        system: str | None,
        body: str | None,
        wine_total: int,
        unload_opened: datetime | None,
        unload_closed: datetime | None,
        is_timed: bool,
    ) -> UnloadStartResult:
        """
        Start a carrier unload operation.
        """
        async with self.unload_lock:
            if await booze_sheets_api.get_current_cruise_state() != CruiseSystemState.ACTIVE:
                raise UnloadOperationError(
                    "Unloads can only be started during an active booze cruise.",
                )

            if system != "N0":
                raise UnloadOperationError(
                    f"Carrier {carrier_id} is not in N0 (HIP 58832); cannot unload wine.",
                )

            if not body:
                raise UnloadOperationError(
                    f"Carrier {carrier_id} must have a body set on the Booze Sheets Website before unloading.",
                )

            if unload_closed:
                raise UnloadOperationError(
                    f"Carrier {carrier_id} has already completed all of its unloads.",
                )

            if unload_opened:
                raise UnloadOperationError(
                    f"Carrier {carrier_id} is already unloading wine.",
                )

            open_time_str = None
            if is_timed:
                hold_minutes = settings.get_setting("timed_unload_hold_duration")
                current_time = datetime.now(UTC)
                open_time = current_time + timedelta(minutes=hold_minutes)
                open_time = open_time + timedelta(seconds=60 - open_time.second)
                open_time_str = open_time.strftime("%H:%M:%S")
                embed_title = "Timed wine unload notification."
                embed_description = (
                    f"Carrier **{carrier_name} ({carrier_id})** will be unloading "
                    + f"**{wine_total}** tonnes of wine from "
                    + f"**{body}**."
                    + f"\n Market will open at {open_time_str} (In game time)."
                )
            else:
                embed_title = "Wine unload notification."
                embed_description = (
                    f"Carrier **{carrier_name} ({carrier_id})** is currently "
                    + f"unloading **{wine_total}** tonnes of wine from "
                    + f"**{body}**."
                )

            wine_load_embed = discord.Embed(
                title=embed_title,
                description=embed_description,
            )
            wine_load_embed.set_footer(
                text="Please react with this emoji once completed.",
                icon_url=f"https://cdn.discordapp.com/emojis/{EMOJI_CARRIER_DONE}.png?v=1",
            )

            try:
                wine_alert_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CELLAR_UNLOADING)
                wine_unload_alert = await wine_alert_channel.send(embed=wine_load_embed)
                self.last_unload_time = None

                discord_alert_id = wine_unload_alert.id
                delay = settings.get_setting("timed_unload_hold_duration") if is_timed else None

                await database.set_unload_message_for_carrier(carrier_id, discord_alert_id)
                await database.set_unload_notification_sent(carrier_id, False)
                await booze_sheets_api.start_carrier_unload(carrier_db_id, delay=delay)

                booze_cruise_chat = await bot.get_or_fetch.channel(CHANNEL_BC_BOOZE_CRUISE_CHAT)
                if is_timed:
                    await booze_cruise_chat.send(
                        f"A new wine unload will be opening soon. See <#{wine_unload_alert.channel.id}>"
                    )
                else:
                    await booze_cruise_chat.send(
                        f"A new wine unload is in progress. See <#{wine_unload_alert.channel.id}>"
                    )
                await booze_cruise_chat.send(random.choice(unload_opened_gifs))
            except Exception as e:
                logger.exception(f"Failed to start unload for carrier {carrier_id}: {e}")
                raise UnloadOperationError(
                    f"Failed to start unload for carrier {carrier_id}: {e}",
                ) from e

            return UnloadStartResult(
                alert_message_id=discord_alert_id,
                alert_channel_id=wine_unload_alert.channel.id,
                open_time_str=open_time_str,
            )

    async def _unload_complete(
        self,
        carrier_data: BoozeCarrier | None,
        requested_by: discord.Member | None = None,
    ) -> UnloadCompleteResult:
        """
        Complete a carrier unload operation.
        """

        async with self.unload_lock:
            if not carrier_data:
                raise UnloadOperationError("Carrier data was not provided.")

            carrier_id = carrier_data.carrier_identifier

            if requested_by and not carrier_data.is_owned_by(requested_by) and not is_staff(requested_by):
                raise UnloadOperationError(f"Carrier {carrier_id} is not owned by you.")

            if carrier_data.wine_status != "Unloading":
                raise UnloadOperationError(
                    f"Carrier {carrier_id} is not currently unloading.",
                )

            message_id = await database.get_unload_message_for_carrier(carrier_id)
            if not message_id:
                raise UnloadOperationError(
                    f"No unload notification found in database for carrier: {carrier_id}.",
                )

            try:
                try:
                    wine_alert_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CELLAR_UNLOADING)
                    message = await wine_alert_channel.fetch_message(message_id)
                    await message.delete()
                    logger.info(f"Deleted unload notification message from Discord for carrier: {carrier_id}.")
                except discord.NotFound:
                    logger.warning(
                        f"Unload notification message ID {message_id} for carrier {carrier_id} not found in channel."
                    )

                await database.delete_carrier_message(carrier_id, "unload")
                logger.info(f"Removed unload notification from database for carrier: {carrier_id}.")

                completed_trip = await booze_sheets_api.complete_carrier_unload(carrier_data.db_id)
                self.last_unload_time = datetime.now(UTC)
            except Exception as e:
                logger.exception(f"Failed to complete unload for carrier {carrier_id}: {e}")
                raise UnloadOperationError(
                    f"Failed to complete unload for carrier {carrier_id}: {e}",
                ) from e

            return UnloadCompleteResult(unload_duration=completed_trip.unload_duration)

    """
    This class is a collection functionality for tracking a booze cruise unload operations
    """
    last_unload_time: datetime | None = None

    # On reaction check if it's in the unloading channel and if the reaction is fc complete,
    # If it is and there are 5 reactions ping the poster
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction_event: discord.RawReactionActionEvent):
        try:
            user = reaction_event.member

            if user.bot:
                return

            if reaction_event.channel_id != CHANNEL_BC_WINE_CELLAR_UNLOADING:
                return

            channel = await bot.get_or_fetch.channel(reaction_event.channel_id)
            message = await channel.fetch_message(reaction_event.message_id)

            if message.pinned:
                return

            if message.author.id != bot.user.id:
                return

            logger.debug(
                f"Processing unload reaction {reaction_event.emoji} from user {user.name} in channel {channel.name}"
            )

            reaction_allowed_roles = {*any_council_role, *any_moderation_role, ROLE_CONN}
            if reaction_event.emoji.id != EMOJI_CARRIER_DONE:
                logger.debug(f"Reaction {reaction_event.emoji} is not FC complete emoji.")
                if not {role.id for role in user.roles} & reaction_allowed_roles:
                    logger.debug(
                        f"User {user.name} does not have permission to add reaction {reaction_event.emoji}. Removing reaction."
                    )
                    await message.remove_reaction(reaction_event.emoji, reaction_event.member)
                    logger.info(f"Removed unload reaction {reaction_event.emoji} from user {user.name}")
                return

            logger.debug(f"Reaction {reaction_event.emoji} is FC complete emoji. Checking reaction count.")

            # Check if the FC complete reaction count meets the threshold
            for message_reaction in message.reactions:
                logger.debug(f"Checking reaction: {message_reaction.emoji} with count {message_reaction.count}")
                if (
                    message_reaction.emoji.id == EMOJI_CARRIER_DONE
                    and message_reaction.count >= self.REACTION_THRESHOLD
                ):
                    # Find carrier data for this message from the database
                    logger.debug(
                        f"FC complete reaction count for message {message.id} has reached threshold. Notifying poster."
                    )

                    carrier_id = await database.get_carrier_for_unload_message(message.id)

                    if not carrier_id:
                        logger.warning(
                            f"Could not find carrier ID for unload message {message.id}. Cannot notify poster."
                        )
                        return
                    async with self.reaction_lock:
                        if await database.get_unload_notification_sent(carrier_id):
                            logger.info(
                                f"Unload notification for carrier {carrier_id} has already been sent. Skipping notification."
                            )
                            return

                        logger.debug(f"Fetching carrier data for ID: {carrier_id}")

                        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

                        logger.debug(
                            f"Fetched carrier data: {carrier_data.to_dictionary() if carrier_data else 'None'}"
                        )

                        close_button = DynamicButton(
                            label="Close Unload",
                            action="close_unload",
                            user_id=carrier_data.owner.discord_id,
                            payload=carrier_data.carrier_identifier,
                        )

                        view = discord.ui.View()
                        view.add_item(close_button)

                        wine_carrier_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CARRIER_COMMAND)
                        await wine_carrier_channel.send(
                            content=f"{carrier_data.owner.mention} "
                            + f"Your unload for {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) "
                            + "has been marked completed. Please check, then click the button below to close it "
                            + "if it is correct.",
                            view=view,
                        )

                        logger.debug("Updating database to set to NULL to avoid multiple notifications.")
                        await database.set_unload_notification_sent(carrier_data.carrier_identifier, True)

                        logger.info(
                            f"Notified poster {carrier_data.owner.username} for carrier {carrier_data.carrier_identifier}"
                        )
                break

        except Exception as e:
            logger.exception(f"Failed to process reaction: {reaction_event}. Error: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting the last unload time loop")
        if not self.last_unload_time_loop.is_running():
            self.last_unload_time_loop.start()
            logger.debug("Last unload time loop started")
        else:
            logger.debug("Last unload time loop is already running")

    @commands.Cog.listener()
    async def on_dynamic_button_close_unload(self, interaction: Interaction, button: DynamicButton):
        logger.info(
            f"Received close unload button interaction for carrier {button.payload} from user {interaction.user.name}"
        )

        await interaction.response.defer()

        carrier_id = button.payload

        logger.debug(f"Fetching carrier data for ID: {carrier_id}")

        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

        logger.debug(f"Fetched carrier data: {carrier_data.to_dictionary() if carrier_data else 'None'}")

        if not carrier_data:
            error_msg = f"Carrier {carrier_id} was not found."
            logger.info(error_msg)
            await interaction.edit_original_response(content=error_msg, view=None)
            return

        try:
            result = await self._unload_complete(carrier_data, requested_by=interaction.user)
        except UnloadOperationError as e:
            logger.info(str(e))
            await interaction.edit_original_response(content=str(e), view=None)
            return

        unload_duration = result.unload_duration

        logger.debug(f"Calculated unload duration: {unload_duration} seconds")

        minutes, seconds = divmod(int(unload_duration), 60)
        time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

        logger.info(f"Deleted unload notification message for carrier: {carrier_id}.")
        response = (
            f"Removed the unload notification for {carrier_data.carrier_name} ({carrier_id})\n"
            f"-# Unload duration: {time_str}."
        )
        allowed_mentions = discord.AllowedMentions.none()
        conn_role = await bot.get_or_fetch.role(ROLE_CONN)
        allowed_mentions.roles = [conn_role]

        logger.info(f"Wine unload for carrier {carrier_id} completed by {interaction.user.name}.")
        await interaction.followup.send(
            content=f"{interaction.user.mention} {response}", allowed_mentions=allowed_mentions, view=None
        )
        await interaction.edit_original_response(
            content=f"<@&{ROLE_CONN}> {interaction.user.mention} {response}",
            allowed_mentions=allowed_mentions,
            view=None,
        )

    @commands.Cog.listener()
    async def on_boozesheets_unload_request(self, data: dict[str, Any]):
        carrier_db_id = data.get("carrierId")
        carrier_id = data.get("fcCallsign")
        carrier_name = data.get("fcName")
        system = data.get("currentSystem")
        body = data.get("currentBody")
        wine_total = data.get("wineTotal")
        unload_opened = data.get("unloadOpened")
        unload_closed = data.get("unloadClosed")
        delay = data.get("delay")
        action_id = data.get("actionId")

        logger.info(
            f"Received unload_request for carrier_db_id={carrier_db_id}, carrier_id={carrier_id}, action_id={action_id}"
        )

        if not carrier_id:
            logger.error(f"unload_request missing fcCallsign: {data}")
            return

        success: bool = False
        error: str | None = None
        try:
            result = await self._unload(
                carrier_id=carrier_id,
                carrier_name=carrier_name or "",
                carrier_db_id=int(carrier_db_id) if carrier_db_id is not None else 0,
                system=system,
                body=body,
                wine_total=int(wine_total) if wine_total is not None else 0,
                unload_opened=unload_opened,
                unload_closed=unload_closed,
                is_timed=bool(delay),
            )
            logger.info(f"Successfully started unload for carrier {carrier_id} from unload_request event.")
            success = True
            if rstc_channel := await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CARRIER_COMMAND):
                if delay:
                    await rstc_channel.send(
                        f"Timed wine unload requested via boozesheets for **{carrier_name} ({carrier_id})**\n"
                        + f"Open the market at {result.open_time_str} (In game time)."
                    )
                else:
                    await rstc_channel.send(
                        content=f"Wine unload requested via boozesheets for **{carrier_name} ({carrier_id})** "
                        + "processed successfully."
                    )
        except UnloadOperationError as e:
            logger.warning(f"Failed to start unload for carrier {carrier_id} from unload_request event: {e}")
            error = str(e)

        if action_id:
            logger.debug(
                f"Sending action ack for unload_request event with action_id {action_id}, success={success}, error={error}"
            )
            await booze_sheets_api.send_action_ack(action_id, success=success, error=error)

    @tasks.loop(seconds=60.0)
    @track_last_run()
    async def last_unload_time_loop(self):
        """
        Checks if the last unload time was more than 20 minutes ago and sends a reminder message to the RSTC channel.
        """

        logger.info("Running last unload time loop.")

        try:
            carriers = await booze_sheets_api.get_unloading_carriers()
            if carriers:
                logger.info("An unload is currently open, skipping reminder check.")
                return
        except Exception as e:
            logger.error(e)
            logger.exception(e)

        if self.last_unload_time is None:
            logger.info("Last unload time is not set, skipping reminder check.")
            return

        if not await ph_check():
            logger.info("PH is not currently active, skipping reminder check.")
            return

        if datetime.now(tz=UTC) - self.last_unload_time >= timedelta(minutes=20):
            logger.info("Last unload time was more than 20 minutes ago, sending reminder message.")
            try:
                rstc_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CARRIER_COMMAND)
                timestamp = int(self.last_unload_time.timestamp())
                content = f"Arrr, ye scurvy dogs! Our last booze unload was <t:{timestamp}:R>. Might be time to open another vessel to the people, ye think?"
                message = await rstc_channel.send(content)
                await message.edit(content=f"<@&{ROLE_CONN}> {content}")
                await message.add_reaction("🏴‍☠️")
                logger.info("Reminder message sent to RSTC channel.")
                # Set the flag back to None so we don't keep sending messages
                self.last_unload_time = None
                logger.debug("Last unload time reset to None after sending reminder.")
            except discord.DiscordException as e:
                logger.exception(f"Failed to notify RSTC channel about the last unload time: {e}")
        else:
            logger.info("Last unload time loop completed without sending reminder.")

    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    async def ctx_menu_close_unload(self, interaction: Interaction, message: discord.Message):
        logger.info(
            f"Received context menu close unload command from user {interaction.user.name} for message ID {message.id}"
        )

        await interaction.response.defer(ephemeral=True)

        try:
            carrier_id = await database.get_carrier_for_unload_message(message.id)

            if not carrier_id:
                error_msg = f"Could not find carrier ID for unload message {message.id}. Cannot close unload."
                logger.warning(error_msg)
                await interaction.edit_original_response(content=error_msg)
                return

            logger.debug(f"Fetching carrier data for ID: {carrier_id}")

            carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

            logger.debug(f"Fetched carrier data: {carrier_data.to_dictionary() if carrier_data else 'None'}")

            if not carrier_data:
                error_msg = f"Carrier {carrier_id} was not found. Cannot close unload."
                logger.warning(error_msg)
                await interaction.edit_original_response(content=error_msg)
                return

            result = await self._unload_complete(carrier_data, requested_by=interaction.user)

            unload_duration = result.unload_duration

            minutes, seconds = divmod(int(unload_duration), 60)
            time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

            response = (
                f"Removed the unload notification for {carrier_data.carrier_name} ({carrier_id}).\n"
                f"-# Unload duration: {time_str}."
            )

            allowed_mentions = discord.AllowedMentions.none()
            conn_role = await bot.get_or_fetch.role(ROLE_CONN)
            allowed_mentions.roles = [conn_role]

            logger.info(f"Unload for carrier {carrier_id} closed by {interaction.user.name}.")
            rstc_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CARRIER_COMMAND)
            message = await rstc_channel.send(
                content=f"{interaction.user.mention} {response}", allowed_mentions=allowed_mentions
            )
            await message.edit(
                content=f"<@&{ROLE_CONN}> {interaction.user.mention} {response}", allowed_mentions=allowed_mentions
            )

            await interaction.edit_original_response(content=response)
        except UnloadOperationError as e:
            logger.info(str(e))
            await interaction.edit_original_response(content=str(e))
        except Exception as e:
            logger.exception(f"Failed to process close unload command: {e}")
            await interaction.edit_original_response(content=f"An error occurred while trying to close the unload: {e}")

    @app_commands.command(
        name="wine_helper_market_open", description="Creates a new unloading helper operation in this channel."
    )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    async def booze_unload_market(self, interaction: discord.Interaction):
        logger.info(
            f"User {interaction.user.name} requested a new booze unload in channel: {interaction.channel.name}."
        )

        embed = discord.Embed(title="Avast Ye!")
        embed.add_field(
            name="If you are INTENDING TO BUY, please react with: :airplane_arriving:.\n"
            + f"Once you are DOCKED react with: <:Assassin:{EMOJI_ASSASSIN!s}>\n"
            + "Once you PURCHASE WINE, react with: :wine_glass:",
            value="Market will be opened once we have aligned the number of commanders.",
            inline=True,
        )
        embed.set_footer(text="All 3 emoji counts should match by the end or Pirate Steve will be unhappy. 🏴‍☠")

        await interaction.response.send_message(embed=embed)
        # Retrieve the message object
        message = await interaction.original_response()
        await message.add_reaction("🛬")
        await message.add_reaction(f"<:Assassin:{EMOJI_ASSASSIN!s}>")
        await message.add_reaction("🍷")

    @app_commands.command(
        name="wine_helper_market_closed",
        description="Sends a message to indicate you have closed your market. Command sent in active channel.",
    )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    async def booze_market_closed(self, interaction: discord.Interaction):
        logger.info(
            f"User {interaction.user.name} requested a to close the market in channel: {interaction.channel.name}."
        )
        embed = discord.Embed(title="Batten Down The Hatches! This sale is currently done!")
        embed.add_field(
            name="Go fight the sidewinder for the landing pad.",
            value="Hopefully you got some booty, now go get your doubloons!",
        )
        embed.set_footer(text="Notified by your friendly neighbourhood pirate bot.")
        await interaction.response.send_message(embed=embed)
        # Retrieve the message object
        message = await interaction.original_response()
        await message.add_reaction("🏴‍☠️")

    """
    carrier unload commands
    """

    @app_commands.command(
        name="wine_unload",
        description="Posts a new unload notice for a carrier. Admin/Sommelier/WineCarrier role required.",
    )
    @describe(
        carrier_id="The XXX-XXX ID string for the carrier",
    )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    @check_command_channel(CHANNEL_BC_WINE_CARRIER_COMMAND)
    @app_commands.autocomplete(carrier_id=booze_sheets_api.carrier_autocomplete(unload_state="full"))
    async def wine_carrier_unload(self, interaction: discord.Interaction, carrier_id: str):
        """
        Posts a wine unload request to the unloading channel.

        :param interaction: the interaction from discord
        :param SlashContext ctx: The discord slash context.
        :param str carrier_id: The carrier ID string
        :returns: A message to the user
        :rtype: Union[discord.Message, dict]
        """

        await interaction.response.defer()
        logger.info(
            f"User {interaction.user.name} has requested a new wine unload operation for carrier: {carrier_id}."
        )

        # Cast this to upper case just in case
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

        logger.debug(f"Fetching carrier data for ID: {carrier_id}")
        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

        logger.debug(f"Fetched carrier data: {carrier_data.to_dictionary() if carrier_data else 'None'}")

        if not carrier_data:
            error_msg = f"Carrier {carrier_id} was not found."
            logger.info(error_msg)
            await interaction.followup.send(error_msg)
            return

        logger.debug(f"Preparing to send unload notification to Discord for carrier {carrier_data.carrier_identifier}.")
        await interaction.edit_original_response(content="**Sending to Discord...**")
        if not carrier_data.is_owned_by(interaction.user) and not is_staff(interaction.user):
            await interaction.edit_original_response(content=f"Carrier {carrier_id} is not owned by you.")
            return
        try:
            _ = await self._unload(
                carrier_id=carrier_data.carrier_identifier,
                carrier_name=carrier_data.carrier_name,
                carrier_db_id=carrier_data.db_id,
                system=carrier_data.system,
                body=carrier_data.body,
                wine_total=carrier_data.wine_total,
                unload_opened=carrier_data.unload_opened,
                unload_closed=carrier_data.unload_closed,
                is_timed=False,
            )
        except UnloadOperationError as e:
            logger.info(str(e))
            await interaction.edit_original_response(content=str(e))
            return

        logger.info(
            f"Wine unload requested by {interaction.user.name} for {carrier_data.carrier_name} ({carrier_id}) processed successfully."
        )
        await interaction.edit_original_response(
            content=f"Wine unload requested by {interaction.user.name} for **{carrier_data.carrier_name} ({carrier_id})** "
            + "processed successfully."
        )

    @app_commands.command(
        name="wine_timed_unload",
        description="Posts a new timed unload notice for a carrier. Admin/Sommelier/WineCarrier role required.",
    )
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    @check_command_channel(CHANNEL_BC_WINE_CARRIER_COMMAND)
    @app_commands.autocomplete(carrier_id=booze_sheets_api.carrier_autocomplete(unload_state="full"))
    async def wine_carrier_timed_unload(self, interaction: discord.Interaction, carrier_id: str):
        """
        Posts a wine unload request to the unloading channel.

        :param interaction: the interaction
        :param str carrier_id: The carrier ID string
        :returns: A message to the user
        :rtype: Union[discord.Message, dict]
        """
        await interaction.response.defer()
        logger.info(
            f"User {interaction.user.name} has requested a new wine timed unload operation for carrier: {carrier_id} "
        )

        if settings.get_setting("timed_unloads_allowed") is False:
            msg = "Timed unloads are not allowed at this time."
            logger.info(msg)
            await interaction.followup.send(msg)
            return

        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not CARRIER_ID_RE.fullmatch(carrier_id):
            msg = (
                f"The carrier ID was invalid, XXX-XXX expected received, {carrier_id}.\n"
                "Carrier IDs cannot contain `'O'`s or `'I'`s, only `'0'`s and `'1'`s respectively."
            )
            logger.info(msg)
            await interaction.followup.send(msg)
            return

        logger.debug(f"Fetching carrier data for ID: {carrier_id}")

        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

        logger.debug(f"Fetched carrier data: {carrier_data.to_dictionary() if carrier_data else 'None'}")

        if not carrier_data:
            error_msg = f"Carrier {carrier_id} was not found."
            logger.info(error_msg)
            await interaction.followup.send(error_msg)
            return

        logger.debug(
            f"Preparing to send timed unload notification to Discord for carrier {carrier_data.carrier_identifier}."
        )
        await interaction.edit_original_response(content="**Sending to Discord...**")
        if not carrier_data.is_owned_by(interaction.user) and not is_staff(interaction.user):
            await interaction.edit_original_response(content=f"Carrier {carrier_id} is not owned by you.")
            return
        try:
            result = await self._unload(
                carrier_id=carrier_data.carrier_identifier,
                carrier_name=carrier_data.carrier_name,
                carrier_db_id=carrier_data.db_id,
                system=carrier_data.system,
                body=carrier_data.body,
                wine_total=carrier_data.wine_total,
                unload_opened=carrier_data.unload_opened,
                unload_closed=carrier_data.unload_closed,
                is_timed=True,
            )
        except UnloadOperationError as e:
            logger.info(str(e))
            await interaction.edit_original_response(content=str(e))
            return

        logger.info(
            f"Timed wine unload requested by {interaction.user.name} for {carrier_data.carrier_name} ({carrier_id}) processed successfully."
        )
        await interaction.followup.send(
            f"Timed wine unload requested by {interaction.user.name} for **{carrier_data.carrier_name} ({carrier_id})**\n"
            + f"Open the market at {result.open_time_str} (In game time)."
        )

    @app_commands.command(
        name="wine_unload_complete",
        description="Removes any trade channel notification for unloading wine. Somm/Conn/Wine Carrier role required.",
    )
    @describe(carrier_id="the XXX-XXX ID string for the carrier")
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    @check_command_channel(CHANNEL_BC_WINE_CARRIER_COMMAND)
    @app_commands.autocomplete(carrier_id=booze_sheets_api.carrier_autocomplete(unload_state="Unloading"))
    async def wine_unloading_complete(self, interaction: discord.Interaction, carrier_id: str):
        await interaction.response.defer()

        logger.info(
            f"User {interaction.user.name} has requested to complete the wine unload operation for carrier: {carrier_id}."
        )

        # Cast this to upper case just in case
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

        logger.debug(f"Fetching carrier data for ID: {carrier_id}")
        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)
        logger.debug(f"Fetched carrier data: {carrier_data.to_dictionary() if carrier_data else 'None'}")

        if not carrier_data:
            error_msg = f"Carrier {carrier_id} not found in the database."
            logger.info(error_msg)
            await interaction.edit_original_response(content=error_msg)
            return

        try:
            result = await self._unload_complete(carrier_data, requested_by=interaction.user)
        except UnloadOperationError as e:
            logger.info(str(e))
            await interaction.edit_original_response(content=str(e))
            return

        unload_duration = result.unload_duration

        logger.debug(f"Calculated unload duration: {unload_duration} seconds")

        minutes, seconds = divmod(int(unload_duration), 60)
        time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

        logger.info(f"Deleted unload notification message for carrier: {carrier_id}.")
        response = (
            f"Removed the unload notification for {carrier_data.carrier_name} ({carrier_id})\n"
            f"-# Unload duration: {time_str}."
        )
        allowed_mentions = discord.AllowedMentions.none()
        conn_role = await bot.get_or_fetch.role(ROLE_CONN)
        allowed_mentions.roles = [conn_role]

        logger.info(f"Wine unload for carrier {carrier_id} completed by {interaction.user.name}.")
        await interaction.edit_original_response(content=response, allowed_mentions=allowed_mentions)
        await interaction.edit_original_response(
            content=f"<@&{ROLE_CONN}> {response}", allowed_mentions=allowed_mentions
        )

    @app_commands.command(name="toggle_timed_unloads", description="Toggle the status of timed unloads.")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    async def toggle_timed_unloads(self, interaction: discord.Interaction):
        """
        Toggle allowing timed unloads.

        Args:
            interaction (discord.Interaction): The discord interaction context.
        """

        await interaction.response.defer(ephemeral=True)

        # Log the request
        steve_says_channel = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)
        new_status = "Disabled" if settings.get_setting("timed_unloads_allowed") else "Enabled"
        msg = f"requested to toggle the timed unloads status to: '{new_status}'."
        logger.info(f"{interaction.user.name} {msg}")
        await steve_says_channel.send(f"{interaction.user.mention} {msg}", silent=True)
        settings.set_setting("timed_unloads_allowed", not settings.get_setting("timed_unloads_allowed"))
        logger.info(f"Timed unloads are now '{new_status}'.")
        await interaction.edit_original_response(content=f"Timed unloads are now '{new_status}'.")

    @app_commands.command(
        name="set_timed_unload_hold_duration", description="Set the hold duration for timed unloads in minutes."
    )
    @describe(duration_minutes="Duration in minutes to hold the timed unload market before it is opened.")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    async def set_timed_unload_hold_duration(self, interaction: discord.Interaction, duration_minutes: float):
        """
        Set the hold duration for timed unloads.

        Args:
            interaction (discord.Interaction): The discord interaction context.
            duration_minutes (float): Duration in minutes to hold the timed unload market before it is opened.
        """

        await interaction.response.defer()

        logger.info(
            f"{interaction.user.name} requested to set the timed unload hold duration to {duration_minutes} minutes."
        )

        settings.set_setting("timed_unload_hold_duration", duration_minutes)

        logger.info(f"Timed unload hold duration set to {duration_minutes} minutes.")
        await interaction.followup.send(f"Timed unload hold duration set to {duration_minutes} minutes.")
