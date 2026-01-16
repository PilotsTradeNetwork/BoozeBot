from datetime import datetime

from ptn_utils.logger.logger import get_logger

logger = get_logger("boozebot.classes.cruise")


class Cruise:
    def __init__(self, info_dict: dict):
        """
        Class represents cruise as returned from the api.
        :param info_dict: The dictionary containing the cruise information.
        """
        logger.debug(f"Initializing Cruise with info_json: {info_dict}")

        self.id = int(info_dict.get("cruiseId", 0))
        self.start = info_dict.get("cruiseStart", None)
        if self.start:
            self.start = datetime.fromisoformat(self.start.replace("Z", "+00:00"))
        self.end = info_dict.get("cruiseEnd", None)
        if self.end:
            self.end = datetime.fromisoformat(self.end.replace("Z", "+00:00"))
        self.faction_state = info_dict.get("factionState", None)
        self.carrier_limit = int(info_dict.get("carrierLimit", 0))
        self.stats = CruiseStats(info_dict.get("stats", {}))

        logger.debug(f"Cruise initialized with stats: {self.stats}")


class CruiseStats:
    def __init__(self, info_dict: dict):
        """
        Class represents cruise statistics as returned from the api.

        :param info_dict: The dictionary containing the cruise statistics information.
        """

        logger.debug(f"Initializing CruiseStats with info_json: {info_dict}")

        self.total_wine = int(info_dict.get("totalWine", 0))
        self.total_trips = int(info_dict.get("totalTrips", 0))
        self.total_carriers = int(info_dict.get("totalCarriers", 0))
        self.carriers_remaining = int(info_dict.get("carriersRemaining", 0))
        self.wine_remaining = int(info_dict.get("wineRemaining", 0))
        self.avg_unload_dur = info_dict.get("avgUnloadDur", None)
        if self.avg_unload_dur is not None:
            self.avg_unload_dur = float(self.avg_unload_dur)
        self.min_unload_dur = info_dict.get("minUnloadDur", None)
        if self.min_unload_dur is not None:
            self.min_unload_dur = float(self.min_unload_dur)
        self.max_unload_dur = info_dict.get("maxUnloadDur", None)
        if self.max_unload_dur is not None:
            self.max_unload_dur = float(self.max_unload_dur)

        logger.debug(
            f"CruiseStats initialized: total_wine={self.total_wine}, total_trips={self.total_trips}, "
            f"total_carriers={self.total_carriers}, carriers_remaining={self.carriers_remaining}, "
            f"wine_remaining={self.wine_remaining}, avg_unload_dur={self.avg_unload_dur}, "
            f"min_unload_dur={self.min_unload_dur}, max_unload_dur={self.max_unload_dur}"
        )
