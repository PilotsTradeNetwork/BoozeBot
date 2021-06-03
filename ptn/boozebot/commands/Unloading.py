import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType

from ptn.boozebot.BoozeCarrier import BoozeCarrier
from ptn.boozebot.constants import bot_guild_id, get_custom_assassin_id, bot, get_discord_booze_unload_channel, \
    server_admin_role_id, server_carrier_owner_role_id, server_sommelier_role_id, server_aux_carrier_role_id
from ptn.boozebot.database.database import carrier_db, carrier_db_lock, carriers_conn


class Unloading(commands.Cog):
    def __init__(self):
        """
        This class is a collection functionality for tracking a booze cruise unload operations
        """

    @cog_ext.cog_slash(
        name="WineHelperMarketOpen",
        guild_ids=[bot_guild_id()],
        description="Creates a new unload operation in this channel.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_aux_carrier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_carrier_owner_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def booze_unload_market(self, ctx: SlashContext):
        """
        Command to set a booze cruise market unload. Generates a default message in the channel that it ran in.

        :param SlashContext ctx: The discord slash context.
        :returns: A discord embed with some emoji's
        """
        print(f'User {ctx.author} requested a new booze unload in channel: {ctx.channel}.')

        embed = discord.Embed(title='Avast Ye!')
        embed.add_field(name='If you are INTENDING TO BUY, please react with: :airplane_arriving:.\n'
                             f'Once you are DOCKED react with: <:Assassin:{str(get_custom_assassin_id())}>\n'
                             f'Once you PURCHASE WINE, react with: :wine_glass:',
                        value='Market will be opened once we have aligned the number of commanders.',
                        inline=True)
        embed.set_footer(text='All 3 emoji counts should match by the end or Pirate Steve will be unhappy. 🏴‍☠')

        message = await ctx.send(embed=embed)
        await message.add_reaction('🛬')
        await message.add_reaction(f'<:Assassin:{str(get_custom_assassin_id())}>')
        await message.add_reaction('🍷')

    @cog_ext.cog_slash(
        name="WineHelperMarketClosed",
        guild_ids=[bot_guild_id()],
        description="Sends a dummy message to indicate you have closed your market. Command sent in active channel.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_aux_carrier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_carrier_owner_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
                ]
            },
        )
    async def booze_market_closed(self, ctx: SlashContext):
        print(f'User {ctx.author} requested a to close the market in channel: {ctx.channel}.')
        embed = discord.Embed(title='Batten Down The Hatches! This sale is currently done!')
        embed.add_field(name='Go fight the sidewinder for the landing pad.',
                        value='Hopefully you got some booty, now go get your doubloons!')
        embed.set_footer(text='Notified by your friendly neighbourhood pirate bot.')
        message = await ctx.send(embed=embed)
        await message.add_reaction('🏴‍☠️')

    @cog_ext.cog_slash(
        name='Wine_Unload',
        guild_ids=[bot_guild_id()],
        description='Posts a new wine unloading notification for a specific carrier.',
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_carrier_owner_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
        options=[
            create_option(
                name='carrier_id',
                description='The XXX-XXX ID string for the carrier',
                option_type=3,
                required=True
            ),
            create_option(
                name='planetary_body',
                description='A string representing the location of the carrier, ie Star, P1, P2',
                option_type=3,
                required=True,
                choices=[
                    create_choice(
                        name="Star",
                        value="Star"
                    ),
                    create_choice(
                        name="Planet 1",
                        value="Planet 1"
                    ),
                    create_choice(
                        name="Planet 2",
                        value="Planet 2"
                    ),
                    create_choice(
                        name="Planet 3",
                        value="Planet 3"
                    ),
                    create_choice(
                        name="Planet 4",
                        value="Planet 4"
                    ),
                    create_choice(
                        name="Planet 5",
                        value="Planet 5"
                    ),
                    create_choice(
                        name="Planet 6",
                        value="Planet 6"
                    )
                ]
            ),
            create_option(
                name='timed_market',
                description='True if carrier is running timed markets, else False',
                option_type=5,
                required=True
            ),
            create_option(
                name='unload_channel',
                description='The discord channel #xxx which the carrier will run timed unloads in',
                option_type=3,
                required=False
            )
        ]
    )
    async def wine_carrier_unload(self, ctx: SlashContext, carrier_id, planetary_body, timed_market: bool,
                                  unload_channel=None):
        """
        Posts a wine unload request to the unloading channel.

        :param SlashContext ctx: The discord slash context.
        :param str carrier_id: The carrier ID string
        :param str planetary_body: Where is the carrier? Star, P1 etc?
        :param bool timed_market: Is the carrier running timed market openings, True or False.
        :param str unload_channel: The discord unload channel. Required if using timed market openings so we can
            point the user where to go. This is an optional value.
        :returns: A message to the user
        :rtype: Union[discord.Message, dict]
        """
        print(f'User {ctx.author} has flagged a new overall unload operation for carrier: {carrier_id} using unload '
              f'channel: {unload_channel} using timed markets: {timed_market}.')

        if timed_market and not unload_channel:
            return await ctx.channel.send(f'Sorry, to run a timed market we need an unload channel, you '
                                          f'provided: {unload_channel}.')

        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )

        # We will only get a single entry back here as the carrierid is a unique field.
        carrier_data = BoozeCarrier(carrier_db.fetchone())
        if not carrier_data:
            return await ctx.send(f'Sorry, during unload we could not find a carrier for the data: {carrier_id}.')

        wine_alert_channel = bot.get_channel(get_discord_booze_unload_channel())
        unloading_channel_id = None
        if unload_channel:
            unloading_channel_id = bot.get_channel(
                int(unload_channel.replace('#', '').replace('<', '').replace('>', ''))
            )

        if carrier_data.discord_unload_notification:
            print(f'Sorry, carrier {carrier_data.carrier_identifier} is already on a wine unload.')
            return await ctx.send(f'Carrier: {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) is '
                                  f'already unloading wine. Check the notification in {unload_channel}.')

        print(f'Starting to post un-load operation for carrier: {carrier_data}')
        message_send = await ctx.channel.send("**Sending to Discord...**")

        market_conditions = 'Timed Openings' if timed_market else f'{carrier_data.platform} Squadron and Friends'

        # Only in the case of timed openings does a channel make sense.
        unload_tracking = f' Tracked in {unload_channel}.' if timed_market else ''

        wine_load_embed = discord.Embed(
            title='Wine unload notification.',
            description=f'Carrier {carrier_data.carrier_name} (**{carrier_data.carrier_identifier}**) is currently '
                        f'unloading **{carrier_data.wine_total}** tonnes of wine from **{planetary_body}**".'
                        f'\n Market Conditions: **{market_conditions}**.{unload_tracking}'
        )
        wine_load_embed.set_footer(text='Please react with 💯 once completed.')
        wine_unload_alert = await wine_alert_channel.send(embed=wine_load_embed)
        await message_send.delete()
        # Get the discord alert ID and drop it into the database
        discord_alert_id = wine_unload_alert.id

        print(f'Posted the wine unload alert for {carrier_data.carrier_name} ({carrier_data.carrier_identifier})')

        try:
            carrier_db_lock.acquire()
            data = (
                discord_alert_id,
                f'%{carrier_id}%'
            )

            carrier_db.execute('''
                UPDATE boozecarriers
                SET discord_unload_in_progress=?, totalunloads=totalunloads+1
                WHERE carrierid LIKE (?)
            ''', data)
            carriers_conn.commit()
        finally:
            carrier_db_lock.release()
        print(f'Discord alert ID written to database for {carrier_data.carrier_identifier}')

        if unload_channel:
            embed = discord.Embed(title='Wine unloading starting shortly')
            # If we have an unload channel ID, go write a message there also.
            embed.add_field(
                name=f'Carrier {carrier_data.carrier_name} ({carrier_data.carrier_identifier}).\n'
                     f'Unloading {carrier_data.wine_total} tonnes of wine with timed openings.\n'
                     f'Location: {planetary_body}',
                value='Market unloads will begin shortly.',
                inline=True
            )
            embed.set_footer(text='C/O: Try the commands /boozecruiseunload and /boozecruisemarketclosed.')
            await unloading_channel_id.send(embed=embed)

        return await ctx.send(
            f'Wine unload requested by {ctx.author} for {carrier_id} processed successfully. Market: '
            f'{market_conditions}. {unload_tracking}'
        )

    @cog_ext.cog_slash(
        name='Wine_Unload_Complete',
        guild_ids=[bot_guild_id()],
        description='Removes any trade channel notification for unloading wine.',
        options=[
            create_option(
                name='carrier_id',
                description='The XXX-XXX ID string for the carrier',
                option_type=3,
                required=True
            )
        ],
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_carrier_owner_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def wine_unloading_complete(self, ctx: SlashContext, carrier_id):
        print(f'Wine unloading complete for {carrier_id} flagged by {ctx.author}.')

        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )

        # We will only get a single entry back here as the carrierid is a unique field.
        carrier_data = BoozeCarrier(carrier_db.fetchone())
        if not carrier_data:
            print(f'No carrier found while searching the DB for: {carrier_id}')
            return await ctx.send(f'Sorry, could not find a carrier for the ID data in DB: {carrier_id}.')

        if carrier_data.discord_unload_notification and carrier_data.discord_unload_notification != 'NULL':
            # If we have a notification, remove it.
            print(f'Deleting the wine carrier unload notification for: {carrier_id}.')
            wine_alert_channel = bot.get_channel(get_discord_booze_unload_channel())
            msg = await wine_alert_channel.fetch_message(carrier_data.discord_unload_notification)
            # Now delete it in the database

            try:
                carrier_db_lock.acquire()
                data = (f'%{carrier_id}%',)
                carrier_db.execute('''
                    UPDATE boozecarriers
                    SET discord_unload_in_progress=NULL
                    WHERE carrierid LIKE (?)
                ''', data)
                carriers_conn.commit()
            finally:
                carrier_db_lock.release()

            await msg.delete()
            response = f'Removed the unload notification for {carrier_id}'
            print(f'Deleted the carrier discord notification for carrier: {carrier_id}')
        else:
            response = f'Sorry {ctx.author}, we have no carrier unload notification found in the database for ' \
                       f'{carrier_id}.'
            print(f'No discord alert found for carrier, {carrier_id}. It likely ran an untracked market.')

        return await ctx.send(content=response)
