"""
Cog for granting and removing the wine carrier role

"""

import asyncio
import random
from loguru import logger

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands
from ptn.boozebot.constants import (
    WCO_ROLE_ICON_URL, WELCOME_MESSAGE_FILE_PATH, bot_spam_channel, get_steve_says_channel, get_wine_carrier_channel,
    server_connoisseur_role_id, server_council_role_ids, server_mod_role_id, server_sommelier_role_id,
    server_wine_carrier_role_id, too_slow_gifs
)
from ptn.boozebot.database.database import pirate_steve_db
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, get_channel, get_member, get_role

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
        self.ctx_menu = app_commands.ContextMenu(name="Make Wine Carrier", callback=self.context_menu_make_wine_carrier)
        self.bot.tree.add_command(self.ctx_menu)

    @check_roles(
        [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()]
    )
    async def context_menu_make_wine_carrier(self, interaction: discord.Interaction, user: discord.Member):
        logger.info(
            f"Context menu make_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user}"
        )
        await make_user_wine_carrier(interaction, user)

    @app_commands.command(
        name="make_wine_carrier",
        description="Give user the Wine Carrier role. Admin/Sommelier/Connoisseur role required.",
    )
    @describe(user="An @ mention of the Discord user to receive the role.")
    @check_roles(
        [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()]
    )
    async def make_wine_carrier(self, interaction: discord.Interaction, user: discord.Member):
        logger.info(
            f"make_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user} to set the Wine Carrier role"
        )

        await make_user_wine_carrier(interaction, user)

    @app_commands.command(
        name="remove_wine_carrier",
        description="Removes the Wine Carrier role from a user. Admin/Sommelier/Connoisseur role required.",
    )
    @describe(user="An @ mention of the Discord user to remove the role from.")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    async def remove_wine_carrier(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        
        logger.info(
            f"remove_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user} to remove the Wine Carrier role"
        )

        logger.debug("Acquiring wine_carrier_toggle_lock to remove Wine Carrier role")
        async with wine_carrier_toggle_lock:
            logger.debug("wine_carrier_toggle_lock acquired")
            # set the target role
            wc_role = await get_role(server_wine_carrier_role_id())
            logger.debug(f"Wine Carrier role name is {wc_role.name}")

            # Refetch the user from the interaction inside the lock
            user = await get_member(user.id)
            
            logger.debug(f"Refetched user: {user}")

            if wc_role in user.roles:
                # remove role
                logger.info(f"Removing {wc_role.name} role from {user}")
                try:
                    await user.remove_roles(wc_role)
                    logger.info(f"Removed Wine Carrier role from {user}")
                    
                    response = f"{user.mention} ({user.name}) no longer has the {wc_role.name} role."
                    await interaction.edit_original_response(content=response)
                    bot_spam = await get_channel(bot_spam_channel())
                    embed = discord.Embed(
                        description=f"{user.mention} ({user.name}) has been removed from the {wc_role.mention} role by {interaction.user.mention} ({interaction.user.name}).",
                    )
                    await bot_spam.send(embed=embed)

                except discord.DiscordException as e:
                    logger.exception(f"Failed removing role {wc_role.name} from {user}: {e}")
                    await interaction.edit_original_response(
                        content=f"Failed removing role {wc_role.name} from {user}: {e}"
                    )
            else:
                logger.info(f"User {user} is not a {wc_role.name}, cannot remove role.")
                await interaction.edit_original_response(content=f"User is not a {wc_role.name}")


# function shared by make_wine_carrier and make_contextuser_wine_carrier
async def make_user_wine_carrier(interaction: discord.Interaction, user: discord.Member) -> None:
    await interaction.response.defer(ephemeral=True)

    logger.debug("Acquiring wine_carrier_toggle_lock to add Wine Carrier role")
    async with wine_carrier_toggle_lock:
        logger.debug("wine_carrier_toggle_lock acquired")
        channel = await get_channel(get_steve_says_channel())
        # set the target role
        wc_role = await get_role(server_wine_carrier_role_id())
        logger.debug(f"Wine Carrier role name is {wc_role.name}")

        # Refetch the user from the interaction inside the lock
        user = await get_member(user.id)
        logger.debug(f"Refetched user: {user}")

        pirate_steve_db.execute(
            "SELECT * FROM corked_users WHERE user_id = ?",
            (str(user.id),),
        )
        result = pirate_steve_db.fetchone()
        
        logger.debug(f"Corked user query result: {dict(result) if result else result}")

        if result:
            logger.info(f"User {user} is corked, cannot make Wine Carrier.")
            await interaction.edit_original_response(
                content=f"User {user.mention} ({user.name}) is corked and cannot be made a {wc_role.name}."
            )
            return

        if wc_role in user.roles:
            logger.info(f"User {user} is already a {wc_role.name}, cannot add role again.")
            embed = discord.Embed(description=f"{user.mention} is already a {wc_role.name}")
            embed.set_image(url=random.choice(too_slow_gifs))
            await interaction.edit_original_response(embed=embed)
            return
        else:
            # toggle on
            logger.info(f"Adding {wc_role.name} role to {user}")
            try:
                await user.add_roles(wc_role)
                logger.info(f"Added Wine Carrier role to {user}")
                response = f"{user.display_name} now has the {wc_role.name} role."

                logger.debug("Opening welcome message file")
                # Open the file in read mode.
                with open(WELCOME_MESSAGE_FILE_PATH, "r", encoding="utf-8") as file:
                    wine_welcome_message = file.read()  # read contents to variable
                    
                logger.debug(f"Welcome message file read successfully. \n {wine_welcome_message}")

                wine_channel = await get_channel(get_wine_carrier_channel())
                embed = discord.Embed(description=wine_welcome_message)
                embed.set_thumbnail(url=WCO_ROLE_ICON_URL)
                await wine_channel.send(f"<@{user.id}>", embed=embed)
                logger.debug("Welcome message sent successfully.")

                msg = f"{user.mention} ({user.name}) has been given the {wc_role.name} role by {interaction.user.mention} ({interaction.user.name})."
                embed = discord.Embed(description=msg)
                await channel.send(content=msg, silent=True)
                await interaction.edit_original_response(content=response)

                bot_spam = await get_channel(bot_spam_channel())
                await bot_spam.send(embed=embed)
                logger.debug("Notified bot_spam and steve_says channels successfully.")

            except discord.DiscordException as e:
                logger.exception(f"Failed adding role {wc_role.name} to {user}: {e}")
                await interaction.edit_original_response(content=f"Failed adding role {wc_role.name} to {user}: {e}")
