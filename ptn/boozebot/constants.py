# Production variables
import ast
import os

from discord import Intents
from discord.ext import commands
from discord_slash import SlashCommand
from dotenv import load_dotenv, find_dotenv

# Get the discord token from the local .env file. Deliberately not hosted in the repo or Discord takes the bot down
# because the keys are exposed. DO NOT HOST IN THE REPO. Seriously do not do it ...
load_dotenv(find_dotenv())

PROD_DISCORD_GUILD = 800080948716503040  # PTN Discord server
PROD_ASSASSIN_ID = 806498760586035200
PROD_DB_PATH = os.path.join(os.path.expanduser('~'), 'boozedatabase', 'booze_carriers.db')
PROD_DB_DUMPS_PATH = os.path.join(os.path.expanduser('~'), 'boozedatabase', 'dumps', 'booze_carriers.sql')
PROD_BOOZE_UNLOAD_ID = 838699587249242162
PROD_ADMIN_ID = 800125148971663392
PROD_SOMMELIER_ID = 838520893181263872
PROD_WINE_CARRIER_ID = 839149899596955708
PROD_BOOZE_BOT_CHANNEL = 841413917468917781  # This is #booze-bot
PROD_SOMMELIER_NOTIFICATION_CHANNEL = 838520662934683648    # booze cruise admin
PROD_MOD_ID = 813814494563401780
PROD_HOLIDAY_ANNOUNCE_CHANNEL_ID = 851110121870196777   # Dread-pirate-steve
PROD_BOOZE_CRUISE_CHAT_CHANNEL = 819295547289501736     # Booze-Cruise
PROD_FC_COMPLETE_ID = 878216234653605968


# Testing variables
TEST_DISCORD_GUILD = 818174236480897055  # test Discord server
TEST_ASSASSIN_ID = 848957573792137247
TEST_DB_PATH = os.path.join(os.path.expanduser('~'), 'boozedatabase', 'booze_carriers.db')
TEST_DB_DUMPS_PATH = os.path.join(os.path.expanduser('~'), 'boozedatabase', 'dumps', 'booze_carriers.sql')
TEST_BOOZE_UNLOAD_ID = 849570829230014464
TEST_ADMIN_ID = 818174400997228545
TEST_SOMMELIER_ID = 849907019502059530
TEST_WINE_CARRIER_ID = 849909113776898071
TEST_BOOZE_BOT_CHANNEL = 842152343441375283
TEST_MOD_ID = 818174400997228545
TEST_HOLIDAY_ANNOUNCE_CHANNEL_ID = 818174236480897058
TEST_SOMMELIER_NOTIFICATION_CHANNEL = 851095042130051072    # bot command channel
TEST_BOOZE_CRUISE_CHAT_CHANNEL = 818174236480897058         # General
TEST_FC_COMPLETE_ID = 884673510067286076

BOOZE_PROFIT_PER_TONNE_WINE = 278000
RACKHAMS_PEAK_POP = 150000

_production = ast.literal_eval(os.environ.get('PTN_BOOZE_BOT', 'False'))

# Check the folder exists
if not os.path.exists(os.path.dirname(PROD_DB_PATH)):
    print(f'Folder {os.path.dirname(PROD_DB_PATH)} does not exist, making it now.')
    os.mkdir(os.path.dirname(PROD_DB_PATH))

# check the dumps folder exists
if not os.path.exists(os.path.dirname(PROD_DB_DUMPS_PATH)):
    print(f'Folder {os.path.dirname(PROD_DB_DUMPS_PATH)} does not exist, making it now.')
    os.mkdir(os.path.dirname(PROD_DB_DUMPS_PATH))


TOKEN = os.getenv('DISCORD_TOKEN_PROD') if _production else os.getenv('DISCORD_TOKEN_TESTING')

# The bot object:
bot = commands.Bot(command_prefix='b/', intents=Intents.all())
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


def server_wine_carrier_role_id():
    """
    Wrapper that returns the wine carrier owner role ID

    :returns: Wine co role id
    :rtype: int
    """
    return PROD_WINE_CARRIER_ID if _production else TEST_WINE_CARRIER_ID


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


def get_db_dumps_path():
    """
    Returns the path for the database dumps file

    :returns: A string representation of the path
    :rtype: str
    """
    return PROD_DB_DUMPS_PATH if _production else TEST_DB_DUMPS_PATH


def get_bot_control_channel():
    """
    Returns the channel ID for the bot control channel.

    :return: The channel ID
    :rtype: int
    """
    return PROD_BOOZE_BOT_CHANNEL if _production else TEST_BOOZE_BOT_CHANNEL


def server_mod_role_id():
    """
    Returns the moderator role ID for the server

    :return: The role ID
    :rtype: int
    """
    return PROD_MOD_ID if _production else TEST_MOD_ID


def rackhams_holiday_channel():
    """
    Returns the channel ID for notficiation of the holiday.

    :return: The channel ID
    :rtype: int
    """
    return PROD_HOLIDAY_ANNOUNCE_CHANNEL_ID if _production else TEST_HOLIDAY_ANNOUNCE_CHANNEL_ID


def get_sommelier_notification_channel():
    """
    Returns the channel ID for the sommelier notifications.

    :return: The channel ID
    :rtype: int
    """
    return PROD_SOMMELIER_NOTIFICATION_CHANNEL if _production else TEST_SOMMELIER_NOTIFICATION_CHANNEL


def get_primary_booze_discussions_channel():
    """
    Returns the booze cruise main chat channel.

    :returns: The channel ID
    :rtype: int
    """
    return PROD_BOOZE_CRUISE_CHAT_CHANNEL if _production else TEST_BOOZE_CRUISE_CHAT_CHANNEL


def get_fc_complete_id():
    """
    Returns the ID of the fc_complete emoji

    :return: The emoji ID
    :rtype: int
    """
    return PROD_FC_COMPLETE_ID if _production else TEST_FC_COMPLETE_ID
