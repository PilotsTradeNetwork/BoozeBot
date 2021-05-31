import ast
import os
from discord import Intents
from discord.ext import commands
from discord_slash import SlashCommand
from dotenv import load_dotenv

from ptn.boozebot.commands.DiscordBotCommands import DiscordBotCommands

_production = ast.literal_eval(os.environ.get('PTN_BOOZE_BOT', 'False'))

# Get the discord token from the local .env file. Deliberately not hosted in the repo or Discord takes the bot down
# because the keys are exposed. DO NOT HOST IN THE REPO. Seriously do not do it ...
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN_PROD') if _production else os.getenv('DISCORD_TOKEN_TESTING')
bot = commands.Bot(command_prefix='b.', intents=Intents.all())
slash = SlashCommand(bot, sync_commands=True)

print(f'Booze bot is connecting against production: {_production}.')

if __name__ == '__main__':
    bot.add_cog(DiscordBotCommands(bot))
    bot.run(TOKEN)
