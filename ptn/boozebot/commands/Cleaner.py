import discord
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
        :returns: A discord embed with some emoji's
        """
        print(f'User {ctx.author} requested BC channel opening in channel: {ctx.channel}.')

        ids_list = get_public_channel_list()
        opened_channel_link_list = ["<#" + str(item) + ">" for item in ids_list]

        embed = discord.Embed(title='Avast! We\'re ready to set sail!')
        for item in opened_channel_link_list:
            embed.add_field(name="Opened", value=item, inline=False)

        await ctx.send(embed=embed)


    @cog_ext.cog_slash(
        name="Booze_Channels_Closen",
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
        Command to open public channels. Generates a message in the channel that it ran in.

        :param SlashContext ctx: The discord slash context.
        :returns: A discord embed with some emoji's
        """
        print(f'User {ctx.author} requested BC channel opening in channel: {ctx.channel}.')

        ids_list = get_public_channel_list()
        opened_channel_link_list = ["<#" + str(item) + ">" for item in ids_list]

        embed = discord.Embed(title='That\'s the end of that, me hearties!')
        for item in opened_channel_link_list:
            embed.add_field(name="Closed", value=item, inline=False)

        await ctx.send(embed=embed)
