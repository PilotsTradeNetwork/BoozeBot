import asyncio
import sqlite3
from datetime import datetime
from loguru import logger

from ptn.boozebot.constants import get_db_dumps_path, get_db_path

db_path = get_db_path()
logger.info(f"Starting database connection at: {db_path}")

pirate_steve_conn = sqlite3.connect(db_path)
pirate_steve_conn.row_factory = sqlite3.Row
pirate_steve_db = pirate_steve_conn.cursor()

def sql_trace_callback(statement):
    logger.debug(f"SQL: {statement}")

pirate_steve_conn.set_trace_callback(sql_trace_callback)

db_sql_store = get_db_dumps_path()
pirate_steve_db_lock = asyncio.Lock()

logger.debug(f"Database initialized. SQL dumps will be stored at: {db_sql_store}")

def dump_database():
    """
    Dumps the booze cruise carrier database into sql.

    :returns: None
    """
    
    logger.info(f"Dumping database to SQL file: {db_sql_store}")
    
    line_count = 0
    with open(db_sql_store, "w", encoding="utf-8") as f:
        for line in pirate_steve_conn.iterdump():
            f.write(line)
            line_count += 1
    
    logger.debug(f"Wrote {line_count} lines to SQL dump file.")
    logger.info("Database dump completed.")


def build_database_on_startup():
    # Define the expected schema for each table
    
    logger.info("Building or updating database schema.")
    
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
            "discord_departure_message_id": "INT",
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
        
        logger.info(f"Checking table: {table_name}")
        logger.debug(f"Expected schema for {table_name}: {schema}")
        
        # Create the table if it does not exist

        pirate_steve_db.execute(
            f"""
            SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = '{table_name}'
        """
        )
        table_exists = bool(pirate_steve_db.fetchone()[0])
        logger.debug(f"Table {table_name} exists: {table_exists}")
        
        if not table_exists:
            logger.info(f"Table {table_name} does not exist. Creating table.")
            create_statement = f"CREATE TABLE {table_name} ({', '.join([f'{col} {col_type}' for col, col_type in schema.items()])})"
            logger.debug(f"Create statement: {create_statement}")
            pirate_steve_db.execute(create_statement)
            pirate_steve_conn.commit()
            logger.debug(f"Committed table creation for {table_name}.")
            logger.info(f"Table {table_name} created successfully.")
            continue

        else:
            logger.info(f"Table {table_name} exists. Checking for missing or incorrect columns.")

            pirate_steve_db.execute(f"""PRAGMA table_info ({table_name})""")
            result = [dict(col) for col in pirate_steve_db.fetchall()]
            logger.debug(f"PRAGMA table_info result for {table_name}: {result}")
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
            
            logger.debug(f"Existing columns in {table_name}: {existing_columns}")

            # Add any missing columns
            columns_added = 0
            for column_name, column_type in schema.items():
                if column_name not in existing_columns:
                    logger.info(f"Column {column_name} missing in table {table_name}. Adding column.")
                    alter_statement = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    logger.debug(f"Alter statement: {alter_statement}")
                    pirate_steve_db.execute(alter_statement)
                    columns_added += 1
            
            if columns_added > 0:
                logger.debug(f"Added {columns_added} column(s) to table {table_name}.")

            # Check for any incorrect column types
            for column_name, column_type in existing_columns.items():
                if column_name in schema:
                    if column_type != schema[column_name]:
                        logger.error(
                            f"Column {column_name} in table {table_name} has type {column_type} but expected {schema[column_name]}"
                        )
                        raise EnvironmentError("Column type mismatch detected. Please check the database schema.")
                    else:
                        logger.debug(f"Column {column_name} in table {table_name} has correct type: {column_type}")

            pirate_steve_conn.commit()
            logger.debug(f"Committed schema changes for table {table_name}.")

    logger.info("Database schema check and update completed successfully. Checking for default values.")

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
        logger.info(f"Checking for default values in table: {table_name}")

        pirate_steve_db.execute(f"SELECT COUNT(*) FROM {table_name}")
        record_count = pirate_steve_db.fetchone()[0]
        logger.debug(f"Table {table_name} has {record_count} existing record(s).")
        
        if record_count == 0:
            logger.info(f"Inserting default values into table: {table_name}")
            for idx, record in enumerate(records, 1):
                columns = ", ".join(record.keys())
                placeholders = ", ".join(["?" for _ in record])
                values = tuple(record.values())
                logger.debug(f"Inserting record {idx}/{len(records)} into {table_name}: {record}")
                pirate_steve_db.execute(
                    f"""
                    INSERT INTO {table_name} ({columns}) VALUES ({placeholders})
                """,
                    values,
                )
            pirate_steve_conn.commit()
            logger.debug(f"Committed {len(records)} default record(s) to {table_name}.")
            logger.info(f"Default values inserted into table: {table_name} successfully.")
        else:
            logger.info(f"Table {table_name} already has data. Skipping default value insertion.")

    


if __name__ == "__main__":
    build_database_on_startup()
