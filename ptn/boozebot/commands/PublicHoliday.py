import random
from datetime import datetime, timedelta

from discord import NotFound
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_permission, create_option

from ptn.boozebot.PHcheck import ph_check
from ptn.boozebot.constants import rackhams_holiday_channel, bot, bot_guild_id, server_admin_role_id, \
    server_sommelier_role_id, server_mod_role_id
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_conn


class PublicHoliday(commands.Cog):
    """
    The public holiday state checker mechanism for booze bot.
    """

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
            print('No PH detected, next check in 15 mins.')
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

    @cog_ext.cog_slash(
        name="booze_started",
        guild_ids=[bot_guild_id()],
        description="Returns a GIF for whether the holiday has started.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        }
    )
    async def holiday_query(self, ctx: SlashContext):
        print(f'User {ctx.author} wanted to know if the holiday has started.')
        gif = None

        if ph_check() or PublicHoliday.admin_override_state:
            if PublicHoliday.admin_override_state:
                print('Admin override was detected - forcefully returning True.')
            else:
                print('Rackhams holiday check says yep.')
            try:
                gif = random.choice(PublicHoliday.holiday_query_started_gifs)
                await ctx.send(random.choice(PublicHoliday.holiday_query_started_gifs))
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await ctx.send('Pirate Steve could not parse the gif. Try again and tell Kutu to check the log.')
        else:
            try:
                gif = random.choice(PublicHoliday.holiday_query_not_started_gifs)
                print('Rackhams holiday check says no.')
                await ctx.send(gif)
            except NotFound:
                print(f'Problem sending the GIF for: {gif}.')
                await ctx.send('Pirate Steve could not parse the gif. Try again and tell Kutu to check the log.')

    @cog_ext.cog_slash(
        name="booze_started_admin_override",
        guild_ids=[bot_guild_id()],
        description="Overrides the holiday admin flag. Used to set the holiday state before the polling API catches "
                    "it.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
        options=[
            create_option(
                name='state',
                description='True or False to override the holiday check flag.',
                option_type=5,
                required=True
            )
        ],
    )
    async def admin_override_holiday_state(self, ctx: SlashContext, state: bool):
        print(f'{ctx.author} requested to override the admin holiday state too: {state}.')
        PublicHoliday.admin_override_state = state
        await ctx.send(f'Set the admin holiday flag to: {state}. Check with /booze_started.', hidden=True)

    @cog_ext.cog_slash(
        name="booze_duration_remaining",
        guild_ids=[bot_guild_id()],
        description="Returns roughly how long the holiday has remaining.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def remaining_time(self, ctx: SlashContext):
        """
        Determines the remaining time and returns it to the users.

        :param SlashContext ctx: The discord slash context.
        :returns: None
        """
        print(f'User {ctx.author} wanted to know if the remaining time of the holiday.')
        if not ph_check():
            await ctx.send(
                "Pirate Steve has not detected the holiday state yet, or it is already over.", hidden=True
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

        current_time_utc = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        remaining_time = end_time - datetime.strptime(current_time_utc, '%Y-%m-%d %H:%M:%S')

        print(f'End time calculated as: {end_time}. Which is around: {remaining_time} from now')

        await ctx.send(f'Pirate Steve thinks the holiday will end around {end_time} UTC. This should be in '
                       f'roughly {remaining_time} hours from now, give or take.')

