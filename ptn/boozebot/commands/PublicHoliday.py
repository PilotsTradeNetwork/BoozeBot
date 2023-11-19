import random
from datetime import datetime, timedelta

# import discord
import discord
from discord import NotFound, app_commands
from discord.ext import commands, tasks

# local imports
from ptn.boozebot import constants
from ptn.boozebot.PHcheck import ph_check
from ptn.boozebot.bot import bot
from ptn.boozebot.commands.ErrorHandler import on_app_command_error
from ptn.boozebot.commands.Helper import check_roles
from ptn.boozebot.constants import rackhams_holiday_channel, server_admin_role_id, \
    server_sommelier_role_id
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_conn


class PublicHoliday(commands.Cog):
    """
    The public holiday state checker mechanism for booze bot.
    """

    def __init__(self, bot: commands.Cog):
        self.bot = bot
        self.summon_message_ids = {}

    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error

    admin_override_state = False
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

    rackhams_holiday_active = False

    @classmethod
    @tasks.loop(minutes=15)
    async def public_holiday_loop(cls):
        """
        Command triggers periodically to check the state at Rackhams Peak. Right now this triggers every 15 minutes.

        :return: None
        """
        print("Rackham's holiday loop running.")
        if ph_check():
            print('PH detected, triggering the notifications.')
            holiday_announce_channel = bot.get_channel(rackhams_holiday_channel())
            if PublicHoliday.admin_override_state:
                print('Turning off the admin override state for holiday check.')
                PublicHoliday.admin_override_state = False

            # Check if we had a holiday flagged already
            pirate_steve_db.execute(
                '''SELECT state FROM holidaystate'''
            )
            holiday_sqlite3 = pirate_steve_db.fetchone()
            holiday_ongoing = bool(dict(holiday_sqlite3).get('state'))
            print(f'Holiday state from database: {holiday_ongoing}')
            if not holiday_ongoing:

                pirate_steve_db.execute(
                    '''UPDATE holidaystate SET state=TRUE, timestamp=CURRENT_TIMESTAMP'''
                )
                pirate_steve_conn.commit()
                print('Holiday was not ongoing, started now - flag it accordingly')
                await holiday_announce_channel.send(PublicHoliday.holiday_start_gif)
                await holiday_announce_channel.send(
                    f'Pirate Steve thinks the folks at Rackhams are partying again. '
                    f'<@&{server_admin_role_id()}>, <@&{server_sommelier_role_id()}> please take note.'
                )
            else:
                print('Holiday already flagged - no need to set it again')
        else:

            # Check if the 48 hours have expired first, to avoid scenarios of the HTTP request failing and turning
            # off an ongoing holiday.

            pirate_steve_db.execute(
                '''SELECT timestamp FROM holidaystate'''
            )
            timestamp = pirate_steve_db.fetchone()

            start_time = datetime.strptime(dict(timestamp).get('timestamp'), '%Y-%m-%d %H:%M:%S')
            end_time = start_time + timedelta(hours=48)

            current_time_utc = datetime.strptime(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
            print('No PH detected, next check in 15 mins.')

            if current_time_utc > end_time:
                # Current time is after the end time, go turn the checks off.
                print('Holiday duration expired, turning the check off.')
                holiday_announce_channel = bot.get_channel(rackhams_holiday_channel())

                # Check if we had a holiday flagged already
                pirate_steve_db.execute(
                    '''SELECT state FROM holidaystate'''
                )
                holiday_sqlite3 = pirate_steve_db.fetchone()
                holiday_ongoing = bool(dict(holiday_sqlite3).get('state'))

                print(f'Holiday state from database: {holiday_ongoing}')
                if holiday_ongoing:
                    pirate_steve_db.execute(
                        '''UPDATE holidaystate SET state=False, timestamp=CURRENT_TIMESTAMP'''
                    )
                    pirate_steve_conn.commit()
                    # Only post it if it is a state change.
                    print('Holiday was ongoing, no longer ongoing - flag it accordingly')
                    await holiday_announce_channel.send(PublicHoliday.holiday_ended_gif)
            else:
                print(f'Holiday has not yet expired, due at: {end_time}. Ignoring the check result for now.')

    @app_commands.command(name="booze_started", description="Returns a GIF for whether the holiday has started.")
    @check_roles(constants.conn_plus_roles)
    async def holiday_query(self, interaction: discord.Interaction):
        print(f'User {interaction.user.display_name} wanted to know if the holiday has started.')
        gif = None

        if ph_check() or PublicHoliday.admin_override_state:
            if PublicHoliday.admin_override_state:
                print('Admin override was detected - forcefully returning True.')
            else:
                print('Rackhams holiday check says yep.')
            try:
                gif = random.choice(PublicHoliday.holiday_query_started_gifs)
                await interaction.response.send_message(random.choice(PublicHoliday.holiday_query_started_gifs))
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await interaction.response.send_message('Pirate Steve could not parse the gif. Try again and tell Kutu to check the log.')
        else:
            try:
                gif = random.choice(PublicHoliday.holiday_query_not_started_gifs)
                print('Rackhams holiday check says no.')
                await interaction.response.send_message(gif)
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await interaction.response.send_message('Pirate Steve could not parse the gif. Try again and tell Kutu to check the log.')

    @app_commands.command(name="booze_started_admin_override", description="Overrides the holiday admin flag. Used to set the holiday state before the polling API catches "
                     "it.")
    async def admin_override_holiday_state(self, interaction: discord.Interaction, state: bool):
        print(f'{interaction.user.display_name} requested to override the admin holiday state too: {state}.')
        PublicHoliday.admin_override_state = state
        await interaction.response.send_message(f'Set the admin holiday flag to: {state}. Check with /booze_started.', ephemeral=True)

    @app_commands.command(name="booze_duration_remaining", description="Returns roughly how long the holiday has remaining.")
    @check_roles(constants.conn_plus_roles)
    async def remaining_time(self, interaction: discord.Interaction):
        """
        Determines the remaining time and returns it to the users.

        :param SlashContext ctx: The discord slash context.
        :returns: None
        """
        print(f'User {interaction.user.display_name} wanted to know if the remaining time of the holiday.')
        if not ph_check():
            await interaction.response.send_message(
                "Pirate Steve has not detected the holiday state yet, or it is already over.", ephemeral=True
            )
            return
        print('Holiday ongoing, go figure out how long is left.')
        # Ok the holiday is ongoing
        duration_hours = 48

        # Get the starting timestamp

        pirate_steve_db.execute(
            '''SELECT timestamp FROM holidaystate'''
        )
        timestamp = pirate_steve_db.fetchone()

        start_time = datetime.strptime(dict(timestamp).get('timestamp'), '%Y-%m-%d %H:%M:%S')
        end_time = start_time + timedelta(hours=duration_hours)

        print(f'End time calculated as: {end_time}. Which is epoch of: {end_time.strftime("%s")}')

        await interaction.response.send_message(f'Pirate Steve thinks the holiday will end around <t:{end_time.strftime("%s")}> [local '
                       f'timezone].')

