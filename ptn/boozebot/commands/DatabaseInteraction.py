import asyncio
from datetime import datetime, timedelta
import math
import os.path
import re

import discord
from discord.ext import tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_permission, create_option, create_choice
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from discord.ext.commands import Cog

from ptn.boozebot.BoozeCarrier import BoozeCarrier
from ptn.boozebot.PHcheck import ph_check
from ptn.boozebot.constants import bot_guild_id, bot, server_admin_role_id, server_sommelier_role_id, \
    BOOZE_PROFIT_PER_TONNE_WINE, RACKHAMS_PEAK_POP, server_mod_role_id, get_bot_control_channel, \
    get_sommelier_notification_channel
from ptn.boozebot.database.database import pirate_steve_db, pirate_steve_conn, dump_database, pirate_steve_lock


class DatabaseInteraction(Cog):

    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

        if not os.path.join(os.path.expanduser('~'), '.ptnboozebot.json'):
            raise EnvironmentError('Cannot find the booze cruise json file.')

        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            os.path.join(os.path.expanduser('~'), '.ptnboozebot.json'), scope)

        # authorize the client sheet
        self.client = gspread.authorize(credentials)
        self.tracking_sheet = None
        self.update_allowed = True  # This might be better stored somewhere over a reset
        pirate_steve_db.execute(
            "SELECT * FROM trackingforms"
        )
        forms = dict(pirate_steve_db.fetchone())

        self.worksheet_key = forms['worksheet_key']

        # On which sheet is the actual data.
        self.worksheet_with_data_id = forms['worksheet_with_data_id']

        # input form is the form we have loaders fill in
        self.loader_signup_form_url = forms['loader_input_form_url']

        self._reconfigure_workbook_and_form()

        self._update_db()  # On instantiation, go build the DB

    def _reconfigure_workbook_and_form(self):
        """
        Reconfigures the tracking sheet to the latest version based on the current worksheet key and sheet ID. Called
        when we update the forms or on startup of the bot.

        :returns: None
        """
        # The key is part of the URL
        try:
            self.tracking_sheet = None
            print(f'Building worksheet with the key: {self.worksheet_key}')
            workbook = self.client.open_by_key(self.worksheet_key)

            for sheet in workbook.worksheets():
                print(sheet.title)

            # Update the tracking sheet object
            self.tracking_sheet = workbook.get_worksheet(self.worksheet_with_data_id)
        except gspread.exceptions.APIError as e:
            print(f'Error reading the worksheet: {e}')

    @cog_ext.cog_slash(
        name="update_booze_db",
        guild_ids=[bot_guild_id()],
        description="Populates the booze cruise database from the updated google sheet. Admin/Sommelier role required.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def user_update_database_from_googlesheets(self, ctx: SlashContext):
        """
        Slash command for updating the database from the GoogleSheet.

        :returns: A discord embed to the user.
        :rtype: None
        """
        print(f'User {ctx.author} requested to re-populate the database at {datetime.now()}')

        try:
            result = self._update_db()
            await self.report_invalid_carriers(result)
            embed = discord.Embed(title="Pirate Steve's DB Update ran successfully.")
            embed.add_field(name=f'Total number of carriers: {result["total_carriers"]:>20}.\n'
                                 f'Number of new carriers added: {result["added_count"]:>8}.\n'
                                 f'Number of carriers amended: {result["updated_count"]:>11}.\n'
                                 f'Number of carriers unchanged: {result["unchanged_count"]:>7}.',
                            value='Pirate Steve hope he got this right.',
                            inline=False)

            return await ctx.send(embed=embed)

        except ValueError as ex:
            return await ctx.send(str(ex))

    async def report_invalid_carriers(self, result=None):
        """
        Reports any invalid carriers to the applicable channels.

        :param dict result: A dict returned from the update_db method
        :returns: None
        """
        if result is None:
            result = {}

        try:
            if result['invalid_database_entries']:

                # In case any problem carriers found, mark them up
                print('Problem: We have invalid carriers!')
                for problem_carrier in result['invalid_database_entries']:
                    print(f'This carrier is no longer in the sheet: {problem_carrier}')

                    # Notify the channels so it can be deleted.
                    booze_bot_channel = bot.get_channel(get_bot_control_channel())
                    sommelier_notification_channel = bot.get_channel(get_sommelier_notification_channel())
                    for channel in [booze_bot_channel, sommelier_notification_channel]:
                        problem_embed = discord.Embed(
                            title='Avast Ye! Pirate Steve found a missing carrier in the database!',
                            description=f'This carrier is no longer in the GoogleSheet:\n'
                                        f'CarrierName: **{problem_carrier.carrier_name}**\n'
                                        f'ID: **{problem_carrier.carrier_identifier}**\n'
                                        f'Total Tonnes of Wine: **{problem_carrier.wine_total}** on '
                                        f'**{problem_carrier.platform}**\n'
                                        f'Number of trips to the peak: **{problem_carrier.run_count}**\n'
                                        f'Total Unloads: **{problem_carrier.total_unloads}**\n'
                                        f'PTN Official: {problem_carrier.ptn_carrier}\n'
                                        f'Operated by: {problem_carrier.discord_username}'
                        )
                        problem_embed.set_footer(text='Pirate Steve recommends verifying and then deleting this entry'
                                                      ' with /booze_delete_carrier')
                        await channel.send(embed=problem_embed)
                        if channel == sommelier_notification_channel:
                            # Add a notification for the sommelier role
                            await channel.send(f'\n<@&{server_sommelier_role_id()}> please take note.')
            else:
                print('No invalid carriers found')
        except KeyError as e:
            print(f'Key did not exist in the input: {result} -> {e}')

    def _update_db(self):
        """
        Private method to wrap the DB update commands.

        :returns:
        :rtype:
        """
        if not self.tracking_sheet:
            raise EnvironmentError('Sorry this cannot be ran as we have no form for tracking the wine presently. '
                                   'Please set a new form first.')

        elif not self.update_allowed:
            print('Update not allowed, user has archived the data but not polled the latest set.')
            return

        updated_db = False
        added_count = 0
        updated_count = 0
        unchanged_count = 0
        # A JSON form tracking all the records
        records_data = self.tracking_sheet.get_all_records()

        total_carriers = len(records_data)
        print(f'Updating the database we have: {total_carriers} records found.')

        # A list of carrier dicts, containing how often they are in the overall input sheet, populate this to start
        # with. This is a quick and dirty amalgamation of the data. We do this first to avoid unnecessary writes to
        # the database.

        carrier_count = []
        try:
            for record in records_data:
                carrier = BoozeCarrier(record)
                if not any(data['carrier_id'] == carrier.carrier_identifier for data in carrier_count):
                    # if the carrier does not exist, then we need to add it
                    carrier_dict = {
                        'carrier_name': carrier.carrier_name,
                        'carrier_id': carrier.carrier_identifier,
                        'run_count': carrier.run_count,
                        'wine_total': carrier.wine_total
                    }
                    carrier_count.append(carrier_dict)
                else:
                    # Go append in the stats for this entry then
                    for data in carrier_count:
                        if data['carrier_id'] == carrier.carrier_identifier:
                            data['run_count'] += 1
                            data['wine_total'] += carrier.wine_total
        except ValueError as ex:
            # This is OK, we want to just log the problem and highlight it to be addressed. We do not have a context
            # here so we cannot actually post anything.
            print(f'Error while paring the stats into carrier records: {ex}')
            # Just re-raise this error
            raise ex
        # We use this later to go find all the carriers in the database and ensure they match up and none were removed
        all_carrier_ids_sheet = [f'{carrier["carrier_id"]}' for carrier in carrier_count]

        print(all_carrier_ids_sheet)
        print(carrier_count)

        # First row is the headers, drop them.
        for record in records_data:
            # Iterate over the records and populate the database as required.

            # Check if it is in the database already
            pirate_steve_db.execute(
                "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{record["Carrier ID"].upper()}%',)
            )
            carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
            if len(carrier_data) > 1:
                raise ValueError(f'{len(carrier_data)} carriers are listed with this carrier ID:'
                                 f' {record["Carrier ID"].upper()}. Problem in the DB!')

            if carrier_data:
                # We have a carrier, just check the values and update it if needed.
                print(f'The carrier for {record["Carrier ID"].upper()} exists, checking the values.')
                expected_carrier_data = BoozeCarrier(record)
                db_carrier_data = carrier_data[0]

                # Update the expected values for wine and count to those coming out of the earlier check if they exist
                for data in carrier_count:
                    # There must be a better solution than this, but this was the simplest path I could see
                    if data['carrier_id'] == expected_carrier_data.carrier_identifier:
                        expected_carrier_data.wine_total = data['wine_total']
                        expected_carrier_data.run_count = data['run_count']

                print(f'EXPECTED: \t{expected_carrier_data}')
                print(f'RECORD: \t{db_carrier_data}')
                print(f'EQUALITY: \t{expected_carrier_data == db_carrier_data}')

                if db_carrier_data != expected_carrier_data:
                    print(f'The DB data for {db_carrier_data.carrier_name} does not equal the input in GoogleSheets '
                          f'- Updating')
                    updated_count += 1
                    try:
                        pirate_steve_lock.acquire()
                        pirate_steve_conn.set_trace_callback(print)
                        data = (
                            expected_carrier_data.carrier_name,
                            expected_carrier_data.carrier_identifier,
                            expected_carrier_data.wine_total,
                            expected_carrier_data.platform,
                            expected_carrier_data.ptn_carrier,
                            expected_carrier_data.discord_username,
                            expected_carrier_data.timestamp,
                            expected_carrier_data.run_count,
                            f'%{db_carrier_data.carrier_name}%'
                        )

                        pirate_steve_db.execute(
                            ''' UPDATE boozecarriers 
                            SET carriername=?, carrierid=?, winetotal=?, platform=?, officialcarrier=?, 
                            discordusername=?, timestamp=?, runtotal=?
                            WHERE carriername LIKE (?) ''', data
                        )

                        pirate_steve_conn.commit()
                    finally:
                        pirate_steve_lock.release()
                else:
                    print(f'The DB data for {db_carrier_data.carrier_name} is the same as the sheets record - '
                          f'skipping over.')
                    unchanged_count += 1

            else:
                added_count += 1
                carrier = BoozeCarrier(record)
                print(carrier.to_dictionary())
                print(f'Carrier {record["Carrier Name"]} is not yet in the database - adding it')
                try:
                    pirate_steve_lock.acquire()
                    pirate_steve_db.execute(''' 
                    INSERT INTO boozecarriers VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?) 
                    ''', (
                        carrier.carrier_name, carrier.carrier_identifier, carrier.wine_total,
                        carrier.platform, carrier.ptn_carrier, carrier.discord_username,
                        carrier.timestamp, carrier.run_count, carrier.total_unloads, carrier.timezone
                    )
                                            )
                finally:
                    pirate_steve_lock.release()

                updated_db = True
                print('Added carrier to the database')

        print(all_carrier_ids_sheet)

        # Now that the records are updated, make sure no carrier was removed - check for anything not matching the
        # carrier id strings.
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid NOT IN ({})".format(
                ', '.join('?' * len(all_carrier_ids_sheet))
            ), all_carrier_ids_sheet
        )

        invalid_datbase_entries = [BoozeCarrier(inv_carrier) for inv_carrier in pirate_steve_db.fetchall()]
        if updated_db:
            # Write the database and then dump the updated SQL
            try:
                pirate_steve_lock.acquire()
                pirate_steve_conn.commit()
            finally:
                pirate_steve_lock.release()
            dump_database()
            print('Wrote the database and dumped the SQL')

        return {
            'updated_db': updated_db,
            'added_count': added_count,
            'updated_count': updated_count,
            'unchanged_count': unchanged_count,
            'total_carriers': total_carriers,
            'invalid_database_entries': invalid_datbase_entries
        }

    @cog_ext.cog_slash(
        name="find_carriers_with_wine",
        guild_ids=[bot_guild_id()],
        description="Returns the carriers in the database that are still flagged as having wine remaining.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def find_carriers_with_wine(self, ctx: SlashContext):
        """
        Returns an interactive list of all the carriers with wine that has not yet been unloaded.

        :param SlashContext ctx: The discord slash context
        :returns: An interactive message embed.
        :rtype: Union[discord.Message, dict]
        """
        await self.report_invalid_carriers(self._update_db())
        print(f'{ctx.author} requested to find the carrier with wine')
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE runtotal > totalunloads"
        )
        carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
        if len(carrier_data) == 0:
            # No carriers remaining
            return await ctx.send('Pirate Steve is sorry, but there are no more carriers with wine remaining.')

        # Else we have wine left

        def chunk(chunk_list, max_size=10):
            """
            Take an input list, and an expected max_size.

            :returns: A chunked list that is yielded back to the caller
            :rtype: iterator
            """
            for i in range(0, len(chunk_list), max_size):
                yield chunk_list[i:i + max_size]

        def validate_response(react, user):
            """
            Validates the user response
            """
            return user == ctx.author and str(react.emoji) in ["◀️", "▶️"]

        pages = [page for page in chunk(carrier_data)]
        max_pages = len(pages)
        current_page = 1

        embed = discord.Embed(
            title=f"{len(carrier_data)} Carriers left with wine in the database. Page: #{current_page} of {max_pages}"
        )
        count = 0  # Track the overall count for all carriers

        # Go populate page 0 by default
        for carrier in pages[0]:
            count += 1
            embed.add_field(
                name=f"{count}: {carrier.carrier_name} ({carrier.carrier_identifier})",
                value=f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
                inline=False
            )

        # Now go send it and wait on a reaction
        message = await ctx.send(embed=embed)

        # From page 0 we can only go forwards
        await message.add_reaction("▶️")
        # 60 seconds time out gets raised by Asyncio
        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60, check=validate_response)
                if str(reaction.emoji) == "▶️" and current_page != max_pages:

                    print(f'{ctx.author} requested to go forward a page.')
                    current_page += 1  # Forward a page
                    new_embed = discord.Embed(
                        title=f"{len(carrier_data)} Carriers left with wine in the database. Page:{current_page}"
                    )
                    for carrier in pages[current_page - 1]:
                        # Page -1 as humans think page 1, 2, but python thinks 0, 1, 2
                        count += 1
                        new_embed.add_field(
                            name=f"{count}: {carrier.carrier_name} ({carrier.carrier_identifier})",
                            value=f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
                            inline=False
                        )

                    await message.edit(embed=new_embed)

                    # Ok now we can go back, check if we can also go forwards still
                    if current_page == max_pages:
                        await message.clear_reaction("▶️")

                    await message.remove_reaction(reaction, user)
                    await message.add_reaction("◀️")

                elif str(reaction.emoji) == "◀️" and current_page > 1:
                    print(f'{ctx.author} requested to go back a page.')
                    current_page -= 1  # Go back a page

                    new_embed = discord.Embed(
                        title=f"{len(carrier_data)} Carriers left with wine in the database. Page:{current_page}"
                    )
                    # Start by counting back however many carriers are in the current page, minus the new page, that way
                    # when we start a 3rd page we don't end up in problems
                    count -= len(pages[current_page - 1])
                    count -= len(pages[current_page])

                    for carrier in pages[current_page - 1]:
                        # Page -1 as humans think page 1, 2, but python thinks 0, 1, 2
                        count += 1
                        new_embed.add_field(
                            name=f"{count}: {carrier.carrier_name} ({carrier.carrier_identifier})",
                            value=f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
                            inline=False
                        )

                    await message.edit(embed=new_embed)
                    # Ok now we can go forwards, check if we can also go backwards still
                    if current_page == 1:
                        await message.clear_reaction("◀️")

                    await message.remove_reaction(reaction, user)
                    await message.add_reaction("▶️")
                else:
                    # It should be impossible to hit this part, but lets gate it just in case.
                    print(
                        f'HAL9000 error: {ctx.author} ended in a random state while trying to handle: {reaction.emoji} '
                        f'and on page: {current_page}.')
                    # HAl-9000 error response.
                    error_embed = discord.Embed(title=f"I'm sorry {ctx.author}, I'm afraid I can't do that.")
                    await message.edit(embed=error_embed)
                    await message.remove_reaction(reaction, user)

            except asyncio.TimeoutError:
                print(f'Timeout hit during carrier request by: {ctx.author}')
                await ctx.send(
                    f'Closed the active carrier list request from: {ctx.author} due to no input in 60 seconds.')
                return await message.delete()

    @cog_ext.cog_slash(
        name="wine_mark_completed_forcefully",
        guild_ids=[bot_guild_id()],
        description="Forcefully marks a carrier in the database as unload completed. Admin/Sommelier required.",
        options=[
            create_option(
                name='carrier_id',
                description='The XXX-XXX ID string for the carrier',
                option_type=3,
                required=True
            )
        ],
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        }
    )
    async def wine_mark_completed_forcefully(self, ctx: SlashContext, carrier_id):
        """
        Forcefully marks a carrier as completed an unload. Ideally will never be used.

        :param SlashContext ctx: The discord slash context.
        :param str carrier_id: The XXX-XXX carrier ID you want to action.
        :returns: None
        """
        await self.report_invalid_carriers(self._update_db())
        print(f'{ctx.author} wants to forcefully mark the carrier {carrier_id} as unloaded.')

        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            print(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')
            return await ctx.channel.send(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, '
                                          f'{carrier_id}.')

        # Check if it is in the database already
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())

        carrier_embed = discord.Embed(
            title=f'Argh We found this data for {carrier_id}:',
            description=f'CarrierName: **{carrier_data.carrier_name}**\n'
                        f'ID: **{carrier_data.carrier_identifier}**\n'
                        f'Total Tonnes of Wine: **{carrier_data.wine_total}** on **{carrier_data.platform}**\n'
                        f'Number of trips to the peak: **{carrier_data.run_count}**\n'
                        f'Total Unloads: **{carrier_data.total_unloads}**\n'
                        f'PTN Official: {carrier_data.ptn_carrier}\n'
                        f'Operated by: {carrier_data.discord_username}'
        )
        carrier_embed.set_footer(text="y/n")

        def check(check_message):
            return check_message.author == ctx.author and check_message.channel == ctx.channel and \
                   check_message.content.lower() in ["y", "n"]

        # Send the embed
        message = await ctx.send(embed=carrier_embed)

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            if msg.content.lower() == "n":
                await message.delete()
                await msg.delete()
                print(f'User {ctx.author} aborted the request to mark the carrier {carrier_id} as unloaded.')
                return await ctx.send(f"Argh you cancelled the action for marking {carrier_id} "
                                      f"as forcefully completed.")

            elif msg.content.lower() == "y":
                try:
                    await message.delete()
                    await msg.delete()
                    print(f'User {ctx.author} agreed to mark the carrier {carrier_id} as unloaded.')

                    # Go update the object in the database.
                    try:
                        pirate_steve_lock.acquire()

                        data = (
                            f'%{carrier_data.carrier_identifier}%',
                        )
                        pirate_steve_db.execute(
                            ''' 
                            UPDATE boozecarriers 
                            SET totalunloads=totalunloads+1, discord_unload_in_progress=NULL
                            WHERE carrierid LIKE (?) 
                            ''', data
                        )
                        pirate_steve_conn.commit()
                    finally:
                        pirate_steve_lock.release()

                    print(f'Database for unloaded forcefully updated by {ctx.author} for {carrier_id}')
                    embed = discord.Embed(
                        description=f"Fleet carrier {carrier_data.carrier_name} marked as unloaded.",
                    )
                    embed.add_field(
                        name=f'Runs Made: {carrier_data.run_count}',
                        value=f'Unloads Completed: {carrier_data.total_unloads}'
                    )
                    return await ctx.send(embed=embed)
                except Exception as e:
                    return ctx.send(f'Something went wrong, go tell the bot team "computer said: {e}"')

        except asyncio.TimeoutError:
            await message.delete()
            return await ctx.send("**Cancelled - timed out**")

        await message.delete()

    @cog_ext.cog_slash(
        name="find_wine_carriers_for_platform",
        guild_ids=[bot_guild_id()],
        description="Returns the carriers in the database for the platform.",
        options=[
            create_option(
                name='platform',
                description='The platform the carrier operates on.',
                option_type=3,
                required=True,
                choices=[
                    create_choice(
                        name="PC (All)",
                        value="PC"
                    ),
                    create_choice(
                        name="PC EDH",
                        value="PC (Horizons Only)"
                    ),
                    create_choice(
                        name="PC EDO",
                        value="PC (Horizons + Odyssey)"
                    ),
                    create_choice(
                        name="Xbox",
                        value="Xbox"
                    ),
                    create_choice(
                        name="Playstation",
                        value="Playstation"
                    ),
                ]
            ),
            create_option(
                name='remaining_wine',
                description='True if you only want carriers with wine, else False. Default True',
                option_type=5,
                required=False
            )
        ],
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
    )
    async def find_carriers_for_platform(self, ctx: SlashContext, platform: str, remaining_wine=True):
        """
        Find carriers for the specified platform.

        :param SlashContext ctx: The discord SlashContext.
        :param str platform: The platform to search for.
        :param bool remaining_wine: True if you only want carriers with wine
        :returns: None
        """
        await self.report_invalid_carriers(self._update_db())
        print(f'{ctx.author} requested to fine carriers for: {platform} with wine: {remaining_wine}')

        if remaining_wine:
            data = (
                f'%{platform}%',
            )
            carrier_search = 'platform LIKE (?) and runtotal > totalunloads'

        else:
            data = (
                f'%{platform}%',
            )
            carrier_search = 'platform LIKE (?)'

        # Check if it is in the database already
        pirate_steve_db.execute(
            f"SELECT * FROM boozecarriers WHERE {carrier_search}", data
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]

        print(f'Found {len(carrier_data)} carriers matching the search')

        if not carrier_data:
            print(f'Did not find a carrier matching the condition: {carrier_search}.')
            return await ctx.send(f'Could not find a carrier matching the inputs: {platform}, '
                                  f'with wine: {remaining_wine}')

        def chunk(chunk_list, max_size=10):
            """
            Take an input list, and an expected max_size.

            :returns: A chunked list that is yielded back to the caller
            :rtype: iterator
            """
            for i in range(0, len(chunk_list), max_size):
                yield chunk_list[i:i + max_size]

        def validate_response(react, user):
            """
            Validates the user response
            """
            return user == ctx.author and str(react.emoji) in ["◀️", "▶️"]

        pages = [page for page in chunk(carrier_data)]
        max_pages = len(pages)
        current_page = 1

        embed = discord.Embed(
            title=f"{len(carrier_data)} {platform} Carriers left with wine in the database. Page: #{current_page} of"
                  f" {max_pages}"
        )
        count = 0  # Track the overall count for all carriers

        # Go populate page 0 by default
        for carrier in pages[0]:
            count += 1
            embed.add_field(
                name=f"{count}: {carrier.carrier_name} ({carrier.carrier_identifier})",
                value=f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
                inline=False
            )

        # Now go send it and wait on a reaction
        message = await ctx.send(embed=embed)

        # From page 0 we can only go forwards
        await message.add_reaction("▶️")
        # 60 seconds time out gets raised by Asyncio
        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60, check=validate_response)
                if str(reaction.emoji) == "▶️" and current_page != max_pages:

                    print(f'{ctx.author} requested to go forward a page.')
                    current_page += 1  # Forward a page
                    new_embed = discord.Embed(
                        title=f"{len(carrier_data)} {platform} Carriers left with wine in the database. Page"
                              f":{current_page}"
                    )
                    for carrier in pages[current_page - 1]:
                        # Page -1 as humans think page 1, 2, but python thinks 0, 1, 2
                        count += 1
                        new_embed.add_field(
                            name=f"{count}: {carrier.carrier_name} ({carrier.carrier_identifier})",
                            value=f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
                            inline=False
                        )

                    await message.edit(embed=new_embed)

                    # Ok now we can go back, check if we can also go forwards still
                    if current_page == max_pages:
                        await message.clear_reaction("▶️")

                    await message.remove_reaction(reaction, user)
                    await message.add_reaction("◀️")

                elif str(reaction.emoji) == "◀️" and current_page > 1:
                    print(f'{ctx.author} requested to go back a page.')
                    current_page -= 1  # Go back a page

                    new_embed = discord.Embed(
                        title=f"{len(carrier_data)} {platform} Carriers left with wine in the database. "
                              f"Page:{current_page}"
                    )
                    # Start by counting back however many carriers are in the current page, minus the new page, that way
                    # when we start a 3rd page we don't end up in problems
                    count -= len(pages[current_page - 1])
                    count -= len(pages[current_page])

                    for carrier in pages[current_page - 1]:
                        # Page -1 as humans think page 1, 2, but python thinks 0, 1, 2
                        count += 1
                        new_embed.add_field(
                            name=f"{count}: {carrier.carrier_name} ({carrier.carrier_identifier})",
                            value=f"{carrier.wine_total // carrier.run_count} tonnes of wine on {carrier.platform}",
                            inline=False
                        )

                    await message.edit(embed=new_embed)
                    # Ok now we can go forwards, check if we can also go backwards still
                    if current_page == 1:
                        await message.clear_reaction("◀️")

                    await message.remove_reaction(reaction, user)
                    await message.add_reaction("▶️")
                else:
                    # It should be impossible to hit this part, but lets gate it just in case.
                    print(
                        f'HAL9001 error: {ctx.author} ended in a random state while trying to handle: {reaction.emoji} '
                        f'and on page: {current_page}.')
                    # HAl-9000 error response.
                    error_embed = discord.Embed(title=f"I'm sorry {ctx.author}, I'm afraid I can't do that.")
                    await message.edit(embed=error_embed)
                    await message.remove_reaction(reaction, user)

            except asyncio.TimeoutError:
                print(f'Timeout hit during carrier request by: {ctx.author}')
                await ctx.send(
                    f'Closed the active carrier list request from: {ctx.author} due to no input in 60 seconds.')
                return await message.delete()

    @cog_ext.cog_slash(
        name="find_wine_carrier_by_id",
        guild_ids=[bot_guild_id()],
        description="Returns the carriers in the database for the ID.",
        options=[
            create_option(
                name='carrier_id',
                description='The XXX-XXX ID string for the carrier',
                option_type=3,
                required=True
            )
        ],
    )
    async def find_carrier_by_id(self, ctx: SlashContext, carrier_id: str):
        await self.report_invalid_carriers(self._update_db())
        print(f'{ctx.author} wants to find a carrier by ID: {carrier_id}.')
        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()
        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            print(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')
            return await ctx.channel.send(
                f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')

        # Check if it is in the database already
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid = (?)", (f'{carrier_id}',)
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())
        print(f'Found: {carrier_data}')

        if not carrier_data:
            print(f'No carrier found for: {carrier_id}')
            return await ctx.send(f'No carrier found for: {carrier_id}')

        carrier_embed = discord.Embed(
            title=f'YARR! Found carrier details for the input: {carrier_id}',
            description=f'CarrierName: **{carrier_data.carrier_name}**\n'
                        f'ID: **{carrier_data.carrier_identifier}**\n'
                        f'Total Tonnes of Wine: **{carrier_data.wine_total}** on **{carrier_data.platform}**\n'
                        f'Number of trips to the peak: **{carrier_data.run_count}**\n'
                        f'Total Unloads: **{carrier_data.total_unloads}**\n'
                        f'PTN Official: {carrier_data.ptn_carrier}\n'
                        f'Operated by: {carrier_data.discord_username}'
        )

        return await ctx.send(embed=carrier_embed)

    @cog_ext.cog_slash(
        name="booze_tally",
        guild_ids=[bot_guild_id()],
        description="Returns a summary of the stats for the current booze cruise. Restricted to Admin and Sommelier's.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
        options=[
            create_option(
                name='cruise_select',
                description='Which cruise do you want data for. 0 is this cruise, 1 the last cruise etc. Default is '
                            'this cruise.',
                option_type=4,
                required=False
            )
        ],
    )
    async def tally(self, ctx: SlashContext, cruise_select=0):
        """
        Returns an embed inspired by (cloned from) @CMDR Suiseiseki's b.tally. Provided to keep things in one place
        is all.

        :param SlashContext ctx: The discord context
        :param int cruise_select: The cruise you want data on, counts backwards. 0 is this cruise, 1 is the last
            cruise etc...
        :return: None
        """
        await self.report_invalid_carriers(self._update_db())
        cruise = 'this' if cruise_select == 0 else f'-{cruise_select}'
        print(f'User {ctx.author} requested the current tally of the cruise stats for {cruise} cruise.')
        target_date = None

        if cruise_select == 0:
            # Go get everything out of the database
            pirate_steve_db.execute(
                "SELECT * FROM boozecarriers"
            )
            all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
            pirate_steve_db.execute(
                "SELECT * FROM boozecarriers WHERE runtotal > 1"
            )

        else:
            # Get the dates in the DB and order them.
            pirate_steve_db.execute(
                "SELECT DISTINCT holiday_start FROM historical ORDER by holiday_start DESC"
            )
            all_dates = [dict(value) for value in pirate_steve_db.fetchall()]

            if cruise_select > len(all_dates):
                print('Input for cruise value was out of bounds for the number of cruises recorded in the database.')
                return await ctx.send(f'Pirate Steve only knows about the last: {len(all_dates)} booze cruises. '
                                      f'You wanted the -{cruise_select} data.')
            # Subtract 1 here, we filter the values out of the historical database, so the current cruise is not
            # there yet
            target_date = all_dates[cruise_select - 1]['holiday_start']
            print(f'We have found the following historical cruise dates: {all_dates}')
            print(f'We are interested in the {cruise} option - {target_date}')

            data = (
                target_date,
            )
            # In this case we want the historical data from the historical database
            pirate_steve_db.execute(
                "SELECT * FROM historical WHERE holiday_start = (?)", data
            )
            all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
            pirate_steve_db.execute(
                "SELECT * FROM historical WHERE runtotal > 1 AND holiday_start = (?)", data
            )

        total_carriers_multiple_trips = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
        stat_embed = self.build_stat_embed(all_carrier_data, total_carriers_multiple_trips, target_date)

        await ctx.send(embed=stat_embed)

        # Go update all the pinned embeds also.
        pirate_steve_db.execute(
            """SELECT * FROM pinned_messages"""
        )
        pins = [dict(value) for value in pirate_steve_db.fetchall()]
        if pins:
            print(f'Updating pinned messages: {pins}')
            for pin in pins:
                channel = await bot.fetch_channel(pin['channel_id'])
                print(f'Channel matched as: {channel} from {pin["channel_id"]}')
                # Now go loop over every pin and update it
                message = await channel.fetch_message(pin['message_id'])
                print(f'Message matched as: {message} from {pin["message_id"]}')
                await message.edit(embed=stat_embed)
        else:
            print('No pinned messages up update')

    def build_stat_embed(self, all_carrier_data, total_carriers_multiple_trips, target_date=None):
        """
        Builds the stat embed

        :param [BoozeCarriers] all_carrier_data: The list of all carriers
        :param [BoozeCarriers] total_carriers_multiple_trips: The list of all carriers making multiple trips
        :param str target_date: the target date
        :return: the built embed object
        :rtype: discord.Embed
        """
        print(f'Carriers with multiple trips: {len(total_carriers_multiple_trips)}.')

        extra_carrier_count = sum(carrier.run_count - 1 for carrier in total_carriers_multiple_trips)

        unique_carrier_count = len(all_carrier_data)
        total_carriers_inc_multiple_trips = unique_carrier_count + extra_carrier_count

        total_wine = sum(carrier.wine_total for carrier in all_carrier_data) if all_carrier_data else 0

        wine_per_capita = (total_wine / RACKHAMS_PEAK_POP) if total_wine else 0
        wine_per_carrier = (total_wine / unique_carrier_count) if total_wine else 0
        python_loads = (total_wine / 280) if total_wine else 0

        total_profit = total_wine * BOOZE_PROFIT_PER_TONNE_WINE

        fleet_carrier_buy_count = (total_profit / 5000000000) if total_profit else 0

        print(f'Carrier Count: {unique_carrier_count} - Total Wine: {total_wine:,} - Total Profit: {total_profit:,} - '
              f'Wine/Carrier: {wine_per_carrier:,.2f} - PythonLoads: {python_loads:,.2f} - '
              f'Wine/Capita: {wine_per_capita:,.2f} - Carrier Buys: {fleet_carrier_buy_count:,.2f}')

        if total_wine > 3000000:
            flavour_text = 'Shiver Me Timbers! This sea dog cannot fathom this much grog!'
        elif total_wine > 2500000:
            flavour_text = 'Sink me! We might send them to Davy Jone`s locker.'
        elif total_wine > 2000000:
            flavour_text = 'Blimey! Pieces of eight all round! We have a lot of grog. Savvy?'
        elif total_wine > 1500000:
            flavour_text = 'The coffers are looking better, get the Galley\'s filled with wine!'
        elif total_wine > 1000000:
            flavour_text = 'Yo ho ho we have some grog!'
        else:
            flavour_text = 'Heave Ho ye Scurvy Dog\'s! Pirate Steve wants more grog!'

        date_text = f':\nHistorical Data: [{target_date} - ' \
                    f'{datetime.strptime(target_date, "%Y-%m-%d").date() + timedelta(days=2)}]' \
            if target_date else ''

        # Build the embed
        stat_embed = discord.Embed(
            title=f"Pirate Steve's Booze Cruise Tally {date_text}",
            description=f'**Total # of Carrier trips:** — {total_carriers_inc_multiple_trips:>1}\n'
                        f'**# of unique Carriers:** — {unique_carrier_count:>24}\n'
                        f'**Profit per ton:** — {BOOZE_PROFIT_PER_TONNE_WINE:>56,}\n'
                        f'**Rackham Pop:** — {RACKHAMS_PEAK_POP:>56,}\n'
                        f'**Wine per capita:** — {wine_per_capita:>56,.2f}\n'
                        f'**Wine per carrier:** — {math.ceil(wine_per_carrier):>56,}\n'
                        f'**Python Loads (280t):** — {math.ceil(python_loads):>56,}\n\n'
                        f'**Total Wine:** — {total_wine:,}\n'
                        f'**Total Profit:** — {total_profit:,}\n\n'
                        f'**# of Fleet Carriers that profit can buy:** — {fleet_carrier_buy_count:,.2f}\n\n'
                        f'{flavour_text}\n\n'
                        f'[Bringing wine? Sign up here]({self.loader_signup_form_url})'
        )
        stat_embed.set_image(
            url='https://cdn.discordapp.com/attachments/783783142737182724/849157248923992085/unknown.png'
        )
        stat_embed.set_footer(text='This function is a clone of b.tally from CMDR Suiseiseki.\nPirate Steve hopes the '
                                   'values match!')

        print('Returning embed to user')
        return stat_embed

    @cog_ext.cog_slash(
        name="booze_pin_message",
        guild_ids=[bot_guild_id()],
        description="Pins a message and records its values into the database. Restricted to Admin and Sommelier's.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
        options=[
            create_option(
                name='message_id',
                description='The message ID to be pinned.',
                option_type=3,
                required=True
            ),
            create_option(
                name='channel_id',
                description='The channel ID to be pinned.',
                option_type=3,
                required=False
            )
        ],
    )
    async def pin_message(self, ctx: SlashContext, message_id, channel_id=None):
        """
        Pins the message in the channel.

        :param SlashContext ctx: The discord slash context
        :param str message_id: The message ID to pin
        :param str channel_id: The channel ID. Optional, if Not provided uses the current channel.
        :returns: None
        """
        print(f'User {ctx.author} wants to pin the message {message_id} in channel: {channel_id} - {type(channel_id)}')
        if not channel_id:
            print(f'No channel ID provided - use the current channel {ctx.channel.id}')
            channel = ctx.channel
            channel_id = channel.id
        else:
            channel = bot.get_channel(int(channel_id))
            print(f'Channel is: {channel}')

        message = await channel.fetch_message(int(message_id))
        if not message:
            print(f'Could not find a message for the ID: {message_id} in channel: {channel_id}')
            return ctx.send(f'Could not find a message for the ID: {message_id} in channel: {channel_id} - '
                            f'Check they are correct', hidden=True)
        data = (
            message_id,
            channel_id,
        )
        try:
            print('Writing to the DB the message data')
            pirate_steve_lock.acquire()
            pirate_steve_db.execute(
                """INSERT INTO pinned_messages VALUES(NULL, ?, ?)""", data
            )
            pirate_steve_conn.commit()
        finally:
            pirate_steve_lock.release()

        if not message.pinned:
            print('Message is not pinned - do it now')
            await message.pin(reason=f'Pirate Steve pinned on behalf of {ctx.author}')
            print(f'Message {message_id} was pinned.')
        else:
            print('Message is already pinned, no action needed')

        await ctx.send(f'Pirate steve recorded message: {message_id} in channel: {channel_id} for pinned updating')

    @cog_ext.cog_slash(
        name="booze_unpin_all",
        guild_ids=[bot_guild_id()],
        description="Unpins all messages for booze stats and updates the DB. Restricted to Admin and Sommelier's.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        }
    )
    async def clear_all_pinned_message(self, ctx: SlashContext):
        """
        Clears all the pinned messages

        :param SlashContext ctx: The discord slash context
        :returns: None
        """
        print(f'User {ctx.author} requested to clear the pinned messages.')

        pirate_steve_db.execute(
            "SELECT * FROM pinned_messages"
        )
        # Get everything
        all_pins = [dict(value) for value in pirate_steve_db.fetchall()]
        if all_pins:
            for pin in all_pins:
                channel = bot.get_channel(int(pin['channel_id']))
                message = await channel.fetch_message(pin['message_id'])
                await message.unpin(reason=f'Pirate Steve unpinned at the request of: {ctx.author}')
                print(f'Removed pinned message: {pin["message_id"]}.')
            try:
                print('Writing to the DB the message data to clear the pins')
                pirate_steve_lock.acquire()
                pirate_steve_db.execute(
                    """DELETE FROM pinned_messages""",
                )
                pirate_steve_conn.commit()
                print('Pinned messages removed')
            finally:
                pirate_steve_lock.release()
            print('Pinned messages removed')
            await ctx.send('Pirate Steve removed all the pinned stat messages', hidden=True)
        else:
            await ctx.send('Pirate Steve has no pinned messages to remove.', hidden=True)

    @cog_ext.cog_slash(
        name="booze_unpin_message",
        guild_ids=[bot_guild_id()],
        description="Unpins a specific message and removes it from the DB. Restricted to Admin and "
                    "Sommelier's.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        },
        options=[
            create_option(
                name='message_id',
                description='The message ID to be pinned.',
                option_type=3,
                required=True
            )
        ]
    )
    async def booze_unpin_message(self, ctx: SlashContext, message_id: str):
        """
        Clears the pinned embed described by the message_id string.

        :param SlashContext ctx: The discord slash context
        :param str message_id: The message ID to unpin
        :returns: None
        """
        print(f'User {ctx.author} requested to clear the pinned message {message_id}.')

        pirate_steve_db.execute(
            "SELECT * FROM pinned_messages WHERE "
        )
        # Get everything
        all_pins = [dict(value) for value in pirate_steve_db.fetchall()]
        if all_pins:
            for pin in all_pins:
                channel = bot.get_channel(int(pin['channel_id']))
                message = await channel.fetch_message(pin['message_id'])
                await message.unpin(reason=f'Pirate Steve unpinned at the request of: {ctx.author}')
                print(f'Removed pinned message: {pin["message_id"]}.')
            try:
                print('Writing to the DB the message data to clear the pins')
                pirate_steve_lock.acquire()
                pirate_steve_db.execute(
                    """DELETE FROM pinned_messages""",
                )
                pirate_steve_conn.commit()
                print('Pinned messages removed')
            finally:
                pirate_steve_lock.release()
            print('Pinned messages removed')
            await ctx.send(f'Pirate Steve removed the pinned stat message for {message_id}', hidden=True)
        else:
            await ctx.send(f'Pirate Steve has no pinned messages matching {message_id}.', hidden=True)

    @tasks.loop(hours=1)
    async def periodic_stat_update(self):
        """
        Loops every hour and updates all pinned embeds.

        :returns: None
        """
        # Periodic trigger that updates all the stat embeds that are pinned.
        print('Period trigger of the embed update.')
        pirate_steve_db.execute(
            "SELECT * FROM pinned_messages"
        )
        # Get everything
        all_pins = [dict(value) for value in pirate_steve_db.fetchall()]
        if all_pins:
            print(f'We have these pins to update: {all_pins}')
            for pin in all_pins:
                channel = bot.get_channel(int(pin['channel_id']))
                message = await channel.fetch_message(pin['message_id'])
                pirate_steve_db.execute(
                    "SELECT * FROM boozecarriers"
                )
                all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
                pirate_steve_db.execute(
                    "SELECT * FROM boozecarriers WHERE runtotal > 1"
                )
                total_carriers_multiple_trips = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
                stat_embed = self.build_stat_embed(all_carrier_data, total_carriers_multiple_trips, None)
                await message.edit(embed=stat_embed)
        else:
            print('No pinned messages to update. Check again in an hour.')

    @cog_ext.cog_slash(
        name="booze_tally_extra_stats",
        guild_ids=[bot_guild_id()],
        description="Returns an set of extra stats for the wine. Restricted to Admin and Sommelier's.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        }
    )
    async def extended_tally_stats(self, ctx: SlashContext):
        """
        Prints an extended tally stats as requested by RandomGazz.

        :param SlashContext ctx: The discord slash Context
        :return: None
        """
        await self.report_invalid_carriers(self._update_db())
        print(f'User {ctx.author} requested the current extended stats of the cruise.')

        # Go get everything out of the database
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers"
        )
        all_carrier_data = ([BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()])
        total_wine = sum(carrier.wine_total for carrier in all_carrier_data)

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
        wine_bottles_per_us_pop = wine_bottles_total / usa_population
        wine_boxes_per_us_pop = wine_boxes_total / usa_population

        scotland_population = 5454000
        wine_bottles_per_scot_pop = wine_bottles_total / scotland_population
        wine_boxes_per_scot_pop = wine_boxes_total / scotland_population

        olympic_swimming_pool_volume = 2500000
        pools_if_bottles = wine_bottles_litres_total / olympic_swimming_pool_volume
        pools_if_boxes = wine_boxes_litres_total / olympic_swimming_pool_volume

        london_bus_volume_l = 112.5 * 1000
        busses_if_bottles = wine_bottles_litres_total / london_bus_volume_l
        busses_if_boxes = wine_boxes_litres_total / london_bus_volume_l

        stat_embed = discord.Embed(
            title='Pirate Steve\'s Extended Booze Comparison Stats',
            description=f'Current Wine Tonnes: {total_wine:,}\n'
                        f'Wine per capita (Rackhams): {total_wine_per_capita:,.2f}\n\n'
                        f'Weight of 1 750ml bottle (kg): {wine_bottles_weight_kg}\n'
                        f'Wine Bottles per Tonne: {wine_bottles_per_tonne}\n'
                        f'Wine Bottles Litres per Tonne: {wine_bottles_litres_per_tonne}\n'
                        f'Wine Bottles Total: {wine_bottles_total:,}\n'
                        f'Wine Bottles Litres Total: {wine_bottles_litres_total:,.2f}\n'
                        f'Wine Bottles per capita (Rackhams): {wine_bottles_per_capita:,.2f}\n'
                        f'Wine Bottles Litres per capita (Rackhams): {wine_bottles_litres_per_capita:,.2f}\n\n'
                        f'Weight of box wine 2.25L (kg): {wine_box_weight_kg:,.2f}\n'
                        f'Wine Boxes per Tonne: {wine_boxes_per_tonne:,.2f}\n'
                        f'Wine Boxes Litre per Tonne: {wine_boxes_litres_per_tonne:,.2f}\n'
                        f'Wine Boxes Total: {wine_boxes_total:,.2f}\n'
                        f'Wine Boxes per capita (Rackhams): {wine_boxes_per_capita:,.2f}\n'
                        f'Wine Boxes Litres per capita (Rackhams): {wine_boxes_litres_per_capita:,.2f}\n\n'
                        f'USA Population: {usa_population:,}\n'
                        f'Wine Bottles per capita (:flag_us:): {wine_bottles_per_us_pop:,.2f}\n'
                        f'Wine Boxes per capita (:flag_us:): {wine_boxes_per_us_pop:,.2f}\n\n'
                        f'Scotland Population: {scotland_population:,}\n'
                        f'Wine Bottles per capita (🏴󠁧󠁢󠁳󠁣󠁴󠁿): {wine_bottles_per_scot_pop:,.2f}\n'
                        f'Wine Boxes per capita (🏴󠁧󠁢󠁳󠁣󠁴󠁿): {wine_boxes_per_scot_pop:,.2f}\n\n'
                        f'Olympic Swimming Pool Volume (L): {olympic_swimming_pool_volume:,}\n'
                        f'Olympic Swimming Pools if Bottles of Wine: {pools_if_bottles:,.2f}\n'
                        f'Olympic Swimming Pools if Boxes of Wine: {pools_if_boxes:,.2f}\n\n'
                        f'London Bus Volume (L): {london_bus_volume_l:,}\n'
                        f'London Busses if Bottles of Wine: {busses_if_bottles:,.2f}\n'
                        f'London Busses if Boxes of Wine: {busses_if_boxes:,.2f}\n\n'
        )
        stat_embed.set_footer(text='Stats requested by RandomGazz.\nPirate Steve approves of these stats!')
        await ctx.send(embed=stat_embed)

    @cog_ext.cog_slash(
        name="booze_delete_carrier",
        guild_ids=[bot_guild_id()],
        description="Removes a carrier from the database. Admin/Sommelier required.",
        options=[
            create_option(
                name='carrier_id',
                description='The XXX-XXX ID string for the carrier',
                option_type=3,
                required=True
            )
        ],
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_sommelier_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(server_mod_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        }
    )
    async def remove_carrier(self, ctx: SlashContext, carrier_id: str):
        """
        Removes a carrier entry from the database after confirmation.

        :param SlashContext ctx: The discord slash context.
        :param str carrier_id: The XXX-XXX carrier ID.
        :returns: None
        """
        print(f'User {ctx.author} wants to remove the carrier with ID {carrier_id} from the database.')
        # Cast this to upper case just in case
        carrier_id = carrier_id.upper()

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            print(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')
            return await ctx.channel.send(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, '
                                          f'{carrier_id}.')

        # Check if it is in the database already
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid = (?)", (f'{carrier_id}',)
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = BoozeCarrier(pirate_steve_db.fetchone())
        print(f'Found: {carrier_data}')

        if not carrier_data:
            print(f'No carrier found for: {carrier_id}')
            return await ctx.send(f'Avast Ye! No carrier found for: {carrier_id}')

        carrier_embed = discord.Embed(
            title=f'YARR! Pirate Steve found these details for the input: {carrier_id}',
            description=f'CarrierName: **{carrier_data.carrier_name}**\n'
                        f'ID: **{carrier_data.carrier_identifier}**\n'
                        f'Total Tonnes of Wine: **{carrier_data.wine_total}** on **{carrier_data.platform}**\n'
                        f'Number of trips to the peak: **{carrier_data.run_count}**\n'
                        f'Total Unloads: **{carrier_data.total_unloads}**\n'
                        f'PTN Official: {carrier_data.ptn_carrier}\n'
                        f'Operated by: {carrier_data.discord_username}'
        )
        carrier_embed.set_footer(text='Confirm you want to delete: y/n')

        def check(check_message):
            return check_message.author == ctx.author and check_message.channel == ctx.channel and \
                   check_message.content.lower() in ["y", "n"]

        # Send the embed
        message = await ctx.send(embed=carrier_embed)

        try:
            response = await bot.wait_for("message", check=check, timeout=30)
            if response.content.lower() == "n":
                await message.delete()
                await response.delete()
                print(f'User {ctx.author} aborted the request delete carrier {carrier_id}.')
                return await ctx.send(f"Avast Ye! you cancelled the action for deleting {carrier_id}.")

            elif response.content.lower() == "y":
                try:
                    await message.delete()
                    await response.delete()
                    print(f'User {ctx.author} agreed to delete the carrier: {carrier_id}.')

                    # Go update the object in the database.
                    try:
                        pirate_steve_lock.acquire()
                        print(f'Removing the entry ({carrier_id}) from the database.')
                        pirate_steve_db.execute(
                            ''' 
                            DELETE FROM boozecarriers 
                            WHERE carrierid LIKE (?) 
                            ''', (f'%{carrier_id}%',)
                        )
                        pirate_steve_conn.commit()
                        dump_database()
                        print(f'Carrier ({carrier_id}) was removed from the database')
                    finally:
                        pirate_steve_lock.release()

                    return await ctx.send(f'Fleet carrier: {carrier_id} for user: {carrier_data.discord_username} was removed')
                except Exception as e:
                    return ctx.send(f'Something went wrong, go tell the bot team "computer said: {e}"')

        except asyncio.TimeoutError:
            await message.delete()
            return await ctx.send("**Cancelled - timed out**")

        await message.delete()

    @cog_ext.cog_slash(
        name="booze_archive_database",
        guild_ids=[bot_guild_id()],
        description="Archives the boozedatabase. Admin/Sommelier required.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        }
    )
    async def archive_database(self, ctx: SlashContext):
        """
        Performs the steps to archive the current booze cruise database. Only possible if we are not in a PH
        currently and if the data has not been archived. Once archived it will be dropped.

        :param SlashContext ctx: The discord slash context.
        :returns: None
        """
        print(f'User {ctx.author} requested to archive the database')

        if ph_check():
            return await ctx.send('Pirate Steve thinks there is a party at Rackhams still. Try again once the grog '
                                  'runs dry.')
        get_date_user = await ctx.send('Pirate Steve wants to know when the booze cruise started in DD-MM-YY '
                                       'format.')

        def check_yes_no(check_message):
            return check_message.author == ctx.author and check_message.channel == ctx.channel and \
                   check_message.content.lower() in ["y", "n"]

        def check_date(check_message):
            return check_message.author == ctx.author and check_message.channel == ctx.channel and \
                   re.match(r'\d{2}-\d{2}-\d{2}', check_message.content)

        resp_date = None

        try:
            response = await bot.wait_for("message", check=check_date, timeout=30)
            if response:
                print(f'User response to date is: {response.content}')

                resp_date = datetime.strptime(response.content, '%d-%m-%y').date()
                today = datetime.now().date()

                if resp_date > today:
                    return await ctx.send('Pirate steve cant set the holiday date in the future, '
                                          f'format is DD-MM-YY. Your date input: {response.content}.')

                print(f'Formatted user response to date: {resp_date}')

        except asyncio.TimeoutError:
            await get_date_user.delete()
            return await ctx.send("**Waiting for date - timed out**")

        await get_date_user.delete()
        await response.delete()

        data = (
            resp_date,
        )
        # Check the date exists in the DB already, if so abort.
        pirate_steve_db.execute(
            "SELECT DISTINCT holiday_start FROM historical WHERE holiday_start = (?)", data
        )
        if pirate_steve_db.fetchall():
            print(f'We have a record for this date ({resp_date}) in the historical DB already.')
            # We found something for that date. stop.
            return await ctx.send(f'Pirate Steve thinks there is a booze cruise on that day ({resp_date}) '
                                  f'already recorded. Check your data, and send him for a memory check up.')

        check_embed = discord.Embed(
            title='Validate the request',
            description='You have requested to archive the data in the database with the following:\n'
                        f'**Holiday Start:** {resp_date.strftime("%d-%m-%y")} - '
                        f'**Holiday End:** {(resp_date + timedelta(days=2)).strftime("%d-%m-%y")}'
        )
        check_embed.set_footer(text='Respond with y/n.')
        sent_embed = await ctx.send(embed=check_embed)

        try:
            user_response = await bot.wait_for("message", check=check_yes_no, timeout=30)
            if user_response.content.lower() == "y":
                print(f'User response to date is: {user_response.content}')
                await user_response.delete()
                await sent_embed.delete()

                try:
                    pirate_steve_lock.acquire()
                    start_date = resp_date
                    end_date = resp_date + timedelta(days=2)
                    data = (
                        start_date,
                        end_date,
                    )
                    pirate_steve_db.execute('''
                              INSERT INTO historical (carriername, carrierid, winetotal, platform, 
                              officialcarrier, discordusername, timestamp, runtotal, totalunloads)
                              SELECT carriername, carrierid, winetotal, platform, officialcarrier, discordusername, 
                              timestamp, runtotal, totalunloads
                              FROM boozecarriers
                          ''')
                    # Now that we copied the columns, go update the timestamps for the cruise. This probably could
                    # be chained into the above statement, but effort to figure the syntax out.
                    pirate_steve_db.execute('''
                              UPDATE historical
                              SET holiday_start=?, holiday_end=?
                              WHERE holiday_start IS NULL
                          ''', data)
                    pirate_steve_conn.commit()

                    print('Removing the values from the current table.')
                    pirate_steve_db.execute('''
                        DELETE FROM boozecarriers
                    ''')
                    pirate_steve_conn.commit()
                    dump_database()
                    # Disable the updates after we commit the changes!
                    self.update_allowed = False
                finally:
                    pirate_steve_lock.release()
                return await ctx.send(f'Pirate Steve rejigged his memory and saved the booze data starting '
                                      f'on: {resp_date}!')
            elif user_response.content.lower() == "n":
                print(f'User {ctx.author} wants to abort the archive process.')
                await user_response.delete()
                await sent_embed.delete()
                return await ctx.send('You aborted the request to archive the data.')

        except asyncio.TimeoutError:
            await sent_embed.delete()
            return await ctx.send("**Waiting for user response - timed out**")

    @cog_ext.cog_slash(
        name="booze_configure_signup_forms",
        guild_ids=[bot_guild_id()],
        description="Updates the booze cruise signup forms. Admin/Sommelier required.",
        permissions={
            bot_guild_id(): [
                create_permission(server_admin_role_id(), SlashCommandPermissionType.ROLE, True),
                create_permission(bot_guild_id(), SlashCommandPermissionType.ROLE, False),
            ]
        }
    )
    async def configure_signup_forms(self, ctx: SlashContext):
        """
        Reconfigures the signup sheet and the tracking sheet to the new forms. Only usable by an admin.

        :param SlashContext ctx: The discord slash context.
        :returns: None
        """
        print(f'{ctx.author} wants to reconfigure the booze cruise signup forms.')

        # Store the current states just in case we need them
        original_sheet_id = self.worksheet_with_data_id
        original_worksheet_key = self.worksheet_key
        original_loader_signup_form = self.loader_signup_form_url

        # track the init value, we reset to this in case of bail out
        init_update_value = self.update_allowed
        self.update_allowed = False
        new_sheet_id = None
        new_worksheet_key = None
        new_loader_signup_form = None

        def check_yes_no(check_message):
            return check_message.author == ctx.author and check_message.channel == ctx.channel and \
                   check_message.content.lower() in ["y", "n"]

        def check_author(check_message):
            return check_message.author == ctx.author and check_message.channel == ctx.channel

        def check_id(check_message):
            return check_message.author == ctx.author and check_message.channel == ctx.channel and \
                   re.match(r'^\d*$', check_message.content)

        # TODO: See if we can add a validation for the URL

        # Check the dB is empty first.
        pirate_steve_db.execute(
            "SELECT * FROM boozecarriers"
        )
        all_carrier_data = [BoozeCarrier(carrier) for carrier in pirate_steve_db.fetchall()]
        if all_carrier_data:
            # archive the database first else we will end up in issues
            return await ctx.send('Pirate Steve has data already for a cruise - go fix his memory by running the '
                                  'archive command first.')

        request_loader_signup_form = await ctx.send('Pirate Steve first wants the loader signup form URL.')
        try:
            # in this case we do not know the shape of the URL
            response = await bot.wait_for("message", check=check_author, timeout=30)
            if response:
                print(f'We have data: {response.content} for the signup URL.')
                new_loader_signup_form = response.content
                await response.delete()
                await request_loader_signup_form.delete()

        except asyncio.TimeoutError:
            self.update_allowed = True
            print('Error getting the response for the google signup form.')
            await request_loader_signup_form.delete()
            return await ctx.send('Pirate Steve saw you timed out.')

        request_new_worksheet_key = await ctx.send('Pirate Steve secondly wants the sheet ID for the form. Start '
                                                   'counting from 1 and Pirate Steve will tell the computer '
                                                   'accordingly.')
        try:
            response = await bot.wait_for("message", check=check_id, timeout=30)
            if response:
                print(f'We have data: {response.content} for the worksheet ID.')
                try:
                    # user counts 1, 2, 3. Computer 0, 1, 2
                    new_sheet_id = int(response.content) - 1
                    if new_sheet_id < 0:
                        raise ValueError('Error ID is less than 0')
                except ValueError:
                    self.update_allowed = init_update_value
                    await request_new_worksheet_key.delete()
                    await response.delete()
                    return await ctx.send(f'Pirate Steve thinks you do not know what an integer starting from 1 is.'
                                          f' {response.content}. Start again!')

        except asyncio.TimeoutError:
            print('Error getting the response for the worksheet key.')
            await request_new_worksheet_key.delete()
            self.update_allowed = True
            return await ctx.send('Pirate Steve saw you timed out on step 2.')

        request_worksheet_id = await ctx.send('Pirate Steve thirdly wants to know the key for the data. The Key is '
                                              'the long unique string in the URL.')
        try:
            # in this case we do not know the shape of the worksheet Key, it is a unique value.
            response = await bot.wait_for("message", check=check_author, timeout=30)
            if response:
                print(f'We have data: {response.content} for the worksheet unique key.')
                new_worksheet_key = response.content
                await response.delete()
                await request_worksheet_id.delete()

        except asyncio.TimeoutError:
            print('Error getting the response for the worksheet key.')
            await request_worksheet_id.delete()
            self.update_allowed = init_update_value
            return await ctx.send('Pirate Steve saw you timed out on step 3.')

        print(f'We received valid data for all points, confirm them with the {ctx.author} it is correct.')

        confirm_embed = discord.Embed(
            title='Pirate Steve wants you to confirm the new values.',
            description=f'**New signup URL:** {new_loader_signup_form}\n'
                        f'**New worksheet key:** {new_worksheet_key}\n'
                        f'**New worksheet ID:** {new_sheet_id + 1}.',
        )
        confirm_embed.set_footer(text='Confirm this with y/n.')

        confirm_details = await ctx.send(embed=confirm_embed)

        try:
            user_response = await bot.wait_for("message", check=check_yes_no, timeout=30)
            if user_response.content.lower() == "y":
                print(f'{ctx.author} confirms to write the database now.')
                await user_response.delete()
                await confirm_details.delete()

                try:
                    pirate_steve_lock.acquire()

                    data = (
                        new_worksheet_key,
                        new_loader_signup_form,
                        new_sheet_id,
                    )
                    pirate_steve_db.execute('''
                        UPDATE trackingforms 
                        SET worksheet_key=?, loader_input_form_url=?, worksheet_with_data_id=?
                      ''', data)

                    pirate_steve_conn.commit()
                    dump_database()
                finally:
                    pirate_steve_lock.release()

                self.worksheet_key = new_worksheet_key
                self.worksheet_with_data_id = new_sheet_id
                self.loader_signup_form_url = new_loader_signup_form
                self.update_allowed = True
                try:

                    # Now go make the new updates to pull the data initially
                    self._reconfigure_workbook_and_form()
                    self._update_db()

                except OSError as e:
                    self.update_allowed = init_update_value
                    return await ctx.send(f'Pirate steve reports an error while updating things: {e}. Fix it and try '
                                          f'again.')

                return await ctx.send('Pirate Steve unfurled out the sails and is now catching the wind with the new '
                                      'values! Try /update_booze_db to check progress.')

            elif user_response.content.lower() == "n":
                print(f'User {ctx.author} wants to abort the archive process.')
                await user_response.delete()
                await confirm_details.delete()
                self.update_allowed = init_update_value
                return await ctx.send('You aborted the request to update the forms.')

        except asyncio.TimeoutError:
            print('Error getting the response for the worksheet ID.')
            await confirm_details.delete()
            self.update_allowed = init_update_value
            return await ctx.send('Pirate Steve saw you timed out on step 3.')

