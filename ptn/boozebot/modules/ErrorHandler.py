"""
ErrorHandler.py

Our custom global error handler for the bot.

Depends on: constants
"""

import random
import logging

# import discord.py
import discord
from discord.ext import commands
from discord import Interaction, app_commands
from discord.app_commands import AppCommandError

# import local constants
from ptn.boozebot.constants import error_gifs, EMBED_COLOUR_ERROR

# custom errors
class CommandChannelError(app_commands.CheckFailure): # channel check error
    def __init__(self, permitted_channel, formatted_channel_list):
        self.permitted_channel = permitted_channel
        self.formatted_channel_list = formatted_channel_list
        super().__init__(permitted_channel, formatted_channel_list, "Channel check error raised")
    pass

class CommandRoleError(app_commands.CheckFailure): # role check error
    def __init__(self, permitted_roles, formatted_role_list):
        self.permitted_roles = permitted_roles
        self.formatted_role_list = formatted_role_list
        super().__init__(permitted_roles, formatted_role_list, "Role check error raised")
    pass

class AsyncioTimeoutError(Exception):
    def __init__(self, message, is_private=True):
        self.message = message
        self.is_private = is_private
    pass

class SilentError(Exception): # generic error
    pass

class GenericError(Exception): # generic error
    pass

class CustomError(Exception): # an error handler that hides the Exception text from the user, but shows custom text sent from the source instead
    def __init__(self, message, is_private=True):
        self.message = message
        self.is_private = is_private
        super().__init__(self.message, "CustomError raised")


# Error handler for command error
async def on_generic_error(ctx: commands.Context, error):
    gif = random.choice(error_gifs)
    if isinstance(error, commands.BadArgument):
        await ctx.send(f'**Bad argument!** {error}')
        print({error})
    elif isinstance(error, commands.CommandNotFound):
        #await ctx.send("**Invalid command.**")
        print({error})
    elif isinstance(error, commands.MissingRequiredArgument):
        print({error})
        await ctx.send("**Sorry, that didn't work**.\n• Check you've included all required arguments. Use `/pirate_steve_help` for details."
                       "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation"
                       " marks are of the same type, i.e. all straight or matching open/close smartquotes.")
    elif isinstance(error, commands.MissingAnyRole):
        print({error})
        roles = ', '.join([ctx.guild.get_role(role_id).name for role_id in error.missing_roles])
        await ctx.send(f'**You must have one of the following roles to use this command:** {roles}')
    else:
        await ctx.send(gif)
        print({error})
        await ctx.send(f"Sorry, that didn't work: {error}")


# Error handler for all app commands (slash & ctx menus)
async def on_app_command_error(interaction: Interaction, error: AppCommandError):
    print(f"Error from {interaction.command.name} in {interaction.channel.name} called by {interaction.user.display_name}: {error}")

    try:
        is_private = True
        
        if isinstance(error, CommandChannelError):
            print("Channel check error raised")
            formatted_channel_list = error.formatted_channel_list
            description=f"Sorry, you can only run this command out of: {formatted_channel_list}"

        elif isinstance(error, CommandRoleError):
            print("Role check error raised")
            permitted_roles = error.permitted_roles
            formatted_role_list = error.formatted_role_list
            if len(permitted_roles)>1:
                description=f"**Permission denied**: You need one of the following roles to use this command:\n{formatted_role_list}"
            else:
                description=f"**Permission denied**: You need the following role to use this command:\n{formatted_role_list}"

        elif isinstance(error, CustomError):
            message = error.message
            is_private = error.is_private
            description=f"❌ {message}"

        elif isinstance(error, GenericError):
            print(f"Generic error raised: {error}")
            description = f"❌ {error}"

        else:
            print("Other type error message raised")
            logging.error(f"Unhandled Error: {error}")
            description = f"❌ Unhandled Error: {error}"

        
        embed = discord.Embed(
            description=description,
            color=EMBED_COLOUR_ERROR
        )
        
        try:
            await interaction.response.send_message(embed=embed, ephemeral=is_private)
        except discord.DiscordException: # response already sent, followup
            await interaction.followup.send(embed=embed, ephemeral=is_private)

    except Exception as e:
        print(f"An error occurred in the error handler (lol): {e}")