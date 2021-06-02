import datetime
import os.path

import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from discord.ext.commands import Cog

from ptn.boozebot.BoozeCarrier import BoozeCarrier
from ptn.boozebot.constants import bot_guild_id
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

        tracking_sheet = workbook.get_worksheet(1)

        # A JSON form tracking all the records
        self.records_data = tracking_sheet.get_all_records()

    @commands.has_any_role('Admin')
    @cog_ext.cog_slash(name="UpdateBoozeCruiseDatabase", guild_ids=[bot_guild_id()],
                       description="Populates the booze cruise database from the updated google sheet.")
    async def update_database_from_googlesheets(self, ctx: SlashContext):
        """
        Slash command for updating the database from the GoogleSheet.
        # TODO: This command itself should not be called by a user, this is provided only as a short-term solution
            for migration towards the actual commands.

        :returns: A discord embed to the user.
        :rtype: None
        """
        print(f'User {ctx.author} requested to re-populate the database at {datetime.datetime.now()}')

        updated_db = False
        added_count = 0
        updated_count = 0
        unchanged_count = 0
        total_carriers = len(self.records_data[1::])

        # First row is the headers, drop them.
        for record in self.records_data[1::]:
            # Iterate over the records and populate the database as required.

            # Check if it is in the database already
            carrier_db.execute(
                "SELECT * FROM boozecarriers WHERE carrierid LIKE (?)", (f'%{record["Carrier ID"]}%', )
            )
            carrier_data = [BoozeCarrier(carrier) for carrier in carrier_db.fetchall()]
            if len(carrier_data) > 1:
                raise ValueError(f'Two carriers are listed with this carrier ID: {record["Carrier ID"]}. Problem '
                                 f'in the sheet!')

            if carrier_data:
                # We have a carrier, just check the values and update it if needed.
                print(f'The carrier for {record["Carrier ID"]} exists, checking the values.')
                expected_carrier_data = BoozeCarrier(record)
                db_carrier_data = carrier_data[0]

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
                            f'%{db_carrier_data.carrier_name}%'
                        )

                        carrier_db.execute(
                            ''' UPDATE boozecarriers 
                            SET carriername=?, carrierid=?, winetotal=?, platform=?, officialcarrier=?, 
                            discordusername=?, timestamp=?
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
                    carrier_db.execute(''' INSERT INTO boozecarriers VALUES(NULL, ?, ?, ?, ?, ?, ?, ?) ''',
                                   (carrier.carrier_name, carrier.carrier_identifier, carrier.wine_total,
                                    carrier.platform, carrier.ptn_carrier, carrier.discord_username, carrier.timestamp)
                                   )
                finally:
                    carrier_db_lock.release()

                updated_db = True
                print('Added carrier to the database')

        if updated_db:
            # Write the database and then dump the updated SQL
            try:
                carrier_db_lock.acquire()
                carriers_conn.commit()
            finally:
                carrier_db_lock.release()
            dump_database()
            print('Wrote the database and dumped the SQL')
        updated_count = 100
        embed = discord.Embed(title="Pirate Steve's DB Update ran successfully.")
        embed.add_field(name=f'Total number of carriers: {total_carriers:>20}.\nNumber of new carriers added: '
                             f'{added_count:>8}.\nNumber of carriers amended: {updated_count:>11}.\nNumber of '
                             f'carriers unchanged: {unchanged_count:>7}.',
                        value='Pirate Steve hope he got this right.',
                        inline=False)

        return await ctx.send(embed=embed)
