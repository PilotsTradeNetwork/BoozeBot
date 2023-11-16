import discord
import os
import asyncio

from discord import app_commands
from discord.ext import commands
# from discord_slash import SlashContext, cog_ext
# from discord_slash.utils.manage_commands import create_option, create_choice
# from discord_slash.utils.manage_commands import create_permission
# from discord_slash.model import SlashCommandPermissionType

import ptn.boozebot.constants as constants

from ptn.boozebot.BoozeCarrier import BoozeCarrier
from ptn.boozebot.commands.Helper import check_roles
from ptn.boozebot.constants import bot_guild_id, get_custom_assassin_id, get_discord_booze_unload_channel, \
    server_admin_role_id, server_sommelier_role_id, server_connoisseur_role_id, server_wine_carrier_role_id, \
    server_mod_role_id, get_primary_booze_discussions_channel, get_fc_complete_id, server_wine_tanker_role_id, \
    get_wine_tanker_role, get_discord_tanker_unload_channel, \
    get_public_channel_list, server_hitchhiker_role_id
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_lock, pirate_steve_conn
from ptn.boozebot.bot import bot
from ptn.boozebot.commands.ErrorHandler import on_app_command_error, on_generic_error, CustomError

class Cleaner(commands.Cog):
    def __init__(self, bot: commands.Cog):
        self.bot = bot
        self.summon_message_ids = {}

    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error

    #@cog_ext.cog_slash(
    #    name="Booze_Channels_Open",
    #    guild_ids=[bot_guild_id()],
    #    description="Opens the Booze Cruise channels to the public.",
    #    permissions={
    #        bot_guild_id(): [
    #            create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
    #            create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
    #            create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
    #            create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
    #        ]
    #    },
    #)
    @app_commands.command(name='booze_channels_open')
    @check_roles(constants.somm_plus_roles)
    async def booze_channels_open(self, interaction: discord.Interaction):
        """
        Command to open public channels. Generates a message in the channel that it ran in.

        :param discord.Interaction interaction: The discord interaction context.
        :returns: A discord embed
        """
        print(f'User {interaction.user.display_name} requested BC channel opening in channel: {interaction.channel.name}'
              f'({interaction.channel.id}).')
        embed = discord.Embed(
            description='Opening booze channels...'
        )
        # For timeout
        await interaction.response.send_message(embed=embed, ephemeral=True)

        ids_list = get_public_channel_list()
        guild = interaction.guild
        embed = discord.Embed()

        for id in ids_list:
            channel = guild.get_channel(id)
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.view_channel = None # less confusing alias for read_messages
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                embed.add_field(name="Opened", value="<#" + str(id) +">", inline=False)
            except Exception as e:
                embed.add_field(name="FAILED to open", value="<#" + str(id) + f">: {e}", inline=False)

        await interaction.delete_original_response()
        await interaction.followup.send(f"<@&{server_sommelier_role_id()}> Avast! We\'re ready to set sail!", embed=embed)




    # @cog_ext.cog_slash(
    #     name="Booze_Channels_Close",
    #     guild_ids=[bot_guild_id()],
    #     description="Opens the Booze Cruise channels to the public.",
    #     permissions={
    #         bot_guild_id(): [
    #             create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
    #         ]
    #     },
    # )
    
    @app_commands.command(name="booze_channels_close", description="Opens the Booze Cruise channels to the public.")
    @check_roles(constants.somm_plus_roles)
    async def booze_channels_close(self, interaction: discord.Interaction):
        """
        Command to close public channels. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord slash context.
        :returns: A discord embed
        """
        print(f'User {interaction.user.display_name} requested BC channel closing in channel: {interaction.channel}.')

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

    # @cog_ext.cog_slash(
    #     name="Clear_Booze_Roles",
    #     guild_ids=[bot_guild_id()],
    #     description="Removes all WC/Hitchhiker users. Requires Admin/Mod/Sommelier - Use with caution.",
    #     permissions={
    #         bot_guild_id(): [
    #             create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
    #         ]
    #     },
    # )
    @app_commands.command(name="clear_booze_roles", description="Removes all WC/Hitchhiker users. Requires Admin/Mod/Sommelier - Use with caution.")
    @check_roles(constants.somm_plus_roles)
    async def clear_booze_roles(self, interaction: discord.Interaction):
        """
        Command to reset the Wine Carrier and Hitchhiker roles to have no members. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord slash context.
        :returns: A discord embed
        """
        print(f'User {interaction.user.display_name} requested clearing all Booze related roles in channel: {interaction.channel}.')

        guild = bot.get_guild(bot_guild_id())

        wine_role_id = server_wine_carrier_role_id()
        wine_role = discord.utils.get(interaction.guild.roles, id=wine_role_id)
        wine_role_members = wine_role.members

        hitch_role_id = server_hitchhiker_role_id()
        hitch_role = discord.utils.get(interaction.guild.roles, id=hitch_role_id)
        hitch_role_members = hitch_role.members

        booze_role_members = hitch_role_members + wine_role_members

        wine_count = 0
        hitch_count = 0
        await interaction.response.send_message(f'This may take a minute...')
        try:
            for member in booze_role_members:
                if wine_role in member.roles:
                    try:
                        await member.remove_roles(wine_role)
                        wine_count += 1
                    except Exception as e:
                        print(e)
                        await interaction.followup.send(f"Unable to remove { wine_role } from { member }")
                if hitch_role in member.roles:
                    try:
                        await member.remove_roles(hitch_role)
                        hitch_count += 1
                    except Exception as e:
                        print(e)
                        await interaction.followup.send(f"Unable to remove { hitch_role } from { member }")
            await interaction.followup.send(f'Successfully removed { hitch_count } users from the Hitchhiker role.')
            await interaction.followup.send(f'Successfully removed { wine_count } users from the Wine Carrier role.')
        except Exception as e:
            print(e)
            await interaction.followup.send('Clear roles command failed.  Contact admin.')

    # @cog_ext.cog_slash(
    #     name="Set_Wine_Carrier_Welcome",
    #     guild_ids=[bot_guild_id()],
    #     description="Sets the welcome message sent to Wine Carriers.",
    #     permissions={
    #         bot_guild_id(): [
    #             create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
    #             create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
    #         ]
    #     },
    # )
    @app_commands.command(name="set_wine_carrier_welcome", description="Sets the welcome message sent to Wine Carriers.")
    @check_roles(constants.somm_plus_roles)
    async def set_wine_carrier_welcome(self, interaction: discord.Interaction):
        """
        Command to set/edit the wine carrier welcome message. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord slash context.
        :returns: A discord embed
        """

        print(f'User {interaction.user.display_name} is changing the wine carrier welcome message in {interaction.channel}.')

        # send the existing message (if there is one) so the user has a copy
        if os.path.isfile("../wine_carrier_welcome.txt"):
            with open("../wine_carrier_welcome.txt", "r") as file:
                wine_welcome_message = file.read()
                await interaction.response.send_message(f"Existing message: ```\n{wine_welcome_message}\n```")

        response_timeout = 20
        try:
            await interaction.response.send_message(f"<@{interaction.user.id}> your next message in this channel will be used as the new welcome message, or wait {response_timeout} seconds to cancel.")
        except:
            await interaction.followup.send(
                f"<@{interaction.user.id}> your next message in this channel will be used as the new welcome message, or wait {response_timeout} seconds to cancel.")
        def check(response):
            return response.author == interaction.user and response.channel == interaction.channel

        try:
            # process the response
            print("Waiting for user response...")
            message = await bot.wait_for("message", check=check, timeout=response_timeout)

        except asyncio.TimeoutError:
            print("No valid response detected")
            return await interaction.followup.send("No valid response detected.")

        if message:
            # Now try to replace the contents
            print("Setting welcome message from user input")
            with open("../wine_carrier_welcome.txt", "w") as wine_welcome_txt_file:
                wine_welcome_txt_file.write(message.content)
                embed = discord.Embed(description=message.content)
                embed.set_thumbnail(url="https://cdn.discordapp.com/role-icons/839149899596955708/2d8298304adbadac79679171ab7f0ae6.webp?quality=lossless")
                await interaction.followup.send("New Wine Carrier welcome message set:", embed=embed)
        else:
            return


