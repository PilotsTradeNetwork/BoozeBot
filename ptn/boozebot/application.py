"""
The Python script that starts the bot.

"""

import asyncio
from loguru import logger

from discord import ConnectionClosed, DiscordException, GatewayNotFound, HTTPException, LoginFailure, Object
from discord.ext.prometheus import PrometheusCog
from ptn.boozebot.botcommands.AutoResponses import AutoResponses
from ptn.boozebot.botcommands.BackgroundTaskCommands import BackgroundTaskCommands
from ptn.boozebot.botcommands.Cleaner import Cleaner
from ptn.boozebot.botcommands.Corked import Corked
from ptn.boozebot.botcommands.DatabaseInteraction import DatabaseInteraction
from ptn.boozebot.botcommands.Departures import Departures
from ptn.boozebot.botcommands.DiscordBotCommands import DiscordBotCommands
from ptn.boozebot.botcommands.MakeWineCarrier import MakeWineCarrier
from ptn.boozebot.botcommands.MimicSteve import MimicSteve
from ptn.boozebot.botcommands.PublicHoliday import PublicHoliday
from ptn.boozebot.botcommands.Unloading import Unloading
from ptn.boozebot.constants import TOKEN, _production, bot, bot_guild_id
from ptn.boozebot.database.database import build_database_on_startup
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, on_text_command_error
from ptn.logger.logger import Logger

logger.info(f"Booze bot is connecting against production: {_production}.")

def run():
    logger.info("Starting Booze Bot...")
    asyncio.run(boozebot())

async def boozebot():
    logger.info("Setting up bot cogs and event listeners.")
    build_database_on_startup()
    async with bot:
        await bot.add_cog(Logger())
        logger.debug("Loaded Logger cog.")
        await bot.add_cog(DiscordBotCommands(bot))
        logger.debug("Loaded DiscordBotCommands cog.")
        await bot.add_cog(Unloading(bot))
        logger.debug("Loaded Unloading cog.")
        await bot.add_cog(DatabaseInteraction(bot))
        logger.debug("Loaded DatabaseInteraction cog.")
        await bot.add_cog(PublicHoliday(bot))
        logger.debug("Loaded PublicHoliday cog.")
        await bot.add_cog(MimicSteve(bot))
        logger.debug("Loaded MimicSteve cog.")
        await bot.add_cog(Cleaner(bot))
        logger.debug("Loaded Cleaner cog.")
        await bot.add_cog(MakeWineCarrier(bot))
        logger.debug("Loaded MakeWineCarrier cog.")
        await bot.add_cog(Departures(bot))
        logger.debug("Loaded Departures cog.")
        await bot.add_cog(BackgroundTaskCommands(bot))
        logger.debug("Loaded BackgroundTaskCommands cog.")
        await bot.add_cog(AutoResponses(bot))
        logger.debug("Loaded AutoResponses cog.")
        await bot.add_cog(Corked(bot))
        logger.debug("Loaded Corked cog.")
        await bot.add_cog(PrometheusCog(bot))
        logger.debug("Loaded PrometheusCog cog.")

        logger.info("Bot cogs and event listeners setup complete.")
        
        logger.info("Setting up error handlers.")
        # Start error handlers
        bot.tree.on_error = on_app_command_error
        bot.add_listener(on_text_command_error, "on_command_error")
        logger.info("Error handlers setup complete.")

        try:
            logger.info("Logging in the bot...")
            await bot.login(TOKEN)
            logger.info("Bot logged in successfully.")
        except (LoginFailure, HTTPException) as e:
            logger.exception(f"Error in bot login: {e}")

        try:
            logger.info("Syncing command tree...")
            bot.tree.copy_global_to(guild=Object(bot_guild_id()))
            await bot.tree.sync(guild=Object(bot_guild_id()))
            logger.info("Command tree synced successfully.")
        except DiscordException as e:
            logger.exception(f"Error in syncing command tree: {e}")

        try:
            logger.info("Connecting the bot...")
            await bot.connect()
        except (GatewayNotFound, ConnectionClosed) as e:
            logger.exception(f"Error in bot connection: {e}")


if __name__ == "__main__":
    """
    If running via `python ptn/boozebot/application.py
    """
    run()
