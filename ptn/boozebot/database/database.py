import os
import sqlite3
import threading

from ptn.boozebot.constants import get_db_path, get_db_dumps_path

print(f'Starting DB at: {get_db_path()}')

carriers_conn = sqlite3.connect(get_db_path())
carriers_conn.row_factory = sqlite3.Row
carrier_db = carriers_conn.cursor()

db_sql_store = get_db_dumps_path()
carrier_db_lock = threading.Lock()


def dump_database():
    """
    Dumps the booze cruise carrier database into sql.

    :returns: None
    """
    with open(db_sql_store, 'w') as f:
        for line in carriers_conn.iterdump():
            f.write(line)


def build_database_on_startup():
    print('Checking whether the booze carriers db exists')
    carrier_db.execute('''SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = 'boozecarriers' ''')
    if not bool(carrier_db.fetchone()[0]):

        if os.path.exists(db_sql_store):
            # recreate from backup file
            print('Recreating database from backup ...')
            with open(db_sql_store) as f:
                sql_script = f.read()
                carrier_db.executescript(sql_script)
        else:
            print('Creating a fresh database')
            carrier_db.execute('''
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
