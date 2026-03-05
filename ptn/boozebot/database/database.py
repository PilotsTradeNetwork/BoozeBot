import asyncio
import sqlite3
from asyncio import Lock
from datetime import datetime
from sqlite3 import Connection, Cursor
from typing import Literal
from warnings import deprecated

from ptn_utils.logger.logger import get_logger
from ptn.boozebot.classes.AutoResponse import AutoResponse
from ptn.boozebot.classes.CorkedUser import CorkedUser

from ptn.boozebot.constants import CARRIERS_DB_DUMPS_PATH, CARRIERS_DB_PATH

logger = get_logger("boozebot.database")
sql_logger = get_logger("boozebot.database.sql")


class Database:
    db: Cursor
    conn: Connection
    lock: Lock

    def __init__(self):
        logger.info(f"Starting database connection at: {CARRIERS_DB_PATH}")
        self.lock = asyncio.Lock()
        self.conn = sqlite3.connect(CARRIERS_DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.set_trace_callback(self._sql_trace_callback)
        self.db = self.conn.cursor()
        logger.info(f"Database initialized. SQL dumps will be stored at: {CARRIERS_DB_DUMPS_PATH}")

        self._build_database_on_startup()

    def _sql_trace_callback(self, statement: str) -> None:
        """
        SQL trace callback - logs all SQL statements at TRACE level via boozebot.database.sql logger

        :param str statement: The SQL statement being executed.
        """
        sql_logger.trace(f"SQL: {statement}")

    def dump_database(self):
        """
        Dumps the booze cruise carrier database into sql.

        :returns: None
        """

        logger.info(f"Dumping database to SQL file: {CARRIERS_DB_DUMPS_PATH}")

        line_count = 0
        with open(CARRIERS_DB_DUMPS_PATH, "w", encoding="utf-8") as f:
            for line in self.conn.iterdump():
                f.write(line)
                line_count += 1

        logger.info(f"Database dump completed. Wrote {line_count} lines to {CARRIERS_DB_DUMPS_PATH}")

    def _build_database_on_startup(self):
        """
        Builds or updates the database schema on startup.

        :returns: None
        """

        logger.info("Building or updating database schema.")

        table_schemas = {
            "holidaystate": {"entry": "INTEGER PRIMARY KEY AUTOINCREMENT", "state": "BOOL", "timestamp": "DATETIME"},
            "pinned_messages": {
                "entry": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "message_id": "TEXT UNIQUE",
                "channel_id": "TEXT UNIQUE",
            },
            "auto_responses": {
                "name": "TEXT PRIMARY KEY",
                "trigger": "TEXT NOT NULL",
                "is_regex": "BOOLEAN NOT NULL DEFAULT 0",
                "response": "TEXT NOT NULL",
            },
            "corked_users": {
                "entry": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "user_id": "TEXT UNIQUE",
                "timestamp": "DATETIME",
            },
            "carrier_messages": {
                "entry": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "carrier_id": "TEXT UNIQUE",
                "unload_id": "INT",
                "unload_notification_sent": "BOOL",
                "departure_id": "INT",
                "departure_notification_sent": "BOOL",
            },
        }

        # Iterate through each table schema and create or update the table
        for table_name, schema in table_schemas.items():
            logger.debug(f"Checking table: {table_name}")
            logger.trace(f"Expected schema for {table_name}: {schema}")

            # Create the table if it does not exist

            self.db.execute(
                f"""
                SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = '{table_name}'
            """
            )
            table_exists = bool(self.db.fetchone()[0])
            logger.trace(f"Table {table_name} exists: {table_exists}")

            if not table_exists:
                logger.debug(f"Table {table_name} does not exist. Creating table.")
                create_statement = f"CREATE TABLE {table_name} ({', '.join([f'{col} {col_type}' for col, col_type in schema.items()])})"
                self.db.execute(create_statement)
                self.conn.commit()
                logger.trace(f"Committed table creation for {table_name}.")
                logger.info(f"Table {table_name} created successfully.")
                continue

            else:
                logger.debug(f"Table {table_name} exists. Checking for missing or incorrect columns.")

                self.db.execute(f"""PRAGMA table_info ({table_name})""")
                result = [dict(col) for col in self.db.fetchall()]
                logger.trace(f"PRAGMA table_info result for {table_name}: {result}")
                # Get full column information including all attributes
                existing_columns = {}
                for element in result:
                    col_name = element["name"]
                    col_type = element["type"]
                    is_pk = element["pk"]
                    not_null = element["notnull"]
                    default_val = element["dflt_value"]

                    # Build full type specification
                    full_type = col_type
                    if is_pk:
                        full_type += " PRIMARY KEY"
                        if "AUTOINCREMENT" in schema.get(col_name, ""):
                            full_type += " AUTOINCREMENT"
                    if not_null and not is_pk:
                        full_type += " NOT NULL"
                    if default_val is not None:
                        full_type += f" DEFAULT {default_val}"
                    if "UNIQUE" in schema.get(col_name, ""):
                        full_type += " UNIQUE"

                    existing_columns[col_name] = full_type

                logger.trace(f"Existing columns in {table_name}: {existing_columns}")

                # Add any missing columns
                columns_added = 0
                for column_name, column_type in schema.items():
                    if column_name not in existing_columns:
                        logger.debug(f"Column {column_name} missing in table {table_name}. Adding column.")
                        alter_statement = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                        self.db.execute(alter_statement)
                        columns_added += 1
                        logger.info(f"Added column {column_name} to table {table_name}.")

                # Check for any incorrect column types
                for column_name, column_type in existing_columns.items():
                    if column_name in schema:
                        if column_type != schema[column_name]:
                            logger.error(
                                f"Column {column_name} in table {table_name} has type {column_type} but expected {schema[column_name]}"
                            )
                            raise EnvironmentError("Column type mismatch detected. Please check the database schema.")
                        else:
                            logger.trace(f"Column {column_name} in table {table_name} has correct type: {column_type}")

                if columns_added > 0:
                    logger.trace(f"Added {columns_added} column(s) to table {table_name}.")
                    self.conn.commit()
                    logger.trace(f"Committed schema changes for table {table_name}.")

        logger.info("Database schema check and update completed successfully. Checking for default values.")

        default_values = {
            "holidaystate": [{"state": 0, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}],
        }

        # Insert default values into tables if they're empty
        for table_name, records in default_values.items():
            logger.trace(f"Checking for default values in table: {table_name}")

            self.db.execute(f"SELECT COUNT(*) FROM {table_name}")
            record_count = self.db.fetchone()[0]
            logger.trace(f"Table {table_name} has {record_count} existing record(s).")

            if record_count == 0:
                logger.debug(f"Inserting default values into table: {table_name}")
                for idx, record in enumerate(records, 1):
                    columns = ", ".join(record.keys())
                    placeholders = ", ".join(["?" for _ in record])
                    values = tuple(record.values())
                    logger.trace(f"Inserting record {idx}/{len(records)} into {table_name}: {record}")
                    self.db.execute(
                        f"""
                        INSERT INTO {table_name} ({columns}) VALUES ({placeholders})
                    """,
                        values,
                    )
                self.conn.commit()
                logger.trace(f"Committed {len(records)} default record(s) to {table_name}.")
                logger.info(f"Inserted {len(records)} default record(s) into table: {table_name}")
            else:
                logger.trace(f"Table {table_name} already has data. Skipping default value insertion.")

    async def get_unload_message_for_carrier(self, carrier_id: str) -> int | None:
        """
        Fetches the unload message for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :returns: The discord message id or None if not found.
        """
        logger.debug(f"Fetching unload message for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute("SELECT unload_id FROM carrier_messages WHERE carrier_id = (?)", (f"{carrier_id}",))

            unload_id = self.db.fetchone()
        if not unload_id:
            logger.debug(f"No unload message found in database for carrier ID: {carrier_id}.")
            return None
        unload_id = unload_id[0]
        logger.debug(f"Found unload message ID {unload_id} for carrier ID: {carrier_id}")
        return unload_id

    async def get_carrier_for_unload_message(self, message_id: int) -> str | None:
        """
        Fetches the carrier ID for a given unload message ID.

        :param message_id: The discord message ID.
        :returns: The carrier ID string or None if not found.
        """
        logger.debug(f"Fetching carrier ID for unload message ID: {message_id}")

        async with self.lock:
            self.db.execute("SELECT carrier_id FROM carrier_messages WHERE unload_id = ?", (message_id,))

            carrier_id = self.db.fetchone()
        if not carrier_id:
            logger.debug(f"No carrier ID found in database for unload message ID: {message_id}.")
            return None
        carrier_id = carrier_id[0]
        logger.debug(f"Found carrier ID {carrier_id} for unload message ID: {message_id}")
        return carrier_id

    async def set_unload_message_for_carrier(self, carrier_id: str, message_id: int) -> None:
        """
        Sets the unload message ID for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :param message_id: The discord message ID.
        """
        logger.debug(f"Setting unload message ID {message_id} for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute(
                "INSERT INTO carrier_messages (carrier_id, unload_id) VALUES (?, ?) "
                + "ON CONFLICT(carrier_id) DO UPDATE SET unload_id = ?",
                (f"{carrier_id}", message_id, message_id),
            )
            self.conn.commit()
        logger.debug(f"Successfully set unload message ID {message_id} for carrier ID: {carrier_id}")

    async def get_unload_notification_sent(self, carrier_id: str) -> bool:
        """
        Gets the unload notification sent flag for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :returns: The unload notification sent flag.
        """
        logger.debug(f"Getting unload notification sent flag for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute(
                "SELECT unload_notification_sent FROM carrier_messages WHERE carrier_id = (?)", (f"{carrier_id}",)
            )

            result = self.db.fetchone()
        if not result:
            logger.debug(f"No carrier found in database for carrier ID: {carrier_id}.")
            return False
        result = result[0]
        logger.debug(f"Unload notification sent flag for carrier ID {carrier_id}: {result}")
        return result

    async def set_unload_notification_sent(self, carrier_id: str, notification_sent: bool) -> None:
        """
        Sets the unload notification sent flag for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :param notification_sent: The unload notification sent flag.
        """
        logger.debug(f"Setting unload notification sent flag to {notification_sent} for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute(
                "INSERT INTO carrier_messages (carrier_id, unload_notification_sent) VALUES (?, ?) "
                + "ON CONFLICT(carrier_id) DO UPDATE SET unload_notification_sent = ?",
                (f"{carrier_id}", notification_sent, notification_sent),
            )
            self.conn.commit()
        logger.debug(
            f"Successfully set unload notification sent flag to {notification_sent} for carrier ID: {carrier_id}"
        )

    async def get_departure_message_for_carrier(self, carrier_id: str) -> int | None:
        """
        Fetches the departure message for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :returns: The discord message id or None if not found.
        """
        logger.debug(f"Fetching departure message for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute("SELECT departure_id FROM carrier_messages WHERE carrier_id = (?)", (f"{carrier_id}",))

            departure_id = self.db.fetchone()
        if not departure_id:
            logger.debug(f"No departure message found in database for carrier ID: {carrier_id}.")
            return None
        departure_id = departure_id[0]
        logger.debug(f"Found departure message ID {departure_id} for carrier ID: {carrier_id}")
        return departure_id

    async def get_carrier_for_departure_message(self, message_id: int) -> str | None:
        """
        Fetches the carrier ID for a given departure message ID.

        :param message_id: The discord message ID.
        :returns: The carrier ID string or None if not found.
        """
        logger.debug(f"Fetching carrier ID for departure message ID: {message_id}")

        async with self.lock:
            self.db.execute("SELECT carrier_id FROM carrier_messages WHERE departure_id = ?", (message_id,))

            carrier_id = self.db.fetchone()
        if not carrier_id:
            logger.debug(f"No carrier ID found in database for departure message ID: {message_id}.")
            return None
        carrier_id = carrier_id[0]
        logger.debug(f"Found carrier ID {carrier_id} for departure message ID: {message_id}")
        return carrier_id

    async def set_departure_message_for_carrier(self, carrier_id: str, message_id: int) -> None:
        """
        Sets the departure message ID for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :param message_id: The discord message ID.
        """
        logger.debug(f"Setting departure message ID {message_id} for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute(
                "INSERT INTO carrier_messages (carrier_id, departure_id) VALUES (?, ?) "
                + "ON CONFLICT(carrier_id) DO UPDATE SET departure_id = ?",
                (f"{carrier_id}", message_id, message_id),
            )
            self.conn.commit()
        logger.debug(f"Successfully set departure message ID {message_id} for carrier ID: {carrier_id}")

    async def get_departure_notification_sent(self, carrier_id: str) -> bool:
        """
        Gets the departure notification sent flag for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :returns: The departure notification sent flag.
        """
        logger.debug(f"Getting departure notification sent flag for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute(
                "SELECT departure_notification_sent FROM carrier_messages WHERE carrier_id = (?)", (f"{carrier_id}",)
            )

            result = self.db.fetchone()
        if not result:
            logger.debug(f"No carrier found in database for carrier ID: {carrier_id}.")
            return False
        result = result[0]
        logger.debug(f"Departure notification sent flag for carrier ID {carrier_id}: {result}")
        return result

    async def set_departure_notification_sent(self, carrier_id: str, notification_sent: bool) -> None:
        """
        Sets the departure notification sent flag for a given carrier ID.

        :param carrier_id: The carrier ID string.
        :param notification_sent: The departure notification sent flag.
        """
        logger.debug(f"Setting departure notification sent flag to {notification_sent} for carrier ID: {carrier_id}")

        async with self.lock:
            self.db.execute(
                "INSERT INTO carrier_messages (carrier_id, departure_notification_sent) VALUES (?, ?) "
                + "ON CONFLICT(carrier_id) DO UPDATE SET departure_notification_sent = ?",
                (f"{carrier_id}", notification_sent, notification_sent),
            )
            self.conn.commit()
        logger.debug(
            f"Successfully set departure notification sent flag to {notification_sent} for carrier ID: {carrier_id}"
        )

    async def delete_carrier_message(self, carrier_id: str, message_type: Literal["unload", "departure"]) -> None:
        """
        Deletes a carrier message entry (unload or departure) for a given carrier ID.
        If both message types are cleared, the entire row is deleted.

        :param carrier_id: The carrier ID string.
        :param message_type: Either 'unload' or 'departure'.
        """
        if message_type not in ["unload", "departure"]:
            raise ValueError(f"Invalid message_type: {message_type}. Must be 'unload' or 'departure'.")

        logger.debug(f"Deleting {message_type} message entry for carrier ID: {carrier_id}")

        if message_type == "unload":
            fields = "unload_id = NULL, unload_notification_sent = NULL"
        else:  # departure
            fields = "departure_id = NULL, departure_notification_sent = NULL"

        async with self.lock:
            self.db.execute(f"UPDATE carrier_messages SET {fields} WHERE carrier_id = ?", (f"{carrier_id}",))
            # Clean up the row if both unload and departure are NULL
            self.db.execute(
                "DELETE FROM carrier_messages WHERE carrier_id = ? AND unload_id IS NULL AND departure_id IS NULL",
                (f"{carrier_id}",),
            )
            self.conn.commit()
        logger.debug(f"Successfully deleted {message_type} message entry for carrier ID: {carrier_id}")

    async def add_auto_response(self, name: str, trigger: str, response: str, is_regex: bool = False) -> None:
        """
        Adds an auto response to the database.

        :param name: The name of the auto response.
        :param trigger: The trigger text or regex.
        :param response: The response text.
        :param is_regex: Whether the trigger is a regex.
        """
        logger.debug(f"Adding auto response '{name}' with trigger '{trigger}' (is_regex={is_regex})")

        async with self.lock:
            self.db.execute(
                "INSERT INTO auto_responses (name, trigger, is_regex, response) VALUES (?, ?, ?, ?)",
                (name, trigger, is_regex, response),
            )
            self.conn.commit()
        logger.debug(f"Successfully added auto response '{name}'")

    async def get_auto_responses(self) -> list[AutoResponse]:
        """
        Retrieves all auto responses from the database.

        :returns: A list of auto response dictionaries.
        """
        logger.debug("Retrieving all auto responses from database")

        async with self.lock:
            self.db.execute("SELECT * FROM auto_responses")
            rows = self.db.fetchall()

        auto_responses = []
        for row in rows:
            auto_responses.append(AutoResponse(row))

        logger.debug(f"Retrieved {len(auto_responses)} auto response(s) from database")
        return auto_responses

    async def get_auto_response_by_name(self, name: str) -> AutoResponse | None:
        """
        Retrieves an auto response by name from the database.

        :param name: The name of the auto response.
        :returns: An AutoResponse object or None if not found.
        """
        logger.debug(f"Retrieving auto response by name: {name}")

        async with self.lock:
            self.db.execute("SELECT * FROM auto_responses WHERE name = ?", (name,))
            row = self.db.fetchone()

        if row is None:
            logger.debug(f"No auto response found with name: {name}")
            return None

        auto_response = AutoResponse(row)

        logger.debug(f"Found auto response '{name}' with trigger '{auto_response.trigger}'")
        return auto_response

    async def delete_auto_response(self, name: str) -> None:
        """
        Deletes an auto response from the database.

        :param str name: The name of the auto response to delete.
        """
        logger.debug(f"Deleting auto response: {name}")

        async with self.lock:
            self.db.execute("DELETE FROM auto_responses WHERE name = ?", (name,))
            self.conn.commit()
        logger.debug(f"Successfully deleted auto response: {name}")

    async def update_auto_response(self, name: str, new_trigger: str, new_response: str) -> None:
        """
        Updates an existing auto response in the database.

        :param name: The name of the auto response to update.
        :param new_trigger: The new trigger text or regex.
        :param new_response: The new response text.
        """
        logger.debug(f"Updating auto response '{name}' with new trigger '{new_trigger}'")

        async with self.lock:
            self.db.execute(
                "UPDATE auto_responses SET trigger = ?, response = ? WHERE name = ?",
                (new_trigger, new_response, name),
            )
            self.conn.commit()
        logger.debug(f"Successfully updated auto response: {name}")

    @deprecated(
        "This function is deprecated and will be removed in a future release. Use boozeSheetsApi.get_current_cruise_state() instead."
    )
    async def get_holiday_status(self) -> tuple[bool, datetime]:
        """
        Retrieves the current holiday status from the database.

        :returns: A tuple containing the holiday status (bool) and the timestamp (datetime).
        """
        logger.debug("Retrieving holiday status from database")

        async with self.lock:
            self.db.execute("SELECT state, timestamp FROM holidaystate ORDER BY entry DESC LIMIT 1")
            row = self.db.fetchone()

        if row is None:
            logger.error("No holiday state found in database.")
            raise ValueError("Holiday state not found in database.")

        holiday_ongoing = bool(row["state"])
        timestamp = datetime.fromisoformat(row["timestamp"])

        logger.debug(f"Holiday status retrieved: ongoing={holiday_ongoing}, timestamp={timestamp}")
        return holiday_ongoing, timestamp

    @deprecated(
        "This function is deprecated and will be removed in a future release. Use boozeSheetsApi.close_cruise(), boozeSheetsApi.update_cruise_start(), and/or boozeSheetsApi.update_cruise_state() instead."
    )
    async def set_holiday_status(self, ongoing: bool, timestamp: datetime | None = None) -> None:
        """
        Sets the current holiday status in the database.

        :param ongoing: The holiday status to set.
        :param timestamp: The timestamp to set. If None, uses current time.
        """
        logger.debug(f"Setting holiday status to ongoing={ongoing} ")

        if timestamp:
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.lock:
            self.db.execute(
                "UPDATE holidaystate SET state = ?, timestamp = ?",
                (ongoing, timestamp_str),
            )
            self.conn.commit()
        logger.debug(f"Successfully set holiday status to ongoing={ongoing} at {timestamp_str}")

    async def get_corked_users(self) -> list[CorkedUser]:
        """
        Retrieves a list of corked user IDs from the database.

        :returns: A list of corked user IDs.
        """
        logger.debug("Retrieving corked users from database")

        async with self.lock:
            self.db.execute("SELECT * FROM corked_users")
            rows = self.db.fetchall()

        corked_users = [CorkedUser(row) for row in rows]
        logger.debug(f"Retrieved {len(corked_users)} corked user(s) from database")
        return corked_users

    async def add_corked_user(self, user_id: int) -> None:
        """
        Adds a corked user to the database.

        :param user_id: The user ID to cork.
        """
        logger.debug(f"Adding corked user: {user_id}")

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.lock:
            self.db.execute(
                "INSERT INTO corked_users (user_id, timestamp) VALUES (?, ?)",
                (str(user_id), timestamp_str),
            )
            self.conn.commit()
        logger.debug(f"Successfully added corked user: {user_id}")

    async def remove_corked_user(self, user_id: int) -> None:
        """
        Removes a corked user from the database.

        :param user_id: The user ID to uncork.
        """
        logger.debug(f"Removing corked user: {user_id}")

        async with self.lock:
            self.db.execute("DELETE FROM corked_users WHERE user_id = ?", (str(user_id),))
            self.conn.commit()

        logger.debug(f"Successfully removed corked user: {user_id}")

    async def is_user_corked(self, user_id: int) -> bool:
        """
        Checks if a user is corked.

        :param user_id: The user ID to check.
        :returns: True if the user is corked, False otherwise.
        """
        logger.debug(f"Checking if user is corked: {user_id}")

        async with self.lock:
            self.db.execute("SELECT COUNT(*) FROM corked_users WHERE user_id = ?", (str(user_id),))
            count = self.db.fetchone()[0]

        is_corked = count > 0
        logger.debug(f"User {user_id} corked status: {is_corked}")
        return is_corked

    async def pin_message(self, message_id: int, channel_id: int) -> None:
        """
        Pins a message by storing its ID and channel ID in the database.

        :param message_id: The Discord message ID to pin.
        :param channel_id: The Discord channel ID where the message is located.
        """
        logger.debug(f"Pinning message ID {message_id} in channel ID {channel_id}")

        async with self.lock:
            self.db.execute(
                "INSERT INTO pinned_messages (message_id, channel_id) VALUES (?, ?)",
                (str(message_id), str(channel_id)),
            )
            self.conn.commit()
        logger.debug(f"Successfully pinned message ID {message_id} in channel ID {channel_id}")

    async def unpin_message(self, message_id: int) -> None:
        """
        Unpins a message by removing its ID from the database.

        :param message_id: The Discord message ID to unpin.
        """
        logger.debug(f"Unpinning message ID {message_id}")

        async with self.lock:
            self.db.execute("DELETE FROM pinned_messages WHERE message_id = ?", (str(message_id),))
            self.conn.commit()

        logger.debug(f"Successfully unpinned message ID {message_id}")

    async def clear_all_pins(self) -> None:
        """
        Clears all pinned messages from the database.
        """
        logger.debug("Clearing all pinned messages from database")

        async with self.lock:
            self.db.execute("DELETE FROM pinned_messages")
            self.conn.commit()

        logger.debug("Successfully cleared all pinned messages from database")

    async def get_all_pinned_messages(self) -> list[tuple[int, int]]:
        """
        Retrieves all pinned messages from the database.

        :returns: A list of tuples containing message IDs and channel IDs.
        """
        logger.debug("Retrieving all pinned messages from database")

        async with self.lock:
            self.db.execute("SELECT message_id, channel_id FROM pinned_messages")
            pinned_messages = self.db.fetchall()

        logger.debug(f"Retrieved {len(pinned_messages)} pinned message(s) from database")
        return pinned_messages

    async def is_message_pinned(self, message_id: int) -> bool:
        """
        Checks if a message is pinned.

        :param message_id: The Discord message ID to check.
        :returns: True if the message is pinned, False otherwise.
        """
        logger.debug(f"Checking if message ID {message_id} is pinned")

        async with self.lock:
            self.db.execute("SELECT COUNT(*) FROM pinned_messages WHERE message_id = ?", (str(message_id),))
            count = self.db.fetchone()[0]

        is_pinned = count > 0
        logger.debug(f"Message ID {message_id} pinned status: {is_pinned}")
        return is_pinned


database = Database()

if __name__ == "__main__":
    database.dump_database()
