# Checking for a public holiday at Rackham's (HIP 58832)
# Returns True or False based on whether or not Rackham's is in public holiday
# Rackham Capital Investments is the faction controlling Rackham's Peak

import httpx
from json import JSONDecodeError

async def get_state_from_ebgs() -> bool:
    ebgs_params = {
        'name': 'Rackham Capital Investments'
    }
    async with httpx.AsyncClient() as client:
        r = await client.get('https://elitebgs.app/api/ebgs/v5/factions', params=ebgs_params, timeout=5)
        r.raise_for_status()
        result = r.json()
        
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
                        print('PH state matched from ebgs')
                        return True
    return False


async def get_state_from_edsm() -> bool:
    async with httpx.AsyncClient() as client:
        r = await client.get('https://www.edsm.net/api-v1/system?systemName=HIP%2058832&showInformation=1', timeout=5)
        r.raise_for_status()
        result = r.json()
    
    if result.get('information', {}).get('factionState') == 'Public Holiday':
        print('PH state matched from edsm')
        return True
    return False


async def ph_check() -> bool:
    try:
        if await get_state_from_ebgs():
            return True
    except (httpx.HTTPError, JSONDecodeError) as exc:
        print('Problem while getting the state from ebgs.')
        print(f"HTTP Exception for {exc.request.url} - {exc}")
        print("Attempting to get the state from the edsm.")
        
        try:
            if await get_state_from_edsm():
                return True
        except (httpx.HTTPError, JSONDecodeError) as exc:
            print('Problem while getting the state from edsm.')
            print(f"HTTP Exception for {exc.request.url} - {exc}")
            print(exc)

    # Return false if there are no public holiday hits
    print('PH was not hit - Returning False.')
    return False
