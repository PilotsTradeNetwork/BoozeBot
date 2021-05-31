import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from ptn.boozebot.constants import bot_guild_id, get_custom_assassin_id


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
