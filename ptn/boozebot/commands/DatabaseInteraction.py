import asyncio
import datetime
import math
import os.path
import re

import discord
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_permission, create_option, create_choice
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from discord.ext.commands import Cog

from ptn.boozebot.BoozeCarrier import BoozeCarrier
from ptn.boozebot.constants import bot_guild_id, bot, server_admin_role_id, server_sommelier_role_id, \
    BOOZE_PROFIT_PER_TONNE_WINE, RACKHAMS_PEAK_POP, server_mod_role_id, get_bot_control_channel, \
    get_sommelier_notification_channel
from ptn.boozebot.database.database import carrier_db, carriers_conn, dump_database, carrier_db_lock


class DatabaseInteraction(Cog):

    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

        if not os.path.join(os.path.expanduser('~'), '.ptnboozebot.json'):
            raise EnvironmentError('Cannot find the booze cruise json file.')

        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            os.path.join(os.path.expanduser('~'), '.ptnboozebot.json'), scope)

        # authorize the client sheet
        client = gspread.authorize(credentials)

        # The key is part of the URL
        workbook = client.open_by_key('1Etk2sZRKKV7LsDVNJ60qrzJs3ZE8Wa99KTv7r6bwgIw')

        for sheet in workbook.worksheets():
            print(sheet.title)

        self.tracking_sheet = workbook.get_worksheet(1)
        self._update_db()  # On instantiation, go build the DB

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
        print(f'User {ctx.author} requested to re-populate the database at {datetime.datetime.now()}')

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

        # We use this later to go find all the carriers in the database and ensure they match up and none were removed
        all_carrier_ids_sheet = [f'{carrier["carrier_id"]}' for carrier in carrier_count]

        print(all_carrier_ids_sheet)
        print(carrier_count)

        # First row is the headers, drop them.
        for record in records_data:
            # Iterate over the records and populate the database as required.

            # Check if it is in the database already
            carrier_db.execute(
                "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{record["Carrier ID"].upper()}%',)
            )
            carrier_data = [BoozeCarrier(carrier) for carrier in carrier_db.fetchall()]
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
                        carrier_db_lock.acquire()
                        carriers_conn.set_trace_callback(print)
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

                        carrier_db.execute(
                            ''' UPDATE boozecarriers 
                            SET carriername=?, carrierid=?, winetotal=?, platform=?, officialcarrier=?, 
                            discordusername=?, timestamp=?, runtotal=?
                            WHERE carriername LIKE (?) ''', data
                        )

                        carriers_conn.commit()
                    finally:
                        carrier_db_lock.release()
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
                    carrier_db_lock.acquire()
                    carrier_db.execute(''' 
                    INSERT INTO boozecarriers VALUES(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL) 
                    ''', (
                        carrier.carrier_name, carrier.carrier_identifier, carrier.wine_total,
                        carrier.platform, carrier.ptn_carrier, carrier.discord_username,
                        carrier.timestamp, carrier.run_count, carrier.total_unloads
                    )
                                       )
                finally:
                    carrier_db_lock.release()

                updated_db = True
                print('Added carrier to the database')

        print(all_carrier_ids_sheet)

        # Now that the records are updated, make sure no carrier was removed - check for anything not matching the
        # carrier id strings.
        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid NOT IN ({})".format(
                ', '.join('?' * len(all_carrier_ids_sheet))
            ), all_carrier_ids_sheet
        )

        invalid_datbase_entries = [BoozeCarrier(inv_carrier) for inv_carrier in carrier_db.fetchall()]
        if updated_db:
            # Write the database and then dump the updated SQL
            try:
                carrier_db_lock.acquire()
                carriers_conn.commit()
            finally:
                carrier_db_lock.release()
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
        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE runtotal > totalunloads"
        )
        carrier_data = [BoozeCarrier(carrier) for carrier in carrier_db.fetchall()]
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

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            print(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')
            return await ctx.channel.send(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, '
                                          f'{carrier_id}.')

        # Check if it is in the database already
        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{carrier_id}%',)
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = BoozeCarrier(carrier_db.fetchone())

        carrier_embed = discord.Embed(
            title=f'Argh We found this data for {carrier_id}:',
            description="y/n"
        )

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
                return await ctx.send(f"Arrgh you cancelled the action for marking {carrier_id} "
                                      f"as forcefully completed.")

            elif msg.content.lower() == "y":
                try:
                    await message.delete()
                    await msg.delete()
                    print(f'User {ctx.author} agreed to mark the carrier {carrier_id} as unloaded.')

                    # Go update the object in the database.
                    try:
                        carrier_db_lock.acquire()

                        data = (
                            f'%{carrier_data.carrier_identifier}%',
                        )
                        carrier_db.execute(
                            ''' 
                            UPDATE boozecarriers 
                            SET totalunloads=totalunloads+1
                            WHERE carrierid LIKE (?) 
                            ''', data
                        )
                        carriers_conn.commit()
                    finally:
                        carrier_db_lock.release()

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
                        name="PC",
                        value="PC"
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
        carrier_db.execute(
            f"SELECT * FROM boozecarriers WHERE {carrier_search}", data
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = [BoozeCarrier(carrier) for carrier in carrier_db.fetchall()]

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

        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            print(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')
            return await ctx.channel.send(
                f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')

        # Check if it is in the database already
        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid = (?)", (f'{carrier_id}',)
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = BoozeCarrier(carrier_db.fetchone())
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
        }
    )
    async def tally(self, ctx: SlashContext):
        """
        Returns an embed inspired by (cloned from) @CMDR Suiseiseki's b.tally. Provided to keep things in one place
        is all.

        :param SlashContext ctx: The discord context
        :return: None
        """
        await self.report_invalid_carriers(self._update_db())
        print(f'User {ctx.author} requested the current tally of the cruise stats.')

        # Go get everything out of the database
        carrier_db.execute(
            "SELECT * FROM boozecarriers"
        )
        all_carrier_data = [BoozeCarrier(carrier) for carrier in carrier_db.fetchall()]
        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE runtotal > 1"
        )
        total_carriers_multiple_trips = [BoozeCarrier(carrier) for carrier in carrier_db.fetchall()]
        print(f'Carriers with multiple trips: {len(total_carriers_multiple_trips)}.')

        extra_carrier_count = sum(carrier.run_count -1 for carrier in total_carriers_multiple_trips)

        unique_carrier_count = len(all_carrier_data)
        total_carriers_inc_multiple_trips = unique_carrier_count + extra_carrier_count

        total_wine = sum(carrier.wine_total for carrier in all_carrier_data)

        wine_per_capita = total_wine / RACKHAMS_PEAK_POP
        wine_per_carrier = total_wine / unique_carrier_count
        python_loads = total_wine / 280

        total_profit = total_wine * BOOZE_PROFIT_PER_TONNE_WINE

        fleet_carrier_buy_count = total_profit / 5000000000

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

        # Build the embed
        stat_embed = discord.Embed(
            title="Pirate Steve's Booze Cruise Tally",
            description=f'**Total # of Carrier trips:** — {total_carriers_inc_multiple_trips:>1}\n'
                        f'**# of unique Carriers:** — {unique_carrier_count:>24}\n'
                        f'**Profit per ton:** — {BOOZE_PROFIT_PER_TONNE_WINE:>56,}\n'
                        f'**Rackham Pop:** — {RACKHAMS_PEAK_POP:>56,}\n'
                        f'**Wine per capita:** — {wine_per_capita:>56,.2f}\n'
                        f'**Wine per carrier:** — {math.ceil(wine_per_carrier):>56,}\n'
                        f'**Python Loads (280t):** — {math.ceil(python_loads):>56,}\n\n'
                        f'**Total Wine:** — {total_wine:,}\n'
                        f'**Total Profit:** — {total_profit:,}\n\n'
                        f'**# of Fleet Carriers that profit can buy:** — {fleet_carrier_buy_count:,}\n\n'
                        f'{flavour_text}\n\n'
                        f'[Bringing wine? Sign up here](https://forms.gle/dWugae3M3i76NNVi7)'
        )
        stat_embed.set_image(
            url='https://cdn.discordapp.com/attachments/783783142737182724/849157248923992085/unknown.png'
        )
        stat_embed.set_footer(text='This function is a clone of b.tally from CMDR Suiseiseki.\nPirate Steve hopes the '
                                   'values match!')

        print('Returning embed to user')
        await ctx.send(embed=stat_embed)

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
        carrier_db.execute(
            "SELECT * FROM boozecarriers"
        )
        all_carrier_data = ([BoozeCarrier(carrier) for carrier in carrier_db.fetchall()])
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

        # Volume of the statue of liberty
        statue_liberty = 2500 * 1000
        statue_liberty_if_bottles = wine_bottles_litres_total / statue_liberty
        statue_liberty_if_boxes = wine_boxes_litres_total / statue_liberty

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
                        f'Statue of Liberty Volume (L): {statue_liberty:,}\n'
                        f'Statue of Liberty if Bottles of Wine: {statue_liberty_if_bottles:,.2f}\n'
                        f'Statue of Liberty if Boxes of Wine: {statue_liberty_if_boxes:,.2f}\n\n'
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
        # Check the carrier ID regex
        if not re.match(r"\w{3}-\w{3}", carrier_id):
            print(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, {carrier_id}.')
            return await ctx.channel.send(f'{ctx.author}, the carrier ID was invalid, XXX-XXX expected received, '
                                          f'{carrier_id}.')

        # Check if it is in the database already
        carrier_db.execute(
            "SELECT * FROM boozecarriers WHERE carrierid = (?)", (f'{carrier_id}',)
        )
        # Really only expect a single entry here, unique field and all that
        carrier_data = BoozeCarrier(carrier_db.fetchone())
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
                        carrier_db_lock.acquire()
                        print(f'Removing the entry ({carrier_id}) from the database.')
                        carrier_db.execute(
                            ''' 
                            DELETE FROM boozecarriers 
                            WHERE carrierid LIKE (?) 
                            ''', (f'%{carrier_id}%',)
                        )
                        carriers_conn.commit()
                        print(f'Carrier ({carrier_id}) was removed from the database')
                    finally:
                        carrier_db_lock.release()

                    return await ctx.send(f'Fleet carrier: {carrier_id} was removed')
                except Exception as e:
                    return ctx.send(f'Something went wrong, go tell the bot team "computer said: {e}"')

        except asyncio.TimeoutError:
            await message.delete()
            return await ctx.send("**Cancelled - timed out**")

        await message.delete()

