from datetime import datetime
from typing import Any, override

import discord
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.modules.helpers import sane_default_datetime, sane_default_duration

logger = get_logger("boozebot.classes.boozecarrier")


class CarrierOwner:
    display_name: str | None
    discord_id: int
    is_role: bool
    mention: str | None
    username: str | None
    scopes: list[str]

    def __init__(self, info_dict: dict[str, Any]):
        """
        Class represents a carrier owner object as returned from the api.

        :param info_dict: The dictionary containing the carrier owner information.
        """

        logger.debug(f"Initializing CarrierOwner with info_json: {info_dict}")

        self.username = info_dict.get("username")
        self.display_name = info_dict.get("displayName")
        discord_id = info_dict.get("discordId")
        if discord_id:
            if discord_id.startswith("&"):
                self.discord_id = int(discord_id[1:])
                self.is_role = True
                self.mention = f"<@&{self.discord_id}>"
            else:
                self.discord_id = int(discord_id)
                self.is_role = False
                self.mention = f"<@{self.discord_id}>"
        else:
            self.discord_id = 0
            self.is_role = False
            self.mention = None

        self.scopes = info_dict.get("scopes", [])

        logger.debug(
            f"CarrierOwner initialized: username={self.username}, discord_id={self.discord_id}, "
            + f"display_name={self.display_name}"
        )

    @override
    def __str__(self) -> str:
        """
        Overloads str to return a readable object

        :rtype: str
        """
        return f"CarrierOwner(): {self.username}, ({self.discord_id})"


class SignupInfo:
    first_time: bool
    notes: str | None
    color: str
    status: str | None

    def __init__(self, info_dict: dict[str, Any]):
        """
        Class represents signup information about a carrier as returned from the api.

        :param info_dict: The dictionary containing the signup information.
        """

        self.status = info_dict.get("status")
        self.color = info_dict.get("color", "000000")
        self.notes = info_dict.get("notes")
        self.first_time = info_dict.get("firstTime", True)


class BoozeCarrier:
    unload_closed: datetime | None
    unload_opened: datetime | None
    availability_end: datetime | None
    availability_start: datetime | None
    status: str | None
    wine_status: str | None
    wine_total: int
    trip_id: int
    cruise_id: int
    owner: CarrierOwner
    queue_timestamp: datetime | None
    carrier_name: str | None
    carrier_identifier: str | None
    system: str | None
    body: str | None
    staff_comment: str | None
    swap_with: str | None
    plotted_body: str | None
    plotted_system: str | None
    in_queue: bool
    db_id: int
    unload_duration: float | None
    signup_info: SignupInfo | None

    def __init__(self, info_dict: dict[str, Any]):
        """
        Class represents a carrier object as returned from the api.

        :param info_dict: The dictionary containing the carrier information.
        """

        logger.debug(f"Initializing BoozeCarrier with info_json: {info_dict}")

        fc_data = info_dict.get("fcData", {})

        self.db_id = int(info_dict.get("fcId", 0))

        # FC data
        self.carrier_name = fc_data.get("fcName", None)
        self.carrier_identifier = fc_data.get("fcCallsign", None)
        self.system = fc_data.get("currentSystem", None)
        self.body = fc_data.get("currentBody", None)
        self.in_queue = bool(fc_data.get("isInQueue", False))
        self.plotted_system = fc_data.get("plottedSystem", None)
        self.plotted_body = fc_data.get("plottedBody", None)
        self.swap_with = fc_data.get("swapWith", None)
        self.queue_timestamp = sane_default_datetime(fc_data.get("queueTs", None))
        self.staff_comment = fc_data.get("staffComment", None)

        # Owner data
        self.owner = CarrierOwner(fc_data.get("owner", {}))

        # Notable info
        if "notable" in info_dict and info_dict.get("notable"):
            self.signup_info = SignupInfo(info_dict.get("notable"))
        else:
            self.signup_info = None

        # Trip data
        self.cruise_id = int(info_dict.get("cruiseId", 0))
        self.trip_id = int(info_dict.get("tripId", 0))
        self.wine_total = int(info_dict.get("wineTotal", 0))
        self.wine_status = info_dict.get("wineStatus")
        self.status = info_dict.get("status")
        self.availability_start = sane_default_datetime(info_dict.get("availabilityStart"))
        self.availability_end = sane_default_datetime(info_dict.get("availabilityEnd"))
        self.unload_opened = sane_default_datetime(info_dict.get("unloadOpened"))
        self.unload_closed = sane_default_datetime(info_dict.get("unloadClosed"))
        self.unload_duration = sane_default_duration(info_dict.get("unloadDur"))

        logger.debug(
            f"BoozeCarrier initialized: carrier_name={self.carrier_name}, carrier_identifier={self.carrier_identifier}, "
            + f"system={self.system}, body={self.body}, in_queue={self.in_queue}, plotted_system={self.plotted_system}, "
            + f"plotted_body={self.plotted_body}, swap_with={self.swap_with}, queue_timestamp={self.queue_timestamp}, "
            + f"staff_comment={self.staff_comment}, owner_username={self.owner.username}, owner_discord_id={self.owner.discord_id}, "
            + f"owner_display_name={self.owner.display_name}, cruise_id={self.cruise_id}, trip_id={self.trip_id}, "
            + f"wine_total={self.wine_total}, wine_status={self.wine_status}, status={self.status}, "
            + f"availability_start={self.availability_start}, availability_end={self.availability_end}, "
            + f"unload_opened={self.unload_opened}, unload_closed={self.unload_closed}, unload_duration={self.unload_duration}"
        )

    @property
    def location_string(self) -> str:
        """
        Returns a formatted string of the carrier's current location.

        :returns: A string representing the carrier's current location.
        :rtype: str
        """

        if self.system and self.body:
            return f"{self.system} - {self.body}"
        elif self.system:
            return self.system
        else:
            return "Unknown"

    @property
    def is_staff(self):
        """
        Checks if the carrier is a staff carrier.

        :returns: True if the carrier is a staff carrier, False otherwise.
        :rtype: bool
        """

        if set(self.owner.scopes) & {"Sommelier", "Connoisseur", "Old Grape"}:
            return True
        return False

    def to_dictionary(self):
        """
        Formats the carrier data into a dictionary for easy access.

        :returns: A dictionary representation for the carrier data.
        :rtype: dict
        """

        logger.debug(f"Converting BoozeCarrier '{self.carrier_name}' to dictionary.")

        response = {}
        for key, value in vars(self).items():
            if value is not None:
                response[key] = value

        logger.debug(f"BoozeCarrier dictionary representation: {response}")

        return response

    @override
    def __str__(self) -> str:
        """
        Overloads str to return a readable object

        :rtype: str
        """
        return "BoozeCarrier: (" + " ".join(f"{key}={value}" for key, value in vars(self).items()) + ")"

    def __bool__(self):
        """
        Override boolean to check if any values are set, if yes then return True, else False, where false is an empty
        class.

        :rtype: bool
        """

        logger.debug(f"Checking boolean state of BoozeCarrier '{self.carrier_name}'.")

        state = any([value for _key, value in vars(self).items()])

        logger.debug(f"BoozeCarrier '{self.carrier_name}' boolean state: {state}")

        return state

    def is_owned_by(self, user: discord.Member) -> bool:
        """
        Check if the carrier is owned by the given Discord ID.

        :param user: The Discord member to check ownership against.
        :return: True if the carrier is owned by the given Discord ID, False otherwise.
        """

        logger.debug(f"Checking ownership of BoozeCarrier '{self.carrier_name}' by user: {user}.")

        if self.owner.is_role:
            is_owner = any(role.id == self.owner.discord_id for role in user.roles)
        else:
            is_owner = user.id == self.owner.discord_id

        logger.debug(f"BoozeCarrier '{self.carrier_name}' owned by user {user}: {is_owner}")
        return is_owner


class CarrierStats:
    last_unload_date: datetime | None
    first_unload_date: datetime | None
    total_trips: int
    total_cruises: int
    total_wine: int
    total_credits: int
    owner: CarrierOwner
    name: str | None
    db_id: int

    def __init__(self, info_dict: dict[str, Any]) -> None:
        """
        Class represents carrier statistics as returned from the api.

        :param info_dict: The dictionary containing the carrier statistics information.
        """

        logger.debug(f"Initializing CarrierStats with info_json: {info_dict}")

        self.db_id = int(info_dict.get("fcId", 0))
        self.name = info_dict.get("fcName")
        self.owner = CarrierOwner(info_dict.get("owner", {}))
        self.total_wine = int(info_dict.get("totalWine", 0))
        self.total_cruises = int(info_dict.get("totalCruises", 0))
        self.total_trips = int(info_dict.get("totalTrips", 0))
        self.total_credits = int(info_dict.get("totalCredits", 0))
        self.first_unload_date = sane_default_datetime(info_dict.get("firstUnloadDate"))
        self.last_unload_date = sane_default_datetime(info_dict.get("lastUnloadDate"))
        logger.debug(
            f"CarrierStats initialized: carrier_name={self.name}, owner_username={self.owner.username}, owner_discord_id={self.owner.discord_id}, "
            + f"total_wine={self.total_wine}, total_cruises={self.total_cruises}, total_trips={self.total_trips}, "
            + f"first_unload_date={self.first_unload_date}, last_unload_date={self.last_unload_date}"
        )

    @override
    def __str__(self) -> str:
        """
        Overloads str to return a readable object
        :rtype: str
        """
        return "CarrierStats: (" + " ".join(f"{key}={value}" for key, value in vars(self).items()) + ")"
