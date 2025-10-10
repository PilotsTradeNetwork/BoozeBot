import logging
import os
import random
import sys

import discord
from discord.ext import commands
from ptn.boozebot._metadata import __version__
from ptn.boozebot.constants import (
    I_AM_STEVE_GIF, bot, error_gifs, get_bot_control_channel, server_council_role_ids, server_sommelier_role_id
)
from ptn.boozebot.modules.ErrorHandler import on_app_command_error
from ptn.boozebot.modules.helpers import get_channel, get_role

"""
A primitive global error handler for text commands.

returns: error message to user and log
"""


@bot.listen()
async def on_command_error(ctx, error):
    gif = random.choice(error_gifs)
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"**Bad argument!** {error}")
        print({error})
    elif isinstance(error, commands.CommandNotFound):
        # await ctx.send("**Invalid command.**")
        print({error})
    elif isinstance(error, commands.MissingRequiredArgument):
        print({error})
        await ctx.send(
            "**Sorry, that didn't work**.\n• Check you've included all required arguments. Use `/pirate_steve_help` for details."
            "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation"
            " marks are of the same type, i.e. all straight or matching open/close smartquotes."
        )
    elif isinstance(error, commands.MissingPermissions):
        print({error})
        await ctx.send("**You must be a Carrier Owner to use this command.**")
    elif isinstance(error, commands.MissingAnyRole):
        print({error})
        roles = ", ".join([await get_role(role_id).name for role_id in error.missing_roles])
        await ctx.send(f"**You must have one of the following roles to use this command:** {roles}")
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
        print(f"{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}")
        try:
            bot_channel = await get_channel(get_bot_control_channel())
            embed = discord.Embed(
                description=f"{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}"
            )
            embed.set_image(url=I_AM_STEVE_GIF)
            await bot_channel.send(embed=embed)
        except AttributeError as e:
            logging.error(f"Error in on_ready: {e}")

        print("Starting the holiday checker.")

    @commands.Cog.listener()
    async def on_disconnect(self):
        print(f"Booze bot has disconnected from discord server, booze bot version: {__version__}.")

    """
    ADMIN COMMANDS
    """

    @commands.command(name="ping", help="Ping the bot")
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
    @commands.command(name="exit", help="Stops the bots process on the VM, ending all functions.")
    @commands.has_any_role(*server_council_role_ids())
    async def exit(self, ctx):
        """
        Stop-quit command for the bot.

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        print(f"User {ctx.author} requested to exit")
        await ctx.send("Ahoy! k thx bye")
        await sys.exit("User requested exit.")

    @commands.command(name="update", help="Restarts the bot.")
    @commands.has_any_role(*server_council_role_ids())
    async def update(self, ctx):
        """
        Restarts the application for updates to take affect on the local system.
        """
        print(f"Restarting the application to perform updates requested by {ctx.author}")
        await ctx.send(f"Restarting. {ctx.author}")
        os.execv(sys.executable, ["python"] + sys.argv)

    @commands.command(name="version", help="Logs the bot version")
    @commands.has_any_role(*server_council_role_ids())
    async def version(self, ctx):
        """
        Logs the bot version

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        print(f"User {ctx.author} requested the version: {__version__}.")
        await ctx.send(f"Avast Ye Landlubber! {self.bot.user.name} is on version: {__version__}.")
