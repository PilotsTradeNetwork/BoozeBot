# libraries
import os
import random
import sys
import datetime
import logging

# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands, tasks
from discord import app_commands, NotFound

# local constants
from ptn.boozebot.constants import bot_guild_id, TOKEN, get_bot_control_channel, get_primary_booze_discussions_channel, \
    server_council_role_ids, bot, error_gifs, ping_response_messages, server_sommelier_role_id
from ptn.boozebot._metadata import __version__

# local modules
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, GenericError, CustomError, on_generic_error, TimeoutError
from ptn.boozebot.modules.helpers import bot_exit, check_roles, check_command_channel
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_lock, pirate_steve_conn

"""
A primitive global error handler for text commands.

returns: error message to user and log
"""

@bot.listen()
async def on_command_error(ctx, error):
    gif = random.choice(error_gifs)
    if isinstance(error, commands.BadArgument):
        await ctx.send(f'**Bad argument!** {error}')
        print({error})
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("**Invalid command.**")
        print({error})
    elif isinstance(error, commands.MissingRequiredArgument):
        print({error})
        await ctx.send("**Sorry, that didn't work**.\n• Check you've included all required arguments. Use `/pirate_steve_help <command>` for details."
                       "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation"
                       " marks are of the same type, i.e. all straight or matching open/close smartquotes.")
    elif isinstance(error, commands.MissingPermissions):
        print({error})
        await ctx.send('**You must be a Carrier Owner to use this command.**')
    else:
        await ctx.send(gif)
        print({error})
        await ctx.send(f"Sorry, that didn't work: {error}")

"""
LISTENERS
on_ready
- Logs it and posts message to bot channel
- Starts PH check loop
- Starts stat update loop
- Sets bot activity status

on_disconnect
- Logs the disconnect

on_message
- If pinged in #booze-cruise-chat respond

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

    # custom global error handler
    # attaching the handler when the cog is loaded
    # and storing the old handler
    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    # detaching the handler when the cog is unloaded
    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error


    """
    LISTENERS
    
    """

    @commands.Cog.listener()
    async def on_ready(self):
        """
        We create a listener for the connection event.

        :returns: None
        """
        print(f'{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}')
        try:
            bot_channel = self.bot.get_channel(get_bot_control_channel())
            await bot_channel.send(f'{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}')
            await bot_channel.send('https://tenor.com/view/minecraft-movie-minecraft-a-minecraft-movie-jack-black-i-am-steve-gif-13691645871022200802')
        except AttributeError as e:
            logging.error(f"Error in on_ready: {e}")

        print('Starting the holiday checker.')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == get_primary_booze_discussions_channel():
            if self.bot.user.mentioned_in(message) and message.author != self.bot.user:

                print(f'{message.author} mentioned PirateSteve.')
                
                await message.channel.send(
                    random.choice(ping_response_messages).format(message_author_id=message.author.id), reference=message
                )

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
        await ctx.send(f"**Avast Ye Landlubber! {self.bot.user.name} is here!**")

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
        await ctx.send(f"Ahoy! k thx bye")
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
                bot.tree.copy_global_to(guild=discord.Object(bot_guild_id()))
                await bot.tree.sync(guild=discord.Object(bot_guild_id()))
                print("Synchronized bot tree.")
                await ctx.send("Synchronized bot tree.")
            except Exception as e:
                print(f"Tree sync failed: {e}.")
                return await ctx.send(f"Failed to sync bot tree: {e}")
