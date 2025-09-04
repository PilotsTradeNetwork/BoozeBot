# libraries
import os
import sys
import logging

# discord.py
import discord
from discord.ext import commands

# local constants
from ptn.boozebot.constants import bot_guild_id, get_bot_control_channel, \
    server_council_role_ids, bot, server_sommelier_role_id, I_AM_STEVE_GIF
from ptn.boozebot._metadata import __version__

# Import command groups
from ptn.boozebot.modules.CommandGroups import somm_command_group, conn_command_group, wine_carrier_command_group, everyone_command_group

"""
LISTENERS
on_ready
- Logs it and posts message to bot channel
- Starts PH check loop
- Starts stat update loop
- Sets bot activity status

on_disconnect
- Logs the disconnect

ADMIN COMMANDS
b/ping - admin
b/update - admin
b/exit - admin
b/version - admin
b/sync - admin
"""

class DiscordBotCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    """
    LISTENERS
    
    """

    @commands.Cog.listener()
    async def on_ready(self):
        """
        We create a listener for the connection event.

        :returns: None
        """
        
        # Register command groups
        self.bot.tree.add_command(somm_command_group.register_commands(bot.cogs))
        self.bot.tree.add_command(conn_command_group.register_commands(bot.cogs))
        self.bot.tree.add_command(wine_carrier_command_group.register_commands(bot.cogs))
        self.bot.tree.add_command(everyone_command_group.register_commands(bot.cogs))
        
        print(f'{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}')
        try:
            bot_channel = self.bot.get_channel(get_bot_control_channel())
            embed = discord.Embed(description=f"{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}")
            embed.set_image(url=I_AM_STEVE_GIF)
            await bot_channel.send(embed=embed)
        except AttributeError as e:
            logging.error(f"Error in on_ready: {e}")

        print('Starting the holiday checker.')

    @commands.Cog.listener()
    async def on_disconnect(self):
        print(f'Booze bot has disconnected from discord server, booze bot version: {__version__}.')

    """
    ADMIN COMMANDS
    """

    @commands.command(name='ping', help='Ping the bot')
    @commands.has_any_role(*server_council_role_ids(), server_sommelier_role_id())

    async def ping(self, ctx):
        """
        Ping the bot and get a response

        :param discord.Context ctx: The Discord context object
        :returns: None
        """
        embed = discord.Embed(description=f"**Avast Ye Landlubber! {self.bot.user.name} is here!**")
        embed.set_image(url=I_AM_STEVE_GIF)
        await ctx.send(embed=embed)

    # quit the bot
    @commands.command(name='exit', help="Stops the bots process on the VM, ending all functions.")
    @commands.has_any_role(*server_council_role_ids())
    async def exit(self, ctx):
        """
        Stop-quit command for the bot.

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        print(f'User {ctx.author} requested to exit')
        await ctx.send("Ahoy! k thx bye")
        await sys.exit("User requested exit.")

    @commands.command(name='update', help="Restarts the bot.")
    @commands.has_any_role(*server_council_role_ids())
    async def update(self, ctx):
        """
        Restarts the application for updates to take affect on the local system.
        """
        print(f'Restarting the application to perform updates requested by {ctx.author}')
        await ctx.send(f"Restarting. {ctx.author}")
        os.execv(sys.executable, ['python'] + sys.argv)

    @commands.command(name='version', help="Logs the bot version")
    @commands.has_any_role(*server_council_role_ids())
    async def version(self, ctx):
        """
        Logs the bot version

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        print(f'User {ctx.author} requested the version: {__version__}.')
        await ctx.send(f"Avast Ye Landlubber! {self.bot.user.name} is on version: {__version__}.")
        
    @commands.command(name='sync', help='Synchronize bot interactions with server')
    @commands.has_any_role(*server_council_role_ids())
    async def sync(self, ctx):
        print(f"Interaction sync called from {ctx.author.display_name}")
        async with ctx.typing():
            try:
                guild = discord.Object(bot_guild_id())
                bot.tree.copy_global_to(guild=guild)
                await bot.tree.sync(guild=guild)
                print("Synchronized bot tree.")
                await ctx.send("Synchronized bot tree.")
            except Exception as e:
                print(f"Tree sync failed: {e}.")
                return await ctx.send(f"Failed to sync bot tree: {e}")
