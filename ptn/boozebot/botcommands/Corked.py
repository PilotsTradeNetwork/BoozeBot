"""
Cog for all the commands related to

"""

from pathlib import Path
from typing import TYPE_CHECKING, cast

import discord
from discord import Embed, PermissionOverwrite, app_commands
from discord.ext import commands
from discord.ext.commands import Bot
from ptn_utils.global_constants import (
    CHANNEL_BC_BOOZE_CRUISE_CHAT,
    CHANNEL_BC_BOOZE_CRUISE_SIGNUPS,
    CHANNEL_BC_BOOZE_GUIDE,
    CHANNEL_BC_PUBLIC,
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER_GUIDE,
    CHANNEL_BC_WINE_STATUS,
    DATA_DIR,
    EMBED_COLOUR_EVIL,
    EMBED_COLOUR_EXPIRED,
    EMBED_COLOUR_OK,
    ROLE_SOMM,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger
from ptn_utils.pagination.pagination import PaginationView

from ptn.boozebot.classes.CorkedUser import CorkedUser
from ptn.boozebot.constants import bot
from ptn.boozebot.database.database import database
from ptn.boozebot.modules.helpers import check_command_channel, check_roles
from ptn.boozebot.modules.Views import ConfirmView

if TYPE_CHECKING:
    from discord.abc import GuildChannel

"""
CLEANER COMMANDS

/booze_admin_cork - council/mod
/booze_admin_uncork - council/mod
/booze_admin_list_corked - council/mod
"""

logger = get_logger("boozebot.commands.corked")


def _build_failed_cork_embed(failed_users: list[tuple[int, str]]) -> Embed:
    try:
        failed_user_messages = [f"- <@{user_id}>: {reason}" for user_id, reason in failed_users]
        embed = Embed(
            title="Rebuilding corked permissions completed with some failures:",
            description="\n".join(failed_user_messages),
            color=EMBED_COLOUR_EVIL,
        )
    except Exception as e:
        logger.exception(e)
        return Embed(title="Failed at Failed Recorks:", description=str(e), color=EMBED_COLOUR_EVIL)
    return embed


class Corked(commands.Cog):
    bot: Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    CORK_CHANNELS: tuple[int] = (
        *CHANNEL_BC_PUBLIC,
        CHANNEL_BC_BOOZE_CRUISE_SIGNUPS,
        CHANNEL_BC_WINE_STATUS,
        CHANNEL_BC_BOOZE_GUIDE,
        CHANNEL_BC_WINE_CARRIER_GUIDE,
    )

    """
    This class handles corking and uncorking users
    """

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            logger.info("Rebuilding corked permissions on startup.")
            corked_users = await database.get_corked_users()
            failed_users = await self._booze_rebuild_corked_perms(corked_users)
            if failed_users:
                embed = _build_failed_cork_embed(failed_users)
                steve_says = cast("GuildChannel", await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS))
                await steve_says.send(embed=embed)
        except Exception as e:
            logger.exception(e)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            logger.debug(f"Member joined: {member.display_name} ({member.name}/{member.id})")
            if await database.is_user_corked(member.id):
                logger.info(f"Found Corked user joining the server: {member.display_name} ({member.name}/{member.id})")
                steve_says = cast("GuildChannel", await bot.get_or_fetch_channel(CHANNEL_BC_STEVE_SAYS))
                corked_users = await database.get_corked_users()
                description = f"YARRRRRR mateys, Pirate Steve spies a bilge rat sneaking into the server! {member.mention} ({member.name}). Rebuilding corked permissions."
                get_recorked_img_path = Path(DATA_DIR, "resources", "getrecorked.png")
                get_corked_img = discord.File(get_recorked_img_path) if get_recorked_img_path.is_file() else None
                embed = Embed(title="Corked User Joining", color=EMBED_COLOUR_EVIL, description=description)
                await steve_says.send(content=f"<@&{ROLE_SOMM}>")
                await steve_says.send(embed=embed, file=get_corked_img)
                failed_users = await self._booze_rebuild_corked_perms(corked_users)
                if failed_users:
                    embed = _build_failed_cork_embed(failed_users)
                    await steve_says.send(embed=embed)

        except Exception as e:
            logger.exception(e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            logger.debug(f"Member left: {member.display_name} ({member.name}/{member.id})")
            if await database.is_user_corked(member.id):
                logger.info(f"Found Corked user leaving the server: {member.display_name} ({member.name}/{member.id})")
                steve_says = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)
                description = f"YARRRRRR mateys, Pirate Steve spies a bilge rat skulking out the airlock! {member.mention} ({member.name}). Good riddance, and don't let the door hit you!"
                embed = Embed(title="Corked User Leaving", color=EMBED_COLOUR_EXPIRED, description=description)
                await steve_says.send(content=f"<@&{ROLE_SOMM}>", silent=True)
                await steve_says.send(embed=embed)
        except Exception as e:
            logger.exception(e)

    @app_commands.command(name="booze_admin_cork", description="Cork a user from the booze cruise channels")
    @app_commands.describe(user="The user to cork")
    @check_roles([*any_council_role, *any_moderation_role])
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def booze_admin_cork(self, interaction: discord.Interaction, user: discord.Member):
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
    async def booze_admin_uncork(self, interaction: discord.Interaction, user: discord.Member):
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
            await interaction.followup.send("Failed to uncork user due to a Discord error.")
            return

        await database.remove_corked_user(user.id)

        logger.info(f"User {user} has been successfully uncorked.")
        await interaction.followup.send(
            f"User {user.mention} ({user.name}) has been uncorked from the booze cruise channels."
        )

    @app_commands.command(name="booze_admin_list_corked", description="List all corked users")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def booze_list_corked(self, interaction: discord.Interaction):
        """
        List all corked users

        :param discord.Interaction interaction: The interaction object
        :returns: None
        """

        logger.info(f"User {interaction.user} requested the list of corked users.")
        await interaction.response.defer()

        corked_users = await database.get_corked_users()

        if not corked_users:
            logger.info("No corked users found.")
            await interaction.followup.send("There are no corked users.")
            return

        for corked_user in corked_users:
            logger.debug(f"Corked User - ID: {corked_user.user_id}, Timestamp: {corked_user.timestamp}")

        corked_user_data = [
            (
                (await corked_user.get_member()).name,
                f"{(await corked_user.get_member()).mention} Corked at {corked_user.timestamp}",
            )
            for corked_user in corked_users
        ]
        logger.debug(f"Prepared corked user data for pagination: {corked_user_data}")

        logger.info("Creating pagination for corked users.")

        view = PaginationView("Corked Users", corked_user_data)
        message = await interaction.edit_original_response(view=view)
        view.message = message

    async def _booze_rebuild_corked_perms(self, corked_users: list[CorkedUser]) -> list[tuple[int, str]]:
        failed_users = []

        # ASSUMPTION: presence of overwrites in BC chat is an acceptable indicator for whether a user is still corked
        channel_chat = cast("GuildChannel", await bot.get_or_fetch.channel(CHANNEL_BC_BOOZE_CRUISE_CHAT))
        active_corks = [key.id for key in channel_chat.overwrites if not isinstance(key, discord.Role)]
        for corked_user in corked_users:
            if int(corked_user.user_id) not in active_corks:
                logger.info(
                    f"corked_user id: {corked_user.user_id}, active corks: {active_corks}, in active corks: {corked_user.user_id in active_corks}"
                )
                user = await bot.get_or_fetch.member(corked_user.user_id)
                if user is None:
                    logger.warning(f"Could not find member with ID {corked_user.user_id}, skipping.")
                    failed_users.append((corked_user.user_id, "User not found"))
                    continue
                overwrite = PermissionOverwrite()
                overwrite.view_channel = False
                channel_id = -1
                try:
                    for channel_id in self.CORK_CHANNELS:
                        logger.debug(f"Setting permissions for corked user {user} in channel ID {channel_id}.")
                        channel = await bot.get_or_fetch.channel(channel_id)
                        await channel.set_permissions(user, overwrite=overwrite, reason="Rebuilding corked permissions")
                except discord.DiscordException as e:
                    logger.exception(f"Error setting permissions for user {user} in channel ID {channel_id}: {e}")
                    failed_users.append((corked_user.user_id, str(e)))
            else:
                logger.debug(f"Skipping user {corked_user.user_id} as their cork appears to remain intact.")

        return failed_users

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

        corked_users = await database.get_corked_users()

        if not corked_users:
            logger.info("No corked users found for permission rebuild.")
            await interaction.edit_original_response(content="There are no corked users to rebuild permissions for.")
            return

        confirm = ConfirmView(author=interaction.user)
        await interaction.edit_original_response(
            content=f"Are you sure you want to rebuild corked permissions for all {len(corked_users)} corked users? This may take some time.",
            view=confirm,
        )

        await confirm.wait()

        if confirm.value is False:
            logger.info(f"User {interaction.user.name} wants to abort the open process.")
            await interaction.edit_original_response(
                content="You aborted the request to rebuild the corked perms", embed=None, view=None
            )
            return
        if confirm.value is None:
            logger.info(f"User {interaction.user.name} did not respond in time to the confirmation view.")
            await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None, view=None
            )
            return

        logger.info(f"Rebuilding corked permissions for {len(corked_users)} corked users.")
        await interaction.edit_original_response(
            content="Rebuilding corked permissions. This may take a while.", embed=None, view=None
        )

        failed_users = await self._booze_rebuild_corked_perms(corked_users)

        if failed_users:
            logger.info(f"Rebuilding corked permissions completed with {len(failed_users)} failures.")
            embed = _build_failed_cork_embed(failed_users)
            await interaction.edit_original_response(
                content=None,
                embed=embed,
                view=None,
            )

        else:
            logger.info("Rebuilding corked permissions completed successfully for all users.")
            await interaction.edit_original_response(
                content=None,
                embed=Embed(
                    description="Rebuilding corked permissions completed successfully for all corked users.",
                    color=EMBED_COLOUR_OK,
                ),
                view=None,
            )
