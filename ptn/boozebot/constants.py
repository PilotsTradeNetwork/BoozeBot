"""
Constants used throughout BoozeBot.

"""

# libraries
import os
import re
from pathlib import Path
from typing import Any, Literal, TypedDict

import discord
from discord.ext import commands
from dotenv import load_dotenv
from ptn_utils.get_or_fetch import GetOrFetch
from ptn_utils.global_constants import (
    CHANNEL_BC_BOOZE_CRUISE_CHAT,
    CHANNEL_BC_BOOZE_CRUISE_SIGNUPS,
    CHANNEL_BC_DEPARTURE_ANNOUNCEMENT,
    CHANNEL_BC_WCO_ANNOUNCEMENTS,
    CHANNEL_BC_WINE_CARRIER_GUIDE,
    CHANNEL_BC_WINE_CELLAR_UNLOADING,
    DATA_DIR,
    DISCORD_GUILD,
    ROLE_BOOZE_CRUISE,
    ROLE_HITCHHIKER,
    ROLE_WINE_CARRIER,
    _production,
)
from ptn_utils.logger.logger import get_logger

logger = get_logger("boozebot.constants")

# database paths
DB_PATH = os.path.join(DATA_DIR, "database")
DB_DUMPS_PATH = os.path.join(DATA_DIR, "database")
CARRIERS_DB_PATH = os.path.join(DATA_DIR, "database", "booze.db")
CARRIERS_DB_DUMPS_PATH = os.path.join(DATA_DIR, "sql", "booze.sql")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings")
SETTINGS_FILE_PATH = Path(SETTINGS_PATH, "settings.json")
WELCOME_MESSAGE_FILE_PATH = Path(SETTINGS_PATH, "welcome_message.txt")
BC_PREP_MESSAGE_FILE_PATH = Path(SETTINGS_PATH, "bc_prep_message.txt")
BC_START_MESSAGE_FILE_PATH = Path(SETTINGS_PATH, "bc_start_message.txt")
BC_END_MESSAGE_FILE_PATH = Path(SETTINGS_PATH, "bc_end_message.txt")
GOOGLE_OAUTH_CREDENTIALS_PATH = os.path.join(DATA_DIR, ".ptnboozebot.json")

load_dotenv(os.path.join(DATA_DIR, ".env"))
BOOZESHEETS_API_BASE_URL = os.getenv("BOOZESHEETS_API_BASE_URL", None)
BOOZESHEETS_API_KEY = os.getenv("BOOZESHEETS_API_KEY", None)

if not BOOZESHEETS_API_BASE_URL:
    logger.critical("BOOZESHEETS_API_BASE_URL is not set")
    exit(1)

if not BOOZESHEETS_API_KEY:
    logger.critical("BOOZESHEETS_API_KEY is not set")
    exit(1)

# define bot object
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.guild_messages = True
intents.message_content = True
intents.guild_reactions = True
intents.expressions = True


# Added for type hints
class GetFetchBot(commands.Bot):
    get_or_fetch: GetOrFetch

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.get_or_fetch = GetOrFetch(self, DISCORD_GUILD)


bot = GetFetchBot(
    command_prefix=commands.when_mentioned_or("b/"),
    intents=intents,
    chunk_guilds_at_startup=False,
    allowed_mentions=discord.AllowedMentions(roles=False, users=False, everyone=False) if not _production else None,
)

RACKHAMS_PEAK_POP = 150000

WCO_ROLE_ICON_URL = (
    "https://cdn.discordapp.com/role-icons/839149899596955708/2d8298304adbadac79679171ab7f0ae6.webp?quality=lossless"
)

I_AM_STEVE_GIF = "https://pilotstradenetwork.com/wp-content/uploads/2025/07/I-Am-Steve.gif"

INTERACTION_CHECK_GIF = "https://c.tenor.com/91firFcrcYsAAAAC/tenor.gif"

CARRIER_ID_RE = re.compile(r"[A-HJ-NP-Za-hj-np-z0-9]{3}-[A-HJ-NP-Za-hj-np-z0-9]{3}|\w{4}")

ping_response_messages = [
    "Yarrr, <@{message_author_id}>, you summoned me?",
    "https://tenor.com/view/hello-there-baby-yoda-mandolorian-hello-gif-20136589",
    "https://tenor.com/view/hello-sexy-hi-hello-mr-bean-gif-13830351",
    "https://tenor.com/view/hello-whale-there-hi-gif-5551502",
    "https://tenor.com/view/funny-animals-gif-13669907",
]

holiday_start_gif = "https://tenor.com/view/jim-carrey-ace-ventura-driving-its-show-time-cool-gif-12905775"
holiday_ended_gif = "https://tenor.com/view/watch-game-of-thrones-jon-snow-gif-5445395"

holiday_query_not_started_gifs = [
    "https://tenor.com/view/mr-bean-waiting-still-waiting-gif-13052487",
    "https://tenor.com/view/waiting-gif-10918805",
    "https://tenor.com/view/not-quite-yet-enough-well-exactly-raphael-chestang-gif-12711794",
    "https://tenor.com/view/no-bugs-bunny-nope-gif-14359850",
    "https://tenor.com/view/waiting-gif-9848405",
    "https://tenor.com/view/duck-duckling-no-no-way-idont-agree-gif-4243311",
    "https://tenor.com/view/sad-pablo-lonely-alone-gif-12928789",
    "https://tenor.com/view/unamused-cat-over-it-stare-done-gif-14630368",
    "https://tenor.com/view/no-no-no-way-never-nuh-uh-gif-14500720",
    "https://tenor.com/view/nope-danny-de-vito-gif-8123780",
    "https://tenor.com/view/steve-carell-no-please-no-gif-5026106",
    "https://tenor.com/view/timon-lion-king-nope-no-shake-gif-3834543",
    "https://tenor.com/view/not-yet-notyet-mace-windu-gif-9797353",
    "https://tenor.com/view/notyet-no-nuhuh-nope-dikembe-mutombo-gif-4945989",
    "https://tenor.com/view/no-not-yet-butters-stotch-south-park-s8e11-quest-for-ratings-gif-22281857",
    "https://tenor.com/view/waiting-house-md-dr-house-hugh-laurie-gif-5289550",
    "https://tenor.com/view/doctor-house-yes-no-agreed-gif-11933192",
    "https://tenor.com/view/doctor-strange-nope-no-benedict-cumberbatch-close-book-gif-13612586",
    "https://tenor.com/view/doctor-who-david-tennant-10th-doctor-hold-on-wait-a-minute-gif-17141817",
    "https://tenor.com/view/david-tennant-doctor-who-no-i-dont-know-gif-7261849",
    "https://tenor.com/view/no-nooo-nope-eat-fingerwag-gif-4880183",
    "https://tenor.com/view/baby-yoda-um-nope-gif-18367579",
    "https://tenor.com/view/despicable-me-minions-ehh-no-nope-gif-4741703",
    "https://tenor.com/view/no-nope-shake-my-head-smh-nah-gif-11696879",
    "https://giphy.com/gifs/boba-fett-bobafett-fan-club-lPiUYaq8PX8svtZQ4L",
    "https://tenor.com/view/varys-conleth-hill-no-game-of-thrones-gif-14629787",
    "https://tenor.com/view/not-today-game-of-thrones-got-gif-14687529",
    "https://tenor.com/view/battle-droid-compute-think-star-wars-gif-17180363",
    "https://tenor.com/view/no-game-of-thrones-got-tyrion-head-shake-gif-7910240",
    "https://tenor.com/view/star-wars-jar-jar-binks-oh-no-the-phantom-menace-uh-oh-gif-16041506",
    "https://tenor.com/view/maz-kanata-maz-kanata-eyes-hmmm-gif-5468497",
    "https://tenor.com/view/i-dont-think-so-no-way-nu-uh-not-happening-fed-up-gif-15626430",
    "https://tenor.com/view/nick-miller-new-girl-jake-johnson-nuh-uh-nope-gif-16700667",
    "https://tenor.com/view/cat-no-no-no-no-nope-nope-nope-i-dont-think-so-gif-17182586",
    "https://tenor.com/view/thats-a-no-its-a-no-star-wars-chewbacca-gif-7663274",
    "https://tenor.com/view/family-guy-peter-griffin-head-shake-no-chance-nope-gif-17521786",
    "https://tenor.com/view/cat-nah-nope-no-gif-4276898",
    "https://tenor.com/view/nope-chester-cheetah-gif-10403624",
    "https://tenor.com/view/nope-no-nothappening-cat-cats-gif-4858845",
    "https://tenor.com/view/worried-waiting-gif-19902178",
    "https://tenor.com/view/paddle-ball-rubberband-ball-game-toy-play-gif-16105634",
    "https://tenor.com/view/waiting-patiently-beetlejuice-numbers-now-serving-gif-14805864",
    "https://tenor.com/view/waiting-annoyed-gif-7469556",
    "https://tenor.com/view/daddys-home2-daddys-home2gifs-jon-lithgow-reunion-waiting-gif-9683398",
    "https://tenor.com/view/im-waiting-daffy-duck-impatient-gif-16985061",
    "https://tenor.com/view/library-books-what-time-is-it-you-are-late-waiting-gif-14235077",
    "https://tenor.com/view/dogs-no-wine-pets-boss-dog-youre-cut-off-gif-11385245",
    "https://tenor.com/view/nope-no-starwars-obiwan-gif-16946630",
]
holiday_query_started_gifs = [
    "https://tenor.com/view/the-lion-king-it-is-time-throwing-monkey-elephants-gif-17842868",
    "https://tenor.com/view/baby-scream-yeah-hockey-kid-angry-gif-11733200",
    "https://tenor.com/view/bear-dance-dancing-lit-get-it-gif-15945949",
    "https://tenor.com/view/kool-aid-man-kool-aid-juice-gif-8291586",
    "https://tenor.com/view/chris-farley-running-lets-do-this-excited-its-time-to-go-gif-15610590",
    "https://tenor.com/view/its-go-time-dog-puppy-truck-pug-gif-15921847",
    "https://tenor.com/view/count-adhemar-its-go-time-aknights-tale-knight-stare-gif-11506631",
    "https://tenor.com/view/yes-sweet-hellyes-pumpit-gif-3532253",
    "https://tenor.com/view/austin-powers-yeah-baby-excited-gif-5316726",
    "https://tenor.com/view/lord-of-the-rings-lotr-so-it-begins-begins-beginning-gif-5322326",
    "https://tenor.com/view/yes-dog-indeed-nod-gif-10818519",
    "https://tenor.com/view/ron-pearlman-the-goon-yes-yep-anchorman-gif-12449331",
    "https://tenor.com/view/monkey-ape-dance-dancing-orangutan-gif-15714845",
    "https://tenor.com/view/clapping-applause-clap-yes-yeah-gif-16616022",
    "https://tenor.com/view/hell-yeah-snoop-dogg-dance-moves-gif-17527488",
    "https://tenor.com/view/baby-dancing-oh-yeah-hell-yeah-dance-gif-17100703",
    "https://tenor.com/view/thor-ragnarok-yes-thor-thor3-happy-excited-gif-15710556",
    "https://tenor.com/view/so-much-yes-yes-yes-yes-yes-yess-clapping-gif-17121638",
    "https://tenor.com/view/will-smith-clap-yay-happy-hooray-gif-13226780",
    "https://tenor.com/view/jonah-hill-yay-african-child-screaming-shouting-gif-7212866",
    "https://tenor.com/view/yay-excited-clap-gif-21025303",
    "https://tenor.com/view/baby-dancing-oh-yeah-gif-13850795",
    "https://tenor.com/view/minions-yay-happy-nice-cheering-gif-17426799",
    "https://tenor.com/view/i-still-love-you-gif-5721545",
    "https://tenor.com/view/the-goon-time-its-time-gif-12353011",
    "https://tenor.com/view/toy-story-woody-about-time-happy-excited-gif-15811226",
    "https://tenor.com/view/its-go-time-show-time-lets-go-time-to-do-this-lets-do-this-gif-14012446",
    "https://tenor.com/view/kermit-the-frog-drive-driving-go-time-gif-12905745",
    "https://tenor.com/view/party-time-to-party-eat-hungry-gif-9675080",
    "https://tenor.com/view/arresteddevelopment-its-happening-michael-cera-realization-gif-5420046",
    "https://tenor.com/view/wreck-it-ralph-vanellope-von-schweetz-this-is-it-exciting-yay-gif-3552211",
    "https://tenor.com/view/todays-the-day-its-happening-do-it-in-this-day-right-now-gif-15844895",
    "https://tenor.com/view/tired-the-mandalorian-baby-yoda-sleeping-sell-them-gif-16077531",
    "https://tenor.com/view/money-donald-duck-cash-counting-gif-7263498",
    "https://tenor.com/view/penguin-cute-hurry-up-on-gif-14010967",
    "https://tenor.com/view/the-office-stanley-hudson-leslie-david-baker-run-away-run-gif-4424450",
]

error_gifs = [
    "https://media.tenor.com/-DSYvCR3HnYAAAAC/beaker-fire.gif",  # muppets
    "https://media.tenor.com/M1rOzWS3NsQAAAAC/nothingtosee-disperse.gif",  # naked gun
    "https://media.tenor.com/oSASxe-6GesAAAAC/spongebob-patrick.gif",  # spongebob
    "https://media.tenor.com/u-1jz7ttHhEAAAAC/angry-panda-rage.gif",  # panda smash
]

too_slow_gifs = [
    "https://media.tenor.com/UttKJzNT7uwAAAAd/funny-very.gif",
    "https://media.tenor.com/JtM1bnp03HEAAAAd/it-looks-like-you-are-too-slow-too-slow.gif",
    "https://media.tenor.com/Et0Nwb11iwoAAAAd/lizard-worm.gif",
    "https://media.tenor.com/uBBA5GTeGT0AAAAd/state-farm-gotta-be-quicker-than-that.gif",
]

N_SYSTEMS = {
    "N0": "HIP 58832",
    "N1": "HD 105341",
    "N2": "HD 104495",
    "N3": "HIP 57784",
    "N4": "HIP 57478",
    "N5": "HIP 56843",
    "N6": "HD 104392",
    "N7": "HD 102779",
    "N8": "HD 102000",
    "N9": "HD 104785",
    "N10": "HD 105548",
    "N11": "HD 107865",
    "N12": "Plaa Trua WQ-C d13-0",
    "N13": "Plaa Trua QL-B c27-0",
    "N14": "Wregoe OP-D b58-0",
    "N15": "Wregoe ZE-B c28-2",
    "N16": "Gali",
    "N16-Trit": "Mandhrithar",
}

# Check the folder exists
if not os.path.exists(os.path.dirname(CARRIERS_DB_PATH)):
    logger.info(f"Folder {os.path.dirname(CARRIERS_DB_PATH)} does not exist, making it now.")
    os.makedirs(os.path.dirname(CARRIERS_DB_PATH))

# check the dumps folder exists
if not os.path.exists(os.path.dirname(CARRIERS_DB_DUMPS_PATH)):
    logger.info(f"Folder {os.path.dirname(CARRIERS_DB_DUMPS_PATH)} does not exist, making it now.")
    os.makedirs(os.path.dirname(CARRIERS_DB_DUMPS_PATH))

# check the settings folder exists
if not os.path.exists(SETTINGS_PATH):
    logger.info(f"Folder {SETTINGS_PATH} does not exist, making it now.")
    os.makedirs(SETTINGS_PATH)

# Move the old db to the new location if the new location doesn't exist and the old one does
old_db_path = os.path.join(DATA_DIR, "database", "booze_carriers.db")
if os.path.exists(old_db_path) and not os.path.exists(CARRIERS_DB_PATH):
    os.rename(old_db_path, CARRIERS_DB_PATH)

_WCO_WELCOME_BLURB = (
    f"Welcome to the <@&{ROLE_WINE_CARRIER}> backrooms! If you are a returning cruiser, it's great to have you back! "
    f"Please have a read of <#{CHANNEL_BC_WINE_CARRIER_GUIDE}>, <#{CHANNEL_BC_WCO_ANNOUNCEMENTS}>, and the pins of this channel. "
    f"As a reminder, everything you read here is **strictly confidential** and should remain in this chat.\n\n"
    "In the pins you'll find a link to a [spreadsheet](https://docs.google.com/spreadsheets/d/1UscA2YRTLckjAg2FSsUhEv5FYICvf70LMGnnaBHWUfA/edit) "
    "where you need to add your carrier.\n\n"
    "If you have any questions please ask in this channel. There are lots of experienced cruisers here that are eager to help!"
)

_BC_PREP_BLURB = (
    "# **PTN Booze Cruise Status**\n\n"
    "**The channels are open, and we are preparing for the next Booze Cruise! "
    f"If you want to receive notifications as the Cruise progresses use the button in <#{CHANNEL_BC_BOOZE_CRUISE_SIGNUPS}> "
    f"to take the <@&{ROLE_BOOZE_CRUISE}> role, which will be pinged when the Holiday begins "
    f"and for other similarly-important events.**"
)

_BC_START_BLURB = (
    "# **PTN Booze Cruise Status**\n\n"
    f"**The Booze Cruise has begun! Head to <#{CHANNEL_BC_WINE_CELLAR_UNLOADING}> to see which carrier is currently unloading, "
    f"or visit <#{CHANNEL_BC_BOOZE_CRUISE_CHAT}> to chat with your fellow cruisers! If you're in N1, N2, or N3 "
    f"and wish to catch a ride up, head to <#{CHANNEL_BC_BOOZE_CRUISE_SIGNUPS}> and take the <@&{ROLE_HITCHHIKER}> role, "
    f"then watch <#{CHANNEL_BC_DEPARTURE_ANNOUNCEMENT}> for departures to or from the peak!\n\n"
    f"If you want to receive other notifications related to the Booze Cruise use the button in <#{CHANNEL_BC_BOOZE_CRUISE_SIGNUPS}> "
    f"to take the <@&{ROLE_BOOZE_CRUISE}> role, which will be pinged for important events related to the Booze Cruise.**"
)

_BC_END_BLURB = (
    "# **PTN Booze Cruise Status**\n\n"
    "**The Booze Cruise has ended, and we're waiting for the next one! If you want to receive a notification when we "
    f"open the channels to begin prepping for the next Cruise use the button in <#{CHANNEL_BC_BOOZE_CRUISE_SIGNUPS}> "
    f"to take the <@&{ROLE_BOOZE_CRUISE}> role, which will be pinged when we open the channels "
    f"and for other similarly-important events.**"
)

BLURB_KEYS = Literal["wco_welcome", "bc_prep", "bc_start", "bc_end"]
BC_STATUS = Literal["bc_prep", "bc_start", "bc_end"]


class BlurbInfo(TypedDict):
    file_path: Path
    default_text: str
    embed_colour: int | discord.Colour


BLURBS: dict[BLURB_KEYS, BlurbInfo] = {
    "wco_welcome": {
        "file_path": WELCOME_MESSAGE_FILE_PATH,
        "default_text": _WCO_WELCOME_BLURB,
        "embed_colour": 0xF16E7F,  # Unused
    },
    "bc_prep": {
        "file_path": BC_PREP_MESSAGE_FILE_PATH,
        "default_text": _BC_PREP_BLURB,
        "embed_colour": discord.Colour.gold(),
    },
    "bc_start": {
        "file_path": BC_START_MESSAGE_FILE_PATH,
        "default_text": _BC_START_BLURB,
        "embed_colour": discord.Colour.green(),
    },
    "bc_end": {"file_path": BC_END_MESSAGE_FILE_PATH, "default_text": _BC_END_BLURB, "embed_colour": 0xEE3563},
}
