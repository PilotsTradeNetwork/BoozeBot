"""
Cog for PH check commands and loop

"""

import random
from datetime import UTC, datetime, timedelta, timezone

import discord
from discord import NotFound, app_commands
from discord.app_commands import describe
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from ptn_utils.enums.booze_enums import CruiseSystemState
from ptn_utils.global_constants import (
    CHANNEL_BC_BOOZE_CRUISE_CHAT,
    CHANNEL_BC_HOLIDAY_ANNOUNCE,
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER,
    CHANNEL_BC_WINE_CARRIER_COMMAND,
    ROLE_CONN,
    ROLE_COUNCIL,
    ROLE_SOMM,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.botcommands.Cleaner import Cleaner
from ptn.boozebot.constants import (
    bot,
    holiday_ended_gif,
    holiday_query_not_started_gifs,
    holiday_query_started_gifs,
    holiday_start_gif,
)
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, track_last_run
from ptn.boozebot.modules.PHcheck import api_ph_check, ph_check
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api

"""
PUBLIC HOLIDAY TASK LOOP

Checks every 15 minutes if the PH at rackhams peak is happening and pings somm and updates the db if it is.


PUBLIC HOLIDAY COMMANDS

/booze_started - conn/somm/mod/admin
/booze_started_admin_override - somm/mod/admin
/booze_duration_remaining - conn/somm/mod/admin
"""

logger = get_logger("boozebot.commands.publicholiday")


class PublicHoliday(commands.Cog):
    bot: Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    """
    The public holiday state checker mechanism for booze bot.
    """

    rackhams_holiday_active: bool = False

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting the public holiday state checker")
        if not self.public_holiday_loop.is_running():
            self.public_holiday_loop.start()
        else:
            logger.debug("Public holiday state checker loop already running.")

    @staticmethod
    async def _set_public_holiday_state(state: bool, timestamp: datetime, force_update: bool = False) -> tuple[bool, str]:
        logger.info(f"Setting public holiday state to: {state}, force update: {force_update}")
        if state:
            logger.info("PH detected, triggering the notifications.")
            holiday_announce_channel = await bot.get_or_fetch.channel(CHANNEL_BC_HOLIDAY_ANNOUNCE)

            # Check if we had a holiday flagged already
            logger.debug("Fetching holiday state from backend.")
            holiday_ongoing = await booze_sheets_api.get_current_cruise_state() == CruiseSystemState.ACTIVE
            logger.debug(f"Holiday Ongoing: {holiday_ongoing}")

            if not holiday_ongoing or force_update:
                logger.info("Holiday was not ongoing, started now - flag it accordingly")
                await holiday_announce_channel.send(holiday_start_gif)
                await holiday_announce_channel.send(
                    f"Pirate Steve thinks the folks at Rackhams are partying again. "
                    + f"<@&{ROLE_COUNCIL}>, <@&{ROLE_SOMM}> please take note."
                )
                logger.debug("Notified council and sommeliers of holiday start. Updating status embed.")
                await Cleaner.update_status_embed("bc_start")

                logger.info(f"Updating cruise start on backend to {timestamp}")
                await booze_sheets_api.update_cruise_start(timestamp)

                logger.info("Updating cruise state on backend to 'active'")
                await booze_sheets_api.update_cruise_state("active")

                return True, "Holiday started and flagged in the backend"
            else:
                logger.info("Holiday already flagged - no need to set it again")
                return False, "Holiday already ongoing, no need to set it again"
        else:
            # Check if the 48 hours have expired first, to avoid scenarios of the HTTP request failing and turning
            # off an ongoing holiday.
            logger.info("No PH detected, checking if holiday duration has expired.")

            logger.debug("Fetching holiday start timestamp from backend.")

            holiday_ongoing = await booze_sheets_api.get_current_cruise_state() == CruiseSystemState.ACTIVE
            current_cruise = await booze_sheets_api.get_cruise_with_stats(0)
            start_time = current_cruise.start
            logger.debug(f"Holiday state from boozeSheetsAPI: {holiday_ongoing}, timestamp: {start_time}")

            end_time = start_time + timedelta(hours=48)

            current_time_utc = datetime.now(tz=timezone.utc)

            logger.debug(f"Current time UTC: {current_time_utc}, holiday end time: {end_time}")

            if current_time_utc > end_time or force_update:
                # Current time is after the end time, go turn the checks off.
                logger.info("Holiday duration expired, turning the check off.")
                holiday_announce_channel = await bot.get_or_fetch.channel(CHANNEL_BC_HOLIDAY_ANNOUNCE)

                if holiday_ongoing or force_update:
                    logger.debug("Holiday ongoing - updating backend to turn it off.")
                    await booze_sheets_api.close_cruise(timestamp)
                    logger.debug("Backend updated to turn off holiday state.")

                    # Only post it if it is a state change.
                    logger.info("Holiday was ongoing, no longer ongoing - flag it accordingly")
                    await holiday_announce_channel.send(holiday_ended_gif)
                    logger.debug("Notified holiday end. Updating status embed.")
                    await Cleaner.update_status_embed("bc_end")

                    return True, "Holiday ended and flagged in the database"
                else:
                    logger.info("Holiday was not ongoing - no need to turn it off")
                    return False, "Holiday was not ongoing, no need to turn it off"
            else:
                logger.info(f"Holiday has not yet expired, no need to turn it off. Due at: {end_time}")
                return False, "Holiday has not yet expired, no need to turn it off"

    @tasks.loop(minutes=10)
    @track_last_run()
    async def public_holiday_loop(self):
        """
        Command triggers periodically to check the state at Rackhams Peak. Right now this triggers every 15 minutes.

        :return: None
        """
        logger.info("Rackham's holiday loop running.")
        try:
            state, updated_at = await api_ph_check()
            logger.info(f"Rackham's holiday API check returned: {state}, last updated: {updated_at}")
            await self._set_public_holiday_state(state,updated_at)

        except Exception as e:
            logger.exception(f"Error in the public holiday loop: {e}")

    @app_commands.command(name="booze_started", description="Returns a GIF for whether the holiday has started.")
    @check_roles([ROLE_CONN, ROLE_SOMM, *any_moderation_role, *any_council_role])
    async def holiday_query(self, interaction: discord.Interaction):
        await interaction.response.defer()
        logger.info(f"User {interaction.user.name} queried the holiday state.")
        gif = ""
        if await ph_check():
            logger.info("Rackhams holiday check says yep.")
            try:
                gif = random.choice(holiday_query_started_gifs)
                await interaction.followup.send(gif)
                logger.debug(f"Sent holiday started GIF: {gif}")
            except NotFound:
                logger.exception(f"Problem sending the GIF for: {gif}.")
                await interaction.followup.send(
                    "Pirate Steve could not parse the gif. Try again and tell Council to check the log."
                )
        else:
            logger.info("Rackhams holiday check says nope.")
            try:
                gif = random.choice(holiday_query_not_started_gifs)
                await interaction.followup.send(gif)
                logger.debug(f"Sent holiday not started gif: {gif}")
            except NotFound:
                logger.exception(f"Problem sending the GIF for: {gif}.")
                await interaction.followup.send(
                    "Pirate Steve could not parse the gif. Try again and tell Council to check the log."
                )

    @app_commands.command(
        name="booze_started_admin_override",
        description="Overrides the holiday admin flag.Used to set the holiday state before the polling API catches it.",
    )
    @check_roles([ROLE_SOMM, *any_moderation_role, *any_council_role])
    @describe(
        state="True or False to override the holiday check flag.",
        force_update="Force the update of the holiday state, even if it is already set.",
    )
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def admin_override_holiday_state(
        self, interaction: discord.Interaction, state: bool, force_update: bool = False
    ):
        logger.info(
            f"User {interaction.user.name} requested to override the admin holiday state to: {state}, forced: {force_update}."
        )
        _success, message = await self._set_public_holiday_state(state, datetime.now(tz=UTC), force_update)

        logger.info(f"Admin override result: {message}")
        await interaction.response.send_message(f"{message}. Check with /booze_started.")

    @app_commands.command(
        name="booze_timestamp_admin_override",
        description="Overrides the holiday start time.Used to set the cruise start time used to get the duration",
    )
    @check_roles([ROLE_SOMM, *any_moderation_role, *any_council_role])
    @describe(timestamp="Date time of the the cruise starting in the format YYYY-MM-DD HH:MI:SS (in UTC)")
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def admin_override_start_timestamp(self, interaction: discord.Interaction, timestamp: str):
        logger.info(f"User {interaction.user.name} requested to override the start time to: {timestamp}.")

        try:
            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            logger.exception("Invalid timestamp format provided.")
            await interaction.response.send_message(
                "Invalid timestamp format. Please use YYYY-MM-DD HH:MI:SS.", ephemeral=True
            )
            return

        # Check if we had a holiday flagged already
        holiday_ongoing = await ph_check()
        logger.debug(f"Holiday state from database: {holiday_ongoing}")

        if holiday_ongoing:
            logger.info("Holiday is ongoing, updating the timestamp.")

            await booze_sheets_api.update_cruise_start(timestamp)

            logger.debug("Database updated with new timestamp.")
            await interaction.response.send_message(
                f"Set the cruise start time to: {timestamp}. Check with /booze_duration_remaining."
            )

        else:
            logger.info("No holiday ongoing, cannot set timestamp.")
            await interaction.response.send_message(
                "No holiday has been detected yet, Wait until steve detects the holiday before using this command."
            )

    @app_commands.command(
        name="booze_duration_remaining", description="Returns roughly how long the holiday has remaining."
    )
    @check_command_channel(
        [
            CHANNEL_BC_WINE_CARRIER,
            CHANNEL_BC_STEVE_SAYS,
            CHANNEL_BC_WINE_CARRIER_COMMAND,
            CHANNEL_BC_BOOZE_CRUISE_CHAT,
        ]
    )
    async def remaining_time(self, interaction: discord.Interaction):
        logger.info(f"User {interaction.user.name} requested remaining holiday duration.")

        await interaction.response.defer()
        if not await ph_check():
            logger.info("Holiday not ongoing, cannot calculate remaining duration.")
            await interaction.edit_original_response(
                content="Pirate Steve has not detected the holiday state yet, or it is already over."
            )
            return
        logger.info("Holiday is ongoing, calculating remaining duration.")
        # Ok the holiday is ongoing
        duration_hours = 48

        # Get the starting timestamp

        logger.debug("Fetching holiday start timestamp from backend.")
        current_cruise = await booze_sheets_api.get_cruise_with_stats(0)
        start_time = current_cruise.start

        end_time = start_time + timedelta(hours=duration_hours)
        end_timestamp = int(end_time.timestamp())

        logger.info(f"Sending remaining duration response with end time: {end_time}.")
        await interaction.edit_original_response(
            content=f"Pirate Steve thinks the holiday will end around <t:{end_timestamp}> (<t:{end_timestamp}:R>) [local timezone]."
        )
