"""
Cog for all the commands that interact with the database

"""

import asyncio
import logging
import math
import os.path
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Literal

import discord
import gspread
import gspread_asyncio
from discord import app_commands
from discord.app_commands import Choice, describe
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
# local classes
from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier
# local constants
from ptn.boozebot.constants import (
    BOOZE_PROFIT_PER_TONNE_WINE, CARRIER_ID_RE, GOOGLE_OAUTH_CREDENTIALS_PATH, RACKHAMS_PEAK_POP, _production, bot,
    get_steve_says_channel, get_wine_carrier_channel, ptn_role_icon_emoji_id, server_connoisseur_role_id,
    server_council_role_ids, server_mod_role_id, server_sommelier_role_id, server_wine_carrier_role_id
)
from ptn.boozebot.database.database import dump_database, pirate_steve_conn, pirate_steve_db, pirate_steve_db_lock
# local modules
from ptn.boozebot.modules.ErrorHandler import CustomError
from ptn.boozebot.modules.helpers import (
    bc_channel_status, check_command_channel, check_roles, get_channel, get_emoji, get_guild, track_last_run
)
from ptn.boozebot.modules.pagination import createPagination
from ptn.boozebot.modules.PHcheck import ph_check
from ptn.boozebot.modules.Views import ConfirmView

"""
DATABASE INTERACTION COMMANDS
    
/update_booze_db - admin/mod/somm/conn
/find_carriers_with_wine - admin/mod/somm/conn/wine carrier
/wine_mark_completed_forcefully - admin/mod/somm
/find_wine_carriers_for_platform - admin/mod/somm/conn/wine carrier
/find_wine_carrier_by_id - admin/mod/somm/conn/wine carrier
/booze_tally - admin/mod/somm/conn
/booze_carrier_summary - admin/mod/somm/conn
/booze_pin_message - admin/mod/somm
/booze_unpin_all - admin/mod/somm
/booze_unpin_message - admin/mod/somm
/booze_tally_extra_stats - admin/mod/somm/conn
/booze_delete_carrier - admin/mod/somm
/booze_archive_database - admin/mod/somm
/booze_configure_signup_forms - admin/mod/somm
/booze_reuse_signup_form - admin/mod/somm
/biggest_cruise_tally - admin/mod/somm/conn
/booze_carrier_stats - admin/mod/somm/conn/wine carrier
/purge_booze_carriers - admin/mod/somm
"""


def get_creds():
    creds = Credentials.from_service_account_file(GOOGLE_OAUTH_CREDENTIALS_PATH)
    scoped = creds.with_scopes(
        [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
    )
    return scoped


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


class DatabaseInteraction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = None
        self.tracking_sheet = None
        self.worksheet_key = None
        self.worksheet_with_data_id = None
        self.loader_signup_form_url = None
        self.client_manager = None

        if not os.path.exists(GOOGLE_OAUTH_CREDENTIALS_PATH):
            raise EnvironmentError(f"Cannot find the booze cruise json file: {GOOGLE_OAUTH_CREDENTIALS_PATH}")

        self.update_allowed = True  # This might be better stored somewhere over a reset

        # authorize the client sheet
        self.client_manager = gspread_asyncio.AsyncioGspreadClientManager(get_creds)

    async def cog_load(self):
        pirate_steve_db.execute("SELECT * FROM trackingforms")
        forms = dict(pirate_steve_db.fetchone())

        self.worksheet_key = forms["worksheet_key"]

        # On which sheet is the actual data.
        self.worksheet_with_data_id = forms["worksheet_with_data_id"]

        # input form is the form we have loaders fill in
        self.loader_signup_form_url = forms["loader_input_form_url"]

        self.client = await self.client_manager.authorize()

        await self._reconfigure_workbook_and_form()
        await self._update_db()  # On instantiation, go build the DB

    async def _reconfigure_workbook_and_form(self):
        """
        Reconfigures the tracking sheet to the latest version based on the current worksheet key and sheet ID. Called
        when we update the forms or on startup of the bot.

        :returns: None
        """
        # The key is part of the URL
        try:
            logging.info(f"Building worksheet with the key: {self.worksheet_key}")
            self.client = await self.client_manager.authorize()
            workbook = await self.client.open_by_key(self.worksheet_key)

            worksheets = await workbook.worksheets()
            for sheet in worksheets:
                print(sheet.title)

            # Update the tracking sheet object
            self.tracking_sheet = await workbook.get_worksheet(self.worksheet_with_data_id)
        except gspread.exceptions.APIError as e:
            logging.exception(f"Error reading the worksheet: {e}")

    async def _update_db(self):
        """
        Private method to wrap the DB update commands.

        :returns:
        :rtype:
        """
        if not self.tracking_sheet:
            raise EnvironmentError(
                "Sorry this cannot be ran as we have no form for tracking the wine presently. "
                "Please set a new form first."
            )

        elif not self.update_allowed:
            print("Update not allowed, user has archived the data but not polled the latest set.")
            return

        updated_db = False
        added_count = 0
        updated_count = 0
        unchanged_count = 0
        # A JSON form tracking all the records
        self.client = await self.client_manager.authorize()
        records_data = await self.tracking_sheet.get_all_records()
        new_signups = []  # type: list[discord.Embed]

        total_entries = len(records_data)
        print(f"Updating the database we have: {total_entries} records found.")

        all_carriers_data = {}  # type: dict[str, BoozeCarrier]

        # Loop through each record and parse it into a BoozeCarrier object
        for record in records_data:
            try:
                carrier_data = BoozeCarrier(record)

                # Check if there is already a object for this carrier and update it if so
                if carrier_data.carrier_identifier in all_carriers_data:
                    all_carriers_data[carrier_data.carrier_identifier].wine_total += carrier_data.wine_total
                    all_carriers_data[carrier_data.carrier_identifier].run_count += 1

                else:
                    all_carriers_data[carrier_data.carrier_identifier] = carrier_data
            except ValueError as ex:
                print(f"Error while paring the stats into carrier records: {ex}")
                return

        print(f"Total Carriers: {len(all_carriers_data)}")

        async with pirate_steve_db_lock:
            for carrier_data in all_carriers_data.items():
                carrier_data = carrier_data[1]

                pirate_steve_db.execute(
                    "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)",
                    (f"%{carrier_data.carrier_identifier}%",),
                )

                old_carrier_data = [BoozeCarrier(carrier_data) for carrier_data in pirate_steve_db.fetchall()]

                if len(old_carrier_data) > 1:
                    raise ValueError(
                        f"{len(old_carrier_data)} carriers are listed with this carrier ID:"
                        f" {carrier_data.carrier_identifier}. Problem in the DB!"
                    )

                # If the carrier is in the database, check if the data is the same
                if old_carrier_data:
                    old_carrier_data = old_carrier_data[0]

                    print(f"EXPECTED: \t{carrier_data}")
                    print(f"RECORD: \t{old_carrier_data}")
                    print(f"EQUALITY: \t{carrier_data == old_carrier_data}")

                    # If the data is the same, skip over, otherwise update it
                    if old_carrier_data != carrier_data:
                        print(
                            f"The DB data for {carrier_data.carrier_name} does not equal the input in GoogleSheets "
                            f"- Updating"
                        )
                        updated_count += 1
                        try:
                            data = (
                                carrier_data.carrier_name,
                                carrier_data.wine_total,
                                carrier_data.discord_username,
                                carrier_data.timestamp,
                                carrier_data.run_count,
                                f"%{old_carrier_data.carrier_identifier}%",
                            )

                            pirate_steve_db.execute(
                                """ UPDATE boozecarriers 
                                SET carriername=?, winetotal=?, 
                                discordusername=?, timestamp=?, runtotal=?
                                WHERE carrierid LIKE (?) """,
                                data,
                            )

                            updated_db = True

                        except sqlite3.IntegrityError as ex:
                            print(f"WARNING: {ex}")
                            print(f"Error updating the carrier data in the db for: {carrier_data}")
                            raise ex

                    else:
                        print(
                            f"The DB data for {carrier_data.carrier_name} is the same as the sheets record - "
                            f"skipping over."
                        )
                        unchanged_count += 1

                # If carrier is not in the database, add it
                else:
                    added_count += 1
                    print(carrier_data.to_dictionary())
                    print(f"Carrier {carrier_data.carrier_name} is not yet in the database - adding it")
                    try:
                        pirate_steve_db.execute(
                            """ 
                        INSERT INTO boozecarriers VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL) 
                        """,
                            (
                                carrier_data.carrier_name,
                                carrier_data.carrier_identifier,
                                carrier_data.wine_total,
                                carrier_data.platform,
                                carrier_data.ptn_carrier,
                                carrier_data.discord_username,
                                carrier_data.timestamp,
                                carrier_data.run_count,
                                carrier_data.total_unloads,
                                carrier_data.timezone,
                            ),
                        )
                    except sqlite3.IntegrityError as ex:
                        print(f"WARNING: {ex}")
                        print(f"Error adding the carrier data in the db for: {carrier_data}")
                        raise ex

                    updated_db = True
                    print("Added carrier to the database")

                    embed = discord.Embed(title="New WineCarrier signed up!")
                    embed.add_field(
                        name=f"Owner: {carrier_data.discord_username}: {carrier_data.carrier_name} ({carrier_data.carrier_identifier})",
                        value=f"{carrier_data.wine_total // carrier_data.run_count} tonnes of wine on {carrier_data.platform}",
                        inline=False,
                    )
                    new_signups.append(embed)

            print(f"all_carrier_sheet_ids: {list(all_carriers_data.keys())}")

            # Now that the records are updated, make sure no carrier was removed - check for anything not matching the
            # carrier id strings.
            pirate_steve_db.execute(
                "SELECT * FROM boozecarriers WHERE carrierid NOT IN ({})".format(
                    ", ".join("?" * len(list(all_carriers_data.keys())))
                ),
                list(all_carriers_data.keys()),
            )

            invalid_database_entries = [BoozeCarrier(invalid_carrier) for invalid_carrier in pirate_steve_db.fetchall()]

            if updated_db:
                # Write the database and then dump the updated SQL
                pirate_steve_conn.commit()
                dump_database()
                print("Wrote the database and dumped the SQL")

        return {
            "updated_db": updated_db,
            "added_count": added_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "total_carriers": len(all_carriers_data),
            "invalid_database_entries": invalid_database_entries,
            "new_signups": new_signups,
        }

    async def report_db_update_result(self, result: dict, force_embed=False):
        if result["updated_db"] or force_embed:
            embed = discord.Embed(title="Pirate Steve's DB Update ran successfully.")
            embed.add_field(
                name=f"Total number of carriers: {result['total_carriers']:>20}.\n"
                f"Number of new carriers added: {result['added_count']:>8}.\n"
                f"Number of carriers amended: {result['updated_count']:>11}.\n"
                f"Number of carriers unchanged: {result['unchanged_count']:>7}.",
                value="Pirate Steve hope he got this right.",
                inline=False,
            )
            steve_says_channel = await get_channel(get_steve_says_channel())
            await steve_says_channel.send(embed=embed)
        await self.report_new_and_invalid_carriers(result)

    async def report_new_and_invalid_carriers(self, result=None):
        """
        Reports any invalid carriers to the applicable channels.

        :param dict result: A dict returned from the update_db method
        :returns: None
        """
        if result is None:
            result = {}

        steve_says_channel = await get_channel(get_steve_says_channel())

        if result.get("invalid_database_entries", False):
            # In case any problem carriers found, mark them up
            print("Problem: We have invalid carriers!")

            for problem_carrier in result["invalid_database_entries"]:
                print(f"This carrier is no longer in the sheet: {problem_carrier}")

                # Notify to #steve-says so it can be deleted.
                problem_embed = discord.Embed(
                    title="Avast Ye! Pirate Steve found a missing carrier in the database!",
                    description=f"This carrier is no longer in the GoogleSheet:\n"
                    f"CarrierName: **{problem_carrier.carrier_name}**\n"
                    f"ID: **{problem_carrier.carrier_identifier}**\n"
                    f"Total Tonnes of Wine: **{problem_carrier.wine_total}** on "
                    f"**{problem_carrier.platform}**\n"
                    f"Number of trips to the peak: **{problem_carrier.run_count}**\n"
                    f"Total Unloads: **{problem_carrier.total_unloads}**\n"
                    f"Operated by: {problem_carrier.discord_username}",
                )
                problem_embed.set_footer(
                    text="Pirate Steve recommends verifying and then deleting this entry with /booze_delete_carrier"
                )
                await steve_says_channel.send(embed=problem_embed)

            # Only ping once after displaying all the invalid carriers
            await steve_says_channel.send(f"\n<@&{server_sommelier_role_id()}> please take note.")

        else:
            print("No invalid carriers found")

        if result.get("new_signups", False):
            for signup in result["new_signups"]:
                print("New signed up carriers found.")
                # loop over the new signups and print them out
                await steve_says_channel.send(embed=signup)
        else:
            print("No new signed up carriers detected")

    async def build_stat_embed(
        self,
        all_carrier_data: list[BoozeCarrier],
        target_date: str = None,
        include_timestamp: bool = False,
        include_not_unloaded: IncludeNotUnloadedChoices | None = None,
    ) -> discord.Embed:
        # Get faction state from the first carrier, assuming all carriers have the same state
        if all_carrier_data:
            faction_state = all_carrier_data[0].faction_state
        else:
            faction_state = None

        # If we have an override for the include_not_unloaded, use it
        if include_not_unloaded:
            if include_not_unloaded == "All Carriers":
                unloaded_stats = [carrier.get_unload_stats(include_not_unloaded=True) for carrier in all_carrier_data]
            else:  # include_not_unloaded == "Only Unloaded":
                unloaded_stats = [carrier.get_unload_stats(include_not_unloaded=False) for carrier in all_carrier_data]

        # Else only show unloaded, except if it was not a public holiday or the current cruise
        else:
            if target_date and faction_state in ["Public Holiday", None]:
                unloaded_stats = [
                    carrier.get_unload_stats(include_not_unloaded=False)
                    for carrier in all_carrier_data
                    if carrier.total_unloads > 0
                ]

            else:
                unloaded_stats = [carrier.get_unload_stats(include_not_unloaded=True) for carrier in all_carrier_data]

        total_wine = sum(unloaded[0] for unloaded in unloaded_stats)
        unique_carrier_count = len(unloaded_stats)
        total_carriers_inc_multiple_trips = sum(unloaded[1] for unloaded in unloaded_stats)

        wine_per_capita = (total_wine / RACKHAMS_PEAK_POP) if total_wine else 0
        wine_per_carrier = (total_wine / unique_carrier_count) if total_wine else 0
        python_loads = (total_wine / 288) if total_wine else 0
        t8_loads = (total_wine / 400) if total_wine else 0

        total_profit = total_wine * BOOZE_PROFIT_PER_TONNE_WINE

        fleet_carrier_buy_count = (total_profit / 5000000000) if total_profit else 0

        print(
            f"Carrier Count: {unique_carrier_count} - Total Wine: {total_wine:,} - Total Profit: {total_profit:,} - "
            f"Wine/Carrier: {wine_per_carrier:,.2f} - PythonLoads: {python_loads:,.2f} - "
            f"Wine/Capita: {wine_per_capita:,.2f} - Carrier Buys: {fleet_carrier_buy_count:,.2f}"
        )

        if total_wine > 4000000:
            flavour_text = "By the powers! That's enough grog to float a man-o'-war! Batten down the barrels!"
        elif total_wine > 3500000:
            flavour_text = "Avast! The wine flows like the seven seas, fetch the biggest cask ye can find!"
        elif total_wine > 3000000:
            flavour_text = "Shiver Me Timbers! This sea dog cannot fathom this much grog!"
        elif total_wine > 2500000:
            flavour_text = "Sink me! We might send them to Davy Jone`s locker."
        elif total_wine > 2000000:
            flavour_text = "Blimey! Pieces of eight all round! We have a lot of grog. Savvy?"
        elif total_wine > 1500000:
            flavour_text = "The coffers are looking better, get the Galley's filled with wine!"
        elif total_wine > 1000000:
            flavour_text = "Yo ho ho we have some grog!"
        else:
            flavour_text = "Heave Ho ye Scurvy Dog's! Pirate Steve wants more grog!"

        date_text = (
            f":\nHistorical Data: [{target_date} - "
            f"{datetime.strptime(target_date, '%Y-%m-%d').date() + timedelta(days=2)}]"
            if target_date
            else ""
        )

        updated_timestamp = f"\n\nLast updated: <t:{int(datetime.now().timestamp())}:F>" if include_timestamp else ""
        signup_form_text = (
            f"[Bringing wine? Sign up here]({self.loader_signup_form_url})" if await bc_channel_status() else ""
        )
        state_warning_msg = (
            "### The Public Holiday did not happen for this cruise.\n### None of these carriers got unloaded.\n\n"
        )
        state_text = state_warning_msg if faction_state not in ["Public Holiday", None] else ""

        # Build the embed
        stat_embed = discord.Embed(
            title=f"Pirate Steve's Booze Cruise Tally {date_text}",
            description=f"{state_text}"
            f"**Total number of carrier trips:** — {total_carriers_inc_multiple_trips:>1}\n"
            f"**Total number of unique carriers:** — {unique_carrier_count:>24}\n"
            f"**Profit per ton:** — {BOOZE_PROFIT_PER_TONNE_WINE:>56,}\n"
            f"**Rackham pop:** — {RACKHAMS_PEAK_POP:>56,}\n"
            f"**Wine per capita:** — {wine_per_capita:>56,.2f}\n"
            f"**Wine per carrier:** — {math.ceil(wine_per_carrier):>56,}\n"
            f"**Python loads (288t):** — {math.ceil(python_loads):>56,}\n"
            f"**Type-8 loads (400t):** — {math.ceil(t8_loads):>56,}\n\n"
            f"**Total wine:** — {total_wine:,}\n"
            f"**Total profit:** — {total_profit:,}\n\n"
            f"**Total number of fleet carriers that profit can buy:** — {fleet_carrier_buy_count:,.2f}\n\n"
            f"{flavour_text}\n\n"
            f"{signup_form_text}"
            f"{updated_timestamp}",
        )
        stat_embed.set_image(
            url="https://cdn.discordapp.com/attachments/783783142737182724/849157248923992085/unknown.png"
        )
        stat_embed.set_footer(
            text="This function is a clone of b.tally from CMDR Suiseiseki.\nPirate Steve hopes the values match!"
        )

        print("Returning embed to user")
        return stat_embed

    async def build_extended_stat_embed(
        self,
        all_carrier_data: list[BoozeCarrier],
        target_date: str = None,
        include_not_unloaded: IncludeNotUnloadedChoices | None = None,
        stat: StatChoices = "All",
    ) -> discord.Embed:
        # Get faction state from the first carrier, assuming all carriers have the same state
        if all_carrier_data:
            faction_state = all_carrier_data[0].faction_state
        else:
            faction_state = None

        # If we have an override for the include_not_unloaded, use it
        if include_not_unloaded:
            if include_not_unloaded == "All Carriers":
                unloaded_stats = [carrier.get_unload_stats(include_not_unloaded=True) for carrier in all_carrier_data]
            elif include_not_unloaded == "Only Unloaded":
                unloaded_stats = [carrier.get_unload_stats(include_not_unloaded=False) for carrier in all_carrier_data]

        # Else only show unloaded, except if it was not a public holiday or the current cruise
        else:
            if target_date and faction_state in ["Public Holiday", None]:
                unloaded_stats = [
                    carrier.get_unload_stats(include_not_unloaded=False)
                    for carrier in all_carrier_data
                    if carrier.total_unloads > 0
                ]

            else:
                unloaded_stats = [carrier.get_unload_stats(include_not_unloaded=True) for carrier in all_carrier_data]

        total_wine = sum(unloaded[0] for unloaded in unloaded_stats)

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

        server_population = (await get_guild()).member_count
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

        date_text = (
            f":\nHistorical Data: [{target_date} - "
            f"{datetime.strptime(target_date, '%Y-%m-%d').date() + timedelta(days=2)}]"
            if target_date
            else ""
        )
        state_warning_msg = (
            "### The Public Holiday did not happen for this cruise.\n### None of these carriers got unloaded.\n\n"
        )
        state_text = state_warning_msg if faction_state not in ["Public Holiday", None] else ""

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

        ptn_logo_emoji = await get_emoji(ptn_role_icon_emoji_id())
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

        stat_embed = discord.Embed(
            title=f"Pirate Steve's Extended Booze Tally {date_text}", description=description_text
        )
        stat_embed.set_footer(text="Stats requested by RandomGazz.\nPirate Steve approves of these stats!")
        return stat_embed

    """
    Pinned Stats and Activity Update Task Loop
    
    """

    @commands.Cog.listener()
    async def on_ready(self):
        print("Starting the pinned message checker")
        if not self.periodic_stat_update.is_running():
            self.periodic_stat_update.start()

    @tasks.loop(minutes=10)
    @track_last_run()
    async def periodic_stat_update(self):
        """
        Loops every hour and updates all pinned embeds and bot activity status.

        :returns: None
        """
        try:
            # Periodic trigger that updates all the stat embeds that are pinned.
            print("Period trigger of the embed update.")

            print("Running db update")
            db_update = await self._update_db()
            await self.report_db_update_result(db_update)

            pirate_steve_db.execute("SELECT * FROM pinned_messages")
            # Get everything
            all_pins = [dict(value) for value in pirate_steve_db.fetchall()]

            # Get all carriers
            pirate_steve_db.execute("SELECT * FROM boozecarriers")
            all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
            stat_embed = await self.build_stat_embed(all_carrier_data, None, True)

            print("Updating pinned messages")
            if all_pins:
                print(f"We have these pins to update: {all_pins}")
                for pin in all_pins:
                    channel = await get_channel(int(pin["channel_id"]))
                    message = await channel.fetch_message(pin["message_id"])
                    await message.edit(embed=stat_embed)
            else:
                print("No pinned messages to update.")

            print("Updating discord activity")
            total_wine = sum(carrier.wine_total for carrier in all_carrier_data) if all_carrier_data else 0

            state_text = (
                f"Total Wine Tracked: {total_wine:,}"
                if await bc_channel_status()
                else "Arrr, the wine be drained, ye thirsty scallywags!"
            )

            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="the Sidewinders landing at Rackhams Peak.",
                    state=state_text,
                )
            )
            print("Activity status updated")
            print("Periodic update complete, checking again in 10 minutes.")
        except Exception as e:
            print(f"Error updating pinned messages: {e}")

    """
    Database interaction Commands
    
    """

    @app_commands.command(
        name="update_booze_db",
        description="Populates the booze cruise database from the updated google sheet. Somm/Conn role required.",
    )
    @check_roles(
        [
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
        ]
    )
    @check_command_channel(get_steve_says_channel())
    async def user_update_database_from_googlesheets(self, interaction: discord.Interaction):
        """
        Slash command for updating the database from the GoogleSheet.

        :returns: A discord embed to the user.
        :rtype: None
        """
        print(f"User {interaction.user.name} requested to re-populate the database at {datetime.now()}")

        await interaction.response.defer()

        try:
            db_update = await self._update_db()
            await self.report_db_update_result(db_update, force_embed=True)
            await interaction.followup.send(content="Pirate Steve's DB Update ran successfully.")

        except ValueError as ex:
            await interaction.followup.send(content=str(ex))

    @app_commands.command(
        name="find_carriers_with_wine",
        description="Returns the carriers in the database that are still flagged as having wine remaining.",
    )
    @check_roles(
        [
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
            server_wine_carrier_role_id(),
        ]
    )
    @check_command_channel([get_wine_carrier_channel(), get_steve_says_channel()])
    async def find_carriers_with_wine(self, interaction: discord.Interaction):
        """
        Returns an interactive list of all the carriers with wine that has not yet been unloaded.

        :param interaction discord.Interaction: The discord interaction context
        :returns: An interactive message embed.
        :rtype: Union[discord.Message, dict]
        """

        await interaction.response.defer()
        db_update = await self._update_db()
        await self.report_db_update_result(db_update)
        print(f"{interaction.user.name} requested to find the carrier with wine")
        pirate_steve_db.execute("SELECT * FROM boozecarriers WHERE runtotal > totalunloads")
        carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
        if len(carrier_data) == 0:
            # No carriers remaining
            await interaction.edit_original_response(
                content="Pirate Steve is sorry, but there are no more carriers with wine remaining.", embed=None
            )
            return

        # Else we have wine left

        carrier_data = [
            (
                f"{carrier.carrier_name} ({carrier.carrier_identifier})",
                f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
            )
            for carrier in carrier_data
        ]

        # Create the pagination
        await createPagination(
            interaction,
            "Carriers with wine remaining",
            carrier_data,
        )

    def _validate_existing_carrier(self, carrier_id: str) -> BoozeCarrier:
        # Cast this to upper case just in case
        carrier_id = carrier_id.upper().strip()
        if not CARRIER_ID_RE.fullmatch(carrier_id):
            raise CustomError(
                f"The carrier ID was invalid, XXX-XXX expected received, {carrier_id}.\n"
                "Carrier IDs cannot contain `'O'`s or `'I'`s, only `'0'`s and `'1'`s respectively."
            )
        # Check if it is in the database already
        pirate_steve_db.execute("SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f"%{carrier_id}%",))
        # Really only expect a single entry here, unique field and all that
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())
        if not carrier_data:
            raise CustomError(f'Avast ye! No carrier found for "{carrier_id}".')
        return carrier_data

    @app_commands.command(
        name="wine_mark_completed_forcefully",
        description="Forcefully marks a carrier in the database as unload completed. Admin/Sommelier required.",
    )
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    async def wine_mark_completed_forcefully(self, interaction: discord.Interaction, carrier_id: str):
        """
        Forcefully marks a carrier as completed an unload. Ideally will never be used.

        :param discord.Interaction interaction: The discord interaction context.
        :param str carrier_id: The XXX-XXX carrier ID you want to action.
        :returns: None
        """

        await interaction.response.defer()
        db_update = await self._update_db()
        await self.report_db_update_result(db_update)
        print(f"{interaction.user.name} wants to forcefully mark the carrier {carrier_id} as unloaded.")

        try:
            carrier_data = self._validate_existing_carrier(carrier_id)
        except CustomError as e:
            print(e.message)
            await interaction.edit_original_response(content=e.message)
            return

        carrier_embed = discord.Embed(
            title=f"Argh We found this data for {carrier_id}:",
            description=f"CarrierName: **{carrier_data.carrier_name}**\n"
            f"ID: **{carrier_data.carrier_identifier}**\n"
            f"Total Tonnes of Wine: **{carrier_data.wine_total}** on **{carrier_data.platform}**\n"
            f"Number of trips to the peak: **{carrier_data.run_count}**\n"
            f"Total Unloads: **{carrier_data.total_unloads}**\n"
            f"Operated by: {carrier_data.discord_username}",
        )
        confirm = ConfirmView(interaction.user)
        # Send the embed
        await interaction.edit_original_response(embed=carrier_embed, view=confirm)
        await confirm.wait()

        if confirm.value:
            try:
                print(f"User {interaction.user.name} agreed to mark the carrier {carrier_id} as unloaded.")
                # Go update the object in the database.
                async with pirate_steve_db_lock:
                    data = (f"%{carrier_data.carrier_identifier}%",)
                    pirate_steve_db.execute(
                        """ 
                        UPDATE boozecarriers 
                        SET totalunloads=totalunloads+1, discord_unload_in_progress=NULL
                        WHERE carrierid LIKE (?) 
                        """,
                        data,
                    )
                    pirate_steve_conn.commit()
                print(f"Database for unloaded forcefully updated by {interaction.user.name} for {carrier_id}")
                embed = discord.Embed(description=f"Fleet carrier {carrier_data.carrier_name} marked as unloaded.")
                embed.add_field(
                    name=f"Runs Made: {carrier_data.run_count}",
                    value=f"Unloads Completed: {carrier_data.total_unloads}",
                )
                await interaction.edit_original_response(content=None, embed=embed, view=None)
            except Exception as e:
                await interaction.edit_original_response(
                    content=f'Something went wrong, go tell the bot team "computer said: {e}"', embed=None, view=None
                )
        elif confirm.value is False:
            print(f"User {interaction.user.name} aborted the request to mark the carrier {carrier_id} as unloaded.")
            await interaction.edit_original_response(
                content=f"Argh you cancelled the action for marking {carrier_id} as forcefully completed.",
                embed=None,
                view=None,
            )
        else:  # view timeout
            await interaction.edit_original_response(content="**Cancelled - timed out**", embed=None, view=None)

    @app_commands.command(
        name="find_wine_carriers_for_platform",
        description="Returns the carriers in the database for the platform.",
    )
    @describe(
        platform="The platform the carrier operates on.",
        remaining_wine="True if you only want carriers with wine, else False. Default True",
    )
    @app_commands.choices(
        platform=[
            Choice(name="PC (All)", value="PC"),
            Choice(name="PC EDH", value="PC (Horizons Only)"),
            Choice(name="PC EDO", value="PC (Horizons + Odyssey)"),
            Choice(name="Xbox", value="Xbox"),
            Choice(name="Playstation", value="Playstation"),
        ]
    )
    @check_roles(
        [
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
            server_wine_carrier_role_id(),
        ]
    )
    @check_command_channel([get_wine_carrier_channel(), get_steve_says_channel()])
    async def find_carriers_for_platform(
        self,
        interaction: discord.Interaction,
        platform: str,
        remaining_wine: bool = True,
    ):
        """
        Find carriers for the specified platform.

        :param SlashContext ctx: The discord SlashContext.
        :param str platform: The platform to search for.
        :param bool remaining_wine: True if you only want carriers with wine
        :returns: None
        """

        await interaction.response.defer()
        db_update = await self._update_db()
        await self.report_db_update_result(db_update)
        print(f"{interaction.user.name} requested to fine carriers for: {platform} with wine: {remaining_wine}")

        if remaining_wine:
            data = (f"%{platform}%",)
            carrier_search = "platform LIKE (?) and runtotal > totalunloads"

        else:
            data = (f"%{platform}%",)
            carrier_search = "platform LIKE (?)"

        # Check if it is in the database already
        pirate_steve_db.execute(f"SELECT * FROM boozecarriers WHERE {carrier_search}", data)
        # Really only expect a single entry here, unique field and all that
        carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        print(f"Found {len(carrier_data)} carriers matching the search")

        if not carrier_data:
            print(f"Did not find a carrier matching the condition: {carrier_search}.")
            await interaction.edit_original_response(
                content=f"Could not find a carrier matching the inputs: {platform}, with wine: {remaining_wine}"
            )
            return

        carrier_data = [
            (
                f"{carrier.carrier_name} ({carrier.carrier_identifier})",
                f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
            )
            for carrier in carrier_data
        ]

        # Create the pagination
        await createPagination(
            interaction,
            "Carriers found for",
            carrier_data,
        )

    @app_commands.command(
        name="find_wine_carrier_by_id",
        description="Returns the carriers in the database for the ID.",
    )
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles(
        [
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
            server_wine_carrier_role_id(),
        ]
    )
    async def find_carrier_by_id(self, interaction: discord.Interaction, carrier_id: str):
        await interaction.response.defer()
        db_update = await self._update_db()
        await self.report_db_update_result(db_update)
        print(f"{interaction.user.name} wants to find a carrier by ID: {carrier_id}.")
        try:
            carrier_data = self._validate_existing_carrier(carrier_id)
        except CustomError as e:
            print(e.message)
            await interaction.edit_original_response(content=e.message)
            return

        carrier_embed = discord.Embed(
            title=f"YARR! Found carrier details for the input: {carrier_id}",
            description=f"CarrierName: **{carrier_data.carrier_name}**\n"
            f"ID: **{carrier_data.carrier_identifier}**\n"
            f"Total Tonnes of Wine: **{carrier_data.wine_total}** on **{carrier_data.platform}**\n"
            f"Number of trips to the peak: **{carrier_data.run_count}**\n"
            f"Total Unloads: **{carrier_data.total_unloads}**\n"
            f"Operated by: {carrier_data.discord_username}",
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
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
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

        cruise = "this" if cruise_select == 0 else f"-{cruise_select}"
        print(f"User {interaction.user.name} requested the current tally of the cruise stats for {cruise} cruise.")
        target_date = None

        db_update = await self._update_db()
        await self.report_db_update_result(db_update)

        if cruise_select == 0:
            # Go get everything out of the database
            pirate_steve_db.execute("SELECT * FROM boozecarriers")
            all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
            pirate_steve_db.execute("SELECT * FROM boozecarriers WHERE runtotal > 1")

        else:
            # Get the dates in the DB and order them.
            pirate_steve_db.execute("SELECT DISTINCT holiday_start FROM historical ORDER by holiday_start DESC")
            all_dates = [dict(value) for value in pirate_steve_db.fetchall()]

            if cruise_select > len(all_dates):
                print("Input for cruise value was out of bounds for the number of cruises recorded in the database.")
                await interaction.edit_original_response(
                    content=f"Pirate Steve only knows about the last: {len(all_dates)} booze cruises. "
                    f"You wanted the -{cruise_select} data."
                )
                return
            # Subtract 1 here, we filter the values out of the historical database, so the current cruise is not
            # there yet
            target_date = all_dates[cruise_select - 1]["holiday_start"]
            print(f"We have found the following historical cruise dates: {all_dates}")
            print(f"We are interested in the {cruise} option - {target_date}")

            data = (target_date,)
            # In this case we want the historical data from the historical database
            pirate_steve_db.execute("SELECT * FROM historical WHERE holiday_start = (?)", data)
            all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        stat_embed = await self.build_stat_embed(
            all_carrier_data, target_date=target_date, include_not_unloaded=include_not_unloaded
        )

        await interaction.edit_original_response(embed=stat_embed)

        if cruise_select == 0:
            pinned_stat_embed = await self.build_stat_embed(all_carrier_data, None, True)

            # Go update all the pinned embeds also.
            pirate_steve_db.execute("""SELECT * FROM pinned_messages""")
            pins = [dict(value) for value in pirate_steve_db.fetchall()]
            if pins:
                print(f"Updating pinned messages: {pins}")
                for pin in pins:
                    channel = await get_channel(pin["channel_id"])
                    print(f"Channel matched as: {channel} from {pin['channel_id']}")
                    # Now go loop over every pin and update it
                    message = await channel.fetch_message(pin["message_id"])
                    print(f"Message matched as: {message} from {pin['message_id']}")
                    await message.edit(embed=pinned_stat_embed)
            else:
                print("No pinned messages up update")

    @app_commands.command(
        name="booze_pin_message",
        description="Pins a steve tally embed for periodic updating. Restricted to Admin and Sommelier's.",
    )
    @describe(message_link="The message link to be pinned")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    async def pin_message(self, interaction: discord.Interaction, message_link: str):
        """
        Pins the message in the channel.

        :param Interaction discord.Interaction: The discord interaction context
        :param str message_link: The link of message to pin
        :returns: None
        """

        await interaction.response.defer(ephemeral=True)

        print(f"User {interaction.user.name} wants to pin the message {message_link}")

        split_message_link = message_link.split("/")
        channel_id = int(split_message_link[5])
        channel = await get_channel(channel_id)
        message_id = int(split_message_link[6])

        message = await channel.fetch_message(message_id)
        if not message:
            print(f"Could not find a message for the link: {message_link}")
            await interaction.edit_original_response(content=f"Could not find a message with the link: {message_link}")
            return

        try:
            message_embed = message.embeds[0]

        except IndexError:
            print("The message entered is not a pirate steve stat embed")
            await interaction.edit_original_response(
                content=f"The message entered is not a pirate steve stat embed. {message_link}"
            )
            return

        if message_embed.title != "Pirate Steve's Booze Cruise Tally":
            print("The message entered is not a pirate steve stat embed")
            await interaction.edit_original_response(
                content=f"The message entered is not a pirate steve stat embed. {message_link}"
            )
            return

        data = (
            message_id,
            channel_id,
        )
        async with pirate_steve_db_lock:
            print("Writing to the DB the message data")
            pirate_steve_db.execute("""INSERT INTO pinned_messages VALUES(NULL, ?, ?)""", data)
            pirate_steve_conn.commit()

        if not message.pinned:
            print("Message is not pinned - do it now")
            await message.pin(reason=f"Pirate Steve pinned on behalf of {interaction.user.name}")
            print(f"Message {message_id} was pinned.")
        else:
            print("Message is already pinned, no action needed")

        await interaction.edit_original_response(
            content=f"Pirate steve recorded message {message_link} for pinned updating"
        )

    @app_commands.command(
        name="booze_unpin_all",
        description="Unpins all messages for booze stats and updates the DB. Restricted to Admin and Sommelier's.",
    )
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel([get_steve_says_channel()])
    async def clear_all_pinned_message(self, interaction: discord.Interaction):
        """
        Clears all the pinned messages

        :param Interaction discord.Interaction: The discord interaction context
        :returns: None
        """

        await interaction.response.defer(ephemeral=True)
        print(f"User {interaction.user.name} requested to clear the pinned messages.")

        pirate_steve_db.execute("SELECT * FROM pinned_messages")
        # Get everything
        all_pins = [dict(value) for value in pirate_steve_db.fetchall()]
        if all_pins:
            for pin in all_pins:
                channel = await get_channel(int(pin["channel_id"]))
                message = await channel.fetch_message(pin["message_id"])
                await message.unpin(reason=f"Pirate Steve unpinned at the request of: {interaction.user.name}")
                print(f"Removed pinned message: {pin['message_id']}.")
            async with pirate_steve_db_lock:
                print("Writing to the DB the message data to clear the pins")
                pirate_steve_db.execute(
                    """DELETE FROM pinned_messages""",
                )
                pirate_steve_conn.commit()
                print("Pinned messages removed")
            print("Pinned messages removed")
            await interaction.edit_original_response(content="Pirate Steve removed all the pinned stat messages")
        else:
            await interaction.edit_original_response(content="Pirate Steve has no pinned messages to remove.")

    @app_commands.command(
        name="booze_unpin_message",
        description="Unpins a specific message and removes it from the DB. Restricted to Admin and Sommelier's.",
    )
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @describe(message_link="The message link to be unpinned")
    @check_command_channel([get_steve_says_channel()])
    async def booze_unpin_message(self, interaction: discord.Interaction, message_link: str):
        """
        Clears the pinned embed described by the message_link string.

        :param Interaction discord.Interaction: The discord interaction context
        :param str message_link: The message url to unpin
        :returns: None
        """

        await interaction.response.defer(ephemeral=True)
        print(f"User {interaction.user.name} requested to clear the pinned message {message_link}.")

        split_message_link = message_link.split("/")
        channel_id = int(split_message_link[5])
        channel = await get_channel(channel_id)
        message_id = int(split_message_link[6])

        pirate_steve_db.execute(f"SELECT * FROM pinned_messages WHERE message_id = {message_id}")
        # Get everything matching message_id
        all_pins = [dict(value) for value in pirate_steve_db.fetchall()]
        if all_pins:
            for pin in all_pins:
                channel = await get_channel(int(pin["channel_id"]))
                message = await channel.fetch_message(pin["message_id"])
                await message.unpin(reason=f"Pirate Steve unpinned at the request of: {interaction.user.name}")
                print(f"Removed pinned message: {pin['message_id']}.")
            async with pirate_steve_db_lock:
                print("Writing to the DB the message data to clear the pins")

                pirate_steve_db.execute(
                    """DELETE FROM pinned_messages""",
                )
                pirate_steve_conn.commit()
                print("Pinned messages removed")
            print("Pinned messages removed")
            await interaction.edit_original_response(
                content=f"Pirate Steve removed the pinned stat message for {message_link}"
            )
        else:
            await interaction.edit_original_response(
                content=f"Pirate Steve has no pinned messages matching {message_link}."
            )

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
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
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
        print(f"User {interaction.user.name} requested the current extended stats of the cruise.")

        db_update = await self._update_db()
        await self.report_db_update_result(db_update)

        cruise = "this" if cruise_select == 0 else f"-{cruise_select}"
        print(f"User {interaction.user.name} requested the current tally of the cruise stats for {cruise} cruise.")
        target_date = None

        if cruise_select == 0:
            # Go get everything out of the database
            pirate_steve_db.execute("SELECT * FROM boozecarriers")
            all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        else:
            # Get the dates in the DB and order them.
            pirate_steve_db.execute("SELECT DISTINCT holiday_start FROM historical ORDER by holiday_start DESC")
            all_dates = [dict(value) for value in pirate_steve_db.fetchall()]

            if cruise_select > len(all_dates):
                print("Input for cruise value was out of bounds for the number of cruises recorded in the database.")
                await interaction.edit_original_response(
                    content=f"Pirate Steve only knows about the last: {len(all_dates)} booze cruises. "
                    f"You wanted the -{cruise_select} data."
                )
                return
            # Subtract 1 here, we filter the values out of the historical database, so the current cruise is not
            # there yet
            target_date = all_dates[cruise_select - 1]["holiday_start"]
            print(f"We have found the following historical cruise dates: {all_dates}")
            print(f"We are interested in the {cruise} option - {target_date}")

            data = (target_date,)
            # In this case we want the historical data from the historical database
            pirate_steve_db.execute("SELECT * FROM historical WHERE holiday_start = (?)", data)
            all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        stat_embed = await self.build_extended_stat_embed(all_carrier_data, target_date, include_not_unloaded, stat)
        await interaction.edit_original_response(embed=stat_embed)

    @app_commands.command(
        name="booze_carrier_summary",
        description="Returns a summary of booze carriers. Restricted to Admin, Sommeliers, and Connoisseurs.",
    )
    @check_roles(
        [
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
        ]
    )
    async def booze_carrier_summary(self, interaction: discord.Interaction):
        """
        Returns an embed of the current booze carrier summary.

        :param Interaction discord.Interaction: The discord interaction context
        :return: None
        """

        await interaction.response.defer()
        print(f"User {interaction.user.name} requested a carrier summary")
        pirate_steve_db.execute("SELECT * FROM boozecarriers")
        carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        total_carriers = len(carrier_data)
        total_unloads = sum([carrier.total_unloads for carrier in carrier_data])
        remaining_carriers = len([carrier for carrier in carrier_data if carrier.run_count - carrier.total_unloads > 0])
        unloaded_carriers = total_carriers - remaining_carriers

        print(f"User {interaction.user.name} wanted to know if the remaining time of the holiday.")
        if not ph_check():
            duration_remaining = "Pirate Steve has not detected the holiday state yet, or it is already over."
        else:
            duration_hours = 48

            pirate_steve_db.execute("""SELECT timestamp FROM holidaystate""")
            timestamp = pirate_steve_db.fetchone()

            start_time = datetime.strptime(dict(timestamp).get("timestamp"), "%Y-%m-%d %H:%M:%S")
            end_time = start_time + timedelta(hours=duration_hours)
            end_timestamp = int(end_time.timestamp())
            duration_remaining = f"Pirate Steve thinks the holiday will end around <t:{end_timestamp}> (<t:{end_timestamp}:R>) [local timezone]."

        stat_embed = discord.Embed(
            title="Pirate Steve's Booze Carrier Summary",
            description=f"Total Carriers: {total_carriers}\n"
            f"Unloaded Carriers: {unloaded_carriers}\n"
            f"Total Unloads: {total_unloads}\n"
            f"Remaining Carriers: {remaining_carriers}\n"
            f"{duration_remaining}",
        )
        await interaction.edit_original_response(embed=stat_embed)

    @app_commands.command(
        name="booze_delete_carrier",
        description="Removes a carrier from the database. Admin/Sommelier required.",
    )
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    async def remove_carrier(self, interaction: discord.Interaction, carrier_id: str):
        """
        Removes a carrier entry from the database after confirmation.

        :param interaction discord.Interaction: The discord interaction context.
        :param str carrier_id: The XXX-XXX carrier ID.
        :returns: None
        """

        await interaction.response.defer()
        print(f"User {interaction.user.name} wants to remove the carrier with ID {carrier_id} from the database.")
        try:
            carrier_data = self._validate_existing_carrier(carrier_id)
        except CustomError as e:
            print(e.message)
            await interaction.edit_original_response(content=e.message)
            return

        carrier_embed = discord.Embed(
            title=f"YARR! Pirate Steve found these details for the input: {carrier_id}",
            description=f"CarrierName: **{carrier_data.carrier_name}**\n"
            f"ID: **{carrier_data.carrier_identifier}**\n"
            f"Total Tonnes of Wine: **{carrier_data.wine_total}** on **{carrier_data.platform}**\n"
            f"Number of trips to the peak: **{carrier_data.run_count}**\n"
            f"Total Unloads: **{carrier_data.total_unloads}**\n"
            f"Operated by: {carrier_data.discord_username}",
        )

        # Send the embed
        confirm = ConfirmView(interaction.user)
        # Send the embed
        await interaction.edit_original_response(embed=carrier_embed, view=confirm)
        await confirm.wait()

        if confirm.value:
            try:
                print(f"User {interaction.user.name} agreed to delete the carrier: {carrier_id}.")

                # Go update the object in the database.
                async with pirate_steve_db_lock:
                    print(f"Removing the entry ({carrier_id}) from the database.")
                    pirate_steve_db.execute(
                        """ 
                        DELETE FROM boozecarriers 
                        WHERE carrierid LIKE (?) 
                        """,
                        (f"%{carrier_id}%",),
                    )
                    pirate_steve_conn.commit()
                    dump_database()
                    print(f"Carrier ({carrier_id}) was removed from the database")

                await interaction.edit_original_response(
                    content=f"Fleet carrier: {carrier_id} for user: {carrier_data.discord_username} was removed",
                    embed=None,
                    view=None,
                )
            except Exception as e:
                await interaction.edit_original_response(
                    content=f'Something went wrong, go tell the bot team "computer said: {e}"', embed=None, view=None
                )
        elif confirm.value is False:
            print(f"User {interaction.user.name} aborted the request delete carrier {carrier_id}.")
            await interaction.edit_original_response(
                content=f"Avast Ye! you cancelled the action for deleting {carrier_id}.", embed=None, view=None
            )
        else:  # view timeout
            await interaction.edit_original_response(content="**Cancelled - timed out**", embed=None, view=None)

    @app_commands.command(
        name="booze_archive_database",
        description="Archives the boozedatabase. Admin/Sommelier required.",
    )
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    @describe(
        start_date="The start date of the cruise in DD-MM-YY format.",
        faction_state="The faction state to archive the data with (defaults to PH).",
    )
    async def archive_database(
        self, interaction: discord.Interaction, start_date: str, faction_state: FactionStateChoices = "Public Holiday"
    ):
        """
        Performs the steps to archive the current booze cruise database. Only possible if we are not in a PH
        currently and if the data has not been archived. Once archived it will be dropped.
        """

        await interaction.response.defer()
        print(
            f"User {interaction.user.name} requested to archive the database for {start_date} with state {faction_state}."
        )

        if _production and ph_check():
            await interaction.edit_original_response(
                content="Pirate Steve thinks there is a party at Rackhams still. Try again once the grog runs dry."
            )
            return

        try:
            start_date = datetime.strptime(start_date, "%d-%m-%y").date()
            today = datetime.now().date()

            if start_date > today:
                await interaction.edit_original_response(
                    content="Pirate steve cant set the holiday date in the future, "
                    f"format is DD-MM-YY. Your date input: {start_date}.",
                    embed=None,
                )
                print("User input date was in the future, aborting.")
                return
        except ValueError:
            await interaction.edit_original_response(
                content="Pirate Steve thinks you are making up dates, format is DD-MM-YY. "
                f"Your date input: {start_date}.",
                embed=None,
            )
            print("User input date was not in the correct format, aborting.")
            return

        data = (start_date,)
        # Check the date exists in the DB already, if so abort.
        pirate_steve_db.execute(
            "SELECT DISTINCT holiday_start FROM historical WHERE holiday_start = (?)",
            data,
        )
        if pirate_steve_db.fetchall():
            print(f"We have a record for this date ({start_date}) in the historical DB already.")
            # We found something for that date. stop.
            await interaction.edit_original_response(
                content=f"Pirate Steve thinks there is a booze cruise on that day ({start_date}) "
                f"already recorded. Check your data, and send him for a memory check up.",
                embed=None,
            )
            return

        check_embed = discord.Embed(
            title="Validate the request",
            description="You have requested to archive the data in the database with the following:\n"
            f"**Holiday Start:** {start_date.strftime('%d-%m-%y')} - "
            f"**Holiday End:** {(start_date + timedelta(days=2)).strftime('%d-%m-%y')}\n"
            f"**Faction State:** {faction_state}\n",
        )
        confirm = ConfirmView(interaction.user)
        # Send the embed
        await interaction.edit_original_response(content=None, embed=check_embed, view=confirm)
        await confirm.wait()

        if confirm.value is False:
            print(f"User {interaction.user.name} wants to abort the archive process.")
            await interaction.edit_original_response(
                content="You aborted the request to archive the data.", embed=None, view=None
            )
            return
        elif confirm.value is None:
            print(f"User {interaction.user.name} did not respond in time.")
            await interaction.edit_original_response(
                content="**Waiting for user response - timed out**", embed=None, view=None
            )
            return

        async with pirate_steve_db_lock:
            end_date = start_date + timedelta(days=2)
            data = (start_date, end_date, faction_state)
            pirate_steve_db.execute(
                """
                    INSERT INTO historical (carriername, carrierid, winetotal, platform, 
                    officialcarrier, discordusername, timestamp, runtotal, totalunloads)
                    SELECT carriername, carrierid, winetotal, platform, officialcarrier, discordusername, 
                    timestamp, runtotal, totalunloads
                    FROM boozecarriers
                """
            )
            # Now that we copied the columns, go update the timestamps for the cruise. This probably could
            # be chained into the above statement, but effort to figure the syntax out.
            pirate_steve_db.execute(
                """
                    UPDATE historical
                    SET holiday_start=?, holiday_end=?, faction_state=?
                    WHERE holiday_start IS NULL
                """,
                data,
            )
            pirate_steve_conn.commit()

            print("Removing the values from the current table.")
            pirate_steve_db.execute("DELETE FROM boozecarriers")
            pirate_steve_conn.commit()
            dump_database()
            # Disable the updates after we commit the changes!
            self.update_allowed = False
        await interaction.edit_original_response(
            content=f"Pirate Steve rejigged his memory and saved the booze data starting on: {start_date}!",
            embed=None,
            view=None,
        )

    @app_commands.command(
        name="booze_configure_signup_forms",
        description="Updates the booze cruise signup forms. Admin/Sommelier required.",
    )
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    async def configure_signup_forms(self, interaction: discord.Interaction):
        """
        Reconfigures the signup sheet and the tracking sheet to the new forms. Only usable by an admin.

        :param interaction discord.Interaction: The discord interaction context.
        :returns: None
        """

        await interaction.response.defer()
        print(f"{interaction.user.name} wants to reconfigure the booze cruise signup forms.")

        # track the init value, we reset to this in case of bail out
        init_update_value = self.update_allowed
        self.update_allowed = False
        new_sheet_id = None
        new_worksheet_key = None
        new_loader_signup_form = None

        def check_author(check_message):
            return check_message.author == interaction.user and check_message.channel == interaction.channel

        def check_id(check_message):
            return (
                check_message.author == interaction.user
                and check_message.channel == interaction.channel
                and re.match(r"^\d*$", check_message.content)
            )

        # TODO: See if we can add a validation for the URL

        # Check the dB is empty first.
        pirate_steve_db.execute("SELECT * FROM boozecarriers")
        all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
        if all_carrier_data:
            # archive the database first else we will end up in issues
            await interaction.edit_original_response(
                content="Pirate Steve has data already for a cruise - go fix his memory by running the "
                "archive command first."
            )
            return

        await interaction.edit_original_response(content="Pirate Steve first wants the loader signup form URL.")
        try:
            # in this case we do not know the shape of the URL
            response = await bot.wait_for("message", check=check_author, timeout=30)
            if response:
                print(f"We have data: {response.content} for the signup URL.")
                new_loader_signup_form = response.content
                await response.delete()

        except asyncio.TimeoutError:
            self.update_allowed = True
            print("Error getting the response for the google signup form.")
            await interaction.edit_original_response(content="Pirate Steve saw you timed out.", embed=None)
            return

        await interaction.edit_original_response(
            content="Pirate Steve secondly wants the sheet ID for the form. Start "
            "counting from 1 and Pirate Steve will tell the computer "
            "accordingly.",
            embed=None,
        )
        try:
            response = await bot.wait_for("message", check=check_id, timeout=30)
            if response:
                print(f"We have data: {response.content} for the worksheet ID.")
                try:
                    # user counts 1, 2, 3. Computer 0, 1, 2
                    new_sheet_id = int(response.content) - 1
                    if new_sheet_id < 0:
                        raise ValueError("Error ID is less than 0")
                    await response.delete()
                except ValueError:
                    self.update_allowed = init_update_value
                    await response.delete()
                    await interaction.edit_original_response(
                        content=f"Pirate Steve thinks you do not know what an integer starting from 1 is."
                        f" {response.content}. Start again!",
                        embed=None,
                    )
                    return

        except asyncio.TimeoutError:
            print("Error getting the response for the worksheet key.")
            self.update_allowed = True
            await interaction.edit_original_response(content="Pirate Steve saw you timed out on step 2.", embed=None)
            return

        await interaction.edit_original_response(
            content="Pirate Steve thirdly wants to know the key for the data. "
            "The Key is the long unique string in the URL.",
            embed=None,
        )
        try:
            # in this case we do not know the shape of the worksheet Key, it is a unique value.
            response = await bot.wait_for("message", check=check_author, timeout=30)
            if response:
                print(f"We have data: {response.content} for the worksheet unique key.")
                new_worksheet_key = response.content
                await response.delete()

        except asyncio.TimeoutError:
            print("Error getting the response for the worksheet key.")
            self.update_allowed = init_update_value
            await interaction.edit_original_response(content="Pirate Steve saw you timed out on step 3.", embed=None)
            return

        print(f"We received valid data for all points, confirm them with the {interaction.user.name} it is correct.")

        confirm_embed = discord.Embed(
            title="Pirate Steve wants you to confirm the new values.",
            description=f"**New signup URL:** {new_loader_signup_form}\n"
            f"**New worksheet key:** {new_worksheet_key}\n"
            f"**New worksheet ID:** {new_sheet_id + 1}.",
        )
        confirm = ConfirmView(interaction.user)
        # Send the embed
        await interaction.edit_original_response(content=None, embed=confirm_embed, view=confirm)
        await confirm.wait()
        if confirm.value:
            print(f"{interaction.user.name} confirms to write the database now.")
            async with pirate_steve_db_lock:
                data = (new_worksheet_key, new_loader_signup_form, new_sheet_id)
                pirate_steve_db.execute(
                    """
                        UPDATE trackingforms 
                        SET worksheet_key=?, loader_input_form_url=?, worksheet_with_data_id=?
                    """,
                    data,
                )
                pirate_steve_conn.commit()
                dump_database()

            self.worksheet_key = new_worksheet_key
            self.worksheet_with_data_id = new_sheet_id
            self.loader_signup_form_url = new_loader_signup_form
            self.update_allowed = True
            try:
                # Now go make the new updates to pull the data initially
                await self._reconfigure_workbook_and_form()
                db_update = await self._update_db()
                await self.report_db_update_result(db_update)

            except OSError as e:
                self.update_allowed = init_update_value
                await interaction.edit_original_response(
                    content=f"Pirate steve reports an error while updating things: {e}. Fix it and try again.",
                    embed=None,
                )
                return

            await interaction.edit_original_response(
                content="Pirate Steve unfurled out the sails and is now catching the wind with the new values! "
                "Try `/update_booze_db` to check progress.",
                embed=None,
                view=None,
            )
        elif confirm.value is False:
            print(f"User {interaction.user.name} wants to abort the archive process.")
            self.update_allowed = init_update_value
            await interaction.edit_original_response(
                content="You aborted the request to update the forms.", embed=None, view=None
            )
        else:  # view timeout
            print("Error getting the confirmation response")
            self.update_allowed = init_update_value
            await interaction.edit_original_response(
                content="Pirate Steve saw you timed on the confirmation.", embed=None, view=None
            )

    @app_commands.command(
        name="booze_reuse_signup_forms",
        description="Reuses the current the booze cruise signup forms. Admin/Sommelier required.",
    )
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    async def reuse_signup_forms(self, interaction: discord.Interaction):
        """
        Reuses the signup sheet and the tracking sheet. And re unlocks the db. Only usable by an admin.

        :param interaction discord.Interaction: The discord interaction context.
        :returns: None
        """

        await interaction.response.defer()
        print(f"{interaction.user.name} wants to reconfigure the booze cruise signup forms.")

        # Store the current states just in case we need them
        original_sheet_id = self.worksheet_with_data_id
        original_worksheet_key = self.worksheet_key
        original_loader_signup_form = self.loader_signup_form_url

        # track the init value, we reset to this in case of bail out
        init_update_value = self.update_allowed
        self.update_allowed = False

        # Check the dB is empty first.
        pirate_steve_db.execute("SELECT * FROM boozecarriers")
        all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
        if all_carrier_data:
            # archive the database first else we will end up in issues
            await interaction.edit_original_response(
                content="Pirate Steve has data already for a cruise - go fix his memory by running the "
                "archive command first."
            )
            return

        confirm_embed = discord.Embed(
            title="Pirate Steve wants you to confirm the values.",
            description=f"**Signup URL:** {original_loader_signup_form}\n"
            f"**Worksheet key:** {original_worksheet_key}\n"
            f"**Worksheet ID:** {original_sheet_id + 1}.",
        )
        confirm = ConfirmView(interaction.user)
        # Send the embed
        await interaction.edit_original_response(embed=confirm_embed, view=confirm)
        await confirm.wait()

        if confirm.value:
            self.worksheet_key = original_worksheet_key
            self.worksheet_with_data_id = original_sheet_id
            self.loader_signup_form_url = original_loader_signup_form
            self.update_allowed = True
            try:
                # Now go make the new updates to pull the data initially
                await self._reconfigure_workbook_and_form()
                db_update = await self._update_db()
                await self.report_db_update_result(db_update)
            except OSError as e:
                self.update_allowed = init_update_value
                await interaction.edit_original_response(
                    content=f"Pirate steve reports an error while updating things: {e}. Fix it and try again.",
                    embed=None,
                    view=None,
                )
                return
            await interaction.edit_original_response(
                content="Pirate Steve unfurled out the sails and is now catching the wind with the new values! "
                "Try `/update_booze_db` to check progress.",
                embed=None,
                view=None,
            )
        elif confirm.value is False:
            print(f"User {interaction.user.name} wants to abort the archive process.")
            self.update_allowed = init_update_value
            await interaction.edit_original_response(
                content="You aborted the request to update the forms.", embed=None, view=None
            )
        else:  # view timeout
            print("Error getting the confirmation response")
            self.update_allowed = init_update_value
            await interaction.edit_original_response(
                content="Pirate Steve saw you timed on the confirmation.", embed=None, view=None
            )

    @app_commands.command(
        name="biggest_cruise_tally", description="Returns the tally for the cruise with the most wine."
    )
    @check_roles(
        [*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id(), server_connoisseur_role_id()]
    )
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

        :param discord.Interaction interaction: The discord interaction context.
        :param bool extended: If the extended stats should be shown.
        :param IncludeNotUnloadedChoices include_not_unloaded: If we should include carriers that did not unload
        :returns: None
        """

        print(f"{interaction.user.name} requested the biggest cruise tally, extended: {extended}.")
        await interaction.response.defer()

        # Fetch the target date
        pirate_steve_db.execute(
            """
                SELECT holiday_start
                FROM historical
                GROUP BY holiday_start
                ORDER BY SUM(ROUND(winetotal/runtotal*totalunloads)) DESC
                LIMIT 1;
            """
        )
        target_date = pirate_steve_db.fetchone()[0]

        # Fetch all carrier data for the target date
        pirate_steve_db.execute("SELECT * FROM historical WHERE holiday_start = ?;", (target_date,))
        all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        # Build the stat embed based on the extended flag
        if not extended:
            stat_embed = await self.build_stat_embed(all_carrier_data, target_date, include_not_unloaded)
        else:
            stat_embed = await self.build_extended_stat_embed(all_carrier_data, target_date, include_not_unloaded, stat)

        # Edit the original interaction response with the stat embed
        await interaction.edit_original_response(embed=stat_embed)

    @app_commands.command(name="booze_carrier_stats", description="Returns the stats for a specific carrier.")
    @describe(carrier_id="The XXX-XXX ID string for the carrier")
    @check_roles(
        [
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
            server_wine_carrier_role_id(),
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

        print(f"{interaction.user.name} requested the stats for the carrier: {carrier_id}.")
        await interaction.response.defer()

        pirate_steve_db.execute("SELECT * FROM historical WHERE carrierid LIKE (?)", (f"%{carrier_id}%",))

        carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        pirate_steve_db.execute("SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f"%{carrier_id}%",))

        carrier_data.append(BoozeCarrier(pirate_steve_db.fetchone()))

        # Remove any carriers that do not match the carrier_id (remove the None entry if carrier is not on current cruise)
        carrier_data = [carrier for carrier in carrier_data if carrier.carrier_identifier == carrier_id]

        if not carrier_data:
            print(f"We failed to find the carrier: {carrier_id} in the database.")
            await interaction.edit_original_response(
                content=f"Sorry, we could not find a carrier with the id: {carrier_id}."
            )
            return

        carrier_name = carrier_data[-1].carrier_name
        total_runs = sum([carrier.run_count for carrier in carrier_data])
        total_wine = sum([carrier.wine_total for carrier in carrier_data])
        total_cruises = len(carrier_data)
        owner = carrier_data[-1].discord_username

        stat_embed = discord.Embed(
            title=f"Stats for {carrier_name} ({carrier_id})",
            description=f"Total Wine: {total_wine}\n"
            f"Total Runs: {total_runs}\n"
            f"Total Cruises: {total_cruises}\n"
            f"Owner: {owner}",
        )

        await interaction.edit_original_response(content=None, embed=stat_embed)

    @app_commands.command(name="booze_purge_full_carriers", description="Purges full carriers from the database.")
    @check_roles([*server_council_role_ids(), server_mod_role_id(), server_sommelier_role_id()])
    @check_command_channel(get_steve_says_channel())
    async def purge_full_carriers(self, interaction: discord.Interaction):
        """
        Purges full carriers from the database.

        :param discord.Interaction interaction: The discord interaction context.
        :returns: None
        """

        print(f"{interaction.user.name} requested to purge full carriers.")
        await interaction.response.defer()
        print(f"{interaction.user.name} requested to delete all full carriers.")
        pirate_steve_db.execute("SELECT * FROM boozecarriers WHERE runtotal > totalunloads")
        carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
        if len(carrier_data) == 0:
            print("No full carriers to delete.")
            await interaction.edit_original_response(content="There are no full carriers to delete.")
            return

        print(f"Found {len(carrier_data)} full carriers to delete. Sending confirmation message.")

        confirmation_embed = discord.Embed(
            title=f"Purge {len(carrier_data)} Full Carriers?",
            description="Are you sure you want to delete all the remaining full carriers?",
        )

        confirm = ConfirmView(interaction.user)
        # Send the embed
        await interaction.edit_original_response(embed=confirmation_embed, view=confirm)
        await confirm.wait()

        if confirm.value:
            print(f"User {interaction.user.name} accepted the request to purge full carriers.")
            await interaction.edit_original_response(content="Purging Carriers...", embed=None, view=None)
            failed_carriers = []

            async with pirate_steve_db_lock:
                try:
                    # "DELETE * FROM boozecarriers WHERE runtotal > totalunloads" ??  TODO
                    carrier_ids = [carrier.carrier_identifier for carrier in carrier_data]
                    pirate_steve_db.execute(
                        "DELETE FROM boozecarriers WHERE carrierid IN ({})".format(", ".join("?" * len(carrier_ids))),
                        carrier_ids,
                    )
                    pirate_steve_conn.commit()
                except Exception as e:
                    print(f"Error deleting carriers: {e}")
                    failed_carriers.extend(carrier_ids)

            if failed_carriers:
                await interaction.followup.send(
                    content=f"Failed to delete the following carriers: {', '.join(failed_carriers)}"
                )

            print("Finished purging full carriers.")
            await interaction.edit_original_response(content="Full carriers have been purged.", embed=None, view=None)
        elif confirm.value is False:
            print(f"User {interaction.user.name} aborted the request to purge full carriers.")
            await interaction.edit_original_response(
                content="Aborted the request to purge full carriers.", embed=None, view=None
            )
        else:  # view timeout
            print("Timed out while waiting for confirmation response.")
            await interaction.edit_original_response(
                content="Waiting for user response - timed out", embed=None, view=None
            )
