import asyncio
import sqlite3
from datetime import datetime

from ptn.boozebot.constants import get_db_dumps_path, get_db_path

print(f"Starting DB at: {get_db_path()}")

pirate_steve_conn = sqlite3.connect(get_db_path())
pirate_steve_conn.row_factory = sqlite3.Row
pirate_steve_db = pirate_steve_conn.cursor()
pirate_steve_conn.set_trace_callback(print)

db_sql_store = get_db_dumps_path()
pirate_steve_db_lock = asyncio.Lock()


def dump_database():
    """
    Dumps the booze cruise carrier database into sql.

    :returns: None
    """
    with open(db_sql_store, "w", encoding="utf-8") as f:
        for line in pirate_steve_conn.iterdump():
            f.write(line)


def build_database_on_startup():
    # Define the expected schema for each table
    table_schemas = {
        "boozecarriers": {
            "entry": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "carriername": "TEXT NOT NULL",
            "carrierid": "TEXT UNIQUE",
            "winetotal": "INT",
            "platform": "TEXT NOT NULL",
            "officialcarrier": "BOOLEAN",
            "discordusername": "TEXT NOT NULL",
            "timestamp": "DATETIME",
            "runtotal": "INT",
            "totalunloads": "INT",
            "discord_unload_in_progress": "INT",
            "discord_unload_poster_id": "INT",
            "user_timezone_in_utc": "TEXT",
        },
        "historical": {
            "entry": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "holiday_start": "DATE",
            "holiday_end": "DATE",
            "carriername": "TEXT NOT NULL",
            "carrierid": "TEXT",
            "winetotal": "INT",
            "platform": "TEXT NOT NULL",
            "officialcarrier": "BOOLEAN",
            "discordusername": "TEXT NOT NULL",
            "timestamp": "DATETIME",
            "runtotal": "INT",
            "totalunloads": "INT",
            "discord_unload_in_progress": "INT",
            "user_timezone_in_utc": "TEXT",
            "faction_state": "TEXT",
        },
        "holidaystate": {"entry": "INTEGER PRIMARY KEY AUTOINCREMENT", "state": "BOOL", "timestamp": "DATETIME"},
        "trackingforms": {
            "entry": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "worksheet_key": "TEXT UNIQUE",
            "loader_input_form_url": "TEXT UNIQUE",
            "worksheet_with_data_id": "INT",
        },
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
    }

    # Iterate through each table schema and create or update the table
    for table_name, schema in table_schemas.items():

        # Create the table if it does not exist

        pirate_steve_db.execute(
            f"""
            SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = '{table_name}'
        """
        )
        if not bool(pirate_steve_db.fetchone()[0]):
            print(f"Table {table_name} does not exist, creating it now.")
            pirate_steve_db.execute(
                f"""
                CREATE TABLE {table_name} (
                    {', '.join([f"{col} {col_type}" for col, col_type in schema.items()])}
                )
            """
            )
            pirate_steve_conn.commit()
            print(f"Table {table_name} created successfully.")
            continue

        else:
            print(f"Table {table_name} already exists, checking columns for updates.")

            pirate_steve_db.execute(f"""PRAGMA table_info ({table_name})""")
            result = [dict(col) for col in pirate_steve_db.fetchall()]
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

            # Add any missing columns
            for column_name, column_type in schema.items():
                if column_name not in existing_columns:
                    print(f"Adding column {column_name} to table {table_name}")
                    pirate_steve_db.execute(f"""ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}""")

            # Check for any incorrect column types
            for column_name, column_type in existing_columns.items():
                if column_name in schema:
                    if column_type != schema[column_name]:
                        print(
                            f"Column {column_name} in table {table_name} has incorrect type {column_type}, expected {schema[column_name]}"
                        )
                        raise EnvironmentError("Column type mismatch detected. Please check the database schema.")

            pirate_steve_conn.commit()

    print("Database schema check and update completed successfully.")

    default_values = {
        "holidaystate": [{"state": 0, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}],
        "trackingforms": [
            {
                "worksheet_key": "1fhdNd1zM4cQrQA0mCWzJAQWy70uiR3I8NLhBO7TAIL8",
                "loader_input_form_url": "https://forms.gle/U1YeSg9Szj1jcFHr5",
                "worksheet_with_data_id": 1,
            }
        ],
    }

    # Insert default values into tables if they're empty
    for table_name, records in default_values.items():
        pirate_steve_db.execute(f"SELECT COUNT(*) FROM {table_name}")
        if pirate_steve_db.fetchone()[0] == 0:
            print(f"Inserting default values into {table_name} table.")
            for record in records:
                columns = ", ".join(record.keys())
                placeholders = ", ".join(["?" for _ in record])
                values = tuple(record.values())
                pirate_steve_db.execute(
                    f"""
                    INSERT INTO {table_name} ({columns}) VALUES ({placeholders})
                """,
                    values,
                )
            pirate_steve_conn.commit()
            print(f"Default values inserted into {table_name} table.")
        else:
            print(f"{table_name} table already has data, skipping default insert.")

    print("Database is ready for use.")


if __name__ == "__main__":
    build_database_on_startup()
