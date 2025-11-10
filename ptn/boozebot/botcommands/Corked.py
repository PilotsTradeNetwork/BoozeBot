"""
Cog for all the commands related to

"""

from datetime import datetime, timezone

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

        print(f"User {interaction.user} requested to cork {user}")
        await interaction.response.defer()

        if user.id == interaction.user.id:
            await interaction.followup.send("You cannot cork yourself.")
            return

        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "SELECT * FROM corked_users WHERE user_id = ?",
                (str(user.id),),
            )
            result = pirate_steve_db.fetchone()

        if result:
            print(f"User {user} is already corked")
            await interaction.followup.send(f"User {user.mention} ({user.name}) is already corked.")
            return
        overwrite = PermissionOverwrite()
        overwrite.view_channel = False

        try:
            for channel_id in self.CORK_CHANNELS:
                channel = await get_channel(channel_id)
                await channel.set_permissions(
                    user, overwrite=overwrite, reason="User corked from booze cruise channels"
                )

        except discord.DiscordException as e:
            print(f"Error corking user {user}: {e}")
            await interaction.followup.send("Failed to cork user due to a Discord error.")
            return

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "INSERT OR IGNORE INTO corked_users (user_id, timestamp) VALUES (?, ?)",
                (str(user.id), timestamp),
            )
            pirate_steve_conn.commit()

        print(f"User {user} has been corked")
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

        print(f"User {interaction.user} requested to uncork {user}")
        await interaction.response.defer()

        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "SELECT * FROM corked_users WHERE user_id = ?",
                (str(user.id),),
            )
            result = pirate_steve_db.fetchone()

        if not result:
            print(f"User {user} is not corked")
            await interaction.followup.send(f"User {user.mention} ({user.name}) is not corked.")
            return

        try:
            for channel_id in self.CORK_CHANNELS:
                channel = await get_channel(channel_id)
                await channel.set_permissions(user, overwrite=None, reason="User uncorked for booze cruise channels")

        except discord.DiscordException as e:
            print(f"Error uncorking user {user}: {e}")
            interaction.followup.send("Failed to uncork user due to a Discord error.")
            return

        async with pirate_steve_db_lock:
            pirate_steve_db.execute(
                "DELETE FROM corked_users WHERE user_id = ?",
                (str(user.id),),
            )
            pirate_steve_conn.commit()

        print(f"User {user} has been uncorked")
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

        print(f"User {interaction.user} requested the list of corked users")
        await interaction.response.defer()

        async with pirate_steve_db_lock:
            pirate_steve_db.execute("SELECT * FROM corked_users")
            results = pirate_steve_db.fetchall()

        if not results:
            print("No corked users found")
            await interaction.followup.send("There are no corked users.")
            return

        corked_users = [CorkedUser(row) for row in results]

        corked_user_data = [
            (
                (await user.get_member()).name,
                f"{(await user.get_member()).mention} Corked at {user.timestamp}",
            )
            for user in corked_users
        ]

        await createPagination(interaction, "Corked Users", corked_user_data)
