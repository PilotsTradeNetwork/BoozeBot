"""
A module for helper functions called by other modules.

Depends on: constants, ErrorHandler, database
"""

# import libraries
import sys
import datetime
import functools

# import discord.py
import discord
from discord import Interaction, app_commands
from discord.errors import HTTPException, Forbidden, NotFound
from discord.ext import commands

# import local constants
import ptn.boozebot.constants as constants
from ptn.boozebot.constants import bot, get_primary_booze_discussions_channel, get_pilot_role_id, bot_guild_id

# import local modules
from ptn.boozebot.modules.ErrorHandler import CommandChannelError, CommandRoleError, CustomError, on_generic_error


# trio of helper functions to check a user's permission to run a command based on their roles, and return a helpful error if they don't have the correct role(s)
def getrole(ctx, id): # takes a Discord role ID and returns the role object
    role = discord.utils.get(ctx.guild.roles, id=id)
    return role

async def checkroles_actual(interaction: discord.Interaction, permitted_role_ids):
    try:
        """
        Check if the user has at least one of the permitted roles to run a command
        """
        print(f"checkroles called.")
        author_roles = interaction.user.roles
        permitted_roles = [getrole(interaction, role) for role in permitted_role_ids]
        print(author_roles)
        print(permitted_roles)
        permission = True if any(x in permitted_roles for x in author_roles) else False
        print(permission)
        return permission, permitted_roles
    except Exception as e:
        print(e)
    return permission


def check_roles(permitted_role_ids):
    async def checkroles(interaction: discord.Interaction): # TODO convert messages to custom error handler, make work with text commands
        permission, permitted_roles = await checkroles_actual(interaction, permitted_role_ids)
        print("Inherited permission from checkroles")
        if not permission: # raise our custom error to notify the user gracefully
            role_list = []
            for role in permitted_role_ids:
                role_list.append(f'<@&{role}> ')
                formatted_role_list = " • ".join(role_list)
            try:
                raise CommandRoleError(permitted_roles, formatted_role_list)
            except CommandRoleError as e:
                print(e)
                raise
        return permission
    return app_commands.check(checkroles)


# helper for channel permission check
def getchannel(id):
    channel = bot.get_channel(id)
    return channel


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
            permitted_channels = [getchannel(id) for id in permitted_channel]
        else:
            permitted_channels = [getchannel(permitted_channel)]

        channel_list = []
        for channel in permitted_channels:
            channel_list.append(f'<#{channel.id}>')
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
        permitted = bot.get_channel(permitted_channel)
        if ctx.channel != permitted:
            # problem, wrong channel, no progress
            embed=discord.Embed(description=f"Sorry, you can only run this command out of: <#{permitted_channel}>.", color=constants.EMBED_COLOUR_ERROR)
            await ctx.channel.send(embed=embed)
            return False
        else:
            return True
    return commands.check(check_text_channel)


# function to stop and quit
def bot_exit():
    sys.exit("User requested exit.")
    
    
def bc_channel_status():
    """
    Check if the booze cruise channels are open to pilot or not.
    """
    try:
        guild = bot.get_guild(bot_guild_id())
        bc_chat_channel = guild.get_channel(get_primary_booze_discussions_channel())
        pilot_role = guild.get_role(get_pilot_role_id())
        
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
            loop.last_run_time = datetime.datetime.now(datetime.UTC)
            return result

        return wrapper
    return decorator