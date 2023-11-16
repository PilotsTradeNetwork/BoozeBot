import asyncio

from ptn.boozebot.commands.DatabaseInteraction import DatabaseInteraction
from ptn.boozebot.commands.DiscordBotCommands import DiscordBotCommands
from ptn.boozebot.commands.Helper import Helper
from ptn.boozebot.commands.PublicHoliday import PublicHoliday
from ptn.boozebot.commands.Unloading import Unloading
from ptn.boozebot.commands.Cleaner import Cleaner
from ptn.boozebot.constants import TOKEN, _production
from ptn.boozebot.bot import bot
from ptn.boozebot.database.database import build_database_on_startup

from ptn.boozebot.commands.MimicSteve import MimicSteve

print(f'Booze bot is connecting against production: {_production}.')

async def boozebot():
    """
    Logic to build the bot and run the script.

    :returns: None
    """
    async with bot:
        build_database_on_startup()
        await bot.add_cog(DiscordBotCommands(bot))
        await bot.add_cog(Unloading(bot))
        await bot.add_cog(DatabaseInteraction())
        await bot.add_cog(Helper(bot))
        await bot.add_cog(PublicHoliday(bot))
        await bot.add_cog(MimicSteve(bot))
        await bot.add_cog(Cleaner(bot))
        # Notice the change here to use bot.start() instead of bot.run()
        await bot.start(TOKEN)

def run():
    # Creating a new event loop for the bot to run in
    loop = asyncio.get_event_loop()
    loop.run_until_complete(boozebot())
    loop.close()

if __name__ == '__main__':
    run()
