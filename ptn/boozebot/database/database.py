import os
import sqlite3
import threading

from ptn.boozebot.constants import get_db_path, get_db_dumps_path

print(f'Starting DB at: {get_db_path()}')

pirate_steve_conn = sqlite3.connect(get_db_path())
pirate_steve_conn.row_factory = sqlite3.Row
pirate_steve_db = pirate_steve_conn.cursor()

db_sql_store = get_db_dumps_path()
pirate_steve_lock = threading.Lock()


def dump_database():
    """
    Dumps the booze cruise carrier database into sql.

    :returns: None
    """
    with open(db_sql_store, 'w') as f:
        for line in pirate_steve_conn.iterdump():
            f.write(line)


def build_database_on_startup():
    print('Checking whether the booze carriers db exists')
    pirate_steve_db.execute('''SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = 'boozecarriers' ''')
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
                    discord_unload_in_progress INT
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
