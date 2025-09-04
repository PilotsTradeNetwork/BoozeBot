"""
Cog for granting and removing the wine carrier role

"""

import asyncio
import random

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands

from ptn.boozebot.constants import (
    WCO_ROLE_ICON_URL, WELCOME_MESSAGE_FILE_PATH, bot, get_steve_says_channel, get_wine_carrier_channel, \
    server_connoisseur_role_id, server_council_role_ids, server_mod_role_id, server_sommelier_role_id, \
    server_wine_carrier_role_id, bot_spam_channel, too_slow_gifs
)
from ptn.boozebot.modules.helpers import check_command_channel, check_roles
from ptn.boozebot.modules.CommandGroups import somm_command_group, conn_command_group

"""
MAKE WINE CARRIER COMMANDS

Member context menu: make_wine_carrier - conn/somm/mod/admin
/make_wine_carrier - conn/somm/mod/admin
/remove_wine_carrier - somm/mod/admin
"""

# lock for wine carrier toggle
wine_carrier_toggle_lock = asyncio.Lock()

# initialise the Cog and attach our global error handler
class MakeWineCarrier(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self):
        self.ctx_menu = app_commands.ContextMenu(
            name="Make Wine Carrier",
            callback=self.context_menu_make_wine_carrier
        )
        self.bot.tree.add_command(self.ctx_menu)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()])
    async def context_menu_make_wine_carrier(self, interaction: discord.Interaction, user: discord.Member):
        print(f"Context menu make_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user}")
        await make_user_wine_carrier(interaction, user)

    @conn_command_group.command(name="make_wine_carrier", description="Give user the Wine Carrier role. Admin/Sommelier/Connoisseur role required.")
    @describe(user="An @ mention of the Discord user to receive the role.")
    async def make_wine_carrier(self, interaction: discord.Interaction, user: discord.Member):
        print(f"make_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user} to set the Wine Carrier role")

        await make_user_wine_carrier(interaction, user)


    @somm_command_group.command(name="remove_wine_carrier", description="Removes the Wine Carrier role from a user. Admin/Sommelier/Connoisseur role required.")
    @describe(user="An @ mention of the Discord user to remove the role from.")
    @check_command_channel(get_steve_says_channel())
    async def remove_wine_carrier(self, interaction: discord.Interaction, user: discord.Member):

        await interaction.response.defer()

        print(f"make_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user} to remove the Wine Carrier role")

        async with wine_carrier_toggle_lock:
            # set the target role
            wc_role = discord.utils.get(interaction.guild.roles, id=server_wine_carrier_role_id())
            print(f"Wine Carrier role name is {wc_role.name}")

            # Refetch the user from the interaction inside the lock
            user = await interaction.guild.fetch_member(user.id)

            if wc_role in user.roles:
                # remove role
                print(f"{user} is a {wc_role.name}, removing the role.")
                try:
                    await user.remove_roles(wc_role)
                    response = f"{user.display_name} no longer has the {wc_role.name} role."
                    await interaction.edit_original_response(content=response)

                    bot_spam = bot.get_channel(bot_spam_channel())
                    embed = discord.Embed(
                        description=f"{user.mention} ({user.name}) has been removed from the {wc_role.mention} role by {interaction.user.mention} ({interaction.user.name}).",
                    )
                    await bot_spam.send(embed=embed)

                except discord.DiscordException as e:
                    print(e)
                    await interaction.edit_original_response(content=f"Failed removing role {wc_role.name} from {user}: {e}")
                    return
            else:
                print("User is not a wine carrier, doing nothing.")
                return await interaction.edit_original_response(content=f"User is not a {wc_role.name}")

# function shared by make_wine_carrier and make_contextuser_wine_carrier
async def make_user_wine_carrier(interaction: discord.Interaction, user: discord.Member) -> None:

    await interaction.response.defer(ephemeral=True)

    async with wine_carrier_toggle_lock:
        channel = bot.get_channel(get_steve_says_channel())
        # set the target role
        wc_role = discord.utils.get(interaction.guild.roles, id=server_wine_carrier_role_id())
        print(f"Wine Carrier role name is {wc_role.name}")

        # Refetch the user from the interaction inside the lock
        user = await interaction.guild.fetch_member(user.id)

        if wc_role in user.roles:
            print(f"{user} is already a {wc_role.name}, doing nothing.")
            embed = discord.Embed(description=f"{user.mention} is already a {wc_role.name}")
            embed.set_image(url=random.choice(too_slow_gifs))
            await interaction.edit_original_response(embed=embed)
            return
        else:
            # toggle on
            print(f"{user} is not a {wc_role.name}, adding the role.")
            try:
                await user.add_roles(wc_role)
                print(f"Added Wine Carrier role to {user}")
                response = f"{user.display_name} now has the {wc_role.name} role."

                # Open the file in read mode.
                with open(WELCOME_MESSAGE_FILE_PATH, "r", encoding="utf-8") as file:
                    wine_welcome_message = file.read() # read contents to variable

                wine_channel = bot.get_channel(get_wine_carrier_channel())
                embed = discord.Embed(description=wine_welcome_message)
                embed.set_thumbnail(url=WCO_ROLE_ICON_URL)
                await wine_channel.send(f"<@{user.id}>", embed=embed)

                msg = f"{user.mention} ({user.name}) has been given the {wc_role.name} role by {interaction.user.mention} ({interaction.user.name})."
                embed = discord.Embed(description=msg)
                await channel.send(content=msg, silent=True)
                await interaction.edit_original_response(content=response)

                bot_spam = bot.get_channel(bot_spam_channel())
                await bot_spam.send(embed=embed)

            except discord.DiscordException as e:
                print(e)
                await interaction.edit_original_response(content=f"Failed adding role {wc_role.name} to {user}: {e}")
