"""
Cog for all the commands related to 

"""

# libraries
import os
import asyncio

# discord.py
import discord
from discord.app_commands import Group, describe, Choice
from discord.ext import commands, tasks
from discord import app_commands, NotFound

# local constants
from ptn.boozebot.constants import bot_guild_id, bot, server_council_role_ids, \
server_sommelier_role_id, server_wine_carrier_role_id, server_mod_role_id, \
    get_public_channel_list, server_hitchhiker_role_id, WELCOME_MESSAGE_FILE_PATH, \
    get_steve_says_channel, get_feedback_channel_id

# local modules
from ptn.boozebot.modules.ErrorHandler import on_app_command_error, GenericError, CustomError, on_generic_error, TimeoutError
from ptn.boozebot.modules.helpers import bot_exit, check_roles, check_command_channel


"""
CLEANER COMMANDS

/booze_channels_open - somm/mod/admin
/booze_channels_close - somm/mod/admin
/clear_booze_roles - somm/mod/admin
/set_wine_carrier_welcome - somm/mod/admin

/open_wine_carrier_feedback - somm/mod/admin
/close_wine_carrier_feedback - somm/mod/admin
"""

class Cleaner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # custom global error handler
    # attaching the handler when the cog is loaded
    # and storing the old handler
    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    # detaching the handler when the cog is unloaded
    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error
    
    """
    This class handles role and channel cleanup after a cruise, as well as opening channels in preparation for a cruise.
    """

    @app_commands.command(name="booze_channels_open", description="Opens the Booze Cruise channels to the public.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def booze_channels_open(self, interaction: discord.Interaction):
        """
        Command to open public channels. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :returns: A discord embed
        """
        print(f'User {interaction.user.name} requested BC channel opening in channel: {interaction.channel.name}.')
        
        def check_yes_no(check_message):
            return (
                check_message.author == interaction.user
                and check_message.channel == interaction.channel
                and check_message.content.lower() in ["y", "n"]
            )
            
        check_embed = discord.Embed(
            title="Validate the request",
            description="You have requested to open the booze cruise channels:"
        )
        check_embed.set_footer(text="Respond with y/n.")
        await interaction.response.send_message(content=None, embed=check_embed)
    
        try:
            user_response = await bot.wait_for(
                "message", check=check_yes_no, timeout=30
            )
            if user_response.content.lower() == "y":
                
                ids_list = get_public_channel_list()
                guild = bot.get_guild(bot_guild_id())

                embed = discord.Embed()
                
                for id in ids_list:
                    channel = bot.get_channel(id)
                    try:
                        overwrite = channel.overwrites_for(guild.default_role)
                        overwrite.view_channel = None # less confusing alias for read_messages
                        await channel.set_permissions(guild.default_role, overwrite=overwrite)
                        embed.add_field(name="Opened", value="<#" + str(id) +">", inline=False)
                    except Exception as e:
                        embed.add_field(name="FAILED to open", value="<#" + str(id) + f">: {e}", inline=False)

                await interaction.edit_original_response(content=f"<@&{server_sommelier_role_id()}> Avast! We\'re ready to set sail!", embed=embed)
                await user_response.delete()
                print("Channels opened successfully.")
                return
                
            elif user_response.content.lower() == "n":
                print(
                    f"User {interaction.user.name} wants to abort the open process."
                )
                await user_response.delete()
                return await interaction.edit_original_response(
                    content="You aborted the request to open the channels.", embed=None
                )

        except asyncio.TimeoutError:
            return await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None
            )

    @app_commands.command(name="booze_channels_close", description="Closes the Booze Cruise channels to the public.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def booze_channels_close(self, interaction: discord.Interaction):
        """
        Command to close public channels. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :returns: A discord embed
        """
        print(f'User {interaction.user.name} requested BC channel closing in channel: {interaction.channel.name}.')

        ids_list = get_public_channel_list()
        guild = bot.get_guild(bot_guild_id())

        embed = discord.Embed()

        for id in ids_list:
            channel = bot.get_channel(id)
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.view_channel = False # less confusing alias for read_messages
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                embed.add_field(name="Closed", value="<#" + str(id) +">", inline=False)
            except Exception as e:
                embed.add_field(name="FAILED to close", value="<#" + str(id) + f">: {e}", inline=False)

        await interaction.response.send_message(f"<@&{server_sommelier_role_id()}> That\'s the end of that, me hearties.", embed=embed)
        return

    @app_commands.command(name="clear_booze_roles", description="Removes all WC/Hitchhiker users. Requires Admin/Mod/Sommelier - Use with caution.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def clear_booze_roles(self, interaction: discord.Interaction):
        """
        Command to clear temporary cruise related roles (wine carrier & hitchhiker). Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :returns: A discord embed
        """
        print(f'User {interaction.user.name} requested clearing all Booze related roles in channel: {interaction.channel.name}.')

        wine_role_id = server_wine_carrier_role_id()
        wine_carrier_role = discord.utils.get(interaction.guild.roles, id=wine_role_id)

        hitch_role_id = server_hitchhiker_role_id()
        hitch_role = discord.utils.get(interaction.guild.roles, id=hitch_role_id)

        wine_count = 0
        hitch_count = 0
        await interaction.response.send_message(f'This may take a minute...')
        try:
            for member in wine_carrier_role.members:
                try:
                    await member.remove_roles(wine_carrier_role)
                    wine_count += 1
                except Exception as e:
                    print(e)
                    await interaction.channel.send(f"Unable to remove { wine_carrier_role } from { member }")
            for member in hitch_role.members:
                try:
                    await member.remove_roles(hitch_role)
                    hitch_count += 1
                except Exception as e:
                    print(e)
                    await interaction.channel.send(f"Unable to remove { hitch_role } from { member }")

            await interaction.channel.send(content = f'Successfully removed { hitch_count } users from the Hitchhiker role.\n'
                               f'Successfully removed { wine_count } users from the Wine Carrier role.', embed = None)
        except Exception as e:
            print(e)
            await interaction.channel.send('Clear roles command failed. Contact admin.')
            return

    @app_commands.command(name="set_wine_carrier_welcome", description="Sets the welcome message sent to Wine Carriers.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def set_wine_carrier_welcome(self, interaction: discord.Interaction):
        print(f'User {interaction.user.name} is changing the wine carrier welcome message in {interaction.channel.name}.')

        # send the existing message (if there is one) so the user has a copy
        wine_welcome_message = ""
        if os.path.isfile(WELCOME_MESSAGE_FILE_PATH):
            with open(WELCOME_MESSAGE_FILE_PATH, "r") as file:
                wine_welcome_message = file.read()
                
        response_timeout = 20

        await interaction.response.send_message(f"Existing message: ```\n{wine_welcome_message}\n```\n"
                                                f"<@{interaction.user.id}> your next message in this channel will be used as the new welcome message, or wait {response_timeout} seconds to cancel.")
        
        def check(response):
            return response.author == interaction.user and response.channel == interaction.channel

        try:
            # process the response
            print("Waiting for user response...")
            message = await bot.wait_for("message", check=check, timeout=response_timeout)

        except TimeoutError:
            print("No valid response detected")
            return await interaction.edit_original_response(content="No valid response detected.")

        if message:
            # Now try to replace the contents
            print("Setting welcome message from user input")
            with open(WELCOME_MESSAGE_FILE_PATH, "w") as wine_welcome_txt_file:
                wine_welcome_txt_file.write(message.content)
                embed = discord.Embed(description=message.content)
                embed.set_thumbnail(url="https://cdn.discordapp.com/role-icons/839149899596955708/2d8298304adbadac79679171ab7f0ae6.webp?quality=lossless")
                await interaction.edit_original_response(content="New Wine Carrier welcome message set:", embed=embed)
                await message.delete()
                return
        else:
            return
        
    @app_commands.command(name="open_wine_carrier_feedback", description="Opens the Wine Carrier feedback channel.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def open_wine_carrier_feedback(self, interaction: discord.Interaction):
        print(f'User {interaction.user.name} is opening the wine carrier feedback channel in {interaction.channel.name}.')
        
        wine_feedback_channel = bot.get_channel(get_feedback_channel_id())        
        wine_carrier_role = interaction.guild.get_role(server_wine_carrier_role_id())
        overwrite = discord.PermissionOverwrite(view_channel=True)
        
        await wine_feedback_channel.set_permissions(wine_carrier_role, overwrite=overwrite)

        await interaction.response.send_message(f"Opened the Wine Carrier feedback channel.", embed=None)
        return
    
    @app_commands.command(name="close_wine_carrier_feedback", description="Closes the Wine Carrier feedback channel.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def close_wine_carrier_feedback(self, interaction: discord.Interaction):
        print(f'User {interaction.user.name} is closing the wine carrier feedback channel in {interaction.channel.name}.')
        
        wine_feedback_channel = bot.get_channel(get_feedback_channel_id())
        wine_carrier_role = interaction.guild.get_role(server_wine_carrier_role_id())
        overwrite = discord.PermissionOverwrite(view_channel=False)
        
        await wine_feedback_channel.set_permissions(wine_carrier_role, overwrite=overwrite)

        await interaction.response.send_message(f"Closed the Wine Carrier feedback channel.", embed=None)
        return