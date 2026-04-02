# Checking for a public holiday at Rackham's (HIP 58832)
# Returns True or False based on whether or not Rackham's is in public holiday
# Rackham Capital Investments is the faction controlling Rackham's Peak
from datetime import UTC, datetime
from json import JSONDecodeError

import httpx
from ptn_utils.enums.booze_enums import CruiseSystemState
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import STALE_DATA_THRESHOLD
from ptn.boozebot.modules.boozeSheetsApi import booze_sheets_api

logger = get_logger("boozebot.modules.phcheck")


class StaleDataException(Exception):
    pass


# Tracks the last time a state change was detected by api_ph_check or an admin override.
# EDSM data is rejected if it is before that timestamp, to avoid flip-flopping between states
LAST_UPDATED: datetime = datetime.now(tz=UTC)

# Tracks the previous PH state so that changes can be detected by api_ph_check.
_previous_ph_state: bool | None = None


def set_last_updated(dt: datetime) -> None:
    """Update LAST_UPDATED to *dt*. Use this instead of a bare ``global`` assignment."""
    global LAST_UPDATED  # noqa: PLW0603
    LAST_UPDATED = dt


def set_previous_ph_state(state: bool | None) -> None:
    """Update _previous_ph_state to *state*. Use this instead of a bare ``global`` assignment."""
    global _previous_ph_state  # noqa: PLW0603
    _previous_ph_state = state


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
    logger.debug(f"Last update: {last_update}")
    now = datetime.now(UTC)
    if now - last_update > STALE_DATA_THRESHOLD:
        raise StaleDataException(f"Stale data detected from EDSM. Last Updated: {last_update}")
    if LAST_UPDATED is not None and last_update < LAST_UPDATED:
        raise StaleDataException(
            "EDSM data predates last known state change. "
            + f"Last Updated: {last_update}, Last State Change: {LAST_UPDATED}"
        )

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
        if state != _previous_ph_state:
            logger.info(f"PH state change detected: {_previous_ph_state} -> {state}. Updating LAST_UPDATED.")
            set_last_updated(updated_at)
            set_previous_ph_state(state)
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


async def ph_check() -> bool:
    logger.info("Checking PH state from the database.")
    try:
        holiday_ongoing = await booze_sheets_api.get_current_cruise_state() == CruiseSystemState.ACTIVE

        logger.debug(f"Fetched holiday state from backend: {holiday_ongoing}")

        if not holiday_ongoing:
            logger.info("PH is not ongoing according to the backend.")
            return False
        logger.info("PH is ongoing according to the backend.")
        return True
    except Exception as e:
        logger.exception(f"Error while checking PH state from the backend: {e}")
        return False
