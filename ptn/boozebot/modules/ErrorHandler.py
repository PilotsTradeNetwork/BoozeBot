"""
ErrorHandler.py

Our custom global error handler for the bot.

Depends on: constants
"""

import logging

# import discord.py
import discord
# import local constants
import ptn.boozebot.constants as constants
from discord import Interaction, app_commands, InteractionResponded
from discord.app_commands import AppCommandError
from ptn.boozebot.constants import bot_spam_channel
from ptn.boozebot.modules.helpers import get_channel


# custom errors
class CommandChannelError(app_commands.CheckFailure):  # channel check error
    def __init__(self, permitted_channel, formatted_channel_list):
        self.permitted_channel = permitted_channel
        self.formatted_channel_list = formatted_channel_list
        super().__init__(permitted_channel, formatted_channel_list, "Channel check error raised")

    pass


class CommandRoleError(app_commands.CheckFailure):  # role check error
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


class SilentError(Exception):  # generic error
    pass


class GenericError(Exception):  # generic error
    pass


class CustomError(
    Exception
):  # an error handler that hides the Exception text from the user, but shows custom text sent from the source instead
    def __init__(self, message, is_private=True):
        self.message = message
        self.is_private = is_private
        super().__init__(self.message, "CustomError raised")



async def on_app_command_error(
    interaction: Interaction, error: AppCommandError
):  # an error handler for discord.py errors
    print(
        f"Error from {interaction.command.name} in {interaction.channel.name} called by {interaction.user.display_name}: {error}"
    )

    try:
        if isinstance(error, CommandChannelError):
            print("Channel check error raised")
            formatted_channel_list = error.formatted_channel_list

            embed = discord.Embed(
                description=f"Sorry, you can only run this command out of: {formatted_channel_list}",
                color=constants.EMBED_COLOUR_ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, CommandRoleError):
            print("Role check error raised")
            permitted_roles = error.permitted_roles
            formatted_role_list = error.formatted_role_list
            if len(permitted_roles) > 1:
                embed = discord.Embed(
                    description=f"**Permission denied**: You need one of the following roles to use this command:\n{formatted_role_list}",
                    color=constants.EMBED_COLOUR_ERROR,
                )
            else:
                embed = discord.Embed(
                    description=f"**Permission denied**: You need the following role to use this command:\n{formatted_role_list}",
                    color=constants.EMBED_COLOUR_ERROR,
                )
            print("notify user")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, CustomError):
            message = error.message
            is_private = error.is_private
            print(f"Raised CustomError from {error} with message {message}")
            embed = discord.Embed(description=f"❌ {message}", color=constants.EMBED_COLOUR_ERROR)
            if is_private:  # message should be ephemeral
                try:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                except InteractionResponded:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:  # message should be public - use for CCO commands
                try:
                    await interaction.response.send_message(embed=embed)
                except InteractionResponded:
                    await interaction.followup.send(embed=embed)

        elif isinstance(error, GenericError):
            print(f"Generic error raised: {error}")
            embed = discord.Embed(description=f"❌ {error}", color=constants.EMBED_COLOUR_ERROR)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)

        else:
            print("Other type error message raised")
            logging.error(f"Unhandled Error: {error}")
            embed = discord.Embed(description=f"❌ Unhandled Error: {error}", color=constants.EMBED_COLOUR_ERROR)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        print(f"An error occurred in the error handler (lol): {e}")
