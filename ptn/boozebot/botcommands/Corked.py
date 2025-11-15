"""
Cog for all the commands related to

"""

from datetime import datetime, timezone
from loguru import logger

import discord
from discord import PermissionOverwrite, app_commands
from discord.ext import commands
from ptn.boozebot.classes.CorkedUser import CorkedUser
from ptn.boozebot.constants import (
    get_booze_cruise_signups_channel, get_booze_guide_channel_id, get_public_channel_list, get_steve_says_channel,
    get_wine_carrier_guide_channel_id, get_wine_status_channel, server_council_role_ids, server_mod_role_id
)
from ptn.boozebot.database.database import pirate_steve_conn, pirate_steve_db, pirate_steve_db_lock
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, get_channel
from ptn.boozebot.modules.pagination import createPagination

"""
CLEANER COMMANDS

/booze_admin_cork - council/mod
/booze_admin_uncork - council/mod
/booze_admin_list_corked - council/mod
"""


class Corked(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    CORK_CHANNELS = get_public_channel_list() + [
        get_booze_cruise_signups_channel(),
        get_wine_status_channel(),
        get_booze_guide_channel_id(),
        get_wine_carrier_guide_channel_id(),
    ]

    """
    This class handles corking and uncorking users
    """

    @app_commands.command(name="booze_admin_cork", description="Cork a user from the booze cruise channels")
    @app_commands.describe(user="The user to cork")
    @check_roles([*server_council_role_ids(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def booze_channels_close(self, interaction: discord.Interaction, user: discord.Member):
        """
        Cork a user from the booze cruise channels

        :param discord.Interaction interaction: The interaction object
        :param discord.Member user: The user to cork
        :returns: None
        """

        logger.info(f"User {interaction.user} requested to cork {user}")
        await interaction.response.defer()

        if user.id == interaction.user.id:
            logger.info(f"{interaction.user} attempted to cork themselves.")
            await interaction.followup.send("You cannot cork yourself.")
            return

        logger.debug(f"Checking if user {user} is already corked.")
        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "SELECT * FROM corked_users WHERE user_id = ?",
                (str(user.id),),
            )
            result = pirate_steve_db.fetchone()
            
        logger.debug(f"Database check complete for user {user}. Result: {result}")

        if result:
            logger.info(f"User {user} is already corked.")
            await interaction.followup.send(f"User {user.mention} ({user.name}) is already corked.")
            return

        overwrite = PermissionOverwrite()
        overwrite.view_channel = False

        logger.info(f"Corking user {user} from booze cruise channels.")
        try:
            for channel_id in self.CORK_CHANNELS:
                logger.debug(f"Setting permissions for user {user} in channel ID {channel_id}.")
                channel = await get_channel(channel_id)
                await channel.set_permissions(
                    user, overwrite=overwrite, reason="User corked from booze cruise channels"
                )
                
            logger.info(f"User {user} successfully corked from booze cruise channels.")

        except discord.DiscordException as e:
            logger.exception(f"Error corking user {user}: {e}")
            await interaction.followup.send("Failed to cork user due to a Discord error.")
            return

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        logger.debug(f"Inserting corked user {user} into the database with timestamp {timestamp}.")
        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "INSERT OR IGNORE INTO corked_users (user_id, timestamp) VALUES (?, ?)",
                (str(user.id), timestamp),
            )
            pirate_steve_conn.commit()
            
        logger.info(f"User {user} has been successfully corked.")

        await interaction.followup.send(
            f"User {user.mention} ({user.name}) has been corked from the booze cruise channels."
        )

    @app_commands.command(name="booze_admin_uncork", description="Uncork a user from the booze cruise channels")
    @app_commands.describe(user="The user to uncork")
    @check_roles([*server_council_role_ids(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def booze_channels_open(self, interaction: discord.Interaction, user: discord.Member):
        """
        Uncork a user from the booze cruise channels

        :param discord.Interaction interaction: The interaction object
        :param discord.Member user: The user to uncork
        :returns: None
        """

        logger.info(f"User {interaction.user} requested to uncork {user}")
        await interaction.response.defer()

        logger.debug(f"Checking if user {user} is corked.")
        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "SELECT * FROM corked_users WHERE user_id = ?",
                (str(user.id),),
            )
            result = pirate_steve_db.fetchone()
            
        logger.debug(f"Database check complete for user {user}. Result: {result}")

        if not result:
            logger.info(f"User {user} is not corked.")
            await interaction.followup.send(f"User {user.mention} ({user.name}) is not corked.")
            return

        logger.info(f"Uncorking user {user} from booze cruise channels.")
        try:
            for channel_id in self.CORK_CHANNELS:
                logger.debug(f"Removing permissions for user {user} in channel ID {channel_id}.")
                channel = await get_channel(channel_id)
                await channel.set_permissions(user, overwrite=None, reason="User uncorked for booze cruise channels")

            logger.info(f"User {user} successfully uncorked from booze cruise channels.")

        except discord.DiscordException as e:
            logger.exception(f"Error uncorking user {user}: {e}")
            interaction.followup.send("Failed to uncork user due to a Discord error.")
            return

        logger.debug(f"Removing corked user {user} from the database.")
        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "DELETE FROM corked_users WHERE user_id = ?",
                (str(user.id),),
            )
            pirate_steve_conn.commit()

        logger.info(f"User {user} has been successfully uncorked.")
        await interaction.followup.send(
            f"User {user.mention} ({user.name}) has been uncorked from the booze cruise channels."
        )

    @app_commands.command(name="booze_admin_list_corked", description="List all corked users")
    @check_roles([*server_council_role_ids(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def booze_list_corked(self, interaction: discord.Interaction):
        """
        List all corked users

        :param discord.Interaction interaction: The interaction object
        :returns: None
        """

        logger.info(f"User {interaction.user} requested the list of corked users.")
        await interaction.response.defer()

        logger.debug("Fetching corked users from the database.")
        async with pirate_steve_db_lock:
            pirate_steve_db.execute("SELECT * FROM corked_users")
            results = pirate_steve_db.fetchall()
        logger.debug(f"Fetched {len(results)} corked users from the database.")

        if not results:
            logger.info("No corked users found.")
            await interaction.followup.send("There are no corked users.")
            return

        corked_users = [CorkedUser(row) for row in results]

        for corked_user in corked_users:
            logger.debug(f"Corked User - ID: {corked_user.user_id}, Timestamp: {corked_user.timestamp}")

        corked_user_data = [
            (
                (await user.get_member()).name,
                f"{(await user.get_member()).mention} Corked at {user.timestamp}",
            )
            for user in corked_users
        ]
        logger.debug(f"Prepared corked user data for pagination: {corked_user_data}")

        logger.info("Creating pagination for corked users.")
        await createPagination(interaction, "Corked Users", corked_user_data)
