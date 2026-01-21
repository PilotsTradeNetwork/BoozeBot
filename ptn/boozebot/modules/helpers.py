"""
A module for helper functions called by other modules.

Depends on: constants, ErrorHandler, database
"""

import datetime
import functools

# import discord.py
import discord
from discord import app_commands
from discord.ext import commands
from ptn_utils.global_constants import (
    CHANNEL_BC_BOOZE_CRUISE_CHAT,
    EMBED_COLOUR_ERROR,
    ROLE_PILOT,
    ROLE_SOMM,
    ROLE_CONN,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import bot
from ptn.boozebot.modules.ErrorHandler import CommandChannelError, CommandRoleError

logger = get_logger("boozebot.modules.helpers")


async def checkroles_actual(interaction: discord.Interaction, permitted_role_ids):
    """
    Check if the user has at least one of the permitted roles to run a command
    """
    try:
        logger.debug(f"checkroles_actual called for user {interaction.user} ({interaction.user.id})")
        author_roles = interaction.user.roles
        permitted_roles = [await bot.get_or_fetch.role(role) for role in permitted_role_ids]
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
    ):
        permission, permitted_roles = await checkroles_actual(interaction, permitted_role_ids)
        logger.debug(f"Permission result from checkroles_actual: {permission}")
        if not permission:
            role_list = []
            for role in permitted_role_ids:
                role_list.append(f"<@&{role}> ")
                formatted_role_list = " • ".join(role_list)
            logger.warning(
                f"User {interaction.user} ({interaction.user.id}) lacks required roles for command. Required: {formatted_role_list}"
            )
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
            permitted_channels = [await bot.get_or_fetch.channel(id) for id in permitted_channel]
        else:
            permitted_channels = [await bot.get_or_fetch.channel(permitted_channel)]

        channel_list = []
        for channel in permitted_channels:
            channel_list.append(f"<#{channel.id}>")
        formatted_channel_list = " • ".join(channel_list)

        logger.debug(f"Permitted channels: {[ch.name for ch in permitted_channels if ch]}")

        permission = True if any(channel == ctx.channel for channel in permitted_channels) else False
        if not permission:
            # problem, wrong channel, no progress
            logger.warning(
                f"Command run in wrong channel. Current: {ctx.channel.name}, Required: {formatted_channel_list}"
            )
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
        permitted = await bot.get_or_fetch.channel(permitted_channel)
        logger.debug(f"Permitted channel: {permitted.name if permitted else 'None'} ({permitted_channel})")

        if ctx.channel != permitted:
            # problem, wrong channel, no progress
            logger.warning(
                f"Text command run in wrong channel. Current: {ctx.channel.name}, Required: {permitted.name if permitted else permitted_channel}"
            )
            embed = discord.Embed(
                description=f"Sorry, you can only run this command out of: <#{permitted_channel}>.",
                color=EMBED_COLOUR_ERROR,
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
        bc_chat_channel = await bot.get_or_fetch.channel(CHANNEL_BC_BOOZE_CRUISE_CHAT)
        pilot_role = await bot.get_or_fetch.role(ROLE_PILOT)

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


def is_staff(user: discord.Member) -> bool:
    """
    Check if a user is wine staff based on their roles.

    :param discord.Member user: The user to check.
    :returns: True if the user is wine staff, False otherwise.
    """

    logger.debug(f"Checking if user {user} ({user.id}) is wine staff.")
    staff_roles = {
        ROLE_SOMM,
        ROLE_CONN,
        *any_council_role,
        *any_moderation_role,
    }

    is_wine_staff = any(role.id in staff_roles for role in user.roles)
    logger.debug(f"User {user} wine staff status: {is_wine_staff}")
    return is_wine_staff
