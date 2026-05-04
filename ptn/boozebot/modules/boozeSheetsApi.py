import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, override

import discord
import httpx
import websockets
from discord import Embed, User, app_commands
from discord.ext.commands import Bot
from httpx import AsyncClient
from ptn_utils.enums.booze_enums import CruiseSystemState
from ptn_utils.global_constants import CHANNEL_BOTSPAM
from ptn_utils.logger.logger import get_logger
from tenacity import (
    RetryCallState,
    retry,
    wait_exponential,
)
from tenacity.stop import stop_base

from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier, CarrierStats
from ptn.boozebot.classes.Cruise import Cruise, CruiseState, CruiseStats
from ptn.boozebot.constants import BOOZESHEETS_API_BASE_URL, BOOZESHEETS_API_KEY, bot
from ptn.boozebot.modules.helpers import is_staff


class PayloadType(Enum):
    BODY = 0
    QUERY = 1


logger = get_logger("boozebot.modules.boozeSheetsApi")

_background_tasks: set[asyncio.Task[None]] = set()


def _should_retry_exception(exception: Exception) -> bool:
    """
    Determine if a request should be retried based on the exception.
    """
    if isinstance(exception, httpx.TimeoutException):
        return True
    if isinstance(exception, (httpx.ConnectError, httpx.NetworkError)):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    return False


class dynamic_attempts(stop_base):
    """Stop strategy that adjusts max attempts based on a condition."""

    def __init__(
        self, condition: Callable[[RetryCallState], bool], attempts_if_true: int = 3, attempts_if_false: int = 1
    ) -> None:
        super().__init__()
        self.condition: Callable[[RetryCallState], bool] = condition
        self.attempts_if_true: int = attempts_if_true
        self.attempts_if_false: int = attempts_if_false

    @override
    def __call__(self, retry_state: "RetryCallState") -> bool:
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        max_attempts = self.attempts_if_true if exception and self.condition(exception) else self.attempts_if_false
        return retry_state.attempt_number >= max_attempts


def _on_api_failure(retry_state: RetryCallState):
    """
    Called when API requests fail after all retries are exhausted.
    Schedules async task to post error message to bot_spam channel.
    """
    exception: BaseException | None = retry_state.outcome.exception()
    if exception is None:
        return
    args = retry_state.args
    kwargs = retry_state.kwargs

    method = args[1] if len(args) > 1 else "UNKNOWN"
    endpoint = args[2] if len(args) > 2 else "UNKNOWN"
    data = kwargs.get("data")

    error_msg = str(exception) or type(exception).__name__

    logger.exception(
        f"BoozeSheets API request failed after {retry_state.attempt_number} attempts: "
        + f"method={method}, endpoint={endpoint}, data={data}, error={error_msg}"
    )

    task = asyncio.create_task(_send_failure_to_discord(method, endpoint, data, exception, retry_state.attempt_number))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _send_failure_to_discord(
    method: str, endpoint: str, data: dict[str, Any], exception: Exception, attempts: int
):
    """
    Sends API failure notification to bot_spam channel.

    :param method: The HTTP method that failed.
    :param endpoint: The API endpoint that failed.
    :param data: The request data.
    :param exception: The exception that occurred.
    :param attempts: Number of retry attempts made.
    """
    try:
        bot_spam = await bot.get_or_fetch.channel(CHANNEL_BOTSPAM)
        error_msg = str(exception) or type(exception).__name__
        embed = Embed(
            title="⚠️ BoozeSheets API Failure",
            description=f"API request failed after {attempts} retry attempts.\n\n"
            + f"**Method:** `{method}`\n"
            + f"**Endpoint:** `{endpoint}`\n"
            + f"**Data:** `{data}`\n"
            + f"**Error:** {error_msg}",
            color=0xFF0000,
        )
        await bot_spam.send(embed=embed)
    except Exception as e:
        logger.exception(f"Failed to send API failure notification to bot_spam: {e}")


def _log_before_sleep(retry_state: RetryCallState):
    """Log retry attempts with exception details."""
    exception = retry_state.outcome.exception()
    error_msg = str(exception) or type(exception).__name__
    logger.warning(
        f"Retrying BoozeSheets API request: attempt {retry_state.attempt_number} "
        + f"after {retry_state.idle_for:.1f}s due to {error_msg}"
    )


class BoozeSheetsApi:
    _ws_connected: bool
    _ws_running: bool
    _ws_connection: websockets.ClientConnection | None
    _carrier_poll_running: bool
    _carrier_cache_last_refresh: datetime | None
    ws_task: asyncio.Task[None] | None
    carrier_poll_task: asyncio.Task[None] | None
    ws_client: AsyncClient | None
    bot: Bot
    client_lock: asyncio.Lock
    carrier_cache_lock: asyncio.Lock
    client: AsyncClient
    base_url: str
    carrier_cache: dict[int, BoozeCarrier]

    def __init__(self):
        self.base_url = BOOZESHEETS_API_BASE_URL
        # Configure transport with retries for connection-level failures
        transport = httpx.AsyncHTTPTransport(retries=3)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            cookies={"X-API-KEY": BOOZESHEETS_API_KEY},
            timeout=10.0,
            transport=transport,
        )
        self.client_lock = asyncio.Lock()
        self.bot = bot
        self.ws_client = None
        self.ws_task = None
        self._ws_running = False
        self._carrier_poll_running = False
        self._last_ws_message_time: datetime | None = None
        self._carrier_cache_last_refresh = None
        self._ws_connected = False
        self._reconnect_delay: int = 5
        self._ws_connection = None
        self.carrier_poll_task = None
        self.carrier_cache = {}
        self.carrier_cache_lock = asyncio.Lock()

    async def _refresh_carrier_cache(self) -> dict[int, BoozeCarrier]:
        """
        Poll all carriers from BoozeSheets and replace the in-memory cache.

        :return: The refreshed carrier cache keyed by carrier DB ID.
        """
        carriers = await self.get_all_carriers_info()
        refreshed_cache = {carrier.db_id: carrier for carrier in carriers}

        async with self.carrier_cache_lock:
            self.carrier_cache = refreshed_cache
            self._carrier_cache_last_refresh = datetime.now(tz=UTC)

        logger.info(f"Carrier cache refreshed from poll with {len(refreshed_cache)} carriers")
        return refreshed_cache

    async def _carrier_cache_ws_update(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Update the in-memory carrier cache based on a websocket event.

        :param event_type: The websocket event type (e.g. carrier_created, carrier_updated).
        :param data: The raw websocket payload.
        """
        logger.debug(f"Carrier WS cache update called for event_type={event_type}")

        if event_type not in {"carrier_update", "carrier_created"}:
            logger.debug("Not a carrier update/create event, skipping cache update")
            return

        async with self.carrier_cache_lock:
            carrier = BoozeCarrier(data["carrier"])

            self.carrier_cache[carrier.db_id] = carrier

        logger.debug(
            f"Carrier cache updated from websocket event for carrier_id={carrier.db_id}, event_type={event_type}"
        )

    async def start_carrier_polling(self):
        """
        Start the periodic carrier cache polling loop (every 5 minutes).
        """
        if self._carrier_poll_running:
            logger.warning("Carrier polling loop is already running")
            return

        self._carrier_poll_running = True
        self.carrier_poll_task = asyncio.create_task(self._carrier_poll_loop())
        logger.info("Started carrier polling loop")

    async def stop_carrier_polling(self):
        """
        Stop the periodic carrier cache polling loop.
        """
        if not self._carrier_poll_running:
            logger.warning("Carrier polling loop is not running")
            return

        self._carrier_poll_running = False
        if self.carrier_poll_task:
            self.carrier_poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.carrier_poll_task
            self.carrier_poll_task = None

        logger.info("Stopped carrier polling loop")

    async def _carrier_poll_loop(self):
        """
        Periodically refresh the carrier cache every 5 minutes.
        """
        while self._carrier_poll_running:
            try:
                await self._refresh_carrier_cache()
            except asyncio.CancelledError:
                logger.info("Carrier polling loop cancelled")
                break
            except Exception as e:
                logger.exception(f"Carrier polling loop iteration failed: {e}")

            await asyncio.sleep(300)

    def carrier_autocomplete(self, only_owned: bool = True, state: Literal["full", "unloading", "empty"] | None = None):
        async def autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            logger.debug(f"Carrier autocomplete called with current input: '{current}' and only_owned={only_owned}")

            show_only_owned = only_owned and not is_staff(interaction.user)
            owned_carriers = [c for c in self.carrier_cache.values() if c.owner.discord_id == interaction.user.id]

            if show_only_owned or (current == "" and len(owned_carriers) > 0):
                carriers = owned_carriers
                carriers.sort(key=lambda c: c.carrier_name.lower())
            else:
                carriers = list(self.carrier_cache.values())
                carriers.sort(key=lambda c: (c.owner.discord_id != interaction.user.id, c.carrier_name.lower()))

            if state == "full":
                carriers = [c for c in carriers if not c.unload_opened and c.system == "N0"]
            elif state == "unloading":
                carriers = [c for c in carriers if c.unload_opened and not c.unload_closed]
            elif state == "empty":
                carriers = [c for c in carriers if c.system == "N16" and c.wine_status in ["Empty", None]]

            display_items = [
                (f"{carrier.carrier_name} ({carrier.carrier_identifier})", carrier.carrier_identifier)
                for carrier in carriers
            ]

            filtered = [
                app_commands.Choice(name=name, value=value)
                for name, value in display_items
                if current.lower() in name.lower()
            ]
            logger.debug(f"Carrier autocomplete choices: {[choice.name for choice in filtered]}")
            return filtered[:25]

        return autocomplete

    @retry(
        stop=dynamic_attempts(_should_retry_exception, 3, 1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=_log_before_sleep,
        after=_on_api_failure,
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        payload_type: PayloadType | None = PayloadType.QUERY,
    ) -> dict[str, Any]:
        """
        Internal method to send HTTP requests to the BoozeSheets API.

        :param method: The HTTP method (GET, POST, PATCH, DELETE, etc.)
        :param endpoint: The API endpoint to send the request to.
        :param data: The data to send in the request body or get params (optional).
        :param payload_type: Determines whether to use query params or json body to pass data to the API (optional)
        :return: The response from the API as a dictionary.
        """

        logger.debug(
            f"Sending {method} request to BoozeSheets API: endpoint={endpoint}, data={data}, PayloadType: {payload_type}"
        )

        async with self.client_lock:
            match payload_type:
                case PayloadType.QUERY:
                    response = await self.client.request(method, endpoint, params=data, follow_redirects=True)
                case PayloadType.BODY:
                    response = await self.client.request(method, endpoint, json=data, follow_redirects=True)
                case _:
                    logger.error(f"Invalid payload_type: {payload_type}, assuming QUERY")
                    response = await self.client.request(method, endpoint, params=data, follow_redirects=True)

        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Received response from BoozeSheets API: {response_data}")

        return response_data

    async def get_carrier_info(self, carrier_id: str) -> BoozeCarrier | None:
        """
        Retrieves carrier information from the BoozeSheets API.

        :param carrier_id: The ID of the carrier to retrieve information for.
        :return: The carrier information as a dictionary.
        """

        logger.debug(f"Getting carrier info for carrier_id={carrier_id}")
        carrier_id = carrier_id.upper()
        endpoint = f"/carriers/by-callsign/{carrier_id}"

        logger.debug(f"Sending GET request to {endpoint}")
        try:
            carrier_info = await self._request("GET", endpoint)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Carrier not found for carrier_id={carrier_id}")
                return None
            raise
        logger.debug(f"Carrier info retrieved: {carrier_info}")

        return BoozeCarrier(carrier_info)

    async def get_all_carriers_info(self) -> list[BoozeCarrier]:
        """
        Retrieves information for all carriers from the BoozeSheets API.

        :return: A list of carrier information dictionaries.
        """

        logger.debug("Getting info for all carriers")
        endpoint = "/carriers"

        logger.debug(f"Sending GET request to {endpoint}")
        try:
            carriers_info = await self._request("GET", endpoint)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("No carriers found")
                return []
            raise
        logger.debug(f"All carriers info retrieved: {carriers_info}")

        return [BoozeCarrier(info) for info in carriers_info]

    async def update_carrier_info(self, carrier_id: str, update_data: dict[str, Any]) -> BoozeCarrier:
        """
        Updates carrier information in the BoozeSheets API.

        :param carrier_id: The ID of the carrier to update.
        :param update_data: The data to update for the carrier.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Updating carrier info for carrier_id={carrier_id}")
        endpoint = f"/carriers/{carrier_id}/admin"

        updated_carrier_info = await self._request("PATCH", endpoint, update_data, PayloadType.BODY)

        logger.debug(f"Carrier info updated: {updated_carrier_info}")
        return BoozeCarrier(updated_carrier_info)

    async def start_carrier_unload(self, carrier_id: str, delay: int | None = None) -> BoozeCarrier:
        """
        Marks a carrier as having started unloading.

        :param carrier_id: The ID of the carrier to mark as unloading.
        :param delay: The delay in seconds before unloading starts.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Starting unload for carrier_id={carrier_id}, delay={delay}")
        endpoint = f"/carriers/{carrier_id}/unload"

        data: dict[str, str | int] = {"unloading": "true"}
        if delay is not None:
            data["delay"] = delay

        logger.debug(f"Sending POST request to {endpoint} with data={data}")
        updated_carrier = await self._request("POST", endpoint, data, PayloadType.QUERY)
        logger.debug(f"Carrier unload started: {updated_carrier}")

        return BoozeCarrier(updated_carrier)

    async def complete_carrier_unload(self, carrier_id: str) -> BoozeCarrier:
        """
        Marks a carrier as having completed unloading.

        :param carrier_id: The ID of the carrier to mark as unloaded.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Completing unload for carrier_id={carrier_id}")
        endpoint = f"/carriers/{carrier_id}/unload"

        data = {"unloading": "false"}
        logger.debug(f"Sending POST request to {endpoint} with data={data}")
        updated_carrier = await self._request("POST", endpoint, data, PayloadType.QUERY)
        logger.debug(f"Carrier unload completed: {updated_carrier}")

        return BoozeCarrier(updated_carrier)

    async def get_carriers_with_wine_remaining(self) -> list[BoozeCarrier]:
        """
        Retrieves a list of carriers that have wine remaining.

        :return: A list of carrier information dictionaries.
        """

        logger.debug("Getting info for all carriers with wine remaining")
        endpoint = "/carriers"
        data = {"wine_status": ["Full", "Partially Full"]}

        logger.debug(f"Sending GET request to {endpoint} with data={data}")
        carriers_info = await self._request("GET", endpoint, data, PayloadType.QUERY)
        logger.debug(f"All carriers info retrieved: {carriers_info}")

        return [BoozeCarrier(info) for info in carriers_info]

    async def get_unloading_carriers(self) -> list[BoozeCarrier]:
        """
        Retrieves a list of carriers that are currently unloading.

        :return: A list of carrier information dictionaries.
        """

        logger.debug("Getting info for all unloading carriers")
        endpoint = "/carriers"
        data = {"wine_status": ["Unloading"]}

        logger.debug(f"Sending GET request to {endpoint} with data={data}")
        carriers_info = await self._request("GET", endpoint, data, PayloadType.QUERY)
        logger.debug(f"All carriers info retrieved: {carriers_info}")

        return [BoozeCarrier(info) for info in carriers_info]

    async def get_cruises_list(self) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Retrieves a list of all cruises from the BoozeSheets API.

        :return: A list of cruises.
        """

        logger.debug("Getting list of all cruises")
        endpoint = "/cruises"

        logger.debug(f"Sending GET request to {endpoint}")
        try:
            cruises = await self._request("GET", endpoint)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("No cruises found")
                return []
            raise
        logger.debug(f"Cruises list retrieved: {cruises}")
        return cruises

    async def get_current_cruise_state(self) -> CruiseState:
        """
        Retrieves the current cruise state from the BoozeSheets API.

        :return: The current cruise state.
        """

        logger.debug("Getting current cruise state")
        endpoint = "/cruises/state"

        logger.debug(f"Sending GET request to {endpoint}")
        try:
            state_data: dict[str, str] = await self._request("GET", endpoint)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get current cruise state: {e}")
            raise

        logger.debug(f"Current cruise state from backend: {state_data}")

        if "state" not in state_data or "updatedAt" not in state_data:
            logger.error(f"Invalid cruise state response format: {state_data}")
            raise KeyError("Missing 'state' or 'updatedAt' in cruise state response")

        return {
            "state": CruiseSystemState(state_data["state"]),
            "updated_at": datetime.fromisoformat(state_data["updatedAt"]),
        }

    async def get_cruise_with_stats(
        self, cruise_id: int, include_not_unloaded: bool | None = None, exclude_staff: bool | None = None
    ) -> Cruise | None:
        """
        Retrieves stats for a specific cruise.

        :param cruise_id: The ID of the cruise to retrieve stats for. Supports relative  (0: current, -1: previous, etc.) or absolute (positive int) indexing
        :param include_not_unloaded: Whether to include carriers that have not yet unloaded.
        :param exclude_staff: Whether to exclude staff carriers.
        :return: The cruise stats.
        """

        logger.debug(
            f"Getting cruise stats for cruise_id={cruise_id}, include_not_unloaded={include_not_unloaded}, exclude_staff={exclude_staff}"
        )

        stats_endpoint = f"/cruises/{cruise_id}"

        data = {}
        if include_not_unloaded is not None:
            data["include_not_unloaded"] = include_not_unloaded
        if exclude_staff:
            data["exclude_staff"] = exclude_staff

        logger.debug(f"Sending GET request to {stats_endpoint} with data={data}")
        try:
            cruise_data = await self._request("GET", stats_endpoint, data, PayloadType.QUERY)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Cruise stats not found for cruise_id={cruise_id}")
                return None
            raise
        logger.debug(f"Cruise stats retrieved: {cruise_data}")

        return Cruise(cruise_data)

    async def get_biggest_cruise_with_stats(self, include_not_unloaded: bool | None = None) -> Cruise | None:
        """
        Retrieves the biggest cruise stats.
        :param include_not_unloaded: Whether to include carriers that have not yet unloaded.
        :return: The biggest cruise stats.
        """

        logger.debug("Getting biggest cruise stats")
        endpoint = "/cruises/biggest_cruise"
        data = {"include_not_unloaded": include_not_unloaded} if include_not_unloaded is not None else {}

        logger.debug(f"Sending GET request to {endpoint} with data={data}")
        try:
            cruise_data = await self._request("GET", endpoint, data, PayloadType.QUERY)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Biggest cruise stats not found")
                return None
            raise
        logger.debug(f"Biggest cruise stats retrieved: {cruise_data}")

        return Cruise(cruise_data)

    async def get_trip_for_carrier(self, carrier_id: str, trip_id: str) -> BoozeCarrier | None:
        """
        Retrieves a specific trip for a specific carrier.

        :param carrier_id: The ID of the carrier to retrieve the trip for.
        :param trip_id: The ID of the trip to retrieve.
        :return: The trip data.
        """

        logger.debug(f"Getting trip for carrier_id={carrier_id}, trip_id={trip_id}")
        endpoint = f"/carriers/by-callsign/{carrier_id}/{trip_id}"

        logger.debug(f"Sending GET request to {endpoint}")
        try:
            trip_data = await self._request("GET", endpoint)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Trip not found for carrier_id={carrier_id}, trip_id={trip_id}")
                return None
            raise
        logger.debug(f"Trip data retrieved: {trip_data}")

        return BoozeCarrier(trip_data)

    async def get_carrier_stats(self, carrier_id: str, include_not_unloaded: bool | None = None) -> CarrierStats | None:
        """
        Retrieves stats for a specific carrier.

        :param carrier_id: The ID of the carrier to retrieve stats for.
        :return: The carrier stats.
        """

        logger.debug(f"Getting carrier stats for carrier_id={carrier_id}")
        endpoint = f"/carriers/by-callsign/{carrier_id}/stats"

        data = {"include_not_unloaded": include_not_unloaded} if include_not_unloaded is not None else {}

        logger.debug(f"Sending GET request to {endpoint}")
        try:
            stats_data = await self._request("GET", endpoint, data, PayloadType.QUERY)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Carrier stats not found for carrier_id={carrier_id}")
                return None
            raise
        logger.debug(f"Carrier stats retrieved: {stats_data}")

        return CarrierStats(stats_data)

    async def get_unpinged_signups(self) -> list[BoozeCarrier]:
        """
        Retrieves a list of unpinged signups from the BoozeSheets API.

        :return: A list of carriers that the owners need pinged for.
        """

        logger.debug("Getting info for unpinged signups")
        endpoint = "/carriers"
        data = {"owner_pinged": False, "pending": True}

        logger.debug(f"Sending GET request to {endpoint} with data={data}")
        carriers_info = await self._request("GET", endpoint, data, PayloadType.QUERY)
        logger.debug(f"Unpinged signups info retrieved: {carriers_info}")
        return [BoozeCarrier(info) for info in carriers_info]

    async def set_user_pinged(self, user_id: int) -> None:
        """
        Sets a user as having been pinged.

        :param user_id: The Discord ID of the user to set as pinged.
        """

        logger.debug(f"Setting user_id={user_id} as pinged")
        endpoint = f"/users/{user_id}/pinged"

        logger.debug(f"Sending POST request to {endpoint}")
        try:
            await self._request("POST", endpoint)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to set user_id={user_id} as pinged: {e}")
        logger.debug(f"User_id={user_id} set as pinged")

    async def get_all_time_stats(self) -> CruiseStats | None:
        """
        Retrieves all-time stats from the BoozeSheets API.

        :return: A dictionary containing all-time stats.
        """

        logger.debug("Getting all-time stats")
        endpoint = "/cruises/all_time"

        logger.debug(f"Sending GET request to {endpoint}")
        try:
            stats_data = await self._request("GET", endpoint)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get all-time stats: {e}")
            return None
        logger.debug(f"All-time stats retrieved: {stats_data}")

        return CruiseStats(stats_data)

    async def update_cruise_state(self, state: CruiseSystemState):
        """
        Update the current cruise state in BoozeSheets.

        :param state: The new cruise state.
        """

        logger.debug(f"Updating cruise state to {state}")
        endpoint = "/cruises/state"
        data = {"state": state}

        await self._request("PATCH", endpoint, data, PayloadType.BODY)
        logger.debug(f"Cruise state updated to {state}")

    async def set_refresh_discord_data(self, user: User):
        """
        Set the refresh_discord_data flag for a user in BoozeSheets.

        :param user: The Discord user to set the flag for.
        """

        logger.debug(f"Setting refresh_discord_data for user_id={user.id}")
        endpoint = "/users/force-refresh"

        data = {"discord_id": str(user.id)}

        logger.debug(f"Sending POST request to {endpoint} with data={data}")
        try:
            await self._request("POST", endpoint, data, PayloadType.QUERY)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to set refresh_discord_data for user_id={user.id}: {e}")
        logger.debug(f"refresh_discord_data set for user_id={user.id}")

    async def update_cruise_start(self, cruise_start: datetime):
        """
        Update the current cruise start time in BoozeSheets. Called when PHCheck first succeeds.

        :param cruise_start: The new cruise start timestamp (tz-aware, UTC).
        """

        endpoint = "/cruises"
        data = {"ph_start": cruise_start.isoformat().replace("Z", "+00:00")}

        try:
            state = (await self.get_current_cruise_state())["state"]
        except Exception as e:
            logger.error(f"Failed to get current cruise state before updating cruise start: {e}")
            raise RuntimeError("Cannot update cruise start without knowing current cruise state") from e

        logger.debug(f"Current cruise state is {state}")
        if state in [CruiseSystemState.PREP, CruiseSystemState.ACTIVE]:
            logger.info(f"Updating current cruise start to {cruise_start}")
            await self._request("PATCH", endpoint, data, PayloadType.BODY)
        else:
            logger.error("Automatic cruise_start update called outside of prep or active.")
            raise RuntimeError("Cannot automatically set cruise_start outside of prep or active.")

    async def end_ph(self, cruise_end: datetime):
        """
        Update the current cruise end time in BoozeSheets. Called when PHCheck first fails.

        :param cruise_end: The new cruise start timestamp (tz-aware, UTC).
        """

        endpoint = "/cruises"
        data = {"ph_end": cruise_end.isoformat().replace("Z", "+00:00")}

        try:
            state = (await self.get_current_cruise_state())["state"]
        except Exception as e:
            logger.error(f"Failed to get current cruise state before updating cruise end: {e}")
            raise RuntimeError("Cannot update cruise end without knowing current cruise state") from e

        logger.debug(f"Current cruise state is {state}")
        if state == CruiseSystemState.ACTIVE:
            logger.info(f"Updating current cruise end to {cruise_end}")
            await self._request("PATCH", endpoint, data, PayloadType.BODY)
            await self.update_cruise_state(CruiseSystemState.ENDED)
        else:
            logger.error("Automatic cruise end update called outside of active.")
            raise RuntimeError("Cannot automatically close cruise outside of active.")

    """
    Websocket stuff
    """

    async def start_websocket_listener(self):
        """
        Start the websocket connection and begin listening for events.
        This should be called after the bot is ready.
        """
        if self._ws_running:
            logger.warning("Websocket listener is already running")
            return

        if not self.bot:
            logger.error("Cannot start websocket listener without bot instance")
            raise RuntimeError("Bot instance not set. Call set_bot() first.")

        self._ws_running = True
        self.ws_task = asyncio.create_task(self._websocket_loop())
        logger.info("Started BoozeSheets websocket listener")

    async def stop_websocket_listener(self):
        """
        Stop the websocket connection.
        """
        if not self._ws_running:
            logger.warning("Websocket listener is not running")
            return

        self._ws_running = False
        if self.ws_task:
            self.ws_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.ws_task
            self.ws_task = None

        if self.ws_client:
            await self.ws_client.aclose()
            self.ws_client = None

        logger.info("Stopped BoozeSheets websocket listener")

    async def _websocket_loop(self):
        """
        Main websocket connection loop with automatic reconnection.
        """
        max_reconnect_delay = 300
        while self._ws_running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                logger.info("Websocket loop cancelled")
                self._ws_connected = False
                self._ws_connection = None
                break
            except Exception as e:
                logger.exception(f"Websocket error: {e}")
                self._ws_connected = False
                self._ws_connection = None

                if self._ws_running:
                    logger.info(f"Reconnecting websocket in {self._reconnect_delay} seconds...")
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, max_reconnect_delay)
                else:
                    break

    async def _connect_and_listen(self):
        """
        Connect to the websocket and listen for events.
        """
        ws_url = f"{self.base_url.replace('http', 'ws')}ws/?api_key={BOOZESHEETS_API_KEY}"

        logger.info(f"Connecting to BoozeSheets websocket: {ws_url.split('?', maxsplit=1)[0]}")

        async with websockets.connect(uri=ws_url) as self._ws_connection:
            logger.info("Connected to BoozeSheets websocket")
            self._ws_connected = True
            self._reconnect_delay = 5

            async for message in self._ws_connection:
                logger.trace(f"Websocket message received: {message}")

                if not self._ws_running:
                    break

                try:
                    self._last_ws_message_time = datetime.now(tz=UTC)
                    await self._handle_websocket_message(message)
                except Exception as e:
                    logger.error(f"Error handling websocket message: {e}", exc_info=True)

    async def _handle_websocket_message(self, message: str):
        """
        Handle incoming websocket messages and dispatch them as Discord bot events.

        :param message: The raw websocket message.
        """
        try:
            data = json.loads(message)
            event_type = data.get("type") or data.get("event")

            if not event_type:
                logger.warning(f"Received message without event type: {data}")
                return

            logger.debug(f"Received websocket event: {event_type}")

            try:
                await self._carrier_cache_ws_update(event_type, data)
            except Exception:
                # Catch to allow event dispatch to continue even if cache update fails, but log the error
                logger.exception("Error updating carrier cache from websocket event")

            event_name = f"boozesheets_{event_type}"

            if self.bot:
                self.bot.dispatch(event_name, data)
                logger.debug(f"Dispatched event: on_{event_name}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode websocket message: {e}")
        except Exception as e:
            logger.error(f"Error in websocket message handler: {e}", exc_info=True)

    def get_websocket_status(self) -> tuple[str, datetime | None]:
        """
        Get the current status of the websocket connection.

        :return: A tuple containing the connection status and the timestamp of the last received message.
        """
        status = "Connected" if self._ws_connected else "Disconnected"
        return status, self._last_ws_message_time

    def get_carrier_poll_status(self) -> tuple[str, datetime | None, int]:
        """
        Get the current status of the carrier polling loop and cache.

        :return: A tuple containing poll status, last refresh timestamp, and cache size.
        """
        status = "Running" if self._carrier_poll_running else "Stopped"
        return status, self._carrier_cache_last_refresh, len(self.carrier_cache)

    async def send_action_ack(self, action_id: str, success: bool = True, error: str | None = None) -> None:
        """
        Send an action acknowledgement back to the BoozeSheets API over the active WebSocket
        connection so that a pending HTTP request (e.g. POST /carriers/{id}/departure) can be
        resolved and returned to the web UI caller.

        :param action_id: The UUID that was included in the original WS request payload.
        :param success: Whether the action was completed successfully.
        :param error: Optional error message when success is False.
        """
        if self._ws_connection is None:
            logger.error(f"Cannot send action_ack for action_id={action_id}: no active WebSocket connection")
            return

        payload = json.dumps({"type": "action_ack", "actionId": action_id, "success": success, "error": error})
        try:
            await self._ws_connection.send(payload)
            logger.debug(f"Sent action_ack: action_id={action_id}, success={success}")
        except Exception as e:
            logger.error(f"Failed to send action_ack for action_id={action_id}: {e}")


booze_sheets_api = BoozeSheetsApi()
