import os
import random
import sys

import discord
from discord import Activity, ActivityType
from discord.ext import commands

from ptn.boozebot import constants
# from discord_slash.utils.manage_commands import remove_all_commands

from ptn.boozebot.commands.DatabaseInteraction import DatabaseInteraction
from ptn.boozebot.commands.ErrorHandler import on_app_command_error
from ptn.boozebot.commands.Helper import check_roles
from ptn.boozebot.commands.PublicHoliday import PublicHoliday
from ptn.boozebot.constants import bot_guild_id, TOKEN, get_bot_control_channel, get_primary_booze_discussions_channel, \
    server_admin_role_id, server_mod_role_id
from ptn.boozebot._metadata import __version__
from ptn.boozebot.bot import bot

class DiscordBotCommands(commands.Cog):
    def __init__(self, bot):
        """
        This class is a collection of generic blocks used throughout the booze bot.

        :param discord.ext.commands.Bot bot: The discord bot object
        """
        self.bot = bot
        self.summon_message_ids = {}

    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error

    @commands.Cog.listener()
    async def on_ready(self):
        """
        We create a listener for the connection event.

        :returns: None
        """
        print(f'{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}')
        bot_channel = self.bot.get_channel(get_bot_control_channel())
        await bot_channel.send(f'{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}')
        print('Starting the holiday checker.')
        PublicHoliday.public_holiday_loop.start()
        print('Starting the pinned message checker')
        DatabaseInteraction().periodic_stat_update.start()
        await self.bot.change_presence(
            activity=discord.Activity(type=3, name='the Sidewinders landing at Rackhams Peak.')
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == get_primary_booze_discussions_channel():
            if self.bot.user.mentioned_in(message) and message.author != self.bot.user:

                print(f'{message.author} mentioned PirateSteve.')

                # list of responses
                responses = [
                    f'Yarrr, <@{message.author.id}>, you summoned me?',
                    'https://tenor.com/view/hello-there-baby-yoda-mandolorian-hello-gif-20136589',
                    'https://tenor.com/view/hello-sexy-hi-hello-mr-bean-gif-13830351',
                    'https://tenor.com/view/hello-whale-there-hi-gif-5551502',
                    'https://tenor.com/view/funny-animals-gif-13669907'
                ]
                await message.channel.send(
                    random.choice(responses), reference=message
                )

    @commands.Cog.listener()
    async def on_disconnect(self):
        print(f'Booze bot has disconnected from discord server, booze bot version: {__version__}.')

    @commands.command(name='ping', help='Ping the bot')
    @commands.has_role('Admin')
    async def ping(self, ctx):
        """
        Ping the bot and get a response

        :param discord.Context ctx: The Discord context object
        :returns: None
        """
        await ctx.send(f"**Avast Ye Landlubber! {self.bot.user.name} is here!**")

    # quit the bot
    @commands.command(name='exit', help="Stops the bots process on the VM, ending all functions.")
    @commands.has_role('Admin')
    async def exit(self, ctx):
        """
        Stop-quit command for the bot.

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        print(f'User {ctx.author} requested to exit')
        await (self.bot.user.id, TOKEN, [bot_guild_id()])
        await ctx.send(f"Ahoy! k thx bye")
        await sys.exit("User requested exit.")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """
        A listener that fires off on a particular error case.

        :param discord.ext.commands.Context ctx: The discord context object
        :param discord.ext.commands.errors error: The error object
        :returns: None
        """
        if isinstance(error, commands.BadArgument):
            await ctx.send('**Bad argument!**')
        elif isinstance(error, commands.CommandNotFound):
            await ctx.send("**Invalid command.**")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('**Please include all required parameters.** Use b.help <command> for details.')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('**You must be a Carrier Owner to use this command.**')
        else:
            await ctx.send(f"Sorry, that didn't work. Check your syntax and permissions, error: {error}")

    @commands.command(name='update', help="Restarts the bot.")
    @commands.has_role('Admin')
    async def update(self, ctx):
        """
        Restarts the application for updates to take affect on the local system.
        """
        print(f'Restarting the application to perform updates requested by {ctx.author}')
        os.execv(sys.executable, ['python'] + sys.argv)

    @commands.command(name='version', help="Logs the bot version")
    @commands.has_role('Admin')
    async def version(self, ctx):
        """
        Logs the bot version

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        print(f'User {ctx.author} requested the version: {__version__}.')
        await ctx.send(f"Avast Ye Landlubber! {self.bot.user.name} is on version: {__version__}.")

    @commands.command(name='sync', help='Synchronise modbot interactions with server')
    @check_roles(constants.any_elevated_role)
    async def sync(self, ctx):
        print(f"Interaction sync called from {ctx.author.display_name}")
        async with ctx.typing():
            try:
                bot.tree.copy_global_to(guild=ctx.guild)
                await bot.tree.sync(guild=ctx.guild)
                print("Synchronised bot tree.")
                await ctx.send("Synchronised bot tree.")
            except Exception as e:
                print(f"Tree sync failed: {e}.")
                return await ctx.send(f"Failed to sync bot tree: {e}")
