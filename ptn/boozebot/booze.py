import ast
import os
from dotenv import load_dotenv

from ptn.boozebot.commands.DatabaseInteraction import DatabaseInteraction
from ptn.boozebot.commands.DiscordBotCommands import DiscordBotCommands
from ptn.boozebot.commands.Unloading import Unloading
from ptn.boozebot.constants import bot
from ptn.boozebot.database.database import build_database_on_startup, dump_database

_production = ast.literal_eval(os.environ.get('PTN_BOOZE_BOT', 'False'))

# Get the discord token from the local .env file. Deliberately not hosted in the repo or Discord takes the bot down
# because the keys are exposed. DO NOT HOST IN THE REPO. Seriously do not do it ...
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN_PROD') if _production else os.getenv('DISCORD_TOKEN_TESTING')

print(f'Booze bot is connecting against production: {_production}.')

if __name__ == '__main__':
    build_database_on_startup()
    bot.add_cog(DiscordBotCommands(bot))
    bot.add_cog(Unloading())
    bot.add_cog(DatabaseInteraction())
    bot.run(TOKEN)
