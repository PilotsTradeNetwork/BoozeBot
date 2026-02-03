"""
Cog for granting and removing the wine carrier role

"""

import asyncio
import random
from typing import Any

import discord
from discord import app_commands, Embed, Member, Interaction, DiscordException
from discord.abc import GuildChannel
from discord.app_commands import describe, ContextMenu
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from discord.ui import View
from ptn_utils.global_constants import (
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER,
    CHANNEL_BOTSPAM,
    ROLE_CONN,
    ROLE_SOMM,
    ROLE_WINE_CARRIER,
    any_council_role,
    any_moderation_role,
    EMOJI_CARRIER_DONE,
)
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import WCO_ROLE_ICON_URL, WELCOME_MESSAGE_FILE_PATH, bot, too_slow_gifs
from ptn.boozebot.database.database import database
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, track_last_run
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api
from ptn.boozebot.modules.Views import DynamicButton

"""
MAKE WINE CARRIER COMMANDS

Member context menu: make_wine_carrier - conn/somm/mod/admin
/make_wine_carrier - conn/somm/mod/admin
/remove_wine_carrier - somm/mod/admin
"""

logger = get_logger("boozebot.commands.makewinecarrier")

# lock for wine carrier toggle
wine_carrier_toggle_lock = asyncio.Lock()


# initialise the Cog
class MakeWineCarrier(commands.Cog):
    ctx_menu: ContextMenu
    bot: Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(name="Make Wine Carrier", callback=self.context_menu_make_wine_carrier)
        self.bot.tree.add_command(self.ctx_menu)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting periodic signup poll task loop")
        if not self.booze_tracker_signup_check.is_running():
            self.booze_tracker_signup_check.start()

    @commands.Cog.listener()
    async def on_dynamic_button_makewinecarrier(self, interaction: Interaction, button: DynamicButton):
        """Handle dynamic button click for making a wine carrier."""
        logger.info(f"Make Wine Carrier button clicked by {interaction.user.name} for user {button.user_id}")

        user_roles = [role.id for role in interaction.user.roles]
        allowed_roles = [*any_council_role, *any_moderation_role, ROLE_SOMM, ROLE_CONN]

        if not any(role in user_roles for role in allowed_roles):
            await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
            return

        user = await bot.get_or_fetch.member(button.user_id)
        if not user:
            await interaction.response.send_message(f"Could not find user with ID {button.user_id}", ephemeral=True)
            return

        await make_user_wine_carrier(interaction, user)

    @commands.Cog.listener()
    async def on_boozesheets_signup(self, data: dict[str, Any]):
        logger.info(f"Received booze tracker signup data: {data}")

        color = int(data["color"], 16) if data.get("color") else 0x000000

        await self.alert_new_signup(
            owner_id=data.get("userId"),
            status=data.get("status"),
            notes=data.get("notes"),
            first_time=data.get("firstTime", False),
            color=color,
        )

    @tasks.loop(minutes=5)
    @track_last_run()
    async def booze_tracker_signup_check(self):
        """Periodically check for new booze tracker signups."""
        logger.debug("Running booze_tracker_signup_check task")

        new_signups = await booze_sheets_api.get_unpinged_signups()

        logger.debug(f"Found {len(new_signups)} new signups")

        unique_signups = {}

        for signup in new_signups:
            if signup.owner.discord_id in unique_signups:
                continue

            unique_signups[signup.owner.discord_id] = signup

            try:
                color = int(signup.signup_info.color, 16) if signup.signup_info else 0x000000

                await self.alert_new_signup(
                    owner_id=signup.owner.discord_id,
                    status=signup.signup_info.status if signup.signup_info else None,
                    notes=signup.signup_info.notes if signup.signup_info else "",
                    first_time=signup.signup_info.first_time if signup.signup_info else True,
                    color=color,
                )
                logger.debug(f"Marked signup {signup.owner.discord_id} as pinged")
            except DiscordException as e:
                logger.exception(f"Failed to alert new signup for user {signup.owner.discord_id}: {e}")
                continue

    async def alert_new_signup(
        self, owner_id: int, status: str | None, notes: str, color: int | str = "gray", first_time: bool = True
    ):
        """Alert about a new signup."""

        logger.debug(f"Alerting new signup for user {owner_id} with status {status} and notes {notes}")

        steve_says = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)
        assert isinstance(steve_says, GuildChannel)

        owner = await bot.get_or_fetch.member(owner_id)
        if not owner:
            logger.error(f"Could not find user with ID {owner_id} to alert about new signup")
            await steve_says.send(f"Could not find user with ID {owner_id} for new signup alert.")
            return

        description = f"User <@{owner_id}> ({owner.name}) has signed up."
        if first_time:
            description += f"\nFirst time WCO, React with {await bot.get_or_fetch.emoji(EMOJI_CARRIER_DONE)} and then DM them the onboarding message."
        if status:
            description += f"\nStatus: {status}"
            description += f"\nNotes: {notes}"

        embed = Embed(title="New Wine Carrier Owner Signup", color=color, description=description)

        view = None
        if not first_time:
            view = View(timeout=None)
            view.add_item(
                DynamicButton(label="Make Wine Carrier", action="makewinecarrier", user_id=owner_id, message_id=0)
            )

        await steve_says.send(content=f"<@&{ROLE_CONN}>", embed=embed, view=view)
        await booze_sheets_api.set_user_pinged(owner_id)

        logger.info(f"Sent new signup alert for user {owner_id} to steve_says channel")

    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM, ROLE_CONN])
    async def context_menu_make_wine_carrier(self, interaction: Interaction, user: Member):
        logger.info(
            f"Context menu make_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user}"
        )
        await make_user_wine_carrier(interaction, user)

    @app_commands.command(
        name="make_wine_carrier",
        description="Give user the Wine Carrier role. Admin/Sommelier/Connoisseur role required.",
    )
    @describe(user="An @ mention of the Discord user to receive the role.")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM, ROLE_CONN])
    async def make_wine_carrier(self, interaction: Interaction, user: Member):
        logger.info(
            f"make_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user} to set the Wine Carrier role"
        )

        await make_user_wine_carrier(interaction, user)

    @app_commands.command(
        name="remove_wine_carrier",
        description="Removes the Wine Carrier role from a user. Admin/Sommelier/Connoisseur role required.",
    )
    @describe(user="An @ mention of the Discord user to remove the role from.")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    @check_command_channel(CHANNEL_BC_STEVE_SAYS)
    async def remove_wine_carrier(self, interaction: Interaction, user: Member):
        await interaction.response.defer()

        logger.info(
            f"remove_wine_carrier called by {interaction.user.name} in {interaction.channel.name} for {user} to remove the Wine Carrier role"
        )

        logger.debug("Acquiring wine_carrier_toggle_lock to remove Wine Carrier role")
        async with wine_carrier_toggle_lock:
            logger.debug("wine_carrier_toggle_lock acquired")
            # set the target role
            wc_role = await bot.get_or_fetch.role(ROLE_WINE_CARRIER)
            logger.debug(f"Wine Carrier role name is {wc_role.name}")

            # Refetch the user from the interaction inside the lock
            user = await bot.get_or_fetch.member(user.id)

            logger.debug(f"Refetched user: {user}")

            if wc_role in user.roles:
                # remove role
                logger.info(f"Removing {wc_role.name} role from {user}")
                try:
                    await user.remove_roles(wc_role)
                    logger.info(f"Removed Wine Carrier role from {user}")

                    response = f"{user.mention} ({user.name}) no longer has the {wc_role.name} role."
                    await interaction.edit_original_response(content=response)
                    bot_spam = await bot.get_or_fetch.channel(CHANNEL_BOTSPAM)
                    embed = Embed(
                        description=f"{user.mention} ({user.name}) has been removed from the {wc_role.mention} role by {interaction.user.mention} ({interaction.user.name}).",
                    )
                    await bot_spam.send(embed=embed)

                except DiscordException as e:
                    logger.exception(f"Failed removing role {wc_role.name} from {user}: {e}")
                    await interaction.edit_original_response(
                        content=f"Failed removing role {wc_role.name} from {user}: {e}"
                    )
            else:
                logger.info(f"User {user} is not a {wc_role.name}, cannot remove role.")
                await interaction.edit_original_response(content=f"User is not a {wc_role.name}")


# function shared by make_wine_carrier and make_contextuser_wine_carrier
async def make_user_wine_carrier(interaction: Interaction, user: Member) -> None:
    await interaction.response.defer(ephemeral=True)

    logger.debug("Acquiring wine_carrier_toggle_lock to add Wine Carrier role")
    async with wine_carrier_toggle_lock:
        logger.debug("wine_carrier_toggle_lock acquired")
        channel = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)
        # set the target role
        wc_role = await bot.get_or_fetch.role(ROLE_WINE_CARRIER)
        logger.debug(f"Wine Carrier role name is {wc_role.name}")

        # Refetch the user from the interaction inside the lock
        user = await bot.get_or_fetch.member(user.id)
        logger.debug(f"Refetched user: {user}")

        async def respond(content: str | None = None, embed: discord.Embed | None = None):
            if interaction.message:
                return await interaction.followup.send(content=content, embed=embed, ephemeral=True)
            else:
                return await interaction.edit_original_response(content=content, embed=embed)

        if await database.is_user_corked(user.id):
            logger.info(f"User {user} is corked, cannot make Wine Carrier.")
            await respond(content=f"User {user.mention} ({user.name}) is corked and cannot be made a {wc_role.name}.")
            return

        if wc_role in user.roles:
            logger.info(f"User {user} is already a {wc_role.name}, cannot add role again.")
            embed = Embed(description=f"{user.mention} is already a {wc_role.name}")
            embed.set_image(url=random.choice(too_slow_gifs))
            await respond(embed=embed)
            return
        else:
            # toggle on
            logger.info(f"Adding {wc_role.name} role to {user}")
            try:
                await user.add_roles(wc_role)
                logger.info(f"Added Wine Carrier role to {user}")
                response = f"{user.display_name} now has the {wc_role.name} role."

                logger.debug("Opening welcome message file")
                with open(WELCOME_MESSAGE_FILE_PATH, "r", encoding="utf-8") as file:
                    wine_welcome_message = file.read()

                logger.debug(f"Welcome message file read successfully. \n {wine_welcome_message}")

                wine_channel = await bot.get_or_fetch.channel(CHANNEL_BC_WINE_CARRIER)
                embed = Embed(description=wine_welcome_message)
                embed.set_thumbnail(url=WCO_ROLE_ICON_URL)
                await wine_channel.send(f"<@{user.id}>", embed=embed)
                logger.debug("Welcome message sent successfully.")

                msg = f"{user.mention} ({user.name}) has been given the {wc_role.name} role by {interaction.user.mention} ({interaction.user.name})."
                embed = Embed(description=msg)
                await channel.send(content=msg, silent=True)
                await respond(content=response)

                if interaction.message:
                    await interaction.message.add_reaction(await bot.get_or_fetch.emoji(EMOJI_CARRIER_DONE))
                    await interaction.message.edit(view=None)

                bot_spam = await bot.get_or_fetch.channel(CHANNEL_BOTSPAM)
                await bot_spam.send(embed=embed)
                logger.debug("Notified bot_spam and steve_says channels successfully.")

            except DiscordException as e:
                logger.exception(f"Failed adding role {wc_role.name} to {user}: {e}")
                await interaction.edit_original_response(content=f"Failed adding role {wc_role.name} to {user}: {e}")
