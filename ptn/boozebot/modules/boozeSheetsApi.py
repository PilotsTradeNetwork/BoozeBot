from datetime import datetime
import httpx
import asyncio

from ptn.boozebot.constants import BOOZESHEETS_API_BASE_URL, BOOZESHEETS_API_KEY
from ptn.boozebot.classes.BoozeCarrier import BoozeCarrier
from ptn_utils.logger.logger import get_logger

logger = get_logger("boozebot.modules.boozeSheetsApi")


class BoozeSheetsApi:
    def __init__(self):
        self.base_url = BOOZESHEETS_API_BASE_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url, 
            cookies={"X-API-KEY": BOOZESHEETS_API_KEY},
            timeout=30.0
        )
        self.client_lock = asyncio.Lock()

    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """
        Internal method to send HTTP requests to the BoozeSheets API.

        :param method: The HTTP method (GET, POST, PATCH, DELETE, etc.)
        :param endpoint: The API endpoint to send the request to.
        :param data: The data to send in the request body or get params (optional).
        :return: The response from the API as a dictionary.
        """

        logger.debug(f"Sending {method} request to BoozeSheets API: endpoint={endpoint}, data={data}")
        async with self.client_lock:
            if method.upper() == "GET":
                response = await self.client.request(method, endpoint, params=data, follow_redirects=True)
            else:
                response = await self.client.request(method, endpoint, json=data, follow_redirects=True)
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Received response from BoozeSheets API: {response_data}")

        return response_data

    async def get_carrier_info(self, carrier_id: str) -> BoozeCarrier:
        """
        Retrieves carrier information from the BoozeSheets API.

        :param carrier_id: The ID of the carrier to retrieve information for.
        :return: The carrier information as a dictionary.
        """

        logger.debug(f"Getting carrier info for carrier_id={carrier_id}")
        carrier_id = carrier_id.upper()
        endpoint = f"/carriers/by-callsign/{carrier_id}"

        logger.debug(f"Sending GET request to {endpoint}")
        carrier_info = await self._request("GET", endpoint)
        logger.debug(f"Carrier info retrieved: {carrier_info}")

        carrier = BoozeCarrier(carrier_info)

        return carrier

    async def get_all_carriers_info(self) -> list[BoozeCarrier]:
        """
        Retrieves information for all carriers from the BoozeSheets API.

        :return: A list of carrier information dictionaries.
        """

        logger.debug("Getting info for all carriers")
        endpoint = "/carriers"

        logger.debug(f"Sending GET request to {endpoint}")
        carriers_info = await self._request("GET", endpoint)
        logger.debug(f"All carriers info retrieved: {carriers_info}")

        carriers = [BoozeCarrier(info) for info in carriers_info]

        return carriers

    async def update_carrier_info(self, carrier_id: str, update_data: dict) -> BoozeCarrier:
        """
        Updates carrier information in the BoozeSheets API.

        :param carrier_id: The ID of the carrier to update.
        :param update_data: The data to update for the carrier.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Updating carrier info for carrier_id={carrier_id}")
        endpoint = f"/carriers/{carrier_id}/admin"

        updated_carrier_info = await self._request("PATCH", endpoint, update_data)

        logger.debug(f"Carrier info updated: {updated_carrier_info}")

        updated_carrier = BoozeCarrier(updated_carrier_info)

        return updated_carrier

    async def start_carrier_unload(self, carrier_id: str, delay: int | None = None) -> BoozeCarrier:
        """
        Marks a carrier as having started unloading.

        :param carrier_id: The ID of the carrier to mark as unloading.
        :param delay: The delay in seconds before unloading starts.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Starting unload for carrier_id={carrier_id}, delay={delay}")
        endpoint = f"/carriers/{carrier_id}/unload?unloading=true"
        
        data = {"delay": delay} if delay is not None else None

        logger.debug(f"Sending POST request to {endpoint} with data={data}")
        updated_carrier = await self._request("POST", endpoint, data)
        logger.debug(f"Carrier unload started: {updated_carrier}")

        return BoozeCarrier(updated_carrier)

    async def complete_carrier_unload(self, carrier_id: str) -> BoozeCarrier:
        """
        Marks a carrier as having completed unloading.

        :param carrier_id: The ID of the carrier to mark as unloaded.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Completing unload for carrier_id={carrier_id}")
        endpoint = f"/carriers/{carrier_id}/unload?unloading=false"

        logger.debug(f"Sending POST request to {endpoint} with")
        updated_carrier = await self._request("POST", endpoint)
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
        carriers_info = await self._request("GET", endpoint, data=data)
        logger.debug(f"All carriers info retrieved: {carriers_info}")

        carriers = [BoozeCarrier(info) for info in carriers_info]

        return carriers

    async def get_cruise_stats(self, cruise_id: str, include_not_unloaded: bool = False) -> dict:
        """
        Retrieves stats for a specific cruise.

        :param cruise_id: The ID of the cruise to retrieve stats for.
        :param include_not_unloaded: Whether to include carriers that have not yet unloaded.
        :return: The cruise stats as a dictionary.
        """

        logger.debug(f"Getting cruise stats for cruise_id={cruise_id}, include_not_unloaded={include_not_unloaded}")
        all_cruises_endpoint = "/cruises"

        logger.debug(f"Sending GET request to {all_cruises_endpoint}")
        all_cruises = await self._request("GET", all_cruises_endpoint)
        logger.debug(f"All cruises retrieved: {all_cruises}")

        sorted_cruises = sorted(
            all_cruises, key=lambda x: datetime.fromisoformat(x.get("cruiseStart", "")), reverse=True
        )

        if cruise_id > len(sorted_cruises):
            logger.warning(f"Cruise ID {cruise_id} is out of range. Total cruises: {len(sorted_cruises)}")
            raise ValueError("Cruise ID is out of range.")
        actual_cruise_id = sorted_cruises[cruise_id].get("cruiseId", None)

        stats_endpoint = f"/cruises/{actual_cruise_id}"
        data = {"include_not_unloaded": include_not_unloaded}

        logger.debug(f"Sending GET request to {stats_endpoint} with data={data}")
        cruise_data = await self._request("GET", stats_endpoint, data)
        logger.debug(f"Cruise stats retrieved: {cruise_data}")

        return cruise_data.get("stats", {})

    async def get_biggest_cruise_stats(self, include_not_unloaded: bool = False) -> dict:
        """
        Retrieves the biggest cruise stats.
        :param include_not_unloaded: Whether to include carriers that have not yet unloaded.
        :return: The biggest cruise stats as a dictionary.
        """

        # TODO real endpoint when available

        logger.debug("Getting biggest cruise stats")
        cruises_endpoint = "/cruises"
        data = {"include_not_unloaded": include_not_unloaded}

        logger.debug("Getting biggest cruise stats")
        cruises = await self._request("GET", cruises_endpoint)
        logger.debug(f"All cruises retrieved: {cruises}")

        all_cruise_stats = []

        for cruise in cruises:
            cruise_id = cruise.get("cruiseId")
            if not cruise_id:
                continue
            cruise_stats_endpoint = f"/cruises/{cruise_id}"

            logger.debug(f"Sending GET request to {cruise_stats_endpoint} with data={data}")
            stats = await self._request("GET", cruise_stats_endpoint, data)
            logger.debug(f"Cruise stats retrieved: {stats}")
            all_cruise_stats.append(stats)

        biggest_cruise = max(all_cruise_stats, key=lambda x: x.get("stats", {}).get("totalWine", 0))
        logger.debug(f"Biggest cruise stats retrieved: {biggest_cruise}")

        return biggest_cruise.get("stats", {})
    
    async def get_trip_for_carrier(self, carrier_id: str, trip_id: str) -> dict:
        """
        Retrieves a specific trip for a specific carrier.

        :param carrier_id: The ID of the carrier to retrieve the trip for.
        :param trip_id: The ID of the trip to retrieve.
        :return: The trip data as a dictionary.
        """

        logger.debug(f"Getting trip for carrier_id={carrier_id}, trip_id={trip_id}")
        endpoint = f"/carriers/by-callsign/{carrier_id}/{trip_id}"

        logger.debug(f"Sending GET request to {endpoint}")
        trip_data = await self._request("GET", endpoint)
        logger.debug(f"Trip data retrieved: {trip_data}")

        return BoozeCarrier(trip_data)

    async def get_carrier_stats(self, carrier_id: str) -> dict:
        """
        Retrieves stats for a specific carrier.

        :param carrier_id: The ID of the carrier to retrieve stats for.
        :return: The carrier stats as a dictionary.
        """

        # TODO implement when endpoint is available
        return {
            "carrierName": "Carrier XYZ",
            "owner": {"discordId": 123456789, "name": "OwnerName", "displayName": "Owner Display Name"},
            "carrierId": carrier_id,
            "totalWine": 20000,
            "totalCruises": 2,
            "totalTrips": 3,
            "firstUnload_date": "01/01/2024",
            "lastUnload_date": "01/01/2025",
        }

booze_sheets_api = BoozeSheetsApi()
