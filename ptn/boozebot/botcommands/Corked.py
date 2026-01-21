"""
Cog for all the commands related to

"""

import discord
from discord import PermissionOverwrite, app_commands
from discord.ext import commands
from ptn_utils.global_constants import (
    CHANNEL_BC_BOOZE_CRUISE_SIGNUPS,
    CHANNEL_BC_BOOZE_GUIDE,
    CHANNEL_BC_PUBLIC,
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER_GUIDE,
    CHANNEL_BC_WINE_STATUS,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.classes.CorkedUser import CorkedUser
from ptn.boozebot.constants import bot
from ptn.boozebot.database.database import database
from ptn.boozebot.modules.helpers import check_command_channel, check_roles
from ptn.boozebot.modules.pagination import createPagination
from ptn.boozebot.modules.Views import ConfirmView

"""
CLEANER COMMANDS

/booze_admin_cork - council/mod
/booze_admin_uncork - council/mod
/booze_admin_list_corked - council/mod
"""

logger = get_logger("boozebot.commands.corked")


class Corked(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    CORK_CHANNELS = CHANNEL_BC_PUBLIC + [
        CHANNEL_BC_BOOZE_CRUISE_SIGNUPS,
        CHANNEL_BC_WINE_STATUS,
        CHANNEL_BC_BOOZE_GUIDE,
        CHANNEL_BC_WINE_CARRIER_GUIDE,
    ]

    """
    This class handles corking and uncorking users
    """

    @app_commands.command(name="booze_admin_cork", description="Cork a user from the booze cruise channels")
    @app_commands.describe(user="The user to cork")
    @check_roles([*any_council_role, *any_moderation_role])
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
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

        if await database.is_user_corked(user.id):
            logger.info(f"User {user} is already corked.")
            await interaction.followup.send(f"User {user.mention} ({user.name}) is already corked.")
            return

        overwrite = PermissionOverwrite()
        overwrite.view_channel = False

        logger.info(f"Corking user {user} from booze cruise channels.")
        try:
            for channel_id in self.CORK_CHANNELS:
                logger.debug(f"Setting permissions for user {user} in channel ID {channel_id}.")
                channel = await bot.get_or_fetch.channel(channel_id)
                await channel.set_permissions(
                    user, overwrite=overwrite, reason="User corked from booze cruise channels"
                )

            logger.info(f"User {user} successfully corked from booze cruise channels.")

        except discord.DiscordException as e:
            logger.exception(f"Error corking user {user}: {e}")
            await interaction.followup.send("Failed to cork user due to a Discord error.")
            return

        await database.add_corked_user(user.id)

        logger.info(f"User {user} has been successfully corked.")

        await interaction.followup.send(
            f"User {user.mention} ({user.name}) has been corked from the booze cruise channels."
        )

    @app_commands.command(name="booze_admin_uncork", description="Uncork a user from the booze cruise channels")
    @app_commands.describe(user="The user to uncork")
    @check_roles([*any_council_role, *any_moderation_role])
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def booze_channels_open(self, interaction: discord.Interaction, user: discord.Member):
        """
        Uncork a user from the booze cruise channels

        :param discord.Interaction interaction: The interaction object
        :param discord.Member user: The user to uncork
        :returns: None
        """

        logger.info(f"User {interaction.user} requested to uncork {user}")
        await interaction.response.defer()

        if not await database.is_user_corked(user.id):
            logger.info(f"User {user} is not corked.")
            await interaction.followup.send(f"User {user.mention} ({user.name}) is not corked.")
            return

        logger.info(f"Uncorking user {user} from booze cruise channels.")
        try:
            for channel_id in self.CORK_CHANNELS:
                logger.debug(f"Removing permissions for user {user} in channel ID {channel_id}.")
                channel = await bot.get_or_fetch.channel(channel_id)
                await channel.set_permissions(user, overwrite=None, reason="User uncorked for booze cruise channels")

            logger.info(f"User {user} successfully uncorked from booze cruise channels.")

        except discord.DiscordException as e:
            logger.exception(f"Error uncorking user {user}: {e}")
            interaction.followup.send("Failed to uncork user due to a Discord error.")
            return

        await database.remove_corked_user(user.id)

        logger.info(f"User {user} has been successfully uncorked.")
        await interaction.followup.send(
            f"User {user.mention} ({user.name}) has been uncorked from the booze cruise channels."
        )

    @app_commands.command(name="booze_admin_list_corked", description="List all corked users")
    @check_roles([*any_council_role, *any_moderation_role])
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def booze_list_corked(self, interaction: discord.Interaction):
        """
        List all corked users

        :param discord.Interaction interaction: The interaction object
        :returns: None
        """

        logger.info(f"User {interaction.user} requested the list of corked users.")
        await interaction.response.defer()

        results = await database.get_all_corked_users()

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

    @app_commands.command(
        name="booze_admin_rebuild_corked_perms", description="Rebuild corked permissions for all corked users"
    )
    @check_roles([*any_council_role, *any_moderation_role])
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def booze_rebuild_corked_perms(self, interaction: discord.Interaction):
        """
        Rebuild corked permissions for all corked users

        :param discord.Interaction interaction: The interaction object
        :returns: None
        """

        logger.info(f"User {interaction.user} requested to rebuild corked permissions.")
        await interaction.response.defer()

        results = await database.get_all_corked_users()

        if not results:
            logger.info("No corked users found for permission rebuild.")
            await interaction.edit_original_response(content="There are no corked users to rebuild permissions for.")
            return

        confirm = ConfirmView(author=interaction.user)
        await interaction.edit_original_response(
            content=f"Are you sure you want to rebuild corked permissions for all {len(results)} corked users? This may take some time.",
            view=confirm,
        )

        await confirm.wait()

        if confirm.value is False:
            logger.info(f"User {interaction.user.name} wants to abort the open process.")
            await interaction.edit_original_response(
                content="You aborted the request to rebuild the corked perms", embed=None, view=None
            )
            return
        elif confirm.value is None:
            logger.info(f"User {interaction.user.name} did not respond in time to the confirmation view.")
            await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None, view=None
            )
            return

        corked_users = [CorkedUser(row) for row in results]

        logger.info(f"Rebuilding corked permissions for {len(corked_users)} corked users.")
        await interaction.edit_original_response(
            content="Rebuilding corked permissions. This may take a while.", embed=None, view=None
        )

        failed_users = []

        for corked_user in corked_users:
            user = await bot.get_or_fetch.member(corked_user.user_id)
            if user is None:
                logger.warning(f"Could not find member with ID {corked_user.user_id}, skipping.")
                failed_users.append((corked_user.user_id, "User not found"))
                continue
            overwrite = PermissionOverwrite()
            overwrite.view_channel = False
            try:
                for channel_id in self.CORK_CHANNELS:
                    logger.debug(f"Setting permissions for corked user {user} in channel ID {channel_id}.")
                    channel = await bot.get_or_fetch.channel(channel_id)
                    await channel.set_permissions(user, overwrite=overwrite, reason="Rebuilding corked permissions")
            except discord.DiscordException as e:
                logger.exception(f"Error setting permissions for user {user} in channel ID {channel_id}: {e}")
                failed_users.append((corked_user.user_id, str(e)))

        if failed_users:
            logger.info(f"Rebuilding corked permissions completed with {len(failed_users)} failures.")
            failed_user_messages = [f"<@{user_id}>: {reason}" for user_id, reason in failed_users]
            await interaction.edit_original_response(
                content="Rebuilding corked permissions completed with some failures:\n"
                + "\n".join(failed_user_messages),
                embed=None,
                view=None,
            )

        else:
            logger.info("Rebuilding corked permissions completed successfully for all users.")
            await interaction.edit_original_response(
                content="Rebuilding corked permissions completed successfully for all corked users.",
                embed=None,
                view=None,
            )
