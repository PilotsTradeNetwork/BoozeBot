import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from ptn.boozebot.BoozeCarrier import BoozeCarrier
from ptn.boozebot.constants import bot_guild_id, get_custom_assassin_id, bot, get_discord_booze_unload_channel
from ptn.boozebot.database.database import carrier_db, carrier_db_lock, carriers_conn


class Unloading(commands.Cog):
    def __init__(self):
        """
        This class is a collection functionality for tracking a booze cruise unload operations
        """

    @commands.has_any_role('Carrier Owner', 'Admin', 'Auxiliary Carrier')
    @cog_ext.cog_slash(name="BoozeCruiseUnload", guild_ids=[bot_guild_id()],
                       description="Creates a new unload operation in this channel.")
    async def booze_unload_market(self, ctx: SlashContext):
        """
        Command to set a booze cruise market unload. Generates a default message in the channel that it ran in.

        :param SlashContext ctx: The discord slash context.
        :returns: A discord embed with some emoji's
        """
        print(f'User {ctx.author} requested a new booze unload in channel: {ctx.channel}.')

        embed = discord.Embed(title='A new market opening is happening.')
        embed.add_field(name='If you are INTENDING TO BUY, please react with:', value=':airplane_arriving:',
                        inline=True)
        embed.add_field(name='Once you are DOCKED react with:', value=f'<:Assassin:{str(get_custom_assassin_id())}>',
                        inline=True)
        embed.add_field(name='Once you PURCHASE WINE, react with:', value=':wine_glass:', inline=True)
        embed.set_footer(text='Market will be opened once we have aligned the number of commanders. All 3 emoji '
                              'counts should match by the end.')

        message = await ctx.send(embed=embed)
        await message.add_reaction('🛬')
        await message.add_reaction(f'<:Assassin:{str(get_custom_assassin_id())}>')
        await message.add_reaction('🍷')

    @commands.has_any_role('Carrier Owner', 'Admin', 'Auxiliary Carrier')
    @cog_ext.cog_slash(name="BoozeCruiseMarketClosed", guild_ids=[bot_guild_id()],
                       description="Sends a dummy message to indicate you have closed your market. Command sent in "
                                   "active channel.")
    async def booze_market_closed(self, ctx: SlashContext):
        print(f'User {ctx.author} requested a to close the market in channel: {ctx.channel}.')
        embed = discord.Embed(title='The market is now closed.')
        embed.add_field(name='Yo Ho Ho, this sale is currently done.', value='Arrrrrrr!')
        embed.set_footer(text='Notified by your friendly neighbourhood pirate bot.')
        message = await ctx.send(embed=embed)
        await message.add_reaction('🏴‍☠️')

    @commands.has_any_role('Carrier Owner', 'Admin', 'Sommelier')
    @cog_ext.cog_slash(name='WineUnload', guild_ids=[bot_guild_id()],
                       description='Posts a new wine unloading notification.')
    async def new_carrier_unload(self, ctx: SlashContext, carrier_id, planetary_body, timed_market: bool,
                                 unload_channel=None
                                 ):
        """
        Posts a wine unload request to the unloading channel.

        :param SlashContext ctx: The discord slash context.
        :param str carrier_id: The carrier ID string
        :param str planetary_body: Where is the carrier? Star, P1 etc?
        :param bool timed_market: Is the carrier running timed market openings, True or False.
        :param str unload_channel: The discord unload channel. Required if using timed market openings so we can
            point the user where to go.
        :returns: A message to the user
        :rtype: Union[discord.Message, dict]
        """
        print(f'User {ctx.author} has flagged a new overall unload operation for carrier: {carrier_id} using unload '
              f'channel: {unload_channel} using timed markets: {timed_market}.')

        if timed_market and not unload_channel:
            return await ctx.send('Sorry, to run a timed market we need an unload channel.')

        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )

        # We will only get a single entry back here as the carrierid is a unique field.
        carrier_data = BoozeCarrier(carrier_db.fetchone())
        if not carrier_data:
            return await ctx.send(f'Sorry, could not find a carrier for the data: {carrier_id}.')

        unload_alert_channel = bot.get_channel(get_discord_booze_unload_channel())
        if carrier_data.discord_unload_notification:
            print(f'Sorry, carrier {carrier_data.carrier_identifier} is already on a wine unload.')
            return await ctx.send(f'Carrier: {carrier_data.carrier_name} ({carrier_data.carrier_identifier}) is '
                                  f'already unloading wine. Check the notification in {unload_channel}.')

        print(f'Starting to post un-load operation for carrier: {carrier_data}')
        message_send = await ctx.send("**Sending to Discord...**")

        market_conditions = 'Timed Openings' if timed_market else f'{carrier_data.platform} Squadron and Friends'

        # Only in the case of timed openings does a channel make sense.
        unload_tracking = f' Tracked in {unload_channel}.' if timed_market else ''

        wine_load_embed = discord.Embed(title='Wine unload notification.',
                                        description=f'Carrier {carrier_data.carrier_name} ('
                                                    f'**{carrier_data.carrier_identifier}**) is currently unloading '
                                                    f'**{carrier_data.wine_total}** tonnes of wine from "'
                                                    f'**{planetary_body}**".\n Running: {market_conditions}.'
                                                    f'{unload_tracking}'
                                        )
        wine_load_embed.set_footer(text='Please react with 💯 once completed.')
        wine_unload_alert = await unload_alert_channel.send(embed=wine_load_embed)
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
                SET discord_unload=?
                WHERE carrierid LIKE (?)
            ''', data)
            carriers_conn.commit()
        finally:
            carrier_db_lock.release()
        print(f'Discord alert ID written to database for {carrier_data.carrier_identifier}')

        return await ctx.send(f'Wine unload requested by {ctx.author} for {carrier_id} processed successfully. '
                              f'Market: {market_conditions}. {unload_tracking}'
                              )
