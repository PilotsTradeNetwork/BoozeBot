from datetime import UTC, datetime
from typing import Any

from ptn_utils.logger.logger import get_logger

from ptn.boozebot.modules.helpers import sane_default_datetime, sane_default_float

logger = get_logger("boozebot.classes.cruise")


class CruiseStats:
    max_unload_dur: float | None
    min_unload_dur: float | None
    avg_unload_dur: float | None
    total_profit: int
    wine_remaining: int
    total_owners: int
    carriers_remaining: int
    total_carriers: int
    total_trips: int
    total_wine: int

    def __init__(self, info_dict: dict[str, Any]):
        """
        Class represents cruise statistics as returned from the api.

        :param info_dict: The dictionary containing the cruise statistics information.
        """

        logger.debug(f"Initializing CruiseStats with info_json: {info_dict}")

        self.total_wine = int(info_dict.get("totalWine", 0))
        self.total_trips = int(info_dict.get("totalTrips", 0))
        self.total_carriers = int(info_dict.get("totalCarriers", 0))
        self.carriers_remaining = int(info_dict.get("carriersRemaining", 0))
        self.total_owners = int(info_dict.get("totalCarrierOwners", 0))
        self.wine_remaining = int(info_dict.get("wineRemaining", 0))
        self.total_profit = int(info_dict.get("totalProfit", 0))
        self.avg_unload_dur = sane_default_float(info_dict.get("avgUnloadDur"))
        self.min_unload_dur = sane_default_float(info_dict.get("minUnloadDur"))
        self.max_unload_dur = sane_default_float(info_dict.get("maxUnloadDur"))

        logger.debug(
            f"CruiseStats initialized: total_wine={self.total_wine}, total_trips={self.total_trips}, "
            + f"total_carriers={self.total_carriers}, carriers_remaining={self.carriers_remaining}, "
            + f"wine_remaining={self.wine_remaining}, avg_unload_dur={self.avg_unload_dur}, "
            + f"min_unload_dur={self.min_unload_dur}, max_unload_dur={self.max_unload_dur}"
        )


class Cruise:
    stats: CruiseStats
    carrier_limit: int
    faction_state: str | None
    end: datetime
    start: datetime
    id: int

    def __init__(self, info_dict: dict[str, Any]):
        """
        Class represents cruise as returned from the api.
        :param info_dict: The dictionary containing the cruise information.
        """
        logger.debug(f"Initializing Cruise with info_json: {info_dict}")

        self.id = int(info_dict.get("cruiseId", 0))
        self.start = sane_default_datetime(info_dict.get("cruiseStart")) or datetime.min.replace(tzinfo=UTC)
        self.end = sane_default_datetime(info_dict.get("cruiseEnd")) or datetime.max.replace(tzinfo=UTC)

        self.faction_state = info_dict.get("factionState")
        self.carrier_limit = int(info_dict.get("carrierLimit", 0))
        self.stats = CruiseStats(info_dict.get("stats", {}))

        logger.debug(f"Cruise initialized with stats: {self.stats}")
