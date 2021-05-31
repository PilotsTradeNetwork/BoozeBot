import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext

from ptn.boozebot.constants import bot_guild_id, get_custom_assassin_id


class Unloading(commands.Cog):
    def __init__(self):
        """
        This class is a collection functionality for tracking a booze cruise unload operations
        """

    @cog_ext.cog_slash(name="booze_cruise_unload", guild_ids=[bot_guild_id()],
                       description="Creates a new unload operation in this channel.")
    async def booze_unload_market(self, ctx: SlashContext):
        """
        Command to set a booze cruise market unload. Generates a default message in the channel that it ran in.

        :param SlashContext ctx: The discord slash context.
        :returns: A discord embed with some emoji's
        """
        print(f'User {ctx.author} requested a new booze unload in channel: {ctx.channel}.')

        embed = discord.Embed(title='A new market opening is happening.')
        embed.add_field(name='If you are INBOUND, please react with:', value=':airplane_arriving:', inline=True)
        embed.add_field(name='Once you are DOCKED react with:', value=':Assassin:', inline=True)
        embed.add_field(name='Once you PURCHASE WINE, react with:', value=':wine_glass:', inline=True)
        embed.set_footer(text='Market will be opened once we have aligned the number of commanders.')

        message = await ctx.send(embed=embed)
        await message.add_reaction('🛬')
        await message.add_reaction(str(get_custom_assassin_id()))
        await message.add_reaction('🍷')
