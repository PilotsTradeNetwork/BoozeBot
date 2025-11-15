import logging
import os
from enum import Enum
from sys import stdout

from discord import Interaction, app_commands
from discord.ext import commands
from loguru import logger
from ptn.logger.InterceptHandler import InterceptHandler


def setup_logging() -> None:
    logger.info("Setting up logging configuration.")

    log_handler = InterceptHandler()
    logging.root.handlers = [log_handler]
    logging.root.setLevel(logging.DEBUG)

    loglevel_input = os.getenv("PTN_BOOZEBOT_LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(stdout, level=loglevel_input)

    logger.info(f"Logging level set to {loglevel_input}.")


class LogLevels(Enum):
    Critical = "CRITICAL"
    Error = "ERROR"
    Warning = "WARNING"
    Info = "INFO"
    Debug = "DEBUG"


class Logger(commands.Cog):
    @app_commands.command(name="set_logging_level", description="Set logging level for the bot")
    @app_commands.checks.has_any_role("Council", "Council Advisor")
    @app_commands.describe(log_level="Logging level to set")
    async def set_logging_level(self, interaction: Interaction, log_level: LogLevels):
        logger.info(f"Setting logging level to {log_level.name} as requested by {interaction.user.name}")

        logger.remove()
        logger.add(stdout, level=log_level.value)

        logger.info(f"Logging level set to {log_level.name}")
        await interaction.response.send_message(f"Logging level set to {log_level.name}", ephemeral=True)

# Setup logging when the module is imported
setup_logging()
