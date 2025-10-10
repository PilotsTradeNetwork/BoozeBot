import logging
import random

import discord

# import local constants
from discord import Interaction, InteractionResponded, app_commands
from discord.app_commands import AppCommandError
from discord.ext import commands
from ptn.boozebot.constants import EMBED_COLOUR_ERROR, error_gifs


# custom errors
class CommandChannelError(app_commands.CheckFailure):
    """Channel check error"""

    def __init__(self, permitted_channel, formatted_channel_list):
        self.permitted_channel = permitted_channel
        self.formatted_channel_list = formatted_channel_list
        super().__init__(permitted_channel, formatted_channel_list, "Channel check error raised")

    pass


class CommandRoleError(app_commands.CheckFailure):
    """Role check error"""
    def __init__(self, permitted_roles, formatted_role_list):
        self.permitted_roles = permitted_roles
        self.formatted_role_list = formatted_role_list
        super().__init__(permitted_roles, formatted_role_list, "Role check error raised")

    pass


class AsyncioTimeoutError(Exception):
    """Timeout error"""

    def __init__(self, message, is_private=True):
        self.message = message
        self.is_private = is_private

    pass



class SilentError(Exception):
    """An error that does not notify the user"""

    pass


class GenericError(Exception):
    """A generic error that notifies the user with the Exception text"""

    pass


class CustomError(Exception):
    """A custom error that notifies the user with a custom message"""

    def __init__(self, message, is_private=True):
        self.message = message
        self.is_private = is_private
        super().__init__(self.message, "CustomError raised")


async def on_text_command_error(ctx: commands.Context, error: Exception):
    """Global error handler for text commands"""
    gif = random.choice(error_gifs)
    print(f"Error from {ctx.command} in {ctx.channel} called by {ctx.author}: {error}")
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"**Bad argument!** {error}")
    elif isinstance(error, commands.CommandNotFound):
        pass # Dont care
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "**Sorry, that didn't work**.\n• Check you've included all required arguments. Use `/pirate_steve_help` for details."
            "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation"
            " marks are of the same type, i.e. all straight or matching open/close smartquotes."
        )
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("**You do not have the required permissions to run this command**")
    elif isinstance(error, commands.MissingAnyRole):
        roles = ", ".join([ctx.guild.get_role(role_id).name for role_id in error.missing_roles])
        await ctx.send(f"**You must have one of the following roles to use this command:** {roles}")
    else:
        await ctx.send(gif)
        await ctx.send(f"Sorry, that didn't work: {error}")


async def on_app_command_error(interaction: Interaction, error: AppCommandError):
    """Global error handler for application commands"""
    print(
        f"Error from {interaction.command.name} in {interaction.channel.name} called by {interaction.user.display_name}: {error}"
    )

    try:
        if isinstance(error, CommandChannelError):
            print("Channel check error raised")
            formatted_channel_list = error.formatted_channel_list

            embed = discord.Embed(
                description=f"Sorry, you can only run this command out of: {formatted_channel_list}",
                color=EMBED_COLOUR_ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, CommandRoleError):
            print("Role check error raised")
            permitted_roles = error.permitted_roles
            formatted_role_list = error.formatted_role_list
            if len(permitted_roles) > 1:
                embed = discord.Embed(
                    description=f"**Permission denied**: You need one of the following roles to use this command:\n{formatted_role_list}",
                    color=EMBED_COLOUR_ERROR,
                )
            else:
                embed = discord.Embed(
                    description=f"**Permission denied**: You need the following role to use this command:\n{formatted_role_list}",
                    color=EMBED_COLOUR_ERROR,
                )
            print("notify user")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, CustomError):
            message = error.message
            is_private = error.is_private
            print(f"Raised CustomError from {error} with message {message}")
            embed = discord.Embed(description=f"❌ {message}", color=EMBED_COLOUR_ERROR)
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
            embed = discord.Embed(description=f"❌ {error}", color=EMBED_COLOUR_ERROR)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)

        else:
            print("Other type error message raised")
            logging.error(f"Unhandled Error: {error}")
            embed = discord.Embed(description=f"❌ Unhandled Error: {error}", color=EMBED_COLOUR_ERROR)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        print(f"An error occurred in the error handler (lol): {e}")
