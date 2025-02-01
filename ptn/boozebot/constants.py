"""
Constants used throughout BoozeBot.

"""

# libraries
import ast
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Define whether the bot is in testing or live mode. Default is testing mode.
_production = ast.literal_eval(os.environ.get('PTN_BOOZE_BOT', 'False'))

# define paths
# TODO - check these all work in both live and testing, particularly default / fonts
TESTING_DATA_PATH = os.path.join(os.getcwd(), 'ptn', 'boozebot', 'data') # defines the path for use in a local testing environment
DATA_DIR = os.getenv('PTN_BOOZEBOT_DATA_DIR', TESTING_DATA_PATH)

# database paths
DB_PATH = os.path.join(DATA_DIR, 'database')
DB_DUMPS_PATH = os.path.join(DATA_DIR, 'database')
CARRIERS_DB_PATH = os.path.join(DATA_DIR, 'database', 'booze_carriers.db')
CARRIERS_DB_DUMPS_PATH = os.path.join(DATA_DIR, 'sql', 'booze_carriers.sql')
SETTINGS_PATH = os.path.join(DATA_DIR, 'settings')
WELCOME_MESSAGE_FILE = "welcome_message.txt"
WELCOME_MESSAGE_FILE_PATH = os.path.join(SETTINGS_PATH, WELCOME_MESSAGE_FILE)
GOOGLE_OAUTH_CREDENTIALS_PATH = os.path.join(DATA_DIR, '.ptnboozebot.json')

# Get the discord token from the local .env file. Deliberately not hosted in the repo or Discord takes the bot down
# because the keys are exposed. DO NOT HOST IN THE PUBLIC REPO.
# load_dotenv(os.path.join(DATA_DIR, '.env'))
load_dotenv(os.path.join(DATA_DIR, '.env'))

# define bot token
TOKEN = os.getenv('DISCORD_TOKEN_PROD') if _production else os.getenv('DISCORD_TOKEN_TESTING')

# define bot object
bot = commands.Bot(command_prefix='b/', intents=discord.Intents.all())

# Production variables
PROD_DISCORD_GUILD = 800080948716503040  # PTN Discord server
PROD_ASSASSIN_ID = 806498760586035200
PROD_BOOZE_UNLOAD_ID = 932918003639648306   # Was 838699587249242162 booze-cruise-announcements
PROD_ADMIN_IDS = (800091021852803072, 1226645094439063612) # Council, Council Advisor
PROD_SOMMELIER_ID = 838520893181263872
PROD_CONNOISSEUR_ID = 1105144902645448915
PROD_WINE_CARRIER_ID = 839149899596955708
PROD_BOOZE_BOT_CHANNEL = 841413917468917781  # This is #booze-bot
PROD_STEVE_SAYS_CHANNEL = 937024914572070922  # This is #steve-says
PROD_WINE_CARRIER_CHANNEL = 839149134938112030 # wine-carrier-chat
PROD_WINE_CARRIER_COMMAND_CHANNEL = 839503109679349780 #rackhams-space-traffic-control
PROD_MOD_ID = 813814494563401780
PROD_HOLIDAY_ANNOUNCE_CHANNEL_ID = 851110121870196777   # Dread-pirate-steve
PROD_BOOZE_CRUISE_CHAT_CHANNEL = 819295547289501736     # Booze-Cruise
PROD_FC_COMPLETE_ID = 878216234653605968
PROD_WINE_TANKER_ID = 978321720630980658
PROD_HITCHHIKER_ID = 998344068524417175
PROD_TANKER_UNLOAD_CHANNEL_ID = 987972565735727124
PROD_BOT_SPAM_CHANNEL = 801258393205604372 # Certain bot logging messages go here
PROD_BC_PUBLIC_CHANNEL_IDS = [838699587249242162, 849460909273120856, 932918003639648306, 819295547289501736, 837764138692378634, 849249916676603944, 1078840174227763301, 1079384804098854972]
# booze-cruise-announcements, booze-cruise-departures, wine-cellar-unloading, booze-cruise-chat, wine-cellar-deliveries, wine-cellar-loading, booze-snooze-and-garage, Rackham’s Peak Tavern
PROD_DEPARTURE_ANNOUNCEMENT_CHANNEL = 849460909273120856
PROD_THOON_EMOJI_ID = 1058010828458176563
PROD_FEEDBACK_CHANNEL_ID = 936218839362969621
PROD_PILOT_ID = 800396412217982999
PROD_WINE_CARRIER_GUIDE_CHANNEL_ID = 943919705763233822
PROD_PTN_BOOZE_CRUISE_ROLE_ID = 838516571571355689

# Testing variables
TEST_DISCORD_GUILD = 818174236480897055  # test Discord server
TEST_ASSASSIN_ID = 848957573792137247
TEST_BOOZE_UNLOAD_ID = 849570829230014464
TEST_ADMIN_IDS = (877586918228000819, 1227350727131660359) # Council, Council Advisor
TEST_SOMMELIER_ID = 849907019502059530
TEST_CONNOISSEUR_ID = 1105144147582656663
TEST_WINE_CARRIER_ID = 849909113776898071
TEST_BOOZE_BOT_CHANNEL = 937026057188552745 # Actually Steve says because we don't have a bot channel on the test server
TEST_STEVE_SAYS_CHANNEL = 937026057188552745  # This is #steve-says
TEST_WINE_CARRIER_CHANNEL = 1108010143070834788 # wine-carrier-chat
TEST_WINE_CARRIER_COMMAND_CHANNEL = 1241483631785152604 #rackhams-space-traffic-control
TEST_MOD_ID = 818174400997228545
TEST_HOLIDAY_ANNOUNCE_CHANNEL_ID = 818174236480897058
TEST_BOOZE_CRUISE_CHAT_CHANNEL = 1107757384069288056
TEST_FC_COMPLETE_ID = 884673510067286076
TEST_WINE_TANKER_ID = 990601307771506708
TEST_HITCHHIKER_ID = 1108112740800798750
TEST_TANKER_UNLOAD_CHANNEL_ID = 995714783678570566
TEST_BOT_SPAM_CHANNEL = 842525081858867211 # Bot logging messages on the test server
TEST_BC_PUBLIC_CHANNEL_IDS = [1107757218318782586, 1107757285817712721, 1107757340381425768, 1107757384069288056, 1107757418517110955, 1107757456517505055, 1107757490940153956, 1107757548779601940]
# booze-cruise-announcements, booze-cruise-departures, wine-cellar-unloading, booze-cruise-chat, wine-cellar-deliveries, wine-cellar-loading, booze-snooze-and-garage, Rackham’s Peak Tavern
TEST_DEPARTURE_ANNOUNCEMENT_CHANNEL = 1107757285817712721
TEST_THOON_EMOJI_ID = 1301319362489356289
TEST_FEEDBACK_CHANNEL_ID = 1314640487587643532
TEST_PILOT_ID = 818174614810787840
TEST_WINE_CARRIER_GUIDE_CHANNEL_ID = 1333822679400059003
TEST_PTN_BOOZE_CRUISE_ROLE_ID = 1333819581596303461

BOOZE_PROFIT_PER_TONNE_WINE = 256000
RACKHAMS_PEAK_POP = 150000

EMBED_COLOUR_ERROR = 0x800000

ping_response_messages = [
    'Yarrr, <@{message_author_id}>, you summoned me?',
    'https://tenor.com/view/hello-there-baby-yoda-mandolorian-hello-gif-20136589',
    'https://tenor.com/view/hello-sexy-hi-hello-mr-bean-gif-13830351',
    'https://tenor.com/view/hello-whale-there-hi-gif-5551502',
    'https://tenor.com/view/funny-animals-gif-13669907'
]

holiday_start_gif = 'https://tenor.com/view/jim-carrey-ace-ventura-driving-its-show-time-cool-gif-12905775'
holiday_ended_gif = 'https://tenor.com/view/watch-game-of-thrones-jon-snow-gif-5445395'

holiday_query_not_started_gifs = [
    'https://tenor.com/view/mr-bean-waiting-still-waiting-gif-13052487',
    'https://tenor.com/view/waiting-gif-10918805',
    'https://tenor.com/view/not-quite-yet-enough-well-exactly-raphael-chestang-gif-12711794',
    'https://tenor.com/view/no-bugs-bunny-nope-gif-14359850',
    'https://tenor.com/view/waiting-gif-9848405',
    'https://tenor.com/view/duck-duckling-no-no-way-idont-agree-gif-4243311',
    'https://tenor.com/view/sad-pablo-lonely-alone-gif-12928789',
    'https://tenor.com/view/unamused-cat-over-it-stare-done-gif-14630368',
    'https://tenor.com/view/no-no-no-way-never-nuh-uh-gif-14500720',
    'https://tenor.com/view/nope-danny-de-vito-gif-8123780',
    'https://tenor.com/view/steve-carell-no-please-no-gif-5026106',
    'https://tenor.com/view/timon-lion-king-nope-no-shake-gif-3834543',
    'https://tenor.com/view/not-yet-notyet-mace-windu-gif-9797353',
    'https://tenor.com/view/notyet-no-nuhuh-nope-dikembe-mutombo-gif-4945989',
    'https://tenor.com/view/no-not-yet-butters-stotch-south-park-s8e11-quest-for-ratings-gif-22281857',
    'https://tenor.com/view/waiting-house-md-dr-house-hugh-laurie-gif-5289550',
    'https://tenor.com/view/doctor-house-yes-no-agreed-gif-11933192',
    'https://tenor.com/view/doctor-strange-nope-no-benedict-cumberbatch-close-book-gif-13612586',
    'https://tenor.com/view/doctor-who-david-tennant-10th-doctor-hold-on-wait-a-minute-gif-17141817',
    'https://tenor.com/view/david-tennant-doctor-who-no-i-dont-know-gif-7261849',
    'https://tenor.com/view/no-nooo-nope-eat-fingerwag-gif-4880183',
    'https://tenor.com/view/baby-yoda-um-nope-gif-18367579',
    'https://tenor.com/view/despicable-me-minions-ehh-no-nope-gif-4741703',
    'https://tenor.com/view/no-nope-shake-my-head-smh-nah-gif-11696879',
    'https://giphy.com/gifs/boba-fett-bobafett-fan-club-lPiUYaq8PX8svtZQ4L',
    'https://tenor.com/view/varys-conleth-hill-no-game-of-thrones-gif-14629787',
    'https://tenor.com/view/not-today-game-of-thrones-got-gif-14687529',
    'https://tenor.com/view/battle-droid-compute-think-star-wars-gif-17180363',
    'https://tenor.com/view/no-game-of-thrones-got-tyrion-head-shake-gif-7910240',
    'https://tenor.com/view/star-wars-jar-jar-binks-oh-no-the-phantom-menace-uh-oh-gif-16041506',
    'https://tenor.com/view/maz-kanata-maz-kanata-eyes-hmmm-gif-5468497',
    'https://tenor.com/view/i-dont-think-so-no-way-nu-uh-not-happening-fed-up-gif-15626430',
    'https://tenor.com/view/nick-miller-new-girl-jake-johnson-nuh-uh-nope-gif-16700667',
    'https://tenor.com/view/cat-no-no-no-no-nope-nope-nope-i-dont-think-so-gif-17182586',
    'https://tenor.com/view/thats-a-no-its-a-no-star-wars-chewbacca-gif-7663274',
    'https://tenor.com/view/family-guy-peter-griffin-head-shake-no-chance-nope-gif-17521786',
    'https://tenor.com/view/cat-nah-nope-no-gif-4276898',
    'https://tenor.com/view/nope-chester-cheetah-gif-10403624',
    'https://tenor.com/view/nope-no-nothappening-cat-cats-gif-4858845',
    'https://tenor.com/view/worried-waiting-gif-19902178',
    'https://tenor.com/view/paddle-ball-rubberband-ball-game-toy-play-gif-16105634',
    'https://tenor.com/view/waiting-patiently-beetlejuice-numbers-now-serving-gif-14805864',
    'https://tenor.com/view/waiting-annoyed-gif-7469556',
    'https://tenor.com/view/daddys-home2-daddys-home2gifs-jon-lithgow-reunion-waiting-gif-9683398',
    'https://tenor.com/view/im-waiting-daffy-duck-impatient-gif-16985061',
    'https://tenor.com/view/library-books-what-time-is-it-you-are-late-waiting-gif-14235077',
    'https://tenor.com/view/dogs-no-wine-pets-boss-dog-youre-cut-off-gif-11385245',
    'https://tenor.com/view/nope-no-starwars-obiwan-gif-16946630'
]
holiday_query_started_gifs = [
    'https://tenor.com/view/the-lion-king-it-is-time-throwing-monkey-elephants-gif-17842868',
    'https://tenor.com/view/baby-scream-yeah-hockey-kid-angry-gif-11733200',
    'https://tenor.com/view/bear-dance-dancing-lit-get-it-gif-15945949',
    'https://tenor.com/view/kool-aid-man-kool-aid-juice-gif-8291586',
    'https://tenor.com/view/chris-farley-running-lets-do-this-excited-its-time-to-go-gif-15610590',
    'https://tenor.com/view/its-go-time-dog-puppy-truck-pug-gif-15921847',
    'https://tenor.com/view/count-adhemar-its-go-time-aknights-tale-knight-stare-gif-11506631',
    'https://tenor.com/view/yes-sweet-hellyes-pumpit-gif-3532253',
    'https://tenor.com/view/austin-powers-yeah-baby-excited-gif-5316726',
    'https://tenor.com/view/lord-of-the-rings-lotr-so-it-begins-begins-beginning-gif-5322326',
    'https://tenor.com/view/yes-dog-indeed-nod-gif-10818519',
    'https://tenor.com/view/ron-pearlman-the-goon-yes-yep-anchorman-gif-12449331',
    'https://tenor.com/view/monkey-ape-dance-dancing-orangutan-gif-15714845',
    'https://tenor.com/view/clapping-applause-clap-yes-yeah-gif-16616022',
    'https://tenor.com/view/hell-yeah-snoop-dogg-dance-moves-gif-17527488',
    'https://tenor.com/view/baby-dancing-oh-yeah-hell-yeah-dance-gif-17100703',
    'https://tenor.com/view/thor-ragnarok-yes-thor-thor3-happy-excited-gif-15710556',
    'https://tenor.com/view/so-much-yes-yes-yes-yes-yes-yess-clapping-gif-17121638',
    'https://tenor.com/view/will-smith-clap-yay-happy-hooray-gif-13226780',
    'https://tenor.com/view/jonah-hill-yay-african-child-screaming-shouting-gif-7212866',
    'https://tenor.com/view/yay-excited-clap-gif-21025303',
    'https://tenor.com/view/baby-dancing-oh-yeah-gif-13850795',
    'https://tenor.com/view/minions-yay-happy-nice-cheering-gif-17426799',
    'https://tenor.com/view/i-still-love-you-gif-5721545',
    'https://tenor.com/view/the-goon-time-its-time-gif-12353011',
    'https://tenor.com/view/toy-story-woody-about-time-happy-excited-gif-15811226',
    'https://tenor.com/view/its-go-time-show-time-lets-go-time-to-do-this-lets-do-this-gif-14012446',
    'https://tenor.com/view/kermit-the-frog-drive-driving-go-time-gif-12905745',
    'https://tenor.com/view/party-time-to-party-eat-hungry-gif-9675080',
    'https://tenor.com/view/arresteddevelopment-its-happening-michael-cera-realization-gif-5420046',
    'https://tenor.com/view/wreck-it-ralph-vanellope-von-schweetz-this-is-it-exciting-yay-gif-3552211',
    'https://tenor.com/view/todays-the-day-its-happening-do-it-in-this-day-right-now-gif-15844895',
    'https://tenor.com/view/tired-the-mandalorian-baby-yoda-sleeping-sell-them-gif-16077531',
    'https://tenor.com/view/money-donald-duck-cash-counting-gif-7263498',
    'https://tenor.com/view/penguin-cute-hurry-up-on-gif-14010967',
    'https://tenor.com/view/the-office-stanley-hudson-leslie-david-baker-run-away-run-gif-4424450',
]

error_gifs = [
    'https://media.tenor.com/-DSYvCR3HnYAAAAC/beaker-fire.gif', # muppets
    'https://media.tenor.com/M1rOzWS3NsQAAAAC/nothingtosee-disperse.gif', # naked gun
    'https://media.tenor.com/oSASxe-6GesAAAAC/spongebob-patrick.gif', # spongebob
    'https://media.tenor.com/u-1jz7ttHhEAAAAC/angry-panda-rage.gif' # panda smash
]

# Check the folder exists
if not os.path.exists(os.path.dirname(CARRIERS_DB_PATH)):
    print(f'Folder {os.path.dirname(CARRIERS_DB_PATH)} does not exist, making it now.')
    os.makedirs(os.path.dirname(CARRIERS_DB_PATH))

# check the dumps folder exists
if not os.path.exists(os.path.dirname(CARRIERS_DB_DUMPS_PATH)):
    print(f'Folder {os.path.dirname(CARRIERS_DB_DUMPS_PATH)} does not exist, making it now.')
    os.makedirs(os.path.dirname(CARRIERS_DB_DUMPS_PATH))
    
# check the settings folder exists
if not os.path.exists(SETTINGS_PATH):
    print(f'Folder {SETTINGS_PATH} does not exist, making it now.')
    os.makedirs(SETTINGS_PATH)

# Move the old db to the new location if the new location doesn't exist and the old one does
old_db_path = os.path.join(os.path.expanduser('~'), 'boozedatabase', 'booze_carriers.db')
if os.path.exists(old_db_path) and not os.path.exists(CARRIERS_DB_PATH):
    os.rename(old_db_path, CARRIERS_DB_PATH)
    
old_db_dumps_path = os.path.join(os.path.expanduser('~'), 'boozedatabase', 'dumps', 'booze_carriers.sql')
if os.path.exists(old_db_dumps_path) and not os.path.exists(CARRIERS_DB_DUMPS_PATH):
    os.rename(old_db_dumps_path, CARRIERS_DB_DUMPS_PATH)
    
old_wine_carrier_welcome = os.path.join('wine_carrier_welcome.txt')
if os.path.exists(old_wine_carrier_welcome) and not os.path.exists(WELCOME_MESSAGE_FILE_PATH):
    os.rename(old_wine_carrier_welcome, WELCOME_MESSAGE_FILE_PATH)
    
old_google_oauth_credentials_path = os.path.join(os.path.expanduser('~'), '.ptnboozebot.json')
if os.path.exists(old_google_oauth_credentials_path) and not os.path.exists(GOOGLE_OAUTH_CREDENTIALS_PATH):
    os.rename(old_google_oauth_credentials_path, GOOGLE_OAUTH_CREDENTIALS_PATH)

def get_db_path():
    """
    Returns the database path. For testing we keep the file locally for ease

    :returns: The path to the db file
    :rtype: str
    """
    return CARRIERS_DB_PATH


def server_council_role_ids():
    """
    Wrapper that returns the council role IDs

    :returns: Council role ids
    :rtype: Tuple[int, ...]
    """
    return PROD_ADMIN_IDS if _production else TEST_ADMIN_IDS


def server_sommelier_role_id():
    """
    Wrapper that returns the sommelier role ID

    :returns: Sommelier role id
    :rtype: int
    """
    return PROD_SOMMELIER_ID if _production else TEST_SOMMELIER_ID


def server_connoisseur_role_id():
    """
    Wrapper that returns the connoisseur role ID

    :returns: Sommelier role id
    :rtype: int
    """
    return PROD_CONNOISSEUR_ID if _production else TEST_CONNOISSEUR_ID


def server_wine_carrier_role_id():
    """
    Wrapper that returns the wine carrier owner role ID

    :returns: Wine co role id
    :rtype: int
    """
    return PROD_WINE_CARRIER_ID if _production else TEST_WINE_CARRIER_ID


def server_wine_tanker_role_id():
    """
    Wrapper that returns the wine tanker owner role ID

    :returns: Wine tanker role id
    :rtype: int
    """
    return PROD_WINE_TANKER_ID if _production else TEST_WINE_TANKER_ID

def server_hitchhiker_role_id():
    """
    Wrapper that returns the wine tanker owner role ID

    :returns: Wine tanker role id
    :rtype: int
    """
    return PROD_HITCHHIKER_ID if _production else TEST_HITCHHIKER_ID

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
    return CARRIERS_DB_DUMPS_PATH


def get_bot_control_channel():
    """
    Returns the channel ID for the bot control channel.

    :return: The channel ID
    :rtype: int
    """
    return PROD_BOOZE_BOT_CHANNEL if _production else TEST_BOOZE_BOT_CHANNEL


def get_wine_carrier_channel():
    """
    Returns the channel ID for the wine carrier chat channel.

    :return: The channel IDs
    :rtype: int
    """
    return PROD_WINE_CARRIER_CHANNEL if _production else TEST_WINE_CARRIER_CHANNEL


def server_mod_role_id():
    """
    Returns the moderator role ID for the server

    :return: The role ID
    :rtype: int
    """
    return PROD_MOD_ID if _production else TEST_MOD_ID


def rackhams_holiday_channel():
    """
    Returns the channel ID for notification of the holiday.

    :return: The channel ID
    :rtype: int
    """
    return PROD_HOLIDAY_ANNOUNCE_CHANNEL_ID if _production else TEST_HOLIDAY_ANNOUNCE_CHANNEL_ID

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


def get_steve_says_channel():
    """
    Returns the channel ID for steve-says commands

    :return: The channel ID
    :rtype: int
    """
    return PROD_STEVE_SAYS_CHANNEL if _production else TEST_STEVE_SAYS_CHANNEL


def get_wine_tanker_role():
    """
    Returns the wine tanker role ID

    :return: The role ID
    :rtype: int
    """
    return PROD_WINE_TANKER_ID if _production else TEST_WINE_TANKER_ID


def get_discord_tanker_unload_channel():
    """
    Gets the tanker unload notification channel

    :return: The channel ID
    :rtype: int
    """
    return PROD_TANKER_UNLOAD_CHANNEL_ID if _production else TEST_TANKER_UNLOAD_CHANNEL_ID

def get_public_channel_list():
    """
    Gets the list of public BC channels

    :return: The channel IDs
    :rtype: list, int
    """
    return PROD_BC_PUBLIC_CHANNEL_IDS if _production else TEST_BC_PUBLIC_CHANNEL_IDS

def bot_spam_channel():
    """
    Gets the bot spam channel

    :return: The channel ID
    :rtype: int
    """
    return PROD_BOT_SPAM_CHANNEL if _production else TEST_BOT_SPAM_CHANNEL

def wine_carrier_command_channel():
    """
    Gets the rackhams space traffic control channel
    
    :return: The channel ID
    :rtype: int
    """
    return PROD_WINE_CARRIER_COMMAND_CHANNEL if _production else TEST_WINE_CARRIER_COMMAND_CHANNEL

def get_departure_announcement_channel():
    """
    Gets the departure announcement channel

    :return: The channel ID
    :rtype: int
    """
    return PROD_DEPARTURE_ANNOUNCEMENT_CHANNEL if _production else TEST_DEPARTURE_ANNOUNCEMENT_CHANNEL

def get_thoon_emoji_id():
    """
    Gets the ID of the Thoon emoji

    :return: The emoji ID
    :rtype: int
    """
    return PROD_THOON_EMOJI_ID if _production else TEST_THOON_EMOJI_ID

def get_feedback_channel_id():
    """
    Gets the ID of the feedback channel

    :return: The channel ID
    :rtype: int
    """
    return PROD_FEEDBACK_CHANNEL_ID if _production else TEST_FEEDBACK_CHANNEL_ID
  
def get_pilot_role_id():
    """
    Gets the ID of the pilot role

    :return: The role ID
    :rtype: int
    """
    return PROD_PILOT_ID if _production else TEST_PILOT_ID

def get_wine_carrier_guide_channel_id():
    """
    Gets the ID of the wine carrier guide channel

    :return: The channel ID
    :rtype: int
    """
    return PROD_WINE_CARRIER_GUIDE_CHANNEL_ID if _production else TEST_WINE_CARRIER_GUIDE_CHANNEL_ID


def get_ptn_booze_cruise_role_id():
    """
    Gets the ID of the PTN Booze Cruise role

    :return: The role ID
    :rtype: int
    """
    return PROD_PTN_BOOZE_CRUISE_ROLE_ID if _production else TEST_PTN_BOOZE_CRUISE_ROLE_ID

full_access_role_ids = {*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()}
elevated_role_ids = {*full_access_role_ids, server_connoisseur_role_id()}