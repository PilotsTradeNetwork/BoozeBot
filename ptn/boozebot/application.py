"""
The Python script that starts the bot.

"""

import asyncio
import logging

from discord import ConnectionClosed, DiscordException, GatewayNotFound, HTTPException, LoginFailure
from discord.ext.prometheus import PrometheusCog
from discord.utils import setup_logging
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
from ptn.boozebot.constants import LOG_LEVEL, TOKEN, _production, bot, log_handler
from ptn.boozebot.database.database import build_database_on_startup
from ptn.boozebot.modules.helpers import sync_command_tree
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, on_text_command_error

print(f"Booze bot is connecting against production: {_production}.")


def run():
    asyncio.run(boozebot())


async def boozebot():
    setup_logging(handler=log_handler, level=LOG_LEVEL)
    build_database_on_startup()
    async with bot:
        await bot.add_cog(DiscordBotCommands(bot))
        await bot.add_cog(Unloading(bot))
        await bot.add_cog(DatabaseInteraction(bot))
        await bot.add_cog(PublicHoliday(bot))
        await bot.add_cog(MimicSteve(bot))
        await bot.add_cog(Cleaner(bot))
        await bot.add_cog(MakeWineCarrier(bot))
        await bot.add_cog(Departures(bot))
        await bot.add_cog(BackgroundTaskCommands(bot))
        await bot.add_cog(AutoResponses(bot))
        await bot.add_cog(Corked(bot))
        await bot.add_cog(PrometheusCog(bot))

        # Start error handlers
        bot.tree.on_error = on_app_command_error
        bot.add_listener(on_text_command_error, "on_command_error")

        try:
            await bot.login(TOKEN)
        except (LoginFailure, HTTPException) as e:
            logging.error(f"Error in bot login: {e}")

        try:
            await sync_command_tree()
        except DiscordException as e:
            logging.error(f"Error in syncing command tree: {e}")

        try:
            await bot.connect()
        except (GatewayNotFound, ConnectionClosed) as e:
            logging.error(f"Error in bot connection: {e}")


if __name__ == "__main__":
    """
    If running via `python ptn/boozebot/application.py
    """
    run()
