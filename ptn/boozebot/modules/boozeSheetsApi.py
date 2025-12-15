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
        self.client = httpx.AsyncClient(base_url=self.base_url)
        self.client_lock = asyncio.Lock()

    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """
        Internal method to send HTTP requests to the BoozeSheets API.

        :param method: The HTTP method (GET, POST, PATCH, DELETE, etc.)
        :param endpoint: The API endpoint to send the request to.
        :param data: The data to send in the request body (optional).
        :return: The response from the API as a dictionary.
        """

        headers = {"Cookie": f"{BOOZESHEETS_API_KEY}", "Content-Type": "application/json"}

        logger.debug(f"Sending {method} request to BoozeSheets API: endpoint={endpoint}, data={data}")
        async with self.client_lock:
            response = await self.client.request(method, endpoint, headers=headers, json=data)
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

        all_carriers = await self.get_all_carriers_info()
        for carrier in all_carriers:
            if carrier.carrier_identifier == carrier_id:
                return carrier
        return None

        logger.debug(f"Getting carrier info for carrier_id={carrier_id}")
        endpoint = f"/carriers/{carrier_id}"
        carrier_info = await self._request("GET", endpoint)

        logger.debug(f"Carrier info retrieved: {carrier_info}")

        carrier = BoozeCarrier(carrier_info)

        return carrier

    async def get_all_carriers_info(self) -> list[BoozeCarrier]:
        """
        Retrieves information for all carriers from the BoozeSheets API.

        :return: A list of carrier information dictionaries.
        """

        endpoint = "/carriers"

        logger.debug("Getting info for all carriers")
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
        endpoint = f"/carrier/{carrier_id}/admin"

        updated_carrier_info = await self._request("PATCH", endpoint, update_data)

        logger.debug(f"Carrier info updated: {updated_carrier_info}")

        updated_carrier = BoozeCarrier(updated_carrier_info)

        return updated_carrier

    async def get_unloading_carriers(self) -> list[BoozeCarrier]:
        """
        Retrieves a list of carriers that are currently unloading.

        :return: A list of carrier information dictionaries.
        """

        endpoint = "/carriers/unloading"

        logger.debug("Getting unloading carriers")
        unloading_carriers_info = await self._request("GET", endpoint)

        logger.debug(f"Unloading carriers info retrieved: {unloading_carriers_info}")

        unloading_carriers = [BoozeCarrier(info) for info in unloading_carriers_info]

        return unloading_carriers

    async def start_carrier_unload(self, carrier_id: str, timed: bool = False) -> BoozeCarrier:
        """
        Marks a carrier as having started unloading.

        :param carrier_id: The ID of the carrier to mark as unloading.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Starting unload for carrier_id={carrier_id}, timed={timed}")
        endpoint = f"/carrier/{carrier_id}/unload/"

        data = {"state": "unloading", "timed": timed}

        # updated_carrier_info = await self._request("POST", endpoint, data) TODO actually implement
        updated_carrier = await self.get_carrier_info(carrier_id)
        # logger.debug(f"Carrier unload started: {updated_carrier_info}")

        # updated_carrier = BoozeCarrier(updated_carrier_info)

        return updated_carrier

    async def complete_carrier_unload(self, carrier_id: str) -> BoozeCarrier:
        """
        Marks a carrier as having completed unloading.

        :param carrier_id: The ID of the carrier to mark as unloaded.
        :return: The updated carrier information as a dictionary.
        """

        logger.debug(f"Completing unload for carrier_id={carrier_id}")
        endpoint = f"/carrier/{carrier_id}/unload/"
        data = {"state": "unloaded"}

        # updated_carrier_info = await self._request("POST", endpoint, data) TODO actually implement
        updated_carrier = await self.get_carrier_info(carrier_id)

        # logger.debug(f"Carrier unload completed: {updated_carrier_info}")

        # updated_carrier = BoozeCarrier(updated_carrier_info)

        return updated_carrier

    async def get_carriers_with_wine_remaining(self) -> list[BoozeCarrier]:
        """
        Retrieves a list of carriers that have wine remaining.

        :return: A list of carrier information dictionaries.
        """

        return []  # TODO implement

    async def get_cruise_stats(self, cruise_id: str, include_not_unloaded: bool = False) -> dict:
        """
        Retrieves stats for a specific cruise.

        :param cruise_id: The ID of the cruise to retrieve stats for.
        :return: The cruise stats as a dictionary.
        """

        # TODO implement
        return {
            "date": "01/01/2025",
            "totalWine": 1000000,
            "totalTrips": 100,
            "totalCarriers": 50,
            "carriersRemaining": 10,
            "wineRemaining": 200000,
            "state": "Public Holiday",
        }

    async def get_biggest_cruise_stats(self) -> dict:
        """
        Retrieves the biggest cruise stats.

        :return: The biggest cruise stats as a dictionary.
        """

        # TODO implement
        return {
            "date": "01/01/2025",
            "totalWine": 1000000,
            "totalTrips": 100,
            "totalCarriers": 50,
            "carriersRemaining": 10,
            "wineRemaining": 200000,
            "state": "Public Holiday",
        }

    async def get_carrier_stats(self, carrier_id: str) -> dict:
        """
        Retrieves stats for a specific carrier.

        :param carrier_id: The ID of the carrier to retrieve stats for.
        :return: The carrier stats as a dictionary.
        """

        # TODO implement
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
