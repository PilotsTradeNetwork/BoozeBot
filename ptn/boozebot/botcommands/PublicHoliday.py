"""
Cog for PH check commands and loop

"""

import random
from datetime import UTC, datetime, timedelta

import discord
from discord import app_commands
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
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, track_last_run
from ptn.boozebot.modules.PHcheck import StaleDataException, api_ph_check

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
    async def _set_holiday_start():
        holiday_announce_channel = await bot.get_or_fetch.channel(CHANNEL_BC_HOLIDAY_ANNOUNCE)
        await holiday_announce_channel.send(holiday_start_gif)
        await holiday_announce_channel.send(
            "Pirate Steve thinks the folks at Rackhams are partying again. "
            + f"<@&{ROLE_COUNCIL}>, <@&{ROLE_SOMM}> please take note."
        )
        logger.debug("Notified council and sommeliers of holiday start. Updating status embed.")
        await Cleaner.update_status_embed("bc_start")
        logger.info("Holiday announced to discord, updating backend state to active.")
        await booze_sheets_api.update_cruise_state("active")
        await booze_sheets_api.update_cruise_start(datetime.now(tz=UTC))

    @staticmethod
    async def _set_holiday_end():
        holiday_announce_channel = await bot.get_or_fetch.channel(CHANNEL_BC_HOLIDAY_ANNOUNCE)
        await holiday_announce_channel.send(holiday_ended_gif)
        logger.debug("Notified holiday end. Updating status embed.")
        await Cleaner.update_status_embed("bc_end")
        logger.info("Holiday end announced to discord, updating backend state to closed.")
        await booze_sheets_api.end_ph(datetime.now(tz=UTC))

    @staticmethod
    async def _set_public_holiday_state(
        new_state: bool, timestamp: datetime, force_update: bool = False
    ) -> tuple[bool, str]:
        logger.info(f"Setting public holiday state to: {new_state}, force update: {force_update}")

        current_state = await booze_sheets_api.get_current_cruise_state()
        holiday_ongoing = current_state["state"] == CruiseSystemState.ACTIVE

        if timestamp < current_state["updated_at"] and not force_update:
            logger.info(
                f"New state info is older than the current state. Current state updated at {current_state['updated_at']}, new state timestamp: {timestamp}. No update performed."
            )
            return False, "New state timestamp is older than current state, no update performed"

        if new_state and (not holiday_ongoing or force_update):
            logger.info("New state is active and holiday is not ongoing, setting holiday start.")
            await PublicHoliday._set_holiday_start()
            return True, "Holiday started and flagged in the backend"

        if not new_state and (holiday_ongoing or force_update):
            logger.info("New state is not active and holiday is ongoing, setting holiday end.")
            await PublicHoliday._set_holiday_end()
            return True, "Holiday ended and flagged in the database"

        return False, "No state change needed for the holiday state"

    @tasks.loop(minutes=10)
    @track_last_run()
    async def public_holiday_loop(self):
        """
        Command triggers periodically to check the state at Rackhams Peak. Right now this triggers every 10 minutes.

        :return: None
        """
        logger.info("Rackham's holiday loop running.")
        try:
            state, updated_at = await api_ph_check()
            logger.info(f"Rackham's holiday API check returned: {state}, last updated: {updated_at}")
            await self._set_public_holiday_state(state, updated_at)
        except StaleDataException as e:
            logger.warning(f"{e}. Not using it.")
        except Exception as e:
            logger.exception(f"Error in the public holiday loop: {e}")

    @app_commands.command(name="booze_started", description="Returns a GIF for whether the holiday has started.")
    @check_roles([ROLE_CONN, ROLE_SOMM, *any_moderation_role, *any_council_role])
    async def holiday_query(self, interaction: discord.Interaction):
        await interaction.response.defer()
        logger.info(f"User {interaction.user.name} queried the holiday state.")

        try:
            holiday_ongoing = (await booze_sheets_api.get_current_cruise_state())["state"] == CruiseSystemState.ACTIVE
        except Exception as e:
            logger.error(f"Error while checking holiday state for /booze_started command: {e}")
            await interaction.followup.send("Sorry, Pirate Steve had trouble determining the holiday state.")
            return

        logger.info(f"Holiday state: {holiday_ongoing}")

        if holiday_ongoing:
            logger.debug("Holiday is ongoing, selecting from started gifs.")
            gifs = holiday_query_started_gifs
        else:
            logger.debug("Holiday is not ongoing, selecting from not started gifs.")
            gifs = holiday_query_not_started_gifs

        gif = random.choice(gifs)

        await interaction.followup.send(gif)
        logger.debug(f"Sent GIF: {gif}")

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
        now = datetime.now(tz=UTC)

        try:
            _success, message = await self._set_public_holiday_state(state, now, force_update)
        except Exception as e:
            logger.exception(f"Error while trying to override the holiday state: {e}")
            await interaction.response.send_message("An error occurred while trying to override the holiday state.")
            return

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
            dt_timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            logger.exception("Invalid timestamp format provided.")
            await interaction.response.send_message(
                "Invalid timestamp format. Please use YYYY-MM-DD HH:MI:SS.", ephemeral=True
            )
            return

        # Check if we had a holiday flagged already
        try:
            holiday_ongoing = booze_sheets_api.get_current_cruise_state().get("state") == CruiseSystemState.ACTIVE
        except Exception as e:
            logger.exception(f"Error while checking current cruise state before overriding start timestamp: {e}")
            await interaction.response.send_message(
                "An error occurred while trying to fetch the current holiday state."
            )
            return
        logger.debug(f"Holiday state from database: {holiday_ongoing}")

        if not holiday_ongoing:
            logger.info("No holiday ongoing, cannot set timestamp.")
            await interaction.response.send_message(
                "No holiday has been detected yet, Wait until steve detects the holiday before using this command."
            )
            return

        logger.info("Holiday is ongoing, updating the timestamp.")

        try:
            await booze_sheets_api.update_cruise_start(dt_timestamp)
        except Exception as e:
            logger.exception(f"Error while updating cruise start timestamp: {e}")
            await interaction.response.send_message(
                "An error occurred while trying to update the cruise start timestamp."
            )
            return

        logger.debug("Database updated with new timestamp.")
        await interaction.response.send_message(
            f"Set the cruise start time to: {dt_timestamp}. Check with /booze_duration_remaining."
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

        try:
            holiday_ongoing = (await booze_sheets_api.get_current_cruise_state())["state"] == CruiseSystemState.ACTIVE
        except Exception as e:
            logger.error(f"Error while checking holiday state for /booze_duration_remaining command: {e}")
            await interaction.edit_original_response(
                content="Sorry, Pirate Steve had trouble determining the holiday state."
            )
            return

        if not holiday_ongoing:
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
        start_time = current_cruise.ph_start

        end_time = start_time + timedelta(hours=duration_hours)
        end_timestamp = int(end_time.timestamp())

        logger.info(f"Sending remaining duration response with end time: {end_time}.")
        await interaction.edit_original_response(
            content=f"Pirate Steve thinks the holiday will end around <t:{end_timestamp}> (<t:{end_timestamp}:R>) [local timezone]."
        )
