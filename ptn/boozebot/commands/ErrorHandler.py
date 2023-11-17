"""
ErrorHandler.py

Our custom global error handler for the bot. v1 is directly imported from MAB

Dependends on: constants
"""

# import discord
import discord
from discord import Interaction, app_commands
from discord.app_commands import AppCommandError
from discord.ext import commands

# import local constants
import ptn.boozebot.constants as constants
from ptn.boozebot.constants import get_bot_control_channel
from ptn.boozebot.bot import bot


@bot.listen()
async def on_command_error(ctx, error):
    print(error)
    if isinstance(error, commands.BadArgument):
        message = f'Bad argument: {error}'

    elif isinstance(error, commands.CommandNotFound):
        message = f"Sorry, were you talking to me? I don't know that command."

    elif isinstance(error, commands.MissingRequiredArgument):
        message = f"Sorry, that didn't work.\n• Check you've included all required arguments." \
                  "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation" \
                  " marks are of the same type, i.e. all straight or matching open/close smartquotes."

    elif isinstance(error, commands.MissingPermissions):
        message = 'Sorry, you\'re missing the required permission for this command.'

    elif isinstance(error, commands.MissingAnyRole):
        message = f'You require one of the following roles to use this command:\n<@&{constants.server_admin_role_id()}> • <@&{constants.server_mod_role_id()}>'

    else:
        message = f'Sorry, that didn\'t work: {error}'

    embed = discord.Embed(description=f"❌ {message}")
    await ctx.send(embed=embed)
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


class GenericError(Exception): # generic error
    pass

class CustomError(Exception): # an error handler that hides the Exception text from the user, but shows custom text sent from the source instead
    def __init__(self, message, isprivate=True):
        self.message = message
        self.isprivate = isprivate
        super().__init__(self.message, "CustomError raised")


"""
A primitive global error handler for all app commands (slash & ctx menus)

returns: the error message to the user and log
"""
async def on_generic_error(
    interaction: Interaction,
    error
): # an error handler for our custom errors
    try:
        spamchannel = bot.get_channel(get_bot_control_channel())
        spam_embed = discord.Embed(
            description=f"Error from `{interaction.command.name}` in <#{interaction.channel.id}> called by <@{interaction.user.id}>: ```{error}```"
        )
        await spamchannel.send(embed=spam_embed)
    except Exception as e:
        print(e)

    if isinstance(error, GenericError):
        print(f"Generic error raised: {error}")
        embed = discord.Embed(
            description=f"❌ {error}"
        )
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=embed, ephemeral=True)

    elif isinstance(error, CustomError): # this class receives custom error messages and displays either privately or publicly
        message = error.message
        isprivate = error.isprivate
        print(f"Raised CustomError from {error} with message {message}")
        embed = discord.Embed(
            description=f"❌ {message}"
        )
        if isprivate: # message should be ephemeral
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                await interaction.followup.send(embed=embed, ephemeral=True)
        else: # message should be public - use for CCO commands
            try:
                await interaction.response.send_message(embed=embed)
            except:
                await interaction.followup.send(embed=embed)

    else:
        print(f"Error {error} was not caught by on_generic_error")


async def on_app_command_error(
    interaction: Interaction,
    error: AppCommandError
): # an error handler for discord.py errors
    print(f"Error from {interaction.command.name} in {interaction.channel.name} called by {interaction.user.display_name}: {error}")

    try:
        if isinstance(error, CommandChannelError):
            print("Channel check error raised")
            formatted_channel_list = error.formatted_channel_list

            embed=discord.Embed(
                description=f"Sorry, you can only run this command out of: {formatted_channel_list}"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, CommandRoleError):
            try:
                print("Role check error raised")
                permitted_roles = error.permitted_roles
                formatted_role_list = error.formatted_role_list
                if len(permitted_roles)>1:
                    embed=discord.Embed(
                        description=f"**Permission denied**: You need one of the following roles to use this command:\n{formatted_role_list}"
                    )
                else:
                    embed=discord.Embed(
                        description=f"**Permission denied**: You need the following role to use this command:\n{formatted_role_list}"
                    )
                print("notify user")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                print(e)

        elif isinstance(error, CustomError):
            message = error.message
            isprivate = error.isprivate
            print(f"Raised CustomError from {error} with message {message}")
            embed = discord.Embed(
                description=f"❌ {message}"
            )
            if isprivate: # message should be ephemeral
                try:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                except:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else: # message should be public - use for CCO commands
                try:
                    await interaction.response.send_message(embed=embed)
                except:
                    await interaction.followup.send(embed=embed)

        elif isinstance(error, GenericError):
            print(f"Generic error raised: {error}")
            embed = discord.Embed(
                description=f"❌ {error}"
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                await interaction.followup.send(embed=embed, ephemeral=True)

        else:
            print("Othertype error message raised")
            embed = discord.Embed(
                description=f"❌ Unhandled Error: {error}"
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        print(f"An error occurred in the error handler (lol): {e}")