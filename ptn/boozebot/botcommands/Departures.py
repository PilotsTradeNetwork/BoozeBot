"""
Cog for departure related commands

"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

import discord
from discord import app_commands
from discord.app_commands import Choice, describe
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from ptn_utils.global_constants import (
    CHANNEL_BC_DEPARTURE_ANNOUNCEMENT,
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER,
    CHANNEL_BC_WINE_CARRIER_COMMAND,
    EMOJI_THOON,
    ROLE_CONN,
    ROLE_HITCHHIKER,
    ROLE_SOMM,
    ROLE_WINE_CARRIER,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier
from ptn.boozebot.constants import CARRIER_ID_RE, N_SYSTEMS, bot
from ptn.boozebot.database.database import database
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api
from ptn.boozebot.modules.helpers import (
    check_command_channel,
    check_roles,
    is_staff,
    track_last_run,
)
from ptn.boozebot.modules.Settings import settings
from ptn.boozebot.modules.Views import ConfirmView

"""
DEPARTURE COMMANDS
/wine_carrier_departure - wine carrier/somm/mod/admin
"""

logger = get_logger("boozebot.commands.departures")


class DepartureOperationError(Exception):
    """Raised when a departure operation cannot be posted or closed."""

    code: str
    is_private: bool

    def __init__(self, message: str, *, code: str = "DEPARTURE_OPERATION_FAILED", is_private: bool = True):
        super().__init__(message)
        self.code = code
        self.is_private = is_private


@dataclass(slots=True)
class DeparturePostResult:
    message_id: int
    jump_url: str


@dataclass(slots=True)
class DepartureCloseResult:
    message_id: int


# initialise the Cog and attach our global error handler
class Departures(commands.Cog):
    bot: Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _post_departure(
        self,
        carrier_data: BoozeCarrier | None,
        arrival_system: str,
        departure_timestamp: datetime | None,
        requested_by: discord.Member | None = None,
    ) -> DeparturePostResult:
        """Post a departure notice and persist the Discord message ID."""

        if not carrier_data:
            raise DepartureOperationError("Carrier data was not provided.", code="MISSING_CARRIER_DATA")

        carrier_id = carrier_data.carrier_identifier

        if requested_by and not carrier_data.is_owned_by(requested_by) and not is_staff(requested_by):
            raise DepartureOperationError(f"You do not own the carrier with ID: {carrier_id}.", code="NOT_OWNER")

        departure_system = carrier_data.system
        if departure_system not in N_SYSTEMS:
            raise DepartureOperationError(
                f"Carrier {carrier_id} current location must be a system on the ladder to post a departure notice. Current location: '{departure_system}'.",
                code="INVALID_DEPARTURE_SYSTEM",
            )

        if arrival_system not in N_SYSTEMS:
            raise DepartureOperationError(
                f"Arrival location '{arrival_system}' is invalid.",
                code="INVALID_ARRIVAL_SYSTEM",
            )

        if departure_system == arrival_system:
            raise DepartureOperationError(
                "Departure and arrival are the same system.",
                code="SAME_SYSTEM",
            )

        # Construct departure message text from structured input.
        carrier_name = carrier_data.carrier_name.replace("<", "").replace(">", "").replace("@", "").replace("|", "")
        clean_carrier_id = carrier_id.replace("<", "").replace(">", "").replace("@", "").replace("|", "")

        def parse_system_index(system_id: str) -> int:
            try:
                return int(system_id[1:])
            except ValueError:
                return 16

        departure_system_index = parse_system_index(departure_system)
        arrival_system_index = parse_system_index(arrival_system)

        if departure_system_index < arrival_system_index:
            direction_arrow = "⬇️"
        elif departure_system_index > arrival_system_index:
            direction_arrow = "⬆️"
        else:
            direction_arrow = ""

        if settings.get_setting("departure_announcement_status") == "Disabled":
            raise DepartureOperationError(
                "Departure announcements are currently disabled.",
                code="DEPARTURES_DISABLED",
            )

        if settings.get_setting("departure_announcement_status") == "Upwards" and direction_arrow == "⬇️":
            raise DepartureOperationError(
                "Departure announcements are currently only enabled for jumps moving up towards N0",
                code="UPWARDS_ONLY",
            )

        departing_thoon = False
        if departure_timestamp:
            departure_time_text = f" <t:{departure_timestamp}:f> (<t:{departure_timestamp}:R>) |"
            departing_thoon = datetime.fromtimestamp(departure_timestamp) < datetime.now() + timedelta(hours=2)
        else:
            departure_time_text = f" {await bot.get_or_fetch.emoji(EMOJI_THOON)} |"

        hitchhiker_systems = [0, 1, 2, 3]
        thoon_systems = [0, 1]
        is_hitchhiking_trip = (
            departure_system_index in hitchhiker_systems and arrival_system_index in hitchhiker_systems
        )
        is_thoon_trip = departure_system_index in thoon_systems or arrival_system_index in thoon_systems

        if is_thoon_trip and departing_thoon:
            departure_time_text = f" {await bot.get_or_fetch.emoji(EMOJI_THOON)} |"

        hitchhiker_ping_text = ""
        if direction_arrow == "⬆️" and is_hitchhiking_trip:
            hitchhiker_ping_text = f"| <@&{ROLE_HITCHHIKER!s}>"

        departure_location_text = f"{departure_system} ({N_SYSTEMS[departure_system]})"
        arrival_location_text = f"{arrival_system} ({N_SYSTEMS[arrival_system]})"

        departure_message_text = (
            f"**{direction_arrow} {departure_location_text} > {arrival_location_text}** |"
            + f"{departure_time_text} **{carrier_name} ({clean_carrier_id})** | "
            + f"<@{carrier_data.owner.discord_id}> {hitchhiker_ping_text}"
        )

        if existing_message_id := await database.get_departure_message_for_carrier(carrier_id):
            try:
                departure_channel = await bot.get_or_fetch.channel(CHANNEL_BC_DEPARTURE_ANNOUNCEMENT)
                existing_message_id = (await departure_channel.fetch_message(existing_message_id)).id
            except discord.NotFound:
                existing_message_id = None
                await database.delete_carrier_message(carrier_id, "departure")

        if existing_message_id:
            raise DepartureOperationError(
                f"A departure message is already posted for carrier ID: {carrier_id}. Please remove it before posting a new one.",
                code="DEPARTURE_ALREADY_POSTED",
            )

        try:
            departure_channel = await bot.get_or_fetch.channel(CHANNEL_BC_DEPARTURE_ANNOUNCEMENT)
            departure_message = await departure_channel.send(departure_message_text)
            await departure_message.add_reaction("🛬")
            await database.set_departure_message_for_carrier(carrier_id, departure_message.id)
            await database.set_departure_notification_sent(carrier_id, False)
        except Exception as e:
            logger.exception(f"Failed to post departure message for carrier {carrier_id}: {e}")
            raise DepartureOperationError(
                f"Failed to post departure message for carrier {carrier_id}: {e}",
                code="DEPARTURE_POST_FAILED",
                is_private=False,
            ) from e

        return DeparturePostResult(message_id=departure_message.id, jump_url=departure_message.jump_url)

    async def _close_departure(
        self,
        carrier_data: BoozeCarrier | None,
        requested_by: discord.Member | None = None,
    ) -> DepartureCloseResult:
        """Close a departure notice by removing the Discord message and DB entry."""

        if not carrier_data:
            raise DepartureOperationError("Carrier data was not provided.", code="MISSING_CARRIER_DATA")

        carrier_id = carrier_data.carrier_identifier

        if requested_by and not carrier_data.is_owned_by(requested_by) and not is_staff(requested_by):
            raise DepartureOperationError(f"You do not own the carrier with ID: {carrier_id}.", code="NOT_OWNER")

        message_id = await database.get_departure_message_for_carrier(carrier_id)
        if not message_id:
            raise DepartureOperationError(
                f"No departure notification found in database for carrier: {carrier_id}.",
                code="MISSING_DEPARTURE_ALERT",
            )

        try:
            try:
                departure_channel = await bot.get_or_fetch.channel(CHANNEL_BC_DEPARTURE_ANNOUNCEMENT)
                departure_message = await departure_channel.fetch_message(message_id)
                await departure_message.delete()
            except discord.NotFound:
                logger.warning(
                    f"Departure notification message ID {message_id} for carrier {carrier_id} not found in channel."
                )

            await database.delete_carrier_message(carrier_id, "departure")
        except Exception as e:
            logger.exception(f"Failed to close departure message for carrier {carrier_id}: {e}")
            raise DepartureOperationError(
                f"Failed to close departure message for carrier {carrier_id}: {e}",
                code="DEPARTURE_CLOSE_FAILED",
                is_private=False,
            ) from e

        return DepartureCloseResult(message_id=message_id)

    """
    This class is a collection functionality for posting departure messages for carriers.
    """

    system_choices: Final[list[Choice[str]]] = [
        Choice(name=f"{system_id} ({system_name})", value=system_id) for system_id, system_name in N_SYSTEMS.items()
    ]

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting the departure message checker")
        if not self.check_departure_messages_loop.is_running():
            self.check_departure_messages_loop.start()
        else:
            logger.debug("Departure message checker already running.")

    @tasks.loop(minutes=5)
    @track_last_run()
    async def check_departure_messages_loop(self):
        departure_channel = await bot.get_or_fetch.channel(CHANNEL_BC_DEPARTURE_ANNOUNCEMENT)
        wine_carrier_chat = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CARRIER)

        logger.info("Checking for passed departure messages.")
        async for message in departure_channel.history(limit=100):
            try:
                if message.pinned:
                    continue

                if message.author.id != bot.user.id:
                    continue

                if len(message.embeds) > 0:
                    continue

                logger.info("Departure message found.")

                has_reacted = False
                for reaction in message.reactions:
                    if reaction.emoji == "⏲️":
                        async for user in reaction.users():
                            if user.id == bot.user.id:
                                has_reacted = True
                                break

                if has_reacted:
                    logger.info("Departure message has been responded to.")
                    continue

                content = message.content
                departure_time = content.split("|")[1].replace(" ", "")

                if departure_time.startswith("<t:"):
                    departure_time = departure_time.split(":")[1]
                elif departure_time == f"{await bot.get_or_fetch.emoji(EMOJI_THOON)}":
                    departure_time = message.created_at.timestamp() + 25 * 60

                try:
                    departure_time = int(departure_time)
                except ValueError:
                    logger.exception(
                        f"Departure time was not an integer: {departure_time}, Probably means they never set a departure time."
                    )
                    continue

                logger.info(f"Departure time: {departure_time}")

                if int(time.time()) > departure_time + 10 * 60:  # Allow a 10-minute grace period
                    logger.info("Departure time has passed.")
                    author_id = self.get_departure_author_id(message)
                    if author_id:
                        logger.info(f"Notifying user with id: {author_id} in WCO chat.")
                        await message.add_reaction("⏲️")
                        await wine_carrier_chat.send(
                            f"<@{author_id}> your scheduled departure time of <t:{departure_time}:F> has passed. If your carrier has entered lockdown or completed its jump, please use the ✅ reaction under your notice to remove it. {message.jump_url}"  # TODO RRPLACE WITH BUTTON
                        )

            except Exception as e:
                logger.exception(
                    f"Failed to process departure message while checking for time passed. message: {message.id}. Error: {e}"
                )

    @app_commands.command(name="wine_carrier_departure", description="Post a departure message for a wine carrier.")
    @describe(
        carrier_id="The XXX-XXX ID string for the carrier",
        departure_location="The location the carrier is departing from.",
        arrival_location="The location the carrier is arriving at.",
        departing_at="The unix timestamp, or discord timestamp of the carrier departure.",
        departing_in="The time in minutes until the carrier departs.",
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
    @app_commands.choices(arrival_location=system_choices, departure_location=system_choices)
    async def wine_carrier_departure(
        self,
        interaction: discord.Interaction,
        carrier_id: str,
        departure_location: str,
        arrival_location: str,
        departing_at: str | None = None,
        departing_in: str | None = None,
    ):
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

        logger.info(
            f"User {interaction.user.name} has requested a new wine carrier departure operation for carrier: {carrier_id} from the "
            + f"location: {departure_location} to {arrival_location}."
        )

        # Defer the interaction response to allow more time for processing
        await interaction.response.defer(ephemeral=True)

        # Convert carrier ID to uppercase
        carrier_id = carrier_id.upper().strip()

        command_string = f"/wine_carrier_departure carrier_id:{carrier_id} departure_location:{departure_location} arrival_location:{arrival_location}"

        if departing_at is not None:
            command_string += f" departing_at:{departing_at}"
        if departing_in is not None:
            command_string += f" departing_in:{departing_in}"

        base_error = f"Error for {interaction.user.mention} ({interaction.user.name}) during `{command_string}`"

        steve_says_channel = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)
        # Validate the carrier ID format
        if not CARRIER_ID_RE.fullmatch(carrier_id):
            msg = (
                f"The carrier ID was invalid, XXX-XXX expected received, {carrier_id}.\n"
                "Carrier IDs cannot contain `'O'`s or `'I'`s, only `'0'`s and `'1'`s respectively."
            )
            logger.info(msg)
            await interaction.edit_original_response(content=msg)
            await steve_says_channel.send(f"{base_error} {msg}")
            return

        logger.debug(f"Fetching carrier data for carrier ID: {carrier_id}")

        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

        # Check if carrier data was found
        if not carrier_data:
            msg = f'could not find a carrier for the data: "{carrier_id}".'
            logger.info(msg)
            await interaction.edit_original_response(content=f"Sorry, we {msg}")
            await steve_says_channel.send(f"{base_error} {msg}")
            return

        departure_time = None

        thoon_inputs = [f"<:thoon:{EMOJI_THOON}>", "thoon"]
        # Handle thoon
        if (departing_at and departing_at.lower() in thoon_inputs) or (
            departing_in and departing_in.lower() in thoon_inputs
        ):
            logger.info("Departure time set to Thoon.")
        # Handle departure time if provided as a timestamp
        elif departing_at:
            try:
                departure_timestamp_str = departing_at
                if departure_timestamp_str.startswith("<t:") and departure_timestamp_str.endswith(">"):
                    departure_timestamp_str = departure_timestamp_str.rstrip(">").split(":")[1]
                departure_time = datetime.fromtimestamp(int(departure_timestamp_str))
            except ValueError:
                msg = f"Departure time was not a valid timestamp: {departing_at}"
                logger.info(msg)
                await interaction.edit_original_response(
                    content=f"{msg}. You can use <https://hammertime.cyou> (or @time on desktop) to generate them."
                )
                await steve_says_channel.send(f"{base_error} {msg}")
                return

        # Handle departure time if provided as a duration in minutes
        elif departing_in:
            try:
                departing_in_minutes = int(departing_in)
            except ValueError:
                msg = f"Departing in was not a valid number: {departing_in}"
                logger.info(msg)
                await interaction.edit_original_response(
                    content=f"{msg}. It should be the number of minutes until your carrier departs."
                )
                await steve_says_channel.send(f"{base_error} {msg}")
                return

            departure_time = datetime.now() + timedelta(minutes=departing_in_minutes)

        try:
            post_result = await self._post_departure(
                carrier_data,
                arrival_location,
                departure_time,
                requested_by=interaction.user,
            )
        except DepartureOperationError as e:
            msg = str(e)
            logger.info(msg)
            await interaction.edit_original_response(content=msg)
            await steve_says_channel.send(f"{base_error} {msg}")
            return

        logger.info(
            f"Departure message sent for carrier {carrier_data.carrier_name} ({carrier_data.carrier_identifier})."
        )

        # Edit the original interaction response with the jump URL of the departure message
        await interaction.edit_original_response(content=f"Departure message sent to {post_result.jump_url}.")

    @app_commands.command(
        name="remove_wine_carrier_departure", description="Remove a departure message for a wine carrier."
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
    async def remove_wine_carrier_departure(
        self,
        interaction: discord.Interaction,
        carrier_id: str,
    ):
        await interaction.response.defer(ephemeral=True)

        carrier_id = carrier_id.upper().strip()

        logger.info(
            f"User {interaction.user.name} has requested to remove a wine carrier departure operation for carrier: {carrier_id}."
        )

        if not CARRIER_ID_RE.fullmatch(carrier_id):
            msg = (
                f"The carrier ID was invalid, XXX-XXX expected received, {carrier_id}.\n"
                "Carrier IDs cannot contain `'O'`s or `'I'`s, only `'0'`s and `'1'`s respectively."
            )
            logger.info(msg)
            await interaction.edit_original_response(content=msg)
            return

        logger.debug(f"Fetching carrier data for carrier ID: {carrier_id}")

        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

        if not carrier_data:
            msg = f'could not find a carrier for the data: "{carrier_id}".'
            logger.info(msg)
            await interaction.edit_original_response(content=f"Sorry, we {msg}")
            return

        try:
            close_result = await self._close_departure(carrier_data, requested_by=interaction.user)
        except DepartureOperationError as e:
            msg = str(e)
            logger.info(msg)
            await interaction.edit_original_response(content=msg)
            return

        logger.info(
            f"Departure message with ID {close_result.message_id} removed for carrier {carrier_data.carrier_name} ({carrier_data.carrier_identifier})."
        )
        await interaction.edit_original_response(content=f"Departure message removed for carrier {carrier_id}.")

    @app_commands.command(name="set_allowed_departures", description="Set the status of departure announcements.")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    @describe(status="The status to set for departure announcements.")
    async def set_allowed_departures(
        self, interaction: discord.Interaction, status: Literal["Disabled", "Upwards", "All"]
    ):
        """
        Set the status of departure announcements.

        Args:
            interaction (discord.Interaction): The discord interaction context.
            status (Literal["Disabled", "Upwards", "All"]): The status of departure announcements.
        """

        await interaction.response.defer(ephemeral=True)

        # Log the request
        steve_says_channel = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)
        msg = f"requested to set the departure announcement status to: '{status}'."
        logger.info(f"{interaction.user.name} {msg}")
        await steve_says_channel.send(f"{interaction.user.mention} {msg}", silent=True)
        # Set the departure announcement status
        settings.set_setting("departure_announcement_status", status)
        # Send the response message
        logger.info(f"Departure announcements are now '{status}'.")
        await interaction.edit_original_response(content=f"Departure announcements are now '{status}'.")

    async def official_departure_name_autocomplete(
        self, _interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """
        Autocomplete function for official departure names.

        Args:
            interaction (discord.Interaction): The discord interaction context.
            current (str): The current input string.

        Returns:
            list[app_commands.Choice[str]]: A list of autocomplete choices.
        """
        official_departure_names = ["Booze Snooze", "N2 Shuttle", "N3 Shuttle", "Garage"]
        return [
            app_commands.Choice(name=name, value=name)
            for name in official_departure_names
            if current.lower() in name.lower()
        ][:25]

    @app_commands.command(name="official_carrier_departure", description="Post an official carrier departure message.")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    @describe(
        carrier_id="The XXX-XXX ID string for the carrier",
        operated_by="The user/role who is operating the carrier.",
        departure_name="The name of the departure",
        departure_location="The location the carrier is departing from.",
        arrival_location="The location the carrier is arriving at.",
        departure_time_type="The type of departure time to use. Start/End of PH or a specific time.",
        departure_timestamp="The unix timestamp, or discord timestamp of the carrier departure.",
    )
    @app_commands.choices(
        arrival_location=system_choices,
        departure_location=system_choices,
        departure_time_type=[
            Choice(name="Start Of Cruise", value="Start Of Cruise"),
            Choice(name="End of Cruise", value="End of Cruise"),
            Choice(name="Custom (requires timestamp)", value="Custom (requires timestamp)"),
            Choice(name="Pre-PH (requires timestamp)", value="Pre-PH (requires timestamp)"),
            Choice(name="Thoon", value="Thoon"),
        ],
    )
    @app_commands.autocomplete(departure_name=official_departure_name_autocomplete)
    async def official_carrier_departure(
        self,
        interaction: discord.Interaction,
        carrier_id: str,
        operated_by: discord.Member | discord.Role,
        departure_name: str,
        departure_location: str,
        arrival_location: str,
        departure_time_type: str,
        departure_timestamp: str = "",
    ):
        logger.info(
            f"User {interaction.user.name} has requested an official carrier departure for carrier: {carrier_id} from {departure_location} to {arrival_location} with type: {departure_time_type}."
        )
        await interaction.response.defer()

        # Convert carrier ID to uppercase
        carrier_id = carrier_id.upper().strip()

        # Validate the carrier ID format
        if not CARRIER_ID_RE.fullmatch(carrier_id):
            msg = (
                f"The carrier ID was invalid, XXX-XXX expected received, {carrier_id}.\n"
                "Carrier IDs cannot contain `'O'`s or `'I'`s, only `'0'`s and `'1'`s respectively."
            )
            logger.info(msg)
            await interaction.edit_original_response(content=msg)
            return

        logger.debug(f"Fetching carrier data for carrier ID: {carrier_id}")
        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)
        logger.debug(f"Fetched carrier data: {carrier_data.to_dictionary() if carrier_data else 'None'}")

        # Check if carrier data was found
        if not carrier_data:
            msg = f'could not find a carrier for the data: "{carrier_id}".'
            logger.info(msg)
            await interaction.edit_original_response(content=f"Sorry, we {msg}")
            return

        carrier_name = carrier_data.carrier_name
        carrier_id = carrier_data.carrier_identifier

        departure_location = f"{departure_location} ({N_SYSTEMS[departure_location]})"
        arrival_location = f"{arrival_location} ({N_SYSTEMS[arrival_location]})"

        logger.debug(f"Departure location: {departure_location}, Arrival location: {arrival_location}")

        async def validate_timestamp(user_input: str) -> int | None:
            if not user_input:
                msg = "You must provide a departure timestamp when using the 'Custom' departure time type."
                logger.info(msg)
                await interaction.edit_original_response(content=msg)
                return None

            try:
                if user_input.startswith("<t:") and user_input.endswith(">"):
                    user_input = user_input.rstrip(">").split(":")[1]
                timestamp = int(user_input)
                if timestamp < datetime.now(UTC).timestamp():
                    msg = f"Departure timestamp must be in the future: {user_input}"
                    logger.info(msg)
                    await interaction.edit_original_response(content=msg)
                    return None
                if timestamp > (datetime.now(UTC) + timedelta(days=7)).timestamp():
                    msg = f"Departure timestamp must be within 1 week of now: {user_input}"
                    logger.info(msg)
                    await interaction.edit_original_response(content=msg)
                    return None
            except ValueError:
                msg = f"Departure timestamp was not a valid integer: {user_input}"
                logger.info(msg)
                await interaction.edit_original_response(content=msg)
                return None

            return timestamp

        departure_time_text = ""
        if departure_time_type == "Start Of Cruise":
            departure_time_text = "Departs when the public holiday is announced at Rackham's Peak"
        elif departure_time_type == "End of Cruise":
            departure_time_text = "Departs when the public holiday ends at Rackham's Peak"
        elif departure_time_type == "Custom (requires timestamp)":
            timestamp = await validate_timestamp(departure_timestamp)
            logger.debug(f"Validated timestamp: {timestamp}")
            if timestamp is None:
                return
            departure_time_text = f"Departs <t:{timestamp}:f> (<t:{timestamp}:R>)"
        elif departure_time_type == "Pre-PH (requires timestamp)":
            timestamp = await validate_timestamp(departure_timestamp)
            logger.debug(f"Validated timestamp: {timestamp}")
            if timestamp is None:
                return
            departure_time_text = f"Departs any time after <t:{timestamp}:f> (<t:{timestamp}:R>) or immediately if the public holiday is announced at Rackham's Peak."
        elif departure_time_type == "Thoon":
            departure_time_text = f"Departs {await bot.get_or_fetch.emoji(EMOJI_THOON)}"

        embed = discord.Embed(
            description=f"# {departure_name}\n"
            + f"## {carrier_name} ({carrier_id})\n"
            + f"## {departure_location} > {arrival_location}\n"
            + f"{departure_time_text}\n"
            + f"Operated by {operated_by.mention}",
            color=15611236,
        )

        departure_channel = await bot.get_or_fetch.channel(CHANNEL_BC_DEPARTURE_ANNOUNCEMENT)

        # Check for existing departure message
        logger.debug("Checking for existing official departure message.")
        if existing_departure_message := await database.get_departure_message_for_carrier(carrier_id):
            try:
                existing_departure_message = await departure_channel.fetch_message(existing_departure_message)
            except discord.NotFound:
                existing_departure_message = None

        if existing_departure_message:
            logger.info("Existing official departure message found, prompting for edit confirmation.")
            check_embed = discord.Embed(
                title="Existing Official Departure Message Found",
                description="Do you want to edit the existing official departure message?",
            )
            confirm = ConfirmView(interaction.user)
            await interaction.edit_original_response(embed=check_embed, view=confirm)
            await confirm.wait()

            logger.debug(f"Confirmation result: {confirm.value}")

            if not confirm.value:
                logger.info("Official departure edit cancelled by user.")
                await interaction.edit_original_response(
                    content="Official departure edit cancelled.", embed=None, view=None
                )
                return

            logger.info("Editing existing official departure message.")
            await existing_departure_message.edit(content=None, embed=embed)
            await existing_departure_message.clear_reaction("✅")
            await existing_departure_message.clear_reaction("⏲️")
            await interaction.edit_original_response(
                content=f"Official carrier departure message edited: {existing_departure_message.jump_url}",
                embed=None,
                view=None,
            )
        else:
            logger.info("Sending new official departure message.")

            departure_message = await departure_channel.send(embed=embed)
            await departure_message.add_reaction("🛬")
            await interaction.edit_original_response(
                content=f"Official carrier departure message sent: {departure_message.jump_url}"
            )
            logger.debug("Updating database with departure message ID.")
            await database.set_departure_message_for_carrier(carrier_id, departure_message.id)
            logger.info("Official departure message posted successfully.")

    def get_departure_author_id(self, message: discord.Message) -> int | None:
        try:
            return int(message.content.split("<@")[1].split(">")[0])
        except IndexError:
            return None
