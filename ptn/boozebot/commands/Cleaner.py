import discord
import os
import asyncio
from discord.ext import commands
from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils.manage_commands import create_permission
from discord_slash.model import SlashCommandPermissionType

from ptn.boozebot.BoozeCarrier import BoozeCarrier
from ptn.boozebot.constants import bot_guild_id, get_custom_assassin_id, bot, get_discord_booze_unload_channel, \
    server_admin_role_id, server_sommelier_role_id, server_connoisseur_role_id, server_wine_carrier_role_id, \
    server_mod_role_id, get_primary_booze_discussions_channel, get_fc_complete_id, server_wine_tanker_role_id, \
    get_wine_tanker_role, get_discord_tanker_unload_channel, \
    get_public_channel_list
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_lock, pirate_steve_conn


class Cleaner(commands.Cog):
    def __init__(self):
        """
        This class handles role and channel cleanup after a cruise, as well as opening channels in preparation for a cruise.
        """

    @cog_ext.cog_slash(
        name="Booze_Channels_Open",
        guild_ids=[bot_guild_id()],
        description="Opens the Booze Cruise channels to the public.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def booze_channels_open(self, ctx: SlashContext):
        """
        Command to open public channels. Generates a message in the channel that it ran in.

        :param SlashContext ctx: The discord slash context.
        :returns: A discord embed
        """
        print(f'User {ctx.author} requested BC channel opening in channel: {ctx.channel}.')

        ids_list = get_public_channel_list()
        guild = bot.get_guild(bot_guild_id())

        embed = discord.Embed()

        for id in ids_list:
            channel = bot.get_channel(id)
            try:
                await channel.set_permissions(guild.default_role, view_channel=None) # less confusing alias for read_messages
                embed.add_field(name="Opened", value="<#" + str(id) +">", inline=False)
            except Exception as e:
                embed.add_field(name="FAILED to open", value="<#" + str(id) + f">: {e}", inline=False)

        await ctx.send(f"<@&{server_sommelier_role_id()}> Avast! We\'re ready to set sail!", embed=embed)


    @cog_ext.cog_slash(
        name="Booze_Channels_Close",
        guild_ids=[bot_guild_id()],
        description="Opens the Booze Cruise channels to the public.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def booze_channels_close(self, ctx: SlashContext):
        """
        Command to close public channels. Generates a message in the channel that it ran in.

        :param SlashContext ctx: The discord slash context.
        :returns: A discord embed
        """
        print(f'User {ctx.author} requested BC channel closing in channel: {ctx.channel}.')

        ids_list = get_public_channel_list()
        guild = bot.get_guild(bot_guild_id())

        embed = discord.Embed()

        for id in ids_list:
            channel = bot.get_channel(id)
            try:
                await channel.set_permissions(guild.default_role, view_channel=False) # less confusing alias for read_messages
                embed.add_field(name="Closed", value="<#" + str(id) +">", inline=False)
            except Exception as e:
                embed.add_field(name="FAILED to close", value="<#" + str(id) + f">: {e}", inline=False)

        await ctx.send(f"<@&{server_sommelier_role_id()}> That\'s the end of that, me hearties.", embed=embed)

    @cog_ext.cog_slash(
        name="Set_Wine_Carrier_Welcome",
        guild_ids=[bot_guild_id()],
        description="Sets the welcome message sent to Wine Carriers.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def set_wine_carrier_welcome(self, ctx: SlashContext):
        """
        Command to set/edit the wine carrier welcome message. Generates a message in the channel that it ran in.

        :param SlashContext ctx: The discord slash context.
        :returns: A discord embed
        """
        print(f'User {ctx.author} is changing the wine carrier welcome message in {ctx.channel}.')

        # send the existing message (if there is one) so the user has a copy
        if os.path.isfile("wine_carrier_welcome.txt"):
            with open("wine_carrier_welcome.txt", "r") as file:
                wine_welcome_message = file.read()
                await ctx.send(f"Existing message: ```\n{wine_welcome_message}\n```")

        response_timeout = 20

        await ctx.send(f"<@{ctx.author.id}> your next message in this channel will be used as the new welcome message, or wait {response_timeout} seconds to cancel.")

        def check(response):
            return response.author == ctx.author and response.channel == ctx.channel

        try:
            # process the response
            print("Waiting for user response...")
            message = await bot.wait_for("message", check=check, timeout=response_timeout)

        except asyncio.TimeoutError:
            print("No valid response detected")
            return await ctx.send("No valid response detected.")

        if message:
            # Now try to replace the contents
            print("Setting welcome message from user input")
            with open("wine_carrier_welcome.txt", "w") as wine_welcome_txt_file:
                wine_welcome_txt_file.write(message.content)
                embed = discord.Embed(description=message.content)
                embed.set_thumbnail(url="https://cdn.discordapp.com/role-icons/839149899596955708/2d8298304adbadac79679171ab7f0ae6.webp?quality=lossless")
                await ctx.send("New Wine Carrier welcome message set:", embed=embed)
        else:
            return
