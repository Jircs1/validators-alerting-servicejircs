
import requests
import sqlite3
from dotenv import load_dotenv
load_dotenv()
import os
import logging
import sseclient
import asyncio

# Environment variables
NETWORK=os.getenv('NETWORK') # Network name
DATABASE=os.getenv('DATABASE') # Local or remote DB name/url
BEACON_URL=os.getenv('BEACON_URL') # Main beacon node
BEACON_FALLBACK_URL=os.getenv('BEACON_FALLBACK_URL') # Fallback beacon node
MISSED_ATTESTATIONS_ALLOWANCE=os.getenv('MISSED_ATTESTATIONS_ALLOWANCE') # Maximum amount of missed attestation before triggering an alert
TABLE_NAME=os.getenv('TABLE_NAME') # Name of the table in database
VALIDATORS=os.getenv('VALIDATORS') # String of comma separated validator indexes

logging.basicConfig(format='%(asctime)s | %(levelname)s: %(message)s', level=logging.INFO)

# Connects to sqlite database
try:
    con = sqlite3.connect(DATABASE)
    cur = con.cursor()
    logging.info(f"The connection with {DATABASE} has been established.")
except sqlite3.Error as err:
    logging.error(err.message)

# Checks whether main beacon node is responding, fallback otherwise
async def check_beacon_url():
    try:
        requests.get(BEACON_URL)
        beacon_url=BEACON_URL
    except requests.exceptions.ConnectionError:
        logging.error(f"URL {BEACON_URL} is not reachable, falling back to {BEACON_FALLBACK_URL}")
        beacon_url=BEACON_FALLBACK_URL
    return beacon_url

# Creating database table if it does not exist
# Creating unique indexes on validator's index value, also if not exists already
async def create_table(table):
    sql = 'create table if not exists ' + table + ' (ind integer, balance integer, missed_attestations_current integer default 0, missed_attestations_total integer default 0)'
    sql_unique = 'create unique index if not exists validators_index on validators ( ind ) ;'
    try:
        cur.execute(sql)
        cur.execute(sql_unique)
        logging.info(f"The table {table} has been created or skipped.")
    except sqlite3.Error as err:
        logging.error(err.message)

# Gets the validators balances from /eth/v1/beacon/states/head/validator_balances url
# Inserts that data to the previously created table
# Tracks the balance of each validators and counts the missed attestations (when balance decreases)
# Upon MISSED_ATTESTATIONS_ALLOWANCE trigger and alert indicating that the node is most likely offline
async def get_validator_balances(url, validators, table_name):

    endpoint = f'{url}/eth/v1/beacon/states/head/validator_balances?id={validators}'
    
    try:
        r = requests.get(endpoint, timeout=5.0)
        r.raise_for_status()
        data = r.json()['data']
        for validator in data:
            try:
                cur.execute(f'INSERT OR IGNORE INTO {table_name} (ind, balance, missed_attestations_current, missed_attestations_total) VALUES (?,?,?,?)',(validator['index'], validator['balance'],0,0))
                filter = cur.execute(f'SELECT * FROM {table_name} WHERE ind = {validator["index"]}')
            except sqlite3.Error as err:
                logging.error(err.message)
            for item in filter:
                balance = item[1]
                missed_attestations_current = item[2]
                missed_attestations_total = item[3]
                if balance > int(validator['balance']):
                    logging.warning(f'Attestation has been missed by {validator["index"]}, count: {missed_attestations_current +1}')
                    try:
                        cur.execute(f'INSERT OR REPLACE INTO {table_name} (ind, balance, missed_attestations_current, missed_attestations_total) VALUES (?,?,?,?)',(validator['index'], validator['balance'], missed_attestations_current +1, missed_attestations_total +1))
                    except sqlite3.Error as err:
                        logging.error(err.message)
                    if missed_attestations_current +1 >= MISSED_ATTESTATIONS_ALLOWANCE:
                        logging.warning('Alert from there!')  
                else:
                    try:
                        cur.execute(f'REPLACE INTO {table_name} (ind, balance, missed_attestations_current, missed_attestations_total) VALUES (?,?,?,?)',(validator['index'], validator['balance'], 0, missed_attestations_total))
                    except sqlite3.Error as err:
                        logging.error(err.message)
                    
        logging.info(f'Inserting data to the {table_name} table.')

    except requests.exceptions.HTTPError as err:
        logging.error(f'Error: {err}')
    except requests.exceptions.RequestException as err:
        logging.error(f'Error: {err}')

# Gets the list of validators that have missed at least 1 attestation
async def get_validators_with_missed_attestations(table):
    with con:
        try:
            cur.execute(f"SELECT ind, missed_attestations_total FROM {table} WHERE missed_attestations_current > 0")
        except sqlite3.Error as err:
            logging.error(err.message)
        logging.info(f"Validators that missed in current epoch: {cur.fetchall()}")

# Reads number of validators to be monitored
# Executes create_table function
# Checks the endpoints availability with check_beacon_url function
# Runs SSE client to listen to finalized_checkpoint topic on beacon node
# Executes get_validator_balances function on each new event
async def main():
    validators = VALIDATORS.split(',')
    logging.info(f"{NETWORK} validators monitored: {len(validators)}")
    
    await create_table(TABLE_NAME)
    
    active_url = await check_beacon_url()
    endpoint = f'{active_url}/eth/v1/events?topics=finalized_checkpoint'
    stream_response = requests.get(endpoint, stream=True)

    checkpoint_topic = sseclient.SSEClient(stream_response)

    for event in checkpoint_topic.events():
        logging.info("Received finalized checkpoint from events stream.")
        logging.info(event.data)
        await get_validator_balances(active_url, VALIDATORS, TABLE_NAME)
        await get_validators_with_missed_attestations(TABLE_NAME)

asyncio.run(main())