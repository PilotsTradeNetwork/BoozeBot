"""
Cog for all the commands related to

"""

from asyncio import TimeoutError
from datetime import datetime, timezone

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
        self.init_blurbs()

    @staticmethod
    def init_blurbs():
        # Ensure all blurb files exist
        for blurb in BLURBS.values():
            if not blurb["file_path"].is_file():
                blurb["file_path"].parent.mkdir(parents=True, exist_ok=True)
                blurb["file_path"].write_text(blurb["default_text"], encoding="utf-8")

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
        print(f"User {interaction.user.name} requested BC channel opening in channel: {interaction.channel.name}.")

        await interaction.response.defer()
        check_embed = discord.Embed(
            title="Open Booze Cruise Channels", description="You have requested to open the booze cruise channels:"
        )
        confirm = ConfirmView(interaction.user)
        await interaction.edit_original_response(embed=check_embed, view=confirm)
        await confirm.wait()
        if confirm.value:
            ids_list = get_public_channel_list()

            embed = discord.Embed()
            Departures.departure_announcement_status = "Disabled"
            Unloading.timed_unloads_allowed = False
            pilot_role = await get_role(server_pilot_role_id())
            channels = {channel_id: pilot_role for channel_id in ids_list}
            channels[get_wine_carrier_guide_channel_id()] = await get_role(get_ptn_booze_cruise_role_id())

            await self.update_status_embed("bc_prep")

            for channel_id, role in channels.items():
                channel = await get_channel(channel_id)
                try:
                    overwrite = channel.overwrites_for(role)
                    overwrite.view_channel = True  # less confusing alias for read_messages
                    await channel.set_permissions(role, overwrite=overwrite)
                    embed.add_field(name="Opened", value="<#" + str(channel_id) + ">", inline=False)
                except Exception as e:
                    embed.add_field(name="FAILED to open", value="<#" + str(channel_id) + f">: {e}", inline=False)

            await interaction.edit_original_response(
                content=f"<@&{server_sommelier_role_id()}> Avast! We're ready to set sail!", embed=embed, view=None
            )
            print("Channels opened successfully.")
        elif confirm.value is False:
            print(f"User {interaction.user.name} wants to abort the open process.")
            await interaction.edit_original_response(
                content="You aborted the request to open the channels", embed=None, view=None
            )
        else:  # (confirm.value is None) Timeout on the view buttons
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
        print(f"User {interaction.user.name} requested BC channel closing in channel: {interaction.channel.name}.")

        await interaction.response.defer()
        check_embed = discord.Embed(
            title="Close Booze Cruise Channels", description="You have requested to close the booze cruise channels:"
        )
        confirm = ConfirmView(interaction.user)
        await interaction.edit_original_response(embed=check_embed, view=confirm)
        await confirm.wait()
        if confirm.value:
            ids_list = get_public_channel_list()

            embed = discord.Embed()
            pilot_role = await get_role(server_pilot_role_id())
            channels = dict.fromkeys(ids_list, pilot_role)
            channels[get_wine_carrier_guide_channel_id()] = await get_role(get_ptn_booze_cruise_role_id())

            for channel_id, role in channels.items():
                channel = await get_channel(channel_id)
                try:
                    overwrite = channel.overwrites_for(role)
                    overwrite.view_channel = False  # less confusing alias for read_messages
                    await channel.set_permissions(role, overwrite=overwrite)
                    embed.add_field(name="Closed", value="<#" + str(channel_id) + ">", inline=False)
                except Exception as e:
                    embed.add_field(name="FAILED to close", value="<#" + str(channel_id) + f">: {e}", inline=False)
            await self.update_status_embed("bc_end")
            await interaction.edit_original_response(
                content=f"<@&{server_sommelier_role_id()}> That's the end of that, me hearties.", embed=embed, view=None
            )
        elif confirm.value is False:
            print(f"User {interaction.user.name} wants to abort the close process.")
            await interaction.edit_original_response(
                content="You aborted the request to close the channels", embed=None, view=None
            )
        else:  # (confirm.value is None) Timeout on the view buttons
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
        print(
            f"User {interaction.user.name} requested clearing all Booze related roles in channel: {interaction.channel.name}."
        )
        await interaction.response.defer()
        check_embed = discord.Embed(
            title="Remove Booze Cruise Roles", description="You have requested to clear all Booze related roles"
        )
        confirm = ConfirmView(interaction.user)
        await interaction.edit_original_response(embed=check_embed, view=confirm)
        await confirm.wait()
        if confirm.value:
            wine_role_id = server_wine_carrier_role_id()
            wine_carrier_role = await get_role(wine_role_id)

            hitch_role_id = server_hitchhiker_role_id()
            hitch_role = await get_role(hitch_role_id)

            wine_count = 0
            hitch_count = 0
            await interaction.edit_original_response(
                content="Removing roles, This may take a minute...", embed=None, view=None
            )
            try:
                for member in wine_carrier_role.members:
                    try:
                        await member.remove_roles(wine_carrier_role)
                        wine_count += 1
                    except Exception as e:
                        print(e)
                        await interaction.channel.send(f"Unable to remove {wine_carrier_role} from {member}")
                for member in hitch_role.members:
                    try:
                        await member.remove_roles(hitch_role)
                        hitch_count += 1
                    except Exception as e:
                        print(e)
                        await interaction.channel.send(f"Unable to remove {hitch_role} from {member}")

                await interaction.edit_original_response(
                    content=f"Successfully removed {hitch_count} users from the Hitchhiker role.\n"
                    f"Successfully removed {wine_count} users from the Wine Carrier role.",
                    embed=None,
                    view=None,
                )
            except Exception as e:
                print(e)
                await interaction.channel.send("Clear roles command failed. Contact admin.")
        elif confirm.value is False:
            print(f"User {interaction.user.name} wants to abort the role-clearing process.")
            await interaction.edit_original_response(
                content="You aborted the request to clear booze roles", embed=None, view=None
            )
        else:  # (confirm.value is None) Timeout on the view buttons
            await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None, view=None
            )

    @app_commands.command(
        name="booze_update_blurb_message", description="Update a blurb message (WCO welcome or announcement)."
    )
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def update_blurb_message(self, interaction: discord.Interaction, blurb: BLURB_KEYS):
        print(f"User {interaction.user.name} is changing the {blurb} message in {interaction.channel.name}.")

        # send the existing message (if there is one) so the user has a copy
        if not BLURBS[blurb]["file_path"].is_file():
            self.init_blurbs()
        blurb_message = BLURBS[blurb]["file_path"].read_text()

        response_timeout = 20

        await interaction.response.send_message(
            f"Existing message: ```\n{blurb_message}\n```\n"
            f"<@{interaction.user.id}> your next message in this channel will be used as the new {blurb} message, "
            f"or wait {response_timeout} seconds to cancel."
        )

        def check(response):
            return response.author == interaction.user and response.channel == interaction.channel

        try:
            # process the response
            print("Waiting for user response...")
            message = await bot.wait_for("message", check=check, timeout=response_timeout)

        except TimeoutError:
            print("No valid response detected")
            return await interaction.edit_original_response(content="No valid response detected.")

        if message:
            # Now try to replace the contents
            print(f"Setting {blurb} message from user input")
            BLURBS[blurb]["file_path"].write_text(message.content.strip())
            embed = discord.Embed(description=message.content)
            if blurb == "wco_welcome":
                embed.set_thumbnail(url=WCO_ROLE_ICON_URL)
            await interaction.edit_original_response(content=f"New {blurb} message set:", embed=embed)
            await message.delete()

    @app_commands.command(name="open_wine_carrier_feedback", description="Opens the Wine Carrier feedback channel.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def open_wine_carrier_feedback(self, interaction: discord.Interaction):
        print(
            f"User {interaction.user.name} is opening the wine carrier feedback channel in {interaction.channel.name}."
        )

        wine_feedback_channel = await get_channel(get_feedback_channel_id())
        wine_carrier_role = await get_role(server_wine_carrier_role_id())
        overwrite = discord.PermissionOverwrite(view_channel=True)

        await wine_feedback_channel.set_permissions(wine_carrier_role, overwrite=overwrite)
        await interaction.response.send_message("Opened the Wine Carrier feedback channel.", embed=None)

    @app_commands.command(name="close_wine_carrier_feedback", description="Closes the Wine Carrier feedback channel.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def close_wine_carrier_feedback(self, interaction: discord.Interaction):
        print(
            f"User {interaction.user.name} is closing the wine carrier feedback channel in {interaction.channel.name}."
        )

        wine_feedback_channel = await get_channel(get_feedback_channel_id())
        wine_carrier_role = await get_role(server_wine_carrier_role_id())
        overwrite = discord.PermissionOverwrite(view_channel=False)

        await wine_feedback_channel.set_permissions(wine_carrier_role, overwrite=overwrite)
        await interaction.response.send_message("Closed the Wine Carrier feedback channel.", embed=None)

    @app_commands.command(name="booze_update_bc_status_embed", description="Updates the booze-cruise-status embed.")
    @check_roles([*server_council_role_ids(), server_sommelier_role_id(), server_mod_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def update_bc_status_embed(self, interaction: discord.Interaction, status: BC_STATUS):
        await interaction.response.defer()
        print(f"User {interaction.user.name} is updating the status embed in {interaction.channel.name}.")
        await self.update_status_embed(status)
        await interaction.followup.send(f"Updated the status embed to {status}.", ephemeral=True)

    @classmethod
    async def update_status_embed(cls, status: BC_STATUS):
        channel = await get_channel(get_wine_status_channel())
        async for message in channel.history():
            if message.author == bot.user or not message.pinned:
                await message.delete()

        if not BLURBS[status]["file_path"].is_file():
            cls.init_blurbs()
        blurb_message = BLURBS[status]["file_path"].read_text()
        blurb_message += f"\n\n-# Updated: <t:{int(datetime.now(timezone.utc).timestamp())}:F>"
        embed_colour = BLURBS[status]["embed_colour"]
        await channel.send(embed=discord.Embed(description=blurb_message, colour=embed_colour))
