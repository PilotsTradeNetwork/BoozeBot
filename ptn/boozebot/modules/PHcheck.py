# Checking for a public holiday at Rackham's (HIP 58832)
# Returns True or False based on whether or not Rackham's is in public holiday
# Rackham Capital Investments is the faction controlling Rackham's Peak
from datetime import UTC, datetime
from json import JSONDecodeError

import httpx
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import STALE_DATA_THRESHOLD

logger = get_logger("boozebot.modules.phcheck")


class StaleDataException(Exception):
    pass


async def get_state_from_edsm() -> tuple[bool, datetime]:
    logger.debug("Getting state from EDSM API.")
    edsm_params = {
        "systemName": "HIP 58832",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get("https://www.edsm.net/api-system-v1/factions", params=edsm_params, timeout=5)
        r.raise_for_status()
        result = r.json()

    logger.debug(f"EDSM API response: {result}")

    faction = (result.get("factions") or [{}]).pop()
    active_states = {x["state"] for x in faction.get("activeStates", [])}
    logger.debug(f"Active States: {active_states}")
    last_update = datetime.fromtimestamp(faction.get("lastUpdate") or 0, tz=UTC)
    now = datetime.now(UTC)
    if now - last_update > STALE_DATA_THRESHOLD:
        raise StaleDataException(f"Stale data detected from EDSM. Last Updated: {last_update}")

    if "Public Holiday" in active_states:
        logger.debug("Public Holiday state found in EDSM response.")
        return True, last_update

    logger.debug("No Public Holiday state found in EDSM response.")
    return False, last_update


async def api_ph_check() -> tuple[bool, datetime]:
    logger.info("Checking PH state from external APIs.")
    updated_at = datetime.now(tz=UTC)
    logger.debug("Attempting to get the state from EDSM.")
    try:
        state, updated_at = await get_state_from_edsm()
        if state:
            logger.info("PH state detected from EDSM.")
            return True, updated_at
    except StaleDataException:
        raise  # Handled in public_holiday_loop
    except Exception as e:
        logger.error("Problem while getting the state from EDSM.")
        if isinstance(e, httpx.HTTPError):
            logger.error(f"HTTP Exception for {e.request.url} - {e}")
        elif isinstance(e, JSONDecodeError):
            logger.error(f"JSON Decode Error - {e}")
        raise
    # Return false if there are no public holiday hits
    logger.info("No PH state detected from external API.")
    return False, updated_at
