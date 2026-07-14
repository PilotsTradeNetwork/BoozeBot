import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

import discord
from discord import app_commands
from discord.app_commands import Choice, describe
from discord.ext import commands
from discord.ext.commands import Bot
from ptn_utils.global_constants import CHANNEL_BC_STEVE_SAYS, ROLE_SOMM, any_council_role, any_moderation_role
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import bot, settings
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api
from ptn.boozebot.modules.helpers import check_command_channel, check_roles

if TYPE_CHECKING:
    from discord.ext.tasks import Loop

logger = get_logger("boozebot.commands.background")


class Task:
    def __init__(
        self,
        start: Callable[..., None],
        stop: Callable[..., None],
        is_running: Callable[..., bool],
        status: Callable[..., str],
    ):
        self._start: Callable[..., None] = start
        self._stop: Callable[..., None] = stop
        self.is_running: Callable[..., bool] = is_running
        self.status: Callable[..., str] = status

    async def start(self):
        if inspect.iscoroutinefunction(self._start):
            await self._start()
        else:
            self._start()

    async def stop(self):
        if inspect.iscoroutinefunction(self._stop):
            await self._stop()
        else:
            self._stop()


class BackgroundTaskCommands(commands.Cog):
    bot: Bot
    task_choices: Final[list[Choice[str]]] = [
        Choice(name="periodic_stat_update", value="periodic_stat_update"),
        Choice(name="check_departure_messages_loop", value="check_departure_messages_loop"),
        Choice(name="public_holiday_loop", value="public_holiday_loop"),
        Choice(name="last_unload_time_loop", value="last_unload_time_loop"),
        Choice(name="periodic_signup_poll", value="periodic_signup_poll"),
        Choice(name="boozesheets_websocket", value="boozesheets_websocket"),
        Choice(name="boozesheets_carrier_poll", value="boozesheets_carrier_poll"),
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Start BoozeSheets background listeners when the bot is ready."""
        if settings.tasks_auto_start.get("boozesheets_websocket", True):
            logger.info("Starting the BoozeSheets websocket listener")
            if not booze_sheets_api.get_websocket_status()[0]:
                try:
                    await booze_sheets_api.start_websocket_listener()
                    logger.info("BoozeSheets websocket listener started.")
                except Exception:
                    logger.exception("Failed to start BoozeSheets websocket listener.")
            else:
                logger.info("BoozeSheets websocket listener is already running.")
        else:
            logger.info("BoozeSheets websocket listener auto-start is disabled in settings.")

        if settings.tasks_auto_start.get("boozesheets_carrier_poll", True):
            logger.info("Starting the BoozeSheets carrier polling loop")
            if not booze_sheets_api.get_carrier_poll_status()[0]:
                try:
                    await booze_sheets_api.start_carrier_polling()
                    logger.info("BoozeSheets carrier polling loop started.")
                except Exception:
                    logger.exception("Failed to start BoozeSheets carrier polling loop.")
            else:
                logger.info("BoozeSheets carrier polling loop is already running.")
        else:
            logger.info("BoozeSheets carrier polling loop auto-start is disabled in settings.")

    @app_commands.command(name="start_task", description="Starts a background task.")
    @check_roles([*any_moderation_role, ROLE_SOMM, *any_council_role])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    @describe(task_name="The name of the task to start.")
    @app_commands.choices(task_name=task_choices)
    async def start_task(self, interaction: discord.Interaction, task_name: str):
        logger.info(f"start_task command called by {interaction.user} for task {task_name}")

        task = self.get_task(task_name)
        if task:
            task_started = False
            task_setting_set = False

            logger.debug(f"Found task {task_name}")

            logger.debug("Checking if task is already running")
            if not task.is_running():
                logger.debug(f"Starting task {task_name}")
                await task.start()
                logger.info(f"Task {task_name} started successfully")
                task_started = True

            logger.debug("Checking if task auto-start setting is set to True")
            if not settings.tasks_auto_start.get(task_name, False):
                logger.debug(f"Setting auto-start for task {task_name} to True")
                settings.tasks_auto_start[task_name] = True
                settings.write()
                logger.info(f"Auto-start for task {task_name} set to True")
                task_setting_set = True

            text = f"Started task: {task_name}." if task_started else f"Task {task_name} is already running."
            text += (
                f"\nAuto-start for task {task_name} is now set to True."
                if task_setting_set
                else f"\nAuto-start for task {task_name} was already set to True."
            )
            await interaction.response.send_message(text)
        else:
            logger.error(f"Task {task_name} not found.")
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)

    @app_commands.command(name="stop_task", description="Stops a background task.")
    @check_roles([*any_moderation_role, ROLE_SOMM, *any_council_role])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    @describe(task_name="The name of the task to stop.")
    @app_commands.choices(task_name=task_choices)
    async def stop_task(self, interaction: discord.Interaction, task_name: str):
        logger.info(f"stop_task command called by {interaction.user} for task {task_name}")

        task = self.get_task(task_name)
        if task:
            task_stopped = False
            task_setting_unset = False
            logger.debug(f"Found task {task_name}")

            logger.debug("Checking if task is running")
            if task.is_running():
                logger.debug(f"Stopping task {task_name}")
                await task.stop()
                logger.info(f"Task {task_name} stopped successfully")
                task_stopped = True

            logger.debug("Checking if task auto-start setting is set to False")
            if settings.tasks_auto_start.get(task_name, True):
                logger.debug(f"Setting auto-start for task {task_name} to False")
                settings.tasks_auto_start[task_name] = False
                settings.write()
                logger.info(f"Auto-start for task {task_name} set to False")
                task_setting_unset = True

            text = f"Stopped task: {task_name}." if task_stopped else f"Task {task_name} is not running."
            text += (
                f"\nAuto-start for task {task_name} is now set to False."
                if task_setting_unset
                else f"\nAuto-start for task {task_name} was already set to False."
            )
            await interaction.response.send_message(text)
        else:
            logger.error(f"Task {task_name} not found.")
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)

    @app_commands.command(name="task_status", description="Gets the status of a background task.")
    @check_roles([*any_moderation_role, ROLE_SOMM, *any_council_role])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    @describe(task_name="The name of the task to check.")
    @app_commands.choices(task_name=task_choices)
    async def task_status(self, interaction: discord.Interaction, task_name: str):
        logger.info(f"task_status command called by {interaction.user} for task {task_name}")

        task = self.get_task(task_name)

        if not task:
            logger.error(f"Task {task_name} not found.")
            await interaction.response.send_message(f"Task {task_name} not found.", ephemeral=True)
            return

        logger.debug(f"Found task {task_name}, getting status")

        status_message = task.status()
        logger.info(f"Status for task {task_name}: {status_message}")
        await interaction.response.send_message(status_message)

    def get_task(self, task_name: str) -> Task | None:
        def discord_task_loop_status(task_loop: "Loop[Any]") -> str:
            last_run_time_str = "never"
            next_run_time_str = "N/A"

            if hasattr(task_loop, "last_run_time") and task_loop.last_run_time:
                last_run_time_unix = int(task_loop.last_run_time.timestamp())
                last_run_time_str = f"<t:{last_run_time_unix}:f> (<t:{last_run_time_unix}:R>)"

            if hasattr(task_loop, "next_iteration") and task_loop.next_iteration:
                next_run_time_unix = int(task_loop.next_iteration.timestamp())
                next_run_time_str = f"<t:{next_run_time_unix}:f> (<t:{next_run_time_unix}:R>)"

            return f"Task {task_name} is currently {'running' if task_loop.is_running() else 'stopped'}, last run was {last_run_time_str}, next run is {next_run_time_str}."

        def websocket_status() -> str:
            ws_status, last_message_time = booze_sheets_api.get_websocket_status()
            last_message_unix = int(last_message_time.timestamp()) if last_message_time else None
            last_message_str = (
                f"<t:{last_message_unix}:f> (<t:{last_message_unix}:R>)" if last_message_unix else "never"
            )
            return f"BoozeSheets API Websocket is currently {'connected' if ws_status else 'disconnected'}, last message received {last_message_str}."

        def carrier_poll_status() -> str:
            poll_status, last_refresh_time, cache_size = booze_sheets_api.get_carrier_poll_status()
            last_refresh_unix = int(last_refresh_time.timestamp()) if last_refresh_time else None
            last_refresh_str = (
                f"<t:{last_refresh_unix}:f> (<t:{last_refresh_unix}:R>)" if last_refresh_unix else "never"
            )
            return f"BoozeSheets Carrier Polling is currently {'active' if poll_status else 'inactive'}, last cache refresh was {last_refresh_str}, cached carriers: {cache_size}."

        match task_name:
            case "periodic_stat_update":
                loop = bot.get_cog("Statistics").periodic_stat_update
                return Task(loop.start, loop.cancel, loop.is_running, lambda: discord_task_loop_status(loop))
            case "check_departure_messages_loop":
                loop = bot.get_cog("Departures").check_departure_messages_loop
                return Task(loop.start, loop.cancel, loop.is_running, lambda: discord_task_loop_status(loop))
            case "public_holiday_loop":
                loop = bot.get_cog("PublicHoliday").public_holiday_loop
                return Task(loop.start, loop.cancel, loop.is_running, lambda: discord_task_loop_status(loop))
            case "last_unload_time_loop":
                loop = bot.get_cog("Unloading").last_unload_time_loop
                return Task(loop.start, loop.cancel, loop.is_running, lambda: discord_task_loop_status(loop))
            case "periodic_signup_poll":
                loop = bot.get_cog("MakeWineCarrier").booze_tracker_signup_check
                return Task(loop.start, loop.cancel, loop.is_running, lambda: discord_task_loop_status(loop))
            case "boozesheets_websocket":
                return Task(
                    booze_sheets_api.start_websocket_listener,
                    booze_sheets_api.stop_websocket_listener,
                    lambda: booze_sheets_api.get_websocket_status()[0],
                    websocket_status,
                )
            case "boozesheets_carrier_poll":
                return Task(
                    booze_sheets_api.start_carrier_polling,
                    booze_sheets_api.stop_carrier_polling,
                    lambda: booze_sheets_api.get_carrier_poll_status()[0],
                    carrier_poll_status,
                )
            case _:
                logger.error(f"Task {task_name} not found.")
                return None
