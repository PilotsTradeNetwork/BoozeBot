"""
A module for helper functions called by other modules.

Depends on: constants, ErrorHandler, database
"""

import datetime
import functools
# import libraries
import sys
from typing import Optional
from loguru import logger
import logging
import inspect

# import discord.py
import discord
import ptn.boozebot.constants as constants
from discord import Emoji, Guild, Member, Role, Thread, User, app_commands
from discord.abc import GuildChannel
from discord.errors import NotFound
from discord.ext import commands
from ptn.boozebot.constants import bot, bot_guild_id, get_pilot_role_id, get_primary_booze_discussions_channel
from ptn.boozebot.modules.ErrorHandler import CommandChannelError, CommandRoleError


async def get_user(user_id: int) -> Optional[User]:
    """Fetch a user from the cache or API."""
    logger.debug(f"Fetching user with ID: {user_id}")
    try:
        user = bot.get_user(user_id)
        if user:
            logger.debug(f"User found in cache: {user}")
            return user
        user = await bot.fetch_user(user_id)
        logger.debug(f"User fetched from API: {user}")
        return user
    except NotFound:
        logger.warning(f"User with ID {user_id} not found.")
        return None


async def get_guild(guild: int = bot_guild_id()) -> Optional[Guild]:
    """Return bot guild instance for use in get_member()"""
    try:
        guild_instance = bot.get_guild(guild)
        if guild_instance:
            logger.debug(f"Guild found: {guild_instance.name} (ID: {guild_instance.id})")
            return guild_instance
        guild_instance = await bot.fetch_guild(guild)
        logger.debug(f"Guild fetched from API: {guild_instance.name} (ID: {guild_instance.id})")
        return guild_instance
    except NotFound:
        logger.warning(f"Guild with ID {guild} not found.")
        return None


async def get_member(member_id: int) -> Optional[Member]:
    """Fetch a member from the cache or API."""
    logger.debug(f"Fetching member with ID: {member_id}")    
    guild = await get_guild()
    try:
        member = guild.get_member(member_id)
        if member:
            logger.debug(f"Member found in cache: {member}")
            return member
        member = await guild.fetch_member(member_id)
        logger.debug(f"Member fetched from API: {member}")
        return member
    except NotFound:
        logger.warning(f"Member with ID {member_id} not found in guild {guild.name}.")
        return None


async def get_role(role_id: int) -> Optional[Role]:
    """Fetch a role from the guild."""
    logger.debug(f"Fetching role with ID: {role_id}")
    guild = await get_guild()
    try:
        role = guild.get_role(role_id)
        if role:
            logger.debug(f"Role found: {role.name} (ID: {role.id})")
            return role
        role = await guild.fetch_role(role_id)
        logger.debug(f"Role fetched from API: {role.name} (ID: {role.id})")
        return role
    except NotFound:
        logger.warning(f"Role with ID {role_id} not found in guild {guild.name}.")
        return None   


async def get_channel(channel_id: int) -> Optional[GuildChannel | Thread]:
    """Fetch a channel or thread from the guild."""
    logger.debug(f"Fetching channel with ID: {channel_id}")
    guild = await get_guild()
    try:
        channel = guild.get_channel(channel_id)
        if channel:
            logger.debug(f"Channel found: {channel.name} (ID: {channel.id})")
            return channel
        channel = await bot.fetch_channel(channel_id)
        logger.debug(f"Channel fetched from API: {channel.name} (ID: {channel.id})")
        return channel
    except NotFound:
        logger.warning(f"Channel with ID {channel_id} not found in guild {guild.name}.")
        return None


async def get_emoji(emoji_id: int) -> Optional[Emoji]:
    """Fetch an emoji from the guild."""
    logger.debug(f"Fetching emoji with ID: {emoji_id}")
    guild = await get_guild()
    try:
        emoji = guild.get_emoji(emoji_id)
        if emoji:
            logger.debug(f"Emoji found: {emoji.name} (ID: {emoji.id})")
            return emoji
        emoji = await bot.fetch_emoji(emoji_id)
        logger.debug(f"Emoji fetched from API: {emoji.name} (ID: {emoji.id})")
        return emoji
    except NotFound:
        logger.warning(f"Emoji with ID {emoji_id} not found in guild {guild.name}.")
        return None


async def checkroles_actual(interaction: discord.Interaction, permitted_role_ids):
    """
    Check if the user has at least one of the permitted roles to run a command
    """
    try:
        logger.debug(f"checkroles_actual called for user {interaction.user} ({interaction.user.id})")
        author_roles = interaction.user.roles
        permitted_roles = [await get_role(role) for role in permitted_role_ids]
        logger.debug(f"Author roles: {[role.name for role in author_roles]}")
        logger.debug(f"Permitted roles: {[role.name for role in permitted_roles if role]}")
        permission = True if any(x in permitted_roles for x in author_roles) else False
        logger.debug(f"Permission granted: {permission}")
        return permission, permitted_roles
    except Exception as e:
        logger.exception(f"Error in checkroles_actual: {e}")
        return False, []


def check_roles(permitted_role_ids):
    async def checkroles(
        interaction: discord.Interaction,
    ):  # TODO convert messages to custom error handler, make work with text commands
        permission, permitted_roles = await checkroles_actual(interaction, permitted_role_ids)
        logger.debug(f"Permission result from checkroles_actual: {permission}")
        if not permission:  # raise our custom error to notify the user gracefully
            role_list = []
            for role in permitted_role_ids:
                role_list.append(f"<@&{role}> ")
                formatted_role_list = " • ".join(role_list)
            logger.warning(f"User {interaction.user} ({interaction.user.id}) lacks required roles for command. Required: {formatted_role_list}")
            try:
                raise CommandRoleError(permitted_roles, formatted_role_list)
            except CommandRoleError as e:
                logger.debug(f"CommandRoleError raised: {e}")
                raise
        logger.info(f"User {interaction.user} ({interaction.user.id}) has required role permissions.")
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
        logger.debug(f"check_command_channel called for channel {ctx.channel.name} ({ctx.channel.id})")
        if isinstance(permitted_channel, list):
            permitted_channels = [await get_channel(id) for id in permitted_channel]
        else:
            permitted_channels = [await get_channel(permitted_channel)]

        channel_list = []
        for channel in permitted_channels:
            channel_list.append(f"<#{channel.id}>")
        formatted_channel_list = " • ".join(channel_list)
        
        logger.debug(f"Permitted channels: {[ch.name for ch in permitted_channels if ch]}")

        permission = True if any(channel == ctx.channel for channel in permitted_channels) else False
        if not permission:
            # problem, wrong channel, no progress
            logger.warning(f"Command run in wrong channel. Current: {ctx.channel.name}, Required: {formatted_channel_list}")
            try:
                raise CommandChannelError(permitted_channel, formatted_channel_list)
            except CommandChannelError as e:
                logger.debug(f"CommandChannelError raised: {e}")
                raise
        else:
            logger.info(f"Command run in permitted channel: {ctx.channel.name}")
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
        logger.debug(f"check_text_command_channel called for channel {ctx.channel.name} ({ctx.channel.id})")
        permitted = await get_channel(permitted_channel)
        logger.debug(f"Permitted channel: {permitted.name if permitted else 'None'} ({permitted_channel})")
        
        if ctx.channel != permitted:
            # problem, wrong channel, no progress
            logger.warning(f"Text command run in wrong channel. Current: {ctx.channel.name}, Required: {permitted.name if permitted else permitted_channel}")
            embed = discord.Embed(
                description=f"Sorry, you can only run this command out of: <#{permitted_channel}>.",
                color=constants.EMBED_COLOUR_ERROR,
            )
            await ctx.channel.send(embed=embed)
            return False
        else:
            logger.info(f"Text command run in permitted channel: {ctx.channel.name}")
            return True

    return commands.check(check_text_channel)

async def bc_channel_status():
    """
    Check if the booze cruise channels are open to pilot or not.
    """
    logger.debug("Checking booze cruise channel status.")
    try:
        bc_chat_channel = await get_channel(get_primary_booze_discussions_channel())
        pilot_role = await get_role(get_pilot_role_id())
        
        logger.debug(f"Fetched bc_chat_channel and pilot_role. {bc_chat_channel}, {pilot_role}")

        if bc_chat_channel.permissions_for(pilot_role).view_channel:
            logger.info("Booze Cruise channel is open to pilots.")
            return True
        else:
            logger.info("Booze Cruise channel is closed to pilots.")
            return False

    except Exception as e:
        logger.exception(f"Error checking booze cruise channel status: {e}")
        return False


# Decorator to track the last run time of a task
def track_last_run():
    def decorator(coro):
        logger.debug(f"Applying track_last_run decorator to {coro.__name__}")
        @functools.wraps(coro)
        async def wrapper(self, *args, **kwargs):
            logger.debug(f"Executing wrapped coroutine {coro.__name__}")
            result = await coro(self, *args, **kwargs)
            loop = getattr(self, coro.__name__)
            loop.last_run_time = datetime.datetime.now(datetime.timezone.utc)
            logger.debug(f"Updated last_run_time for {coro.__name__} to {loop.last_run_time}")
            return result

        return wrapper
    return decorator
