"""
Cog for all the commands that interact with the database

"""

from datetime import datetime, timedelta
import math
from typing import Any, Literal

import discord
from discord import CustomActivity, Embed, Status, app_commands
from discord.app_commands import describe
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from ptn_utils.enums.booze_enums import CruiseSystemState
from ptn_utils.global_constants import (
    CHANNEL_BC_STEVE_SAYS,
    CHANNEL_BC_WINE_CARRIER,
    DISCORD_GUILD,
    EMOJI_PTN_ROLE_ICON,
    ROLE_CONN,
    ROLE_SOMM,
    ROLE_WINE_CARRIER,
    any_council_role,
    any_moderation_role,
)
from ptn_utils.logger.logger import get_logger
from ptn_utils.pagination.pagination import PaginationView

from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier
from ptn.boozebot.classes.Cruise import Cruise
from ptn.boozebot.constants import RACKHAMS_PEAK_POP, bot
from ptn.boozebot.database.database import database
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api
from ptn.boozebot.modules.helpers import (
    bc_channel_status,
    check_command_channel,
    check_roles,
    track_last_run,
)

"""
Statistics COMMANDS

/find_carriers_with_wine - admin/mod/somm/conn/wine carrier
/find_wine_carrier_by_id - admin/mod/somm/conn/wine carrier
/booze_tally - admin/mod/somm/conn
/booze_carrier_summary - admin/mod/somm/conn
/booze_pin_message - admin/mod/somm
/booze_unpin_all - admin/mod/somm
/booze_unpin_message - admin/mod/somm
/booze_tally_extra_stats - admin/mod/somm/conn
/biggest_cruise_tally - admin/mod/somm/conn
/booze_carrier_stats - admin/mod/somm/conn/wine carrier
"""

logger = get_logger("boozebot.commands.statistics")


def format_large_number(number: int | float) -> str:
    """
    Formats a large number with proper quantifier (Million, Billion, Trillion).

    :param number: The number to format
    :returns: Formatted string with quantifier
    """
    if number < 10**6:
        return f"{number:,.0f}"
    elif number < 10**9:
        return f"{number / 10**6:.2f} Million"
    elif number < 10**12:
        return f"{number / 10**9:.2f} Billion"
    else:
        return f"{number / 10**12:.2f} Trillion"


def format_duration(seconds: int | float) -> str:
    """
    Formats a duration in seconds with proper time units (seconds/minutes/hours).

    :param seconds: The duration in seconds
    :returns: Formatted string with time unit
    """
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 60 * 60:
        return f"{seconds / 60:.2f} minutes"
    else:
        return f"{seconds / 3600:.2f} hours"


IncludeNotUnloadedChoices = Literal["All Carriers", "Only Unloaded"]
FactionStateChoices = Literal[
    "Public Holiday",
    "Blight",
    "Boom",
    "Bust",
    "Civil liberty",
    "Civil unrest",
    "Civil war",
    "Cold war",
    "Colonisation",
    "Drought",
    "Elections",
    "Expansion",
    "Famine",
    "Historic event",
    "Infrastructure failure",
    "Investment",
    "Lockdown",
    "Natural disaster",
    "Outbreak",
    "Pirate attack",
    "Retreat",
    "Revolution",
    "Technological leap",
    "Terrorist attack",
]
StatChoices = Literal[
    "All",
    "Rackhams Population",
    "Server Population",
    "USA Population",
    "Scotland Population",
    "London Busses",
    "Swimming Pools",
    "Volume Maths",
]


class Statistics(commands.Cog):
    bot: Bot

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def build_stat_embed(
        self,
        cruise: Cruise,
        target_date: str = None,
        include_timestamp: bool = False,
    ) -> discord.Embed:
        # Get faction state from the first carrier, assuming all carriers have the same state
        logger.info(f"Building stat embed for booze tally, target_date: {target_date}")
        total_wine = cruise.stats.total_wine
        unique_carrier_count = cruise.stats.total_carriers
        total_trips = cruise.stats.total_trips
        total_profit = cruise.stats.total_profit

        profit_per_tonne = total_profit // total_wine if total_wine else 0

        wine_per_capita = total_wine / RACKHAMS_PEAK_POP
        wine_per_carrier = total_wine / unique_carrier_count if unique_carrier_count > 0 else 0
        python_loads = total_wine / 288
        t8_loads = total_wine / 400
        fleet_carrier_buy_count = total_profit / 5000000000

        logger.debug(
            f"Calculated stats - Carrier Count: {unique_carrier_count}, Total Wine: {total_wine}, Total Profit: {total_profit}, "
            + f"Wine/Carrier: {wine_per_carrier}, PythonLoads: {python_loads}, Wine/Capita: {wine_per_capita}, Carrier Buys: {fleet_carrier_buy_count}"
        )

        if total_wine > 4000000:
            flavour_text = "By the powers! That's enough grog to float a man-o'-war!\nBatten down the barrels!"
        elif total_wine > 3500000:
            flavour_text = "Avast! The wine flows like the seven seas, fetch the biggest cask ye can find!"
        elif total_wine > 3000000:
            flavour_text = "Shiver Me Timbers! This sea dog cannot fathom this much grog!"
        elif total_wine > 2500000:
            flavour_text = "Sink me! We might send them to Davy Jone`s locker."
        elif total_wine > 2000000:
            flavour_text = "Blimey! Pieces of eight all round! We have a lot of grog. Savvy?"
        elif total_wine > 1500000:
            flavour_text = "The coffers are looking better, get the Galleys filled with wine!"
        elif total_wine > 1000000:
            flavour_text = "Yo ho ho we have some grog!"
        else:
            flavour_text = "Heave Ho ye Scurvy Dogs! Pirate Steve wants more grog!"

        date_text = (
            f":\nHistorical Data: [{target_date} - "
            + f"{datetime.strptime(target_date, '%Y-%m-%d').date() + timedelta(days=2)}]"
            if target_date
            else ""
        )

        updated_timestamp = f"\n\nLast updated: <t:{int(datetime.now().timestamp())}:F>" if include_timestamp else ""
        state_warning_msg = (
            "### The Public Holiday did not happen for this cruise.\n### None of these carriers got unloaded.\n\n"
        )
        state_text = state_warning_msg if cruise.faction_state not in ["Public Holiday", None] else ""

        # Build the embed
        stat_embed = discord.Embed(
            title=f"Pirate Steve's Booze Cruise Tally {date_text}",
            description=f"{state_text}"
            + f"**Total number of carrier trips:** — {total_trips:>1}\n"
            + f"**Total number of unique carriers:** — {unique_carrier_count:>24}\n"
            + f"**Profit per ton:** — {profit_per_tonne:>56,}\n"
            + f"**Rackham pop:** — {RACKHAMS_PEAK_POP:>56,}\n"
            + f"**Wine per capita:** — {wine_per_capita:>56,.2f}\n"
            + f"**Wine per carrier:** — {math.ceil(wine_per_carrier):>56,}\n"
            + f"**Python loads (288t):** — {math.ceil(python_loads):>56,}\n"
            + f"**Type-8 loads (400t):** — {math.ceil(t8_loads):>56,}\n\n"
            + f"**Total wine:** — {total_wine:,}\n"
            + f"**Total profit:** — {total_profit:,}\n\n"
            + f"**Total number of fleet carriers that profit can buy:** — {fleet_carrier_buy_count:,.2f}\n\n"
            + f"{flavour_text}\n\n"
            + f"{updated_timestamp}",
        )
        stat_embed.set_image(
            url="https://cdn.discordapp.com/attachments/783783142737182724/849157248923992085/unknown.png"
        )
        stat_embed.set_footer(
            text="This function is a clone of b.tally from CMDR Suiseiseki.\nPirate Steve hopes the values match!"
        )

        logger.info("Stat embed built successfully")
        return stat_embed

    async def build_extended_stat_embed(
        self,
        cruise: Cruise,
        target_date: str = None,
        stat: StatChoices = "All",
    ) -> discord.Embed:
        # Get faction state from the first carrier, assuming all carriers have the same state

        logger.info(
            f"Building extended stat embed for booze tally extra stats, target_date: {target_date}, stat: {stat}"
        )

        total_wine = cruise.stats.total_wine

        total_wine_per_capita = total_wine / RACKHAMS_PEAK_POP

        # Some constants for the data. The figures came from RandomGazz, complain to him if they are wrong.
        wine_bottles_weight_kg = 1.25
        wine_bottles_per_tonne = 1000 / wine_bottles_weight_kg
        wine_bottles_litres_per_tonne = wine_bottles_per_tonne * 0.75
        wine_bottles_total = total_wine * wine_bottles_per_tonne
        wine_bottles_litres_total = total_wine * wine_bottles_litres_per_tonne
        wine_bottles_per_capita = total_wine_per_capita * wine_bottles_per_tonne
        wine_bottles_litres_per_capita = total_wine_per_capita * wine_bottles_litres_per_tonne

        wine_box_weight_kg = 2.30
        wine_boxes_per_tonne = 1000 / wine_box_weight_kg
        wine_boxes_litres_per_tonne = wine_boxes_per_tonne * 2.25
        wine_boxes_total = wine_boxes_per_tonne * total_wine
        wine_boxes_litres_total = wine_boxes_litres_per_tonne * total_wine
        wine_boxes_per_capita = total_wine_per_capita * wine_boxes_per_tonne
        wine_boxes_litres_per_capita = total_wine_per_capita * wine_boxes_litres_per_tonne

        usa_population = 328200000
        tons_per_us_pop = total_wine / usa_population
        wine_bottles_per_us_pop = wine_bottles_total / usa_population
        wine_bottles_litres_per_us_pop = wine_bottles_litres_total / usa_population
        wine_boxes_per_us_pop = wine_boxes_total / usa_population
        wine_boxes_litres_per_us_pop = wine_boxes_litres_total / usa_population

        scotland_population = 5454000
        tons_per_scot_pop = total_wine / scotland_population
        wine_bottles_per_scot_pop = wine_bottles_total / scotland_population
        wine_bottles_litres_per_scot_pop = wine_bottles_litres_total / scotland_population
        wine_boxes_per_scot_pop = wine_boxes_total / scotland_population
        wine_boxes_litres_per_scot_pop = wine_boxes_litres_total / scotland_population

        server_population = (await bot.get_or_fetch.guild(DISCORD_GUILD)).member_count or 1
        tons_per_server_pop = total_wine / server_population
        wine_bottles_per_server_pop = wine_bottles_total / server_population
        wine_bottles_litres_per_server_pop = wine_bottles_litres_total / server_population
        wine_boxes_per_server_pop = wine_boxes_total / server_population
        wine_boxes_litres_per_server_pop = wine_boxes_litres_total / server_population

        olympic_swimming_pool_volume = 2500000
        pools_if_bottles = wine_bottles_litres_total / olympic_swimming_pool_volume
        pools_if_boxes = wine_boxes_litres_total / olympic_swimming_pool_volume

        london_bus_volume_l = 112.5 * 1000
        busses_if_bottles = wine_bottles_litres_total / london_bus_volume_l
        busses_if_boxes = wine_boxes_litres_total / london_bus_volume_l

        logger.debug("Calculated extended stats for embed")

        date_text = (
            f":\nHistorical Data: [{target_date} - "
            + f"{datetime.strptime(target_date, '%Y-%m-%d').date() + timedelta(days=2)}]"
            if target_date
            else ""
        )
        state_warning_msg = (
            "### The Public Holiday did not happen for this cruise.\n### None of these carriers got unloaded.\n\n"
        )
        state_text = state_warning_msg if cruise.faction_state not in ["Public Holiday", None] else ""

        volume_text = (
            "### Volume Maths :straight_ruler:\n"
            f"Weight of 1 750ml bottle (kg): {wine_bottles_weight_kg}\n"
            f"Wine bottles per tonne: {wine_bottles_per_tonne}\n"
            f"Wine bottles litres per tonne: {wine_bottles_litres_per_tonne:,.2f}\n"
            f"Wine bottles total: {wine_bottles_total:,.0f}\n"
            f"Wine bottles litres total: {wine_bottles_litres_total:,.2f}\n\n"
            f"Weight of box wine 2.25L (kg): {wine_box_weight_kg:,.2f}\n"
            f"Wine boxes per tonne: {wine_boxes_per_tonne:,.2f}\n"
            f"Wine boxes litre per tonne: {wine_boxes_litres_per_tonne:,.2f}\n"
            f"Wine boxes total: {wine_boxes_total:,.2f}\n"
            f"Wine boxes litres total: {wine_boxes_litres_total:,.2f}\n\n"
        )

        rackhams_text = (
            "### Rackhams Peak Population Stats :wine_glass:\n"
            f"Population: {RACKHAMS_PEAK_POP:,}\n"
            f"Tonnes per capita: {total_wine_per_capita:,.2f}\n"
            f"Bottles per capita: {wine_bottles_per_capita:,.2f}\n"
            f"Bottles litres per capita: {wine_bottles_litres_per_capita:,.2f}\n"
            f"Boxes per capita: {wine_boxes_per_capita:,.2f}\n"
            f"Boxes litres per capita: {wine_boxes_litres_per_capita:,.2f}\n\n"
        )

        ptn_logo_emoji = await bot.get_or_fetch.emoji(EMOJI_PTN_ROLE_ICON)
        server_text = (
            f"### Server Population Stats {ptn_logo_emoji}\n"
            f"Population: {server_population:,}\n"
            f"Tonnes per capita: {tons_per_server_pop:,.2f}\n"
            f"Bottles per capita: {wine_bottles_per_server_pop:,.2f}\n"
            f"Bottles litres per capita: {wine_bottles_litres_per_server_pop:,.2f}\n"
            f"Boxes per capita: {wine_boxes_per_server_pop:,.2f}\n"
            f"Boxes litres per capita: {wine_boxes_litres_per_server_pop:,.2f}\n\n"
        )

        usa_text = (
            "### USA Population Stats :flag_us:\n"
            f"Population: {usa_population:,}\n"
            f"Tonnes per capita: {tons_per_us_pop:,.2f}\n"
            f"Bottles per capita: {wine_bottles_per_us_pop:,.2f}\n"
            f"Bottles litres per capita: {wine_bottles_litres_per_us_pop:,.2f}\n"
            f"Boxes per capita: {wine_boxes_per_us_pop:,.2f}\n"
            f"Boxes litres per capita: {wine_boxes_litres_per_us_pop:,.2f}\n\n"
        )

        scotland_text = (
            "### Scotland Population Stats :scotland:\n"
            f"Population: {scotland_population:,}\n"
            f"Tonnes per capita: {tons_per_scot_pop:,.2f}\n"
            f"Bottles per capita: {wine_bottles_per_scot_pop:,.2f}\n"
            f"Bottles litres per capita: {wine_bottles_litres_per_scot_pop:,.2f}\n"
            f"Boxes per capita: {wine_boxes_per_scot_pop:,.2f}\n"
            f"Boxes litres per capita: {wine_boxes_litres_per_scot_pop:,.2f}\n\n"
        )

        busses_text = (
            "### London Bus Volume\n"
            f"London bus volume (L): {london_bus_volume_l:,}\n"
            f"London busses if bottles of wine: {busses_if_bottles:,.2f}\n"
            f"London busses if boxes of wine: {busses_if_boxes:,.2f}\n\n"
        )

        swimming_pools_text = (
            "### Olympic Swimming Pool Volume\n"
            f"Olympic swimming pool volume (L): {olympic_swimming_pool_volume:,}\n"
            f"Olympic swimming pools if bottles of wine: {pools_if_bottles:,.2f}\n"
            f"Olympic swimming pools if boxes of wine: {pools_if_boxes:,.2f}\n\n"
        )

        description_text = f"{state_text}## Wine Tonnes: {total_wine:,}\n\n"

        logger.debug(f"Assembling extended stat embed description based on selected stat: {stat}")

        match stat:
            case "All":
                description_text += (
                    volume_text
                    + rackhams_text
                    + server_text
                    + usa_text
                    + scotland_text
                    + swimming_pools_text
                    + busses_text
                )
            case "Rackhams Population":
                description_text += rackhams_text
            case "Server Population":
                description_text += server_text
            case "USA Population":
                description_text += usa_text
            case "Scotland Population":
                description_text += scotland_text
            case "London Busses":
                description_text += busses_text
            case "Swimming Pools":
                description_text += swimming_pools_text
            case "Volume Maths":
                description_text += volume_text

        logger.debug("Extended stat embed description assembled successfully")

        stat_embed = discord.Embed(
            title=f"Pirate Steve's Extended Booze Tally {date_text}", description=description_text
        )
        stat_embed.set_footer(text="Stats requested by RandomGazz.\nPirate Steve approves of these stats!")
        logger.info("Extended stat embed built successfully")
        return stat_embed

    """
    Pinned Stats and Activity Update Task Loop

    """

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Starting periodic stat update task loop")
        if not self.periodic_stat_update.is_running():
            self.periodic_stat_update.start()

    @commands.Cog.listener()
    async def on_boozesheets_carrier_created(self, data: dict[str, Any]):
        logger.info("BoozeSheets carrier created event received")

        carrier = BoozeCarrier(data.get("carrier", {}))

        embed = Embed(
            title="New WineCarrier signed up!",
            description=(
                f"**{carrier.carrier_name} ({carrier.carrier_identifier})**\n"
                + f"Trip Number: {carrier.trip_id}\n"
                + f"**{carrier.wine_total} tonnes of wine**\n"
                + f"Owned by {carrier.owner.mention} ({carrier.owner.username})"
            ),
        )

        steve_says = await bot.get_or_fetch.channel(CHANNEL_BC_STEVE_SAYS)

        await steve_says.send(embed=embed)

        logger.info("New WineCarrier announcement sent to Steve Says channel")

    @tasks.loop(minutes=10)
    @track_last_run()
    async def periodic_stat_update(self):
        """
        Loops every hour and updates all pinned embeds and bot activity status.

        :returns: None
        """
        logger.info("Running periodic stat update task")
        try:
            # Periodic trigger that updates all the stat embeds that are pinned.

            # Get everything
            all_pins = await database.get_all_pinned_messages()

            cruise = await booze_sheets_api.get_cruise_with_stats(0)

            if not cruise:
                logger.warning("No cruise data available, skipping periodic stat update")
                return

            stat_embed = await self.build_stat_embed(cruise, None, True)

            logger.debug("Updating pinned messages with new stat embed")
            if all_pins:
                logger.info(f"Found {len(all_pins)} pinned messages to update")
                for pin in all_pins:
                    logger.debug(f"Updating pinned message: {pin}")
                    channel = await bot.get_or_fetch.channel(int(pin[1]))
                    message = await channel.fetch_message(pin[0])
                    await message.edit(embed=stat_embed)
                    logger.debug(f"Pinned message updated successfully: {pin}")
                logger.info("All pinned messages updated successfully")
            else:
                logger.debug("No pinned messages found to update")

            logger.debug("Updating bot activity status")
            total_wine = cruise.stats.total_wine

            if await bc_channel_status():
                state_text = f"Total Wine Tracked: {total_wine:,}"
                status = Status.online
            else:
                state_text = "Arrr, the wine be drained!"
                status = Status.idle

            activity = CustomActivity(
                name=state_text,
            )

            await self.bot.change_presence(
                activity=activity,
                status=status,
            )
            logger.debug("Bot activity status updated successfully")
            logger.info("Periodic stat update task completed successfully")
        except Exception as e:
            logger.exception(f"Error during periodic stat update: {e}")

    """
    Database interaction Commands

    """

    @app_commands.command(
        name="find_carriers_with_wine",
        description="Returns the carriers in the database that are still flagged as having wine remaining.",
    )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    @check_command_channel([CHANNEL_BC_WINE_CARRIER, CHANNEL_BC_STEVE_SAYS])
    async def find_carriers_with_wine(self, interaction: discord.Interaction):
        """
        Returns an interactive list of all the carriers with wine that has not yet been unloaded.

        :param interaction discord.Interaction: The discord interaction context
        :returns: An interactive message embed.
        :rtype: Union[discord.Message, dict]
        """

        await interaction.response.defer()

        logger.info(f"{interaction.user.name} requested to find the carriers with wine")

        carrier_data = await booze_sheets_api.get_carriers_with_wine_remaining()
        if len(carrier_data) == 0:
            # No carriers remaining
            logger.info("No carriers with wine remaining found in the database")
            await interaction.edit_original_response(
                content="Pirate Steve is sorry, but there are no more carriers with wine remaining.", embed=None
            )
            return

        # Else we have wine left

        carrier_list_data = [
            (
                f"{carrier.carrier_name} ({carrier.carrier_identifier})",
                f"{carrier.wine_total} tonnes",
            )
            for carrier in carrier_data
        ]

        logger.info(f"Found {len(carrier_data)} carriers with wine remaining")
        for carrier in carrier_data:
            logger.debug(f"Carrier with wine remaining: {carrier}")

        async def buttons_callback(interaction: discord.Interaction, title: str, index: int):
            carrier = carrier_data[index]

            total_unloads = carrier.trip_id if carrier.unload_closed else carrier.trip_id - 1

            carrier_embed = discord.Embed(
                title=f"{title} Details",
                description=f"CarrierName: **{carrier.carrier_name}**\n"
                + f"ID: **{carrier.carrier_identifier}**\n"
                + f"Location: **{carrier.location_string}\n**"
                + f"Trip wine total: **{carrier.wine_total}**\n"
                + f"Number of trips to the peak: **{carrier.trip_id}**\n"
                + f"Total unloads: **{total_unloads}**\n"
                + f"Operated by: {carrier.owner.mention}\n"
                + f"Is staff: {'Yes' if carrier.is_staff else 'No'}",
            )

            await interaction.response.send_message(embed=carrier_embed, ephemeral=True)

        view = PaginationView(
            title="Carriers with wine remaining",
            content=carrier_list_data,
            buttons_text="More info",
            buttons_callback=buttons_callback,
        )

        message = await interaction.edit_original_response(view=view)
        view.message = message

    @app_commands.command(
        name="find_wine_carrier_by_id",
        description="Returns the carriers in the database for the ID.",
    )
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    async def find_carrier_by_id(self, interaction: discord.Interaction, carrier_id: str):
        await interaction.response.defer()
        logger.info(f"{interaction.user.name} ({interaction.user.id}) wants to find a carrier by ID: {carrier_id}.")

        carrier_data = await booze_sheets_api.get_carrier_info(carrier_id)

        if not carrier_data:
            logger.info(f"No carrier found for ID: {carrier_id}.")
            await interaction.edit_original_response(content=f'No carrier found for ID: "{carrier_id}".')
            return

        all_carrier_trips = [carrier_data]

        for trip_id in range(1, carrier_data.trip_id):
            trip_data = await booze_sheets_api.get_trip_for_carrier(carrier_id, trip_id)
            if trip_data:
                all_carrier_trips.append(trip_data)

        all_carrier_trips.sort(key=lambda x: x.trip_id)

        total_wine = sum(trip.wine_total for trip in all_carrier_trips)
        total_unloads = sum(1 if trip.unload_closed else 0 for trip in all_carrier_trips)

        carrier_embed = discord.Embed(
            title=f"YARR! Found carrier details for the input: {carrier_id}",
            description=f"CarrierName: **{carrier_data.carrier_name}**\n"
            + f"ID: **{carrier_data.carrier_identifier}**\n"
            + f"Total Tonnes of Wine: **{total_wine}**\n"
            + f"Number of trips to the peak: **{carrier_data.trip_id}**\n"
            + f"Total Unloads: **{total_unloads}**\n"
            + f"Operated by: {carrier_data.owner.mention}",
        )
        await interaction.edit_original_response(embed=carrier_embed)

    @app_commands.command(
        name="booze_tally",
        description="Returns a summary of the stats for the current booze cruise. Restricted to Somms and Connoisseurs.",
    )
    @describe(
        cruise_select="Which cruise do you want data for. 0 is this cruise, 1 the last cruise etc. Default is this cruise.",
        include_not_unloaded="Force select if we should include carriers that have not unloaded yet.",
    )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
        ]
    )
    async def tally(
        self,
        interaction: discord.Interaction,
        cruise_select: int = 0,
        include_not_unloaded: IncludeNotUnloadedChoices | None = None,
    ):
        """
        Returns an embed inspired by (cloned from) @CMDR Suiseiseki's b.tally. Provided to keep things in one place
        is all.

        :param discord.Interaction interaction: The discord interaction context
        :param int cruise_select: The cruise you want data on, counts backwards. 0 is this cruise, 1 is the last
            cruise etc...
        :return: None
        """

        await interaction.response.defer()

        if include_not_unloaded:
            if include_not_unloaded == "All Carriers":
                include_not_unloaded_bool = True
            else:
                include_not_unloaded_bool = False
        else:
            include_not_unloaded_bool = None

        cruise_name = "this" if cruise_select == 0 else f"-{cruise_select}"
        logger.info(
            f"User {interaction.user.name} ({interaction.user.id}) requested the current tally of the cruise stats for {cruise_name} cruise."
        )
        target_date = None

        cruise = await booze_sheets_api.get_cruise_with_stats(-cruise_select, include_not_unloaded_bool)

        if cruise_select != 0:
            target_date = cruise.start.strftime("%Y-%m-%d")
            logger.debug(f"Target date for historical cruise determined as: {target_date}")

        stat_embed = await self.build_stat_embed(cruise, target_date=target_date)

        await interaction.edit_original_response(embed=stat_embed)

        if cruise_select == 0:
            pinned_stat_embed = await self.build_stat_embed(cruise, None, True)

            # Go update all the pinned embeds also.
            pins = await database.get_all_pinned_messages()
            if pins:
                logger.debug(f"Updating pinned messages: {pins}")
                for pin in pins:
                    logger.debug(pin)
                    channel = await bot.get_or_fetch.channel(pin[1])
                    logger.debug(f"Channel matched as: {channel} from {pin[1]}")
                    # Now go loop over every pin and update it
                    message = await channel.fetch_message(pin[0])
                    logger.debug(f"Message matched as: {message} from {pin[0]}")
                    await message.edit(embed=pinned_stat_embed)
            else:
                logger.debug("No pinned messages to update")

    @app_commands.command(
        name="booze_pin_message",
        description="Pins a steve tally embed for periodic updating. Restricted to Admin and Sommelier's.",
    )
    @describe(message_link="The message link to be pinned")
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    async def pin_message(self, interaction: discord.Interaction, message_link: str):
        """
        Pins the message in the channel.

        :param Interaction discord.Interaction: The discord interaction context
        :param str message_link: The link of message to pin
        :returns: None
        """

        await interaction.response.defer(ephemeral=True)

        logger.info(f"User {interaction.user.name} ({interaction.user.id}) wants to pin the message {message_link}")

        split_message_link = message_link.split("/")
        channel_id = int(split_message_link[5])
        channel = await bot.get_or_fetch.channel(channel_id)
        message_id = int(split_message_link[6])

        message = await channel.fetch_message(message_id)
        if not message:
            logger.warning(f"Could not find a message for the link: {message_link}")
            await interaction.edit_original_response(content=f"Could not find a message with the link: {message_link}")
            return

        try:
            message_embed = message.embeds[0]

        except IndexError:
            logger.warning(f"The message entered is not a pirate steve stat embed: {message_link}")
            await interaction.edit_original_response(
                content=f"The message entered is not a pirate steve stat embed. {message_link}"
            )
            return

        if message_embed.title != "Pirate Steve's Booze Cruise Tally":
            logger.warning(f"The message entered is not a pirate steve stat embed: {message_link}")
            await interaction.edit_original_response(
                content=f"The message entered is not a pirate steve stat embed. {message_link}"
            )
            return

        await database.pin_message(message.id, channel.id)

        if not message.pinned:
            logger.info(f"Message is not pinned - pinning now: {message_id}")
            await message.pin(reason=f"Pirate Steve pinned on behalf of {interaction.user.name}")
            logger.info(f"Message {message_id} was pinned.")
        else:
            logger.debug(f"Message {message_id} is already pinned, no action needed")

        await interaction.edit_original_response(
            content=f"Pirate steve recorded message {message_link} for pinned updating"
        )

    @app_commands.command(
        name="booze_unpin_all",
        description="Unpins all messages for booze stats and updates the DB. Restricted to Admin and Sommelier's.",
    )
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def clear_all_pinned_message(self, interaction: discord.Interaction):
        """
        Clears all the pinned messages

        :param interaction: The discord interaction context
        :returns: None
        """

        await interaction.response.defer(ephemeral=True)
        logger.info(f"User {interaction.user.name} ({interaction.user.id}) requested to clear the pinned messages.")

        all_pins = await database.get_all_pinned_messages()
        if all_pins:
            for pin in all_pins:
                channel = await bot.get_or_fetch.channel(int(pin[1]))
                message = await channel.fetch_message(pin[0])
                await message.unpin(reason=f"Pirate Steve unpinned at the request of: {interaction.user.name}")
                logger.debug(f"Removed pinned message: {pin[0]}.")
            await database.clear_all_pins()
            logger.info("All pinned messages removed successfully")
            await interaction.edit_original_response(content="Pirate Steve removed all the pinned stat messages")
        else:
            await interaction.edit_original_response(content="Pirate Steve has no pinned messages to remove.")

    @app_commands.command(
        name="booze_unpin_message",
        description="Unpins a specific message and removes it from the DB. Restricted to Admin and Sommelier's.",
    )
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM])
    @describe(message_link="The message link to be unpinned")
    @check_command_channel([CHANNEL_BC_STEVE_SAYS])
    async def booze_unpin_message(self, interaction: discord.Interaction, message_link: str):
        """
        Clears the pinned embed described by the message_link string.

        :param interaction: The discord interaction context
        :param str message_link: The message url to unpin
        :returns: None
        """

        await interaction.response.defer(ephemeral=True)
        logger.info(
            f"User {interaction.user.name} ({interaction.user.id}) requested to clear the pinned message {message_link}."
        )

        split_message_link = message_link.split("/")
        channel_id = int(split_message_link[5])
        channel = await bot.get_or_fetch.channel(channel_id)
        message_id = int(split_message_link[6])
        message = await channel.fetch_message(message_id)

        if not await database.is_message_pinned(message.id):
            logger.warning(f"Message {message_link} is not recorded as pinned in the database.")
            await interaction.edit_original_response(
                content=f"Pirate Steve could not find the pinned message {message_link} in his records."
            )
            return

        await message.unpin(reason=f"Pirate Steve unpinned at the request of: {interaction.user.name}")
        logger.debug(f"Unpinned message: {message_id}.")
        await database.unpin_message(message.id)
        logger.info(f"Removed pinned message {message_id} from the database.")
        await interaction.edit_original_response(content=f"Pirate Steve unpinned the message {message_link}.")

    @app_commands.command(
        name="booze_tally_extra_stats",
        description="Returns an set of extra stats for the wine. Restricted to Admin, Sommeliers, and Connoisseurs.",
    )
    @describe(
        cruise_select="Which cruise do you want data for. 0 is this cruise, 1 the last cruise etc. Default is this cruise.",
        include_not_unloaded="Force select if we should include carriers that have not unloaded yet.",
        stat="The specific stat you want to see.",
    )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
        ]
    )
    async def extended_tally_stats(
        self,
        interaction: discord.Interaction,
        cruise_select: int = 0,
        include_not_unloaded: IncludeNotUnloadedChoices | None = None,
        stat: StatChoices = "All",
    ):
        """
        Prints an extended tally stats as requested by RandomGazz.
        """

        await interaction.response.defer()
        logger.info(
            f"User {interaction.user.name} ({interaction.user.id}) requested the current extended stats of the cruise."
        )

        cruise = "this" if cruise_select == 0 else f"-{cruise_select}"
        logger.debug(
            f"User {interaction.user.name} ({interaction.user.id}) requested the current tally of the cruise stats for {cruise} cruise (extended stats)."
        )
        target_date = None

        if include_not_unloaded:
            if include_not_unloaded == "All Carriers":
                include_not_unloaded_bool = True
            else:
                include_not_unloaded_bool = False
        else:
            include_not_unloaded_bool = None

        cruise = await booze_sheets_api.get_cruise_with_stats(-cruise_select, include_not_unloaded_bool)

        if cruise_select != 0:
            target_date = cruise.start.strftime("%Y-%m-%d")
            logger.debug(f"Target date for historical cruise determined as: {target_date}")

        stat_embed = await self.build_extended_stat_embed(cruise, target_date, stat)
        await interaction.edit_original_response(embed=stat_embed)

    @app_commands.command(
        name="booze_carrier_summary",
        description="Returns a summary of booze carriers. Restricted to Admin, Sommeliers, and Connoisseurs.",
    )
    @describe(
        exclude_staff="Whether to exclude staff carriers.",
        )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
        ]
    )
    async def booze_carrier_summary(self, interaction: discord.Interaction, exclude_staff: bool = False):
        """
        Returns an embed of the current booze carrier summary.

        :param Interaction discord.Interaction: The discord interaction context
        :return: None
        """

        await interaction.response.defer()
        logger.info(f"User {interaction.user.name} ({interaction.user.id}) requested a carrier summary")

        cruise = await booze_sheets_api.get_cruise_with_stats(0, exclude_staff=exclude_staff)

        total_carriers = cruise.stats.total_carriers
        remaining_carriers = cruise.stats.carriers_remaining
        total_unloads = cruise.stats.total_trips - remaining_carriers
        unloaded_carriers = total_carriers - remaining_carriers

        logger.debug(
            f"User {interaction.user.name} ({interaction.user.id}) wanted to know the remaining time of the holiday."
        )
        holiday_ongoing = await booze_sheets_api.get_current_cruise_state() == CruiseSystemState.ACTIVE
        current_cruise = await booze_sheets_api.get_cruise_with_stats(0)
        start_time = current_cruise.start
        if not holiday_ongoing:
            duration_remaining = "Pirate Steve has not detected the holiday state yet, or it is already over."
        else:
            duration_hours = 48

            end_time = start_time + timedelta(hours=duration_hours)
            end_timestamp = int(end_time.timestamp())
            duration_remaining = f"Pirate Steve thinks the holiday will end around <t:{end_timestamp}> (<t:{end_timestamp}:R>) [local timezone]."

        stat_embed = discord.Embed(
            title="Pirate Steve's Booze Carrier Summary",
            description=f"Total Carriers: {total_carriers}\n"
            + f"Unloaded Carriers: {unloaded_carriers}\n"
            + f"Total Unloads: {total_unloads}\n"
            + f"Remaining Carriers: {remaining_carriers}\n"
            + f"{duration_remaining}",
        )
        await interaction.edit_original_response(embed=stat_embed)

    @app_commands.command(
        name="biggest_cruise_tally", description="Returns the tally for the cruise with the most wine."
    )
    @check_roles([*any_council_role, *any_moderation_role, ROLE_SOMM, ROLE_CONN])
    @describe(
        extended="If the extended stats should be shown",
        include_not_unloaded="Force select if we should include carriers that have not unloaded yet.",
        stat="The specific stat you want to see. (Only applies for extended tallies)",
    )
    async def biggest_cruise_tally(
        self,
        interaction: discord.Interaction,
        extended: bool = False,
        include_not_unloaded: IncludeNotUnloadedChoices | None = None,
        stat: StatChoices = "All",
    ):
        """
        Returns the tally for the cruise with the most wine.

        :param stat: Selection of stats to print. can take values 'All', 'Rackhams Population', 'Server Population', 'USA Population', 'Scotland Population', 'London Busses', 'Swimming Pools', 'Volume Maths'
        :param discord.Interaction interaction: The discord interaction context.
        :param bool extended: If the extended stats should be shown.
        :param IncludeNotUnloadedChoices include_not_unloaded: If we should include carriers that did not unload
        :returns: None
        """

        logger.info(
            f"{interaction.user.name} ({interaction.user.id}) requested the biggest cruise tally, extended: {extended}."
        )
        await interaction.response.defer()

        if include_not_unloaded:
            if include_not_unloaded == "All Carriers":
                include_not_unloaded_bool = True
            else:
                include_not_unloaded_bool = False
        else:
            include_not_unloaded_bool = None

        cruise = await booze_sheets_api.get_biggest_cruise_with_stats(include_not_unloaded_bool)

        # Build the stat embed based on the extended flag
        if not extended:
            stat_embed = await self.build_stat_embed(cruise, target_date=cruise.start.strftime("%Y-%m-%d"))
        else:
            stat_embed = await self.build_extended_stat_embed(cruise, cruise.start.strftime("%Y-%m-%d"), stat)

        # Edit the original interaction response with the stat embed
        await interaction.edit_original_response(embed=stat_embed)

    @app_commands.command(name="booze_carrier_stats", description="Returns the stats for a specific carrier.")
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
            ROLE_WINE_CARRIER,
        ]
    )
    async def carrier_stats(self, interaction: discord.Interaction, carrier_id: str):
        """
        Returns the stats for a specific carrier.

        :param discord.Interaction interaction: The discord interaction context.
        :param str carrier_id: he XXX-XXX carrier ID.
        :returns: None
        """

        carrier_id = carrier_id.upper()

        logger.info(f"{interaction.user.name} requested the stats for the carrier: {carrier_id}.")
        await interaction.response.defer()

        logger.debug("Fetching historical data for carrier stats.")

        carrier_stats = await booze_sheets_api.get_carrier_stats(carrier_id)

        if not carrier_stats:
            logger.warning(f"Carrier with ID {carrier_id} not found in the database.")
            await interaction.edit_original_response(
                content=f"Sorry, we could not find a carrier with the id: {carrier_id}."
            )
            return

        formatted_first_unload_date = f"<t:{int(carrier_stats.first_unload_date.timestamp())}:d>" if carrier_stats.first_unload_date else "N/A"
        formatted_last_unload_date = f"<t:{int(carrier_stats.last_unload_date.timestamp())}:d>" if carrier_stats.last_unload_date else "N/A"

        average_wine_per_trip = carrier_stats.total_wine / carrier_stats.total_trips if carrier_stats.total_trips > 0 else 0
        average_credits_per_trip = carrier_stats.total_credits / carrier_stats.total_trips if carrier_stats.total_trips > 0 else 0

        logger.debug(
            f"Carrier stats for {carrier_id} - Name: {carrier_stats.name}, "
            + f"Total Wine: {carrier_stats.total_wine}, "
            + f"Total Trips: {carrier_stats.total_trips}, "
            + f"Total Cruises: {carrier_stats.total_cruises}, "
            + f"Owner: {carrier_stats.owner}, "
            + f"Average Wine per Trip: {average_wine_per_trip:.2f}, "
            + f"Average Credits per Trip: {average_credits_per_trip:.2f},"
            + f"First Unload Date: {formatted_first_unload_date}, "
            + f"Last Unload Date: {formatted_last_unload_date}."
        )

        stat_embed = discord.Embed(
            title=f"Stats for {carrier_stats.name} ({carrier_id})",
            description=f"Total Wine: {format_large_number(carrier_stats.total_wine)} tonnes\n"
            + f"Total Runs: {carrier_stats.total_trips}\n"
            + f"Total Cruises: {carrier_stats.total_cruises}\n"
            + f"Owner: {carrier_stats.owner.mention}\n"
            + f"Average Wine per Trip: {format_large_number(average_wine_per_trip)} tonnes\n"
            + f"Average Credits per Trip: {format_large_number(average_credits_per_trip)} credits\n"
            + f"First Unload Date: {formatted_first_unload_date}\n"
            + f"Last Unload Date: {formatted_last_unload_date}"
        )

        logger.info(f"Sending stats embed for carrier {carrier_id}.")
        await interaction.edit_original_response(content=None, embed=stat_embed)

    @app_commands.command(
        name="booze_all_time_tally",
        description="Returns an all-time tally of the booze cruises. Restricted to Somms and Connoisseurs.",
    )
    @check_roles(
        [
            *any_council_role,
            *any_moderation_role,
            ROLE_SOMM,
            ROLE_CONN,
        ]
    )
    async def all_time_tally(self, interaction: discord.Interaction):
        """
        Returns an embed of the all-time booze cruise stats.

        :param discord.Interaction interaction: The discord interaction context
        :return: None
        """

        await interaction.response.defer()

        logger.info(
            f"User {interaction.user.name} ({interaction.user.id}) requested the all-time tally of the booze cruise stats."
        )

        stats = await booze_sheets_api.get_all_time_stats()

        cruises = await booze_sheets_api.get_cruises_list()

        total_cruises = len(cruises)

        avg_wine_per_cruise = stats.total_wine // total_cruises if total_cruises > 0 else 0
        avg_profit_per_cruise = stats.total_profit // total_cruises if total_cruises > 0 else 0
        avg_trips_per_cruise = stats.total_trips / total_cruises if total_cruises > 0 else 0

        embed = Embed(
            title="Pirate Steve's All-Time Booze Cruise Tally",
            description=(
                f"**Total Wine Delivered:** — {format_large_number(stats.total_wine)} tonnes\n"
                + f"**Total Cruises:** — {total_cruises:,}\n"
                + f"**Total Trips:** — {stats.total_trips:,}\n"
                + f"**Total Carriers:** — {stats.total_carriers:,}\n"
                + f"**Total Carrier Owners:** — {stats.total_owners:,}\n"
                + f"**Total Profit:** — {format_large_number(stats.total_profit)} credits\n"
                + f"**Carriers Remaining:** — {stats.carriers_remaining:,}\n"
                + f"**Wine Remaining:** — {format_large_number(stats.wine_remaining)} tonnes\n"
                + f"**Average Unload Duration:** — {format_duration(stats.avg_unload_dur)}\n"
                + f"**Minimum Unload Duration:** — {format_duration(stats.min_unload_dur)}\n"
                + f"**Maximum Unload Duration:** — {format_duration(stats.max_unload_dur)}\n\n"
                + f"**Average Wine per Cruise:** — {format_large_number(avg_wine_per_cruise)} tonnes\n"
                + f"**Average Profit per Cruise:** — {format_large_number(avg_profit_per_cruise)} credits\n"
                + f"**Average Trips per Cruise:** — {avg_trips_per_cruise:.2f}\n"
            ),
        )

        await interaction.edit_original_response(embed=embed)
