import sys

import discord
from discord.ext import commands
from ptn_utils.global_constants import CHANNEL_DEV_STEVE_BOT, ROLE_SOMM, any_council_role
from ptn_utils.logger.logger import get_logger

from ptn.boozebot._metadata import __version__
from ptn.boozebot.constants import I_AM_STEVE_GIF, bot

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

logger = get_logger("boozebot.commands.discord")


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
        logger.info(f"{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}")
        try:
            bot_channel = await bot.get_or_fetch.channel(CHANNEL_DEV_STEVE_BOT)
            embed = discord.Embed(
                description=f"{self.bot.user.name} has connected to Discord server Booze bot version: {__version__}"
            )
            logger.debug("Sending on_ready message to bot control channel.")
            embed.set_image(url=I_AM_STEVE_GIF)
            await bot_channel.send(embed=embed)
        except AttributeError as e:
            logger.exception(f"Error in on_ready: {e}")

    @commands.Cog.listener()
    async def on_disconnect(self):
        logger.warning(f"Booze bot has disconnected from discord server, booze bot version: {__version__}.")

    """
    ADMIN COMMANDS
    """

    @commands.command(name="ping", help="Ping the bot")
    @commands.has_any_role(*any_council_role, ROLE_SOMM)
    async def ping(self, ctx):
        """
        Ping the bot and get a response

        :param discord.Context ctx: The Discord context object
        :returns: None
        """
        logger.info(f"Ping command called by {ctx.author}.")
        embed = discord.Embed(
            description=f"**Avast Ye Landlubber! {self.bot.user.name} version {__version__} is here!**"
        )
        embed.set_image(url=I_AM_STEVE_GIF)
        await ctx.send(embed=embed)
        logger.debug(f"Ping response sent to {ctx.author}.")

    # quit the bot
    @commands.command(name="exit", help="Stops the bots process on the VM, ending all functions.")
    @commands.has_any_role(*any_council_role)
    async def exit(self, ctx):
        """
        Stop-quit command for the bot.

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        logger.info(f"Exit command called by {ctx.author}.")
        await ctx.send("Ahoy! k thx bye")
        logger.warning("Bot is shutting down per user request.")
        await sys.exit("User requested exit.")

    @commands.command(name="version", help="Logs the bot version")
    @commands.has_any_role(*any_council_role)
    async def version(self, ctx):
        """
        Logs the bot version

        :param discord.ext.commands.Context ctx: The Discord context object
        :returns: None
        """
        logger.info(f"Version command called by {ctx.author}. Version: {__version__}")
        await ctx.send(f"Avast Ye Landlubber! {self.bot.user.name} is on version: {__version__}.")
        logger.debug(f"Version response sent to {ctx.author}.")
