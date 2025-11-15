from loguru import logger
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
    logger.error(f"Error from {ctx.command} in {ctx.channel} called by {ctx.author}: {error}")
    if isinstance(error, commands.BadArgument):
        logger.debug("Bad argument error raised, reporting to user")
        await ctx.send(f"**Bad argument!** {error}")
    elif isinstance(error, commands.CommandNotFound):
        logger.debug("Command not found error raised")
        pass # Dont care
    elif isinstance(error, commands.MissingRequiredArgument):
        logger.debug("Missing required argument error raised, reporting to user")
        await ctx.send(
            "**Sorry, that didn't work**.\n• Check you've included all required arguments. Use `/pirate_steve_help` for details."
            "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation"
            " marks are of the same type, i.e. all straight or matching open/close smartquotes."
        )
    elif isinstance(error, commands.MissingPermissions):
        logger.debug("Missing permissions error raised, reporting to user")
        await ctx.send("**You do not have the required permissions to run this command**")
    elif isinstance(error, commands.MissingAnyRole):
        logger.debug("Missing any role error raised, reporting to user")
        logger.debug(f"User missing roles: {error.missing_roles}")
        roles = ", ".join([ctx.guild.get_role(role_id).name for role_id in error.missing_roles])
        await ctx.send(f"**You must have one of the following roles to use this command:** {roles}")
    else:
        logger.debug("Other type error message raised, reporting to user")
        await ctx.send(gif)
        await ctx.send(f"Sorry, that didn't work: {error}")


async def on_app_command_error(interaction: Interaction, error: AppCommandError):
    """Global error handler for application commands"""
    
    logger.error(f"Error from {interaction.command.name} in {interaction.channel.name} called by {interaction.user.display_name}: {error}")

    try:
        if isinstance(error, CommandChannelError):
            logger.debug(f"Channel check error raised. Permitted channel(s): {error.permitted_channel}, reporting to user")
            formatted_channel_list = error.formatted_channel_list

            embed = discord.Embed(
                description=f"Sorry, you can only run this command out of: {formatted_channel_list}",
                color=EMBED_COLOUR_ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.debug("Channel check error message sent to user")

        elif isinstance(error, CommandRoleError):
            logger.debug(f"Role check error raised. Permitted role(s): {error.permitted_roles}, reporting to user")
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
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.debug("Role check error message sent to user")

        elif isinstance(error, CustomError):
            message = error.message
            is_private = error.is_private
            logger.debug(f"Custom error raised with message: {message}, is_private: {is_private}")
            embed = discord.Embed(description=f"❌ {message}", color=EMBED_COLOUR_ERROR)
            if is_private:  # message should be ephemeral
                try:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                except InteractionResponded:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:  # message should be public
                try:
                    await interaction.response.send_message(embed=embed)
                except InteractionResponded:
                    await interaction.followup.send(embed=embed)
            logger.debug("Custom error message sent to user")

        elif isinstance(error, GenericError):
            logger.debug(f"Generic error raised with message: {error}, reporting to user")
            embed = discord.Embed(description=f"❌ {error}", color=EMBED_COLOUR_ERROR)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)
            logger.debug("Generic error message sent to user")

        else:
            logger.debug(f"Unhandled error type: {type(error)}, reporting to user")
            embed = discord.Embed(description=f"❌ Unhandled Error: {error}", color=EMBED_COLOUR_ERROR)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except InteractionResponded:
                await interaction.followup.send(embed=embed, ephemeral=True)
            logger.debug("Unhandled error message sent to user")

    except Exception as e:
        logger.exception(f"An error occurred in the error handler (lol): {e}")
