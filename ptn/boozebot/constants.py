# Production variables
import ast
import os

from discord import Intents
from discord.ext import commands
from discord_slash import SlashCommand

PROD_DISCORD_GUILD = 800080948716503040  # PTN Discord server
PROD_ASSASSIN_ID = 806498760586035200
PROD_DB_PATH = os.path.join(os.path.expanduser('~'), 'booze_carriers.db')
PROD_BOOZE_UNLOAD_ID = 838699587249242162
PROD_ADMIN_ID = 800125148971663392
PROD_SOMMELIER_ID = 838520893181263872
PROD_CO_ID = 800091463160430654
PROD_AUX_CO_ID = 839149899596955708

# Testing variables
TEST_DISCORD_GUILD = 818174236480897055  # test Discord server
TEST_ASSASSIN_ID = 848957573792137247
TEST_DB_PATH = 'booze_carriers.db'
TEST_BOOZE_UNLOAD_ID = 849570829230014464
TEST_ADMIN_ID = 818174400997228545
TEST_SOMMELIER_ID = 849907019502059530
TEST_CO_ID = 822999970012463154
TEST_AUX_CO_DI = 849909113776898071

_production = ast.literal_eval(os.environ.get('PTN_BOOZE_BOT', 'False'))

# The bot object:
bot = commands.Bot(command_prefix='b.', intents=Intents.all())
slash = SlashCommand(bot, sync_commands=True)


def get_db_path():
    """
    Returns the database path. For testing we keep the file locally for ease

    :returns: The path to the db file
    :rtype: str
    """
    return PROD_DB_PATH if _production else TEST_DB_PATH


def server_admin_role_id():
    """
    Wrapper that returns the admin role ID

    :returns: Admin role id
    :rtype: int
    """
    return PROD_ADMIN_ID if _production else TEST_ADMIN_ID


def server_sommelier_role_id():
    """
    Wrapper that returns the sommelier role ID

    :returns: Sommelier role id
    :rtype: int
    """
    return PROD_SOMMELIER_ID if _production else TEST_SOMMELIER_ID


def server_carrier_owner_role_id():
    """
    Wrapper that returns the carrier owner role ID

    :returns: CO role id
    :rtype: int
    """
    return PROD_CO_ID if _production else TEST_CO_ID


def server_aux_carrier_role_id():
    """
    Wrapper that returns the uxilliary carrier owner role ID

    :returns: Aux co role id
    :rtype: int
    """
    return PROD_AUX_CO_ID if _production else TEST_AUX_CO_ID


def bot_guild_id():
    """
    Returns the bots guild ID

    :returns: The guild ID value
    :rtype: int
    """
    return PROD_DISCORD_GUILD if _production else TEST_DISCORD_GUILD


def get_custom_assassin_id():
    """
    Returns the custom emoji ID for assassin

    :returns: The object ID field
    :rtype: str
    """
    return PROD_ASSASSIN_ID if _production else TEST_ASSASSIN_ID


def get_discord_booze_unload_channel():
    """
    Returns the channel ID for booze cruise unloads in discord.

    :returns: The ID value
    :rtype: int
    """
    return PROD_BOOZE_UNLOAD_ID if _production else TEST_BOOZE_UNLOAD_ID