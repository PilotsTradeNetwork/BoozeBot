# Checking for a public holiday at Rackham's (HIP 58832)
# Returns True or False based on whether or not Rackham's is in public holiday
# Rackham Capital Investments is the faction controlling Rackham's Peak

import httpx
from json import JSONDecodeError
from loguru import logger

from ptn.boozebot.database.database import pirate_steve_db

async def get_state_from_ebgs() -> bool:
    logger.debug("Getting state from EBGS API.")
    ebgs_params = {
        'name': 'Rackham Capital Investments'
    }
    async with httpx.AsyncClient() as client:
        r = await client.get('https://elitebgs.app/api/ebgs/v5/factions', params=ebgs_params, timeout=5)
        r.raise_for_status()
        result = r.json()
        
    logger.debug(f"EBGS API response: {result}")

    # Search each element in the result
    for element in result['docs']:
        # Search each system in which the faction is present
        for system in element['faction_presence']:
            # If there are no active states in the system, skip to the next system
            if not system['active_states'] or system['system_name'] != "HIP 58832":
                continue
            # If there is an active state, look through the active states for a public holiday
            else:
                for active_states in system['active_states']:
                    # If the system is in public holiday, return True
                    if active_states['state'] == 'publicholiday':
                        logger.debug("Public Holiday state found in EBGS response.")
                        return True
                    
    logger.debug("No Public Holiday state found in EBGS response.")
    return False


async def get_state_from_edsm() -> bool:
    logger.debug("Getting state from EDSM API.")
    edsm_params = {
        'systemName': 'HIP 58832',
    }
    async with httpx.AsyncClient() as client:
        r = await client.get('https://www.edsm.net/api-system-v1/factions', params=edsm_params,  timeout=5)
        r.raise_for_status()
        result = r.json()
    
    logger.debug(f"EDSM API response: {result}")

    active_states = {x["state"] for x in result.get('factions', [{}]).pop().get('activeStates', [])}
    if 'Public Holiday' in active_states:
        logger.debug("Public Holiday state found in EDSM response.")
        return True
    
    logger.debug("No Public Holiday state found in EDSM response.")
    return False


async def api_ph_check() -> bool:
    logger.info("Checking PH state from external APIs.")
    try:
        logger.debug("Attempting to get the state from EDSM.")
        if await get_state_from_edsm():
            logger.info("PH state detected from EDSM.")
            return True
    except (httpx.HTTPError, JSONDecodeError) as exc:
        logger.error('Problem while getting the state from EDSM.')
        logger.error(f"HTTP Exception for {exc.request.url} - {exc}")
        logger.debug("Attempting to get the state from EBGS.")

        try:
            if await get_state_from_ebgs():
                logger.info("PH state detected from EBGS.")
                return True
        except (httpx.HTTPError, JSONDecodeError) as exc:
            logger.error('Problem while getting the state from EBGS.')
            logger.error(f"HTTP Exception for {exc.request.url} - {exc}")


    # Return false if there are no public holiday hits
    logger.info("No PH state detected from external APIs.")
    return False

def ph_check() -> bool:
    logger.info("Checking PH state from the database.")
    try:
        pirate_steve_db.execute(
            '''SELECT state FROM holidaystate'''
        )
        holiday_sqlite3 = pirate_steve_db.fetchone()
        logger.debug(f"Fetched holiday state from database: {dict(holiday_sqlite3)}")
        holiday_ongoing = bool(dict(holiday_sqlite3).get('state'))
        if not holiday_ongoing:
            logger.info("PH is not ongoing according to the database.")
            return False
        else:
            logger.info("PH is ongoing according to the database.")
            return True
    except Exception as e:
        logger.exception(f"Error while checking PH state from the database: {e}")
        return False
