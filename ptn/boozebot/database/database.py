import os
import sqlite3
import threading

from ptn.boozebot.constants import get_db_path, get_db_dumps_path

print(f'Starting DB at: {get_db_path()}')

pirate_steve_conn = sqlite3.connect(get_db_path())
pirate_steve_conn.row_factory = sqlite3.Row
pirate_steve_db = pirate_steve_conn.cursor()
pirate_steve_conn.set_trace_callback(print)

db_sql_store = get_db_dumps_path()
pirate_steve_lock = threading.Lock()


def dump_database():
    """
    Dumps the booze cruise carrier database into sql.

    :returns: None
    """
    with open(db_sql_store, 'w', encoding="utf-8") as f:
        for line in pirate_steve_conn.iterdump():
            f.write(line)


def build_database_on_startup():
    print('Checking whether the booze carriers db exists')
    pirate_steve_db.execute(
        '''SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = 'boozecarriers' ''')
    if not bool(pirate_steve_db.fetchone()[0]):

        if os.path.exists(db_sql_store):
            # recreate from backup file
            print('Recreating database from backup ...')
            with open(db_sql_store) as f:
                sql_script = f.read()
                pirate_steve_db.executescript(sql_script)
        else:
            print('Creating a fresh database')
            pirate_steve_db.execute('''
                CREATE TABLE boozecarriers( 
                    entry INTEGER PRIMARY KEY AUTOINCREMENT,
                    carriername TEXT NOT NULL, 
                    carrierid TEXT UNIQUE,
                    winetotal INT,
                    platform TEXT NOT NULL,
                    officialcarrier BOOLEAN,
                    discordusername TEXT NOT NULL,
                    timestamp DATETIME,
                    runtotal INT,
                    totalunloads INT,
                    discord_unload_in_progress INT,
                    discord_unload_poster_id INT,
                    user_timezone_in_utc TEXT
                ) 
            ''')
            print('Database created')
    else:
        print('The booze carrier database already exists')

    print('Checking whether the holiday database db exists')
    pirate_steve_db.execute(
        '''SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = 'holidaystate' '''
    )
    if not bool(pirate_steve_db.fetchone()[0]):
        print('Creating a fresh holiday database')
        pirate_steve_db.execute('''
            CREATE TABLE holidaystate(
                entry INTEGER PRIMARY KEY AUTOINCREMENT,
                state BOOL, 
                timestamp DATETIME
            ) 
        ''')
        # Write some defaults
        pirate_steve_db.execute('''
            INSERT INTO holidaystate VALUES(
                NULL,
                0,
                CURRENT_TIMESTAMP
                ) 
            ''')
        pirate_steve_conn.commit()
        print('Database created')
    else:
        print('The holiday state database already exists')

    print('Checking whether the historical database exists')
    pirate_steve_db.execute(
        '''SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = 'historical' '''
    )
    if not bool(pirate_steve_db.fetchone()[0]):
        print('Creating a fresh historical state database')
        pirate_steve_db.execute('''
            CREATE TABLE historical(
                entry INTEGER PRIMARY KEY AUTOINCREMENT,
                holiday_start DATE,
                holiday_end DATE,
                carriername TEXT NOT NULL, 
                carrierid TEXT,
                winetotal INT,
                platform TEXT NOT NULL,
                officialcarrier BOOLEAN,
                discordusername TEXT NOT NULL,
                timestamp DATETIME,
                runtotal INT,
                totalunloads INT,
                discord_unload_in_progress INT,
                user_timezone_in_utc TEXT
            ) 
        ''')
        pirate_steve_conn.commit()
        print('Historical Database created')
    else:
        print('The historical state database already exists')

    print('Checking whether the the input tracking database exists')
    pirate_steve_db.execute(
        '''SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = 'trackingforms' '''
    )
    if not bool(pirate_steve_db.fetchone()[0]):
        print('Creating a fresh trackingforms database')
        pirate_steve_db.execute('''
                CREATE TABLE trackingforms(
                    entry INTEGER PRIMARY KEY AUTOINCREMENT,
                    worksheet_key TEXT UNIQUE,
                    loader_input_form_url TEXT UNIQUE,
                    worksheet_with_data_id INT
                ) 
            ''')
        # Some default values in the case we need to make the table. These will need to be set accordingly,
        # These are the values for the testing form.
        pirate_steve_db.execute('''
            INSERT INTO trackingforms VALUES(
                NULL,
                '1fhdNd1zM4cQrQA0mCWzJAQWy70uiR3I8NLhBO7TAIL8',
                'https://forms.gle/U1YeSg9Szj1jcFHr5',
                1
            ) 
        ''')
        pirate_steve_conn.commit()
        print('Forms Database created')
    else:
        print('The tracking forms database already exists')
            
    print('Checking whether the the pinned message tracking database exists')
    pirate_steve_db.execute(
        '''SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = 'pinned_messages' '''
    )
    if not bool(pirate_steve_db.fetchone()[0]):
        print('Creating a fresh pinned_messages database')
        pirate_steve_db.execute('''
                CREATE TABLE pinned_messages(
                    entry INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE,
                    channel_id TEXT UNIQUE
                ) 
            ''')
        pirate_steve_conn.commit()
        print('Pinned message Database created')
    else:
        print('The pinned message database already exists')

    # Check to add any new columns to the database tables.
    pirate_steve_db.execute('''PRAGMA table_info (boozecarriers)''')
    result = [dict(col) for col in pirate_steve_db.fetchall()]
    col_names = [element['name'] for element in result]

    if 'user_timezone_in_utc' not in col_names:
        print('Adding the user_timezone_in_utc field.')
        # Go add it
        pirate_steve_db.execute(
            '''ALTER TABLE boozecarriers ADD COLUMN user_timezone_in_utc TEXT'''
        )
        pirate_steve_conn.commit()
        
    if 'discord_unload_poster_id' not in col_names:
        print('Adding the discord_unload_poster_id field.')
        # Go add it
        pirate_steve_db.execute(
            '''ALTER TABLE boozecarriers ADD COLUMN discord_unload_poster_id INT'''
        )
        pirate_steve_conn.commit()
        