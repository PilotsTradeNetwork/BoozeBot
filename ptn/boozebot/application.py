"""
The Python script that starts the bot.

"""

# import libraries
import asyncio
import logging
import os

from discord import LoginFailure, GatewayNotFound, ConnectionClosed, HTTPException
from discord.ext.prometheus import PrometheusCog

# import build functions
from ptn.boozebot.database.database import build_database_on_startup

# import bot Cogs
from ptn.boozebot.botcommands.DiscordBotCommands import DiscordBotCommands
from ptn.boozebot.botcommands.Unloading import Unloading
from ptn.boozebot.botcommands.DatabaseInteraction import DatabaseInteraction
from ptn.boozebot.botcommands.PublicHoliday import PublicHoliday
from ptn.boozebot.botcommands.MimicSteve import MimicSteve
from ptn.boozebot.botcommands.Cleaner import Cleaner
from ptn.boozebot.botcommands.MakeWineCarrier import MakeWineCarrier
from ptn.boozebot.botcommands.Departures import Departures
from ptn.boozebot.botcommands.BackgroundTaskCommands import BackgroundTaskCommands

# import bot object, token, production status
from ptn.boozebot.constants import bot, TOKEN, _production, log_handler, LOG_LEVEL
from discord.utils import setup_logging


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
        await bot.add_cog(PrometheusCog(bot))

        try:
            await bot.login(TOKEN)
        except (LoginFailure, HTTPException) as e:
            logging.error(f"Error in bot login: {e}")

        try:
            await bot.connect()
        except (GatewayNotFound, ConnectionClosed) as e:
            logging.error(f"Error in bot connection: {e}")

if __name__ == "__main__":
    """
    If running via `python ptn/boozebot/application.py
    """
    run()
