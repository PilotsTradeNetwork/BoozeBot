"""
A module for helper functions called by other modules.

Depends on: constants, ErrorHandler, database
"""

import datetime
import functools
# import libraries
import sys
from typing import Optional

# import discord.py
import discord
# import local constants
import ptn.boozebot.constants as constants
from discord import Emoji, Guild, Member, Role, Thread, User, app_commands
from discord.abc import GuildChannel
from discord.errors import NotFound
from discord.ext import commands
from ptn.boozebot.constants import bot, bot_guild_id, get_pilot_role_id, get_primary_booze_discussions_channel
# import local modules
from ptn.boozebot.modules.ErrorHandler import CommandChannelError, CommandRoleError


async def get_user(user_id: int) -> Optional[User]:
    """Fetch a user from the cache or API."""
    try:
        return bot.get_user(user_id) or await bot.fetch_user(user_id)
    except NotFound:
        return None


async def get_guild(guild: int = bot_guild_id()) -> Optional[Guild]:
    """Return bot guild instance for use in get_member()"""
    return bot.get_guild(guild) or await bot.fetch_guild(guild)


async def get_member(member_id: int) -> Optional[Member]:
    """Fetch a member from the cache or API."""
    guild = await get_guild()
    try:
        return guild.get_member(member_id) or await guild.fetch_member(member_id)
    except NotFound:
        return None


async def get_role(role_id: int) -> Optional[Role]:
    """Fetch a role from the guild."""
    guild = await get_guild()
    try:
        return guild.get_role(role_id) or await guild.fetch_role(role_id)
    except NotFound:
        return None


async def get_channel(channel_id: int) -> Optional[GuildChannel | Thread]:
    """Fetch a channel or thread from the guild."""
    guild = await get_guild()
    try:
        return guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
    except NotFound:
        return None


async def get_emoji(emoji_id: int) -> Optional[Emoji]:
    """Fetch an emoji from the guild."""
    guild = await get_guild()
    try:
        return guild.get_emoji(emoji_id) or await guild.fetch_emoji(emoji_id)
    except NotFound:
        return None


async def checkroles_actual(interaction: discord.Interaction, permitted_role_ids):
    try:
        """
        Check if the user has at least one of the permitted roles to run a command
        """
        print("checkroles called.")
        author_roles = interaction.user.roles
        permitted_roles = [await get_role(role) for role in permitted_role_ids]
        print(author_roles)
        print(permitted_roles)
        permission = True if any(x in permitted_roles for x in author_roles) else False
        print(permission)
        return permission, permitted_roles
    except Exception as e:
        print(e)
    return permission


def check_roles(permitted_role_ids):
    async def checkroles(
        interaction: discord.Interaction,
    ):  # TODO convert messages to custom error handler, make work with text commands
        permission, permitted_roles = await checkroles_actual(interaction, permitted_role_ids)
        print("Inherited permission from checkroles")
        if not permission:  # raise our custom error to notify the user gracefully
            role_list = []
            for role in permitted_role_ids:
                role_list.append(f"<@&{role}> ")
                formatted_role_list = " • ".join(role_list)
            try:
                raise CommandRoleError(permitted_roles, formatted_role_list)
            except CommandRoleError as e:
                print(e)
                raise
        return permission

    return app_commands.check(checkroles)


# decorator for interaction channel checks
def check_command_channel(permitted_channel):
    """
    Decorator used on an interaction to limit it to specified channels
    """

    async def check_channel(ctx):
        """
        Check if the channel the command was run from matches any permitted channels for that command
        """
        print("check_command_channel called")
        if isinstance(permitted_channel, list):
            permitted_channels = [await get_channel(id) for id in permitted_channel]
        else:
            permitted_channels = [await get_channel(permitted_channel)]

        channel_list = []
        for channel in permitted_channels:
            channel_list.append(f"<#{channel.id}>")
        formatted_channel_list = " • ".join(channel_list)

        permission = True if any(channel == ctx.channel for channel in permitted_channels) else False
        if not permission:
            # problem, wrong channel, no progress
            try:
                raise CommandChannelError(permitted_channel, formatted_channel_list)
            except CommandChannelError as e:
                print(e)
                raise
        else:
            return True

    return app_commands.check(check_channel)


# decorator for text command channel checks
def check_text_command_channel(permitted_channel):
    """
    Decorator used on a text command to limit it to a specified channel
    """

    async def check_text_channel(ctx):
        """
        Check if the channel the command was run in, matches the channel it can only be run from
        """
        permitted = await get_channel(permitted_channel)
        if ctx.channel != permitted:
            # problem, wrong channel, no progress
            embed = discord.Embed(
                description=f"Sorry, you can only run this command out of: <#{permitted_channel}>.",
                color=constants.EMBED_COLOUR_ERROR,
            )
            await ctx.channel.send(embed=embed)
            return False
        else:
            return True

    return commands.check(check_text_channel)


# function to stop and quit
def bot_exit():
    sys.exit("User requested exit.")


async def bc_channel_status():
    """
    Check if the booze cruise channels are open to pilot or not.
    """
    try:
        bc_chat_channel = await get_channel(get_primary_booze_discussions_channel())
        pilot_role = await get_role(get_pilot_role_id())

        if bc_chat_channel.permissions_for(pilot_role).view_channel:
            print("Booze Cruise channel is open to pilots.")
            return True

    except Exception as e:
        print(f"Error checking bc channel status: {e}")
        return False


# Decorator to track the last run time of a task
def track_last_run():
    def decorator(coro):
        @functools.wraps(coro)
        async def wrapper(self, *args, **kwargs):
            result = await coro(self, *args, **kwargs)
            loop = getattr(self, coro.__name__)
            loop.last_run_time = datetime.datetime.now(datetime.timezone.utc)
            return result

        return wrapper
    return decorator

async def sync_command_tree():
    bot.tree.copy_global_to(guild=discord.Object(bot_guild_id()))
    await bot.tree.sync(guild=discord.Object(bot_guild_id()))
    print("Synchronized bot tree.")
