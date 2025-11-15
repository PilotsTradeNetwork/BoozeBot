"""
Cog for all the commands related to

"""

from asyncio import TimeoutError
from datetime import datetime, timezone
from loguru import logger

import discord
from discord import app_commands
from discord.ext import commands
from ptn.boozebot.botcommands.Departures import Departures
from ptn.boozebot.botcommands.Unloading import Unloading
from ptn.boozebot.constants import (
    BC_STATUS, BLURB_KEYS, BLURBS, WCO_ROLE_ICON_URL, bot, get_feedback_channel_id, get_ptn_booze_cruise_role_id,
    get_public_channel_list, get_steve_says_channel, get_wine_carrier_guide_channel_id, get_wine_status_channel,
    server_council_role_ids, server_hitchhiker_role_id, server_mod_role_id, server_pilot_role_id,
    server_sommelier_role_id, server_wine_carrier_role_id
)
from ptn.boozebot.modules.helpers import check_command_channel, check_roles, get_channel, get_role
from ptn.boozebot.modules.Views import ConfirmView

"""
CLEANER COMMANDS

/booze_channels_open - somm/mod/admin
/booze_channels_close - somm/mod/admin
/clear_booze_roles - somm/mod/admin
/set_wine_carrier_welcome - somm/mod/admin

/open_wine_carrier_feedback - somm/mod/admin
/close_wine_carrier_feedback - somm/mod/admin
"""


class Cleaner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Initializing Cleaner cog.")
        self.init_blurbs()

    @staticmethod
    def init_blurbs():
        # Ensure all blurb files exist
        logger.info("Initializing blurb files if they do not exist.")
        for blurb in BLURBS.values():
            logger.debug(f"Checking blurb file at: {blurb['file_path']}")
            if not blurb["file_path"].is_file():
                logger.info(f"Blurb file not found. Creating default at: {blurb['file_path']}")
                blurb["file_path"].parent.mkdir(parents=True, exist_ok=True)
                blurb["file_path"].write_text(blurb["default_text"], encoding="utf-8")
                logger.debug(f"Default blurb file created at: {blurb['file_path']}")
            else:
                logger.debug(f"Blurb file already exists at: {blurb['file_path']}")
        logger.info("Blurb file initialization complete.")

    """
    This class handles role and channel cleanup after a cruise, as well as opening channels in preparation for a cruise.
    """

    @app_commands.command(name="booze_channels_open", description="Opens the Booze Cruise channels to the public.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def booze_channels_open(self, interaction: discord.Interaction):
        """
        Command to open public channels. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :returns: A discord embed
        """
        logger.info(f"User {interaction.user.name} requested BC channel opening in channel: {interaction.channel.name}. Sending confirmation view.")

        await interaction.response.defer()
        check_embed = discord.Embed(
            title="Open Booze Cruise Channels", description="You have requested to open the booze cruise channels:"
        )
        confirm = ConfirmView(interaction.user)
        await interaction.edit_original_response(embed=check_embed, view=confirm)
        await confirm.wait()
        
        logger.info(f"User {interaction.user.name} responded to confirmation view with: {confirm.value}")
        
        if confirm.value:
            logger.info(f"User {interaction.user.name} accepted the request to open channels.")
            ids_list = get_public_channel_list()

            embed = discord.Embed()
            Departures.departure_announcement_status = "Disabled"
            Unloading.timed_unloads_allowed = False
            pilot_role = await get_role(server_pilot_role_id())
            channels = {channel_id: pilot_role for channel_id in ids_list}
            channels[get_wine_carrier_guide_channel_id()] = await get_role(get_ptn_booze_cruise_role_id())

            logger.info("Updating status embed to 'bc_prep'.")
            await self.update_status_embed("bc_prep")

            logger.info("Opening Booze Cruise channels to the public.")
            for channel_id, role in channels.items():
                channel = await get_channel(channel_id)
                logger.debug(f"Setting permissions for channel ID: {channel_id} and role: {role.name}")
                try:
                    overwrite = channel.overwrites_for(role)
                    overwrite.view_channel = True  # less confusing alias for read_messages
                    await channel.set_permissions(role, overwrite=overwrite)
                    embed.add_field(name="Opened", value="<#" + str(channel_id) + ">", inline=False)
                    logger.debug(f"Channel ID: {channel_id} opened successfully for role: {role.name}")
                except Exception as e:
                    logger.exception(f"Failed to open channel ID: {channel_id} for role: {role.name}: {e}")
                    embed.add_field(name="FAILED to open", value="<#" + str(channel_id) + f">: {e}", inline=False)

            await interaction.edit_original_response(
                content=f"<@&{server_sommelier_role_id()}> Avast! We're ready to set sail!", embed=embed, view=None
            )
            logger.info("Booze Cruise channels opened successfully.")
        elif confirm.value is False:
            logger.info(f"User {interaction.user.name} wants to abort the open process.")
            await interaction.edit_original_response(
                content="You aborted the request to open the channels", embed=None, view=None
            )
        else:  # (confirm.value is None) Timeout on the view buttons
            logger.info(f"User {interaction.user.name} did not respond in time to the confirmation view.")
            await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None, view=None
            )

    @app_commands.command(name="booze_channels_close", description="Closes the Booze Cruise channels to the public.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def booze_channels_close(self, interaction: discord.Interaction):
        """
        Command to close public channels. Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :returns: A discord embed
        """
        logger.info(f"User {interaction.user.name} requested BC channel closing in channel: {interaction.channel.name}. Sending confirmation view.")

        await interaction.response.defer()
        check_embed = discord.Embed(
            title="Close Booze Cruise Channels", description="You have requested to close the booze cruise channels:"
        )
        confirm = ConfirmView(interaction.user)
        await interaction.edit_original_response(embed=check_embed, view=confirm)
        await confirm.wait()
        
        logger.info(f"User {interaction.user.name} responded to confirmation view with: {confirm.value}")
        
        if confirm.value:
            logger.info(f"User {interaction.user.name} accepted the request to close channels.")
            ids_list = get_public_channel_list()

            embed = discord.Embed()
            pilot_role = await get_role(server_pilot_role_id())
            channels = dict.fromkeys(ids_list, pilot_role)
            channels[get_wine_carrier_guide_channel_id()] = await get_role(get_ptn_booze_cruise_role_id())
            
            logger.info("Closing Booze Cruise channels to the public.")

            for channel_id, role in channels.items():
                channel = await get_channel(channel_id)
                logger.debug(f"Setting permissions for channel ID: {channel_id} and role: {role.name}")
                try:
                    overwrite = channel.overwrites_for(role)
                    overwrite.view_channel = False  # less confusing alias for read_messages
                    await channel.set_permissions(role, overwrite=overwrite)
                    embed.add_field(name="Closed", value="<#" + str(channel_id) + ">", inline=False)
                except Exception as e:
                    logger.exception(f"Failed to close channel ID: {channel_id} for role: {role.name}: {e}")
                    embed.add_field(name="FAILED to close", value="<#" + str(channel_id) + f">: {e}", inline=False)

            logger.info("Updating status embed to 'bc_end'.")
            await self.update_status_embed("bc_end")
            
            logger.info("Booze Cruise channels closed successfully.")
            await interaction.edit_original_response(
                content=f"<@&{server_sommelier_role_id()}> That's the end of that, me hearties.", embed=embed, view=None
            )
        elif confirm.value is False:
            logger.info(f"User {interaction.user.name} wants to abort the close process.")
            await interaction.edit_original_response(
                content="You aborted the request to close the channels", embed=None, view=None
            )
        else:  # (confirm.value is None) Timeout on the view buttons
            logger.info(f"User {interaction.user.name} did not respond in time to the confirmation view.")
            await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None, view=None
            )

    @app_commands.command(
        name="clear_booze_roles",
        description="Removes all WC/Hitchhiker users. Requires Admin/Mod/Sommelier - Use with caution.",
    )
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def clear_booze_roles(self, interaction: discord.Interaction):
        """
        Command to clear temporary cruise related roles (wine carrier & hitchhiker). Generates a message in the channel that it ran in.

        :param Interaction interaction: The discord interaction context.
        :returns: A discord embed
        """
        logger.info(
            f"User {interaction.user.name} requested clearing all Booze related roles in channel: {interaction.channel.name}. Sending confirmation view."
        )
        
        await interaction.response.defer()
        check_embed = discord.Embed(
            title="Remove Booze Cruise Roles", description="You have requested to clear all Booze related roles"
        )
        confirm = ConfirmView(interaction.user)
        await interaction.edit_original_response(embed=check_embed, view=confirm)
        await confirm.wait()
        
        logger.info(f"User {interaction.user.name} responded to confirmation view with: {confirm.value}")
        
        if confirm.value:
            logger.info(f"User {interaction.user.name} accepted the request to clear booze roles.")
            wine_role_id = server_wine_carrier_role_id()
            wine_carrier_role = await get_role(wine_role_id)

            hitch_role_id = server_hitchhiker_role_id()
            hitch_role = await get_role(hitch_role_id)

            wine_count = 0
            hitch_count = 0
            await interaction.edit_original_response(
                content="Removing roles, This may take a minute...", embed=None, view=None
            )
            logger.debug("Beginning role removal process.")
            
            try:
                for member in wine_carrier_role.members:
                    logger.debug(f"Removing {wine_carrier_role} from member: {member.name}")
                    try:
                        await member.remove_roles(wine_carrier_role)
                        wine_count += 1
                        logger.debug(f"Removed {wine_carrier_role} from member: {member.name}")
                    except Exception as e:
                        logger.exception(f"Unable to remove {wine_carrier_role} from {member}: {e}")
                        await interaction.channel.send(f"Unable to remove {wine_carrier_role} from {member}")
                for member in hitch_role.members:
                    logger.debug(f"Removing {hitch_role} from member: {member.name}")
                    try:
                        await member.remove_roles(hitch_role)
                        hitch_count += 1
                        logger.debug(f"Removed {hitch_role} from member: {member.name}")
                    except Exception as e:
                        logger.exception(f"Unable to remove {hitch_role} from {member}: {e}")
                        await interaction.channel.send(f"Unable to remove {hitch_role} from {member}")

                logger.info(f"Role removal process completed successfully. Removed {hitch_count} Hitchhiker roles and {wine_count} Wine Carrier roles.")
                await interaction.edit_original_response(
                    content=f"Successfully removed {hitch_count} users from the Hitchhiker role.\n"
                    f"Successfully removed {wine_count} users from the Wine Carrier role.",
                    embed=None,
                    view=None,
                )
            except Exception as e:
                logger.exception(f"Clear roles command failed: {e}")
                await interaction.channel.send("Clear roles command failed. Contact admin.")
        elif confirm.value is False:
            logger.info(f"User {interaction.user.name} wants to abort the role-clearing process.")
            await interaction.edit_original_response(
                content="You aborted the request to clear booze roles", embed=None, view=None
            )
        else:  # (confirm.value is None) Timeout on the view buttons
            logger.info(f"User {interaction.user.name} did not respond in time to the confirmation view.")
            await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None, view=None
            )

    @app_commands.command(
        name="booze_update_blurb_message", description="Update a blurb message (WCO welcome or announcement)."
    )
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def update_blurb_message(self, interaction: discord.Interaction, blurb: BLURB_KEYS):
        logger.info(f"User {interaction.user.name} is changing the {blurb} message in {interaction.channel.name}.")

        # send the existing message (if there is one) so the user has a copy
        if not BLURBS[blurb]["file_path"].is_file():
            logger.warning(f"Blurb file for '{blurb}' not found. Initializing blurb files.")
            self.init_blurbs()
        blurb_message = BLURBS[blurb]["file_path"].read_text()

        response_timeout = 20

        logger.info(f"Prompting user {interaction.user.name} to provide new {blurb} message within {response_timeout} seconds.")
        await interaction.response.send_message(
            f"Existing message: ```\n{blurb_message}\n```\n"
            f"<@{interaction.user.id}> your next message in this channel will be used as the new {blurb} message, "
            f"or wait {response_timeout} seconds to cancel."
        )

        def check(response):
            valid =  response.author == interaction.user and response.channel == interaction.channel
            if not valid:
                logger.debug(f"Ignored message from {response.author.name} in channel {response.channel.name}.")
            return valid

        try:
            # process the response
            logger.debug("Waiting for user message response.")
            message = await bot.wait_for("message", check=check, timeout=response_timeout)

        except TimeoutError:
            logger.info(f"User {interaction.user.name} did not provide a new {blurb} message within the timeout period.")
            return await interaction.edit_original_response(content="No valid response detected.")

        if message:
            logger.info(f"Received new {blurb} message from user {interaction.user.name}.")
            # Now try to replace the contents
            logger.debug(f"Old {blurb} message: {blurb_message}")
            logger.debug(f"New {blurb} message: {message.content.strip()}")
            logger.debug(f"Writing new {blurb} message to file: {BLURBS[blurb]['file_path']}")
            BLURBS[blurb]["file_path"].write_text(message.content.strip())
            embed = discord.Embed(description=message.content)
            if blurb == "wco_welcome":
                logger.debug("Setting thumbnail for WCO welcome message.")
                embed.set_thumbnail(url=WCO_ROLE_ICON_URL)
            logger.info(f"{blurb} message updated successfully by user {interaction.user.name}.")
            await interaction.edit_original_response(content=f"New {blurb} message set:", embed=embed)
            await message.delete()

    @app_commands.command(name="open_wine_carrier_feedback", description="Opens the Wine Carrier feedback channel.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def open_wine_carrier_feedback(self, interaction: discord.Interaction):
        logger.info(
            f"User {interaction.user.name} is opening the wine carrier feedback channel in {interaction.channel.name}."
        )

        wine_feedback_channel = await get_channel(get_feedback_channel_id())
        wine_carrier_role = await get_role(server_wine_carrier_role_id())
        overwrite = discord.PermissionOverwrite(view_channel=True)

        await wine_feedback_channel.set_permissions(wine_carrier_role, overwrite=overwrite)
        
        logger.info("Wine Carrier feedback channel opened successfully.")
        await interaction.response.send_message("Opened the Wine Carrier feedback channel.", embed=None)

    @app_commands.command(name="close_wine_carrier_feedback", description="Closes the Wine Carrier feedback channel.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def close_wine_carrier_feedback(self, interaction: discord.Interaction):
        logger.info(
            f"User {interaction.user.name} is closing the wine carrier feedback channel in {interaction.channel.name}."
        )

        wine_feedback_channel = await get_channel(get_feedback_channel_id())
        wine_carrier_role = await get_role(server_wine_carrier_role_id())
        overwrite = discord.PermissionOverwrite(view_channel=False)

        await wine_feedback_channel.set_permissions(wine_carrier_role, overwrite=overwrite)
        
        logger.info("Wine Carrier feedback channel closed successfully.")
        await interaction.response.send_message("Closed the Wine Carrier feedback channel.", embed=None)

    @app_commands.command(name="booze_update_bc_status_embed", description="Updates the booze-cruise-status embed.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def update_bc_status_embed(self, interaction: discord.Interaction, status: BC_STATUS):
        await interaction.response.defer()
        logger.info(f"User {interaction.user.name} is updating the status embed to {status}.")
        await self.update_status_embed(status)
        logger.info(f"Status embed updated to {status} by user {interaction.user.name}.")
        await interaction.followup.send(f"Updated the status embed to {status}.", ephemeral=True)

    @classmethod
    async def update_status_embed(cls, status: BC_STATUS):
        logger.debug(f"Updating status embed to: {status}")
        channel = await get_channel(get_wine_status_channel())
        async for message in channel.history():
            logger.debug(f"Checking message ID: {message.id} for deletion.")
            if message.author == bot.user or not message.pinned:
                await message.delete()
                logger.debug(f"Deleted message ID: {message.id}")

        if not BLURBS[status]["file_path"].is_file():
            logger.warning(f"Blurb file for status '{status}' not found. Initializing blurb files.")
            cls.init_blurbs()
        blurb_message = BLURBS[status]["file_path"].read_text()
        blurb_message += f"\n\n-# Updated: <t:{int(datetime.now(timezone.utc).timestamp())}:F>"
        embed_colour = BLURBS[status]["embed_colour"]
        await channel.send(embed=discord.Embed(description=blurb_message, colour=embed_colour))
        logger.debug(f"Sent new status embed for status: {status}")
