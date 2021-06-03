# Checking for a public holiday at Rackham's (HIP 58832)
# Returns True or False based on whether or not Rackham's is in public holiday
# Rackham Capital Investments is the faction controlling Rackham's Peak

import requests

def phCheck():
    params = {
        'name' : 'Rackham Capital Investments'
    }
    try:
        r = requests.get('https://elitebgs.app/api/ebgs/v5/factions',params=params)
        result = r.json()
    except:
        return None

    # Search each element in the result
    for element in result['docs']:
        # Search each system in which the faction is present
        for system in element['faction_presence']:
            # If there are no active states in the system, skip to the next system
            if system['active_states'] == []:
                continue
            # If there is an active state, look through the active states for a public holiday
            else:
                for active_states in system['active_states']:
                    # If the system is in public holiday, return True
                    if active_states['state'] == 'publicholiday':
                        return True
                    # If the system is not in public holiday, continue through the loop
                    else:
                        continue
    # Return false if there are no public holiday hits
    return False