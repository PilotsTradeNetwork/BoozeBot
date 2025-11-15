import logging
import os
from enum import Enum
from sys import stdout

from discord import Interaction, app_commands
from discord.ext import commands
from loguru import logger
from ptn.logger.InterceptHandler import InterceptHandler

LOG_SINKS: dict[str, int] = {}

logger = logger.bind(logger_name="ptnlogger")

def create_default_logger_sink(level: str) -> None:
    if "_default" in LOG_SINKS:
        logger.remove(LOG_SINKS["_default"])

    def filter_function(record: dict) -> bool:
        record_logger_name = record["extra"].get("logger_name", []).split(".")
        for logger_name in LOG_SINKS:
            if logger_name == "_default":
                continue
            logger_name_list = logger_name.split(".")
            if len(record_logger_name) >= len(logger_name_list):
                if record_logger_name[:len(logger_name_list)] == logger_name_list:
                    return False
        return True

    sink_id = logger.add(
        stdout,
        level=level,
        filter=filter_function,
    )
    LOG_SINKS["_default"] = sink_id

def create_logger_sink(logger_name: str, level: str) -> None:
    
    if logger_name in LOG_SINKS:
        logger.remove(LOG_SINKS[logger_name])
        
    def filter_function(record: dict) -> bool:
        record_logger_name = record["extra"].get("logger_name", []).split(".")
        logger_name_list = logger_name.split(".")
        if len(record_logger_name) >= len(logger_name_list):
            return record_logger_name[:len(logger_name_list)] == logger_name_list
        return False

    sink_id = logger.add(
        stdout,
        level=level,
        filter=filter_function,
    )
    LOG_SINKS[logger_name] = sink_id
    

def setup_logging() -> None:
    logger.info("Setting up logging configuration.")

    # Send all logging through loguru
    log_handler = InterceptHandler()
    logging.root.handlers = [log_handler]
    logging.root.setLevel(logging.DEBUG)

    # Set default logging level from environment variable or INFO
    loglevel_input = os.getenv("PTN_BOOZEBOT_LOG_LEVEL", "INFO")
    logger.remove()
    create_default_logger_sink(loglevel_input)

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
    @app_commands.describe(log_level="Logging level to set", logger_name="Which logger to set the level for (default: all, resets any current overrides)")
    async def set_logging_level(self, interaction: Interaction, log_level: LogLevels, logger_name: str | None = None) -> None:
        logger.info(f"Setting logging level to {log_level.name} as requested by {interaction.user.name}")

        if logger_name:
            if logger_name == "_default":
                await interaction.response.send_message("Cannot set logging level for reserved logger name '_default'.")
                return
            
            create_logger_sink(logger_name, log_level.value)
            logger.info(f"Logging level for {logger_name} set to {log_level.name}")
            await interaction.response.send_message(f"Logging level for {logger_name} set to {log_level.name}")
        
        else:
            create_default_logger_sink(log_level.value)
            LOG_SINKS.clear()
            logger.info(f"Logging level set to {log_level.name}")
            await interaction.response.send_message(f"Logging level set to {log_level.name}")


# Setup logging when the module is imported
setup_logging()
