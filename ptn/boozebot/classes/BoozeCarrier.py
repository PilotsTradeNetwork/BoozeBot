
from ptn.boozebot.constants import CARRIER_ID_RE


class BoozeCarrier:

    COMPARISON_KEYS = ["carrier_name", "wine_total", "carrier_identifier", "discord_username", "run_count"]

    def __init__(self, info_dict=None):
        """
        Class represents a carrier object as returned from the database.

        :param sqlite3.Row info_dict: A single row from the sqlite query.
        """

        if info_dict:
            # Convert the sqlite3.Row object to a dictionary
            info_dict = dict(info_dict)
        else:
            info_dict = dict()

        # Because we also pass a DB object, we should also covert those to the same fields
        self.carrier_name = info_dict.get("Carrier Name", None) or info_dict.get("carriername", None)

        if self.carrier_name:
            self.carrier_name = str(self.carrier_name)

        self.wine_total = info_dict.get("Wine Total (tons)", None) or info_dict.get("winetotal", None)

        if self.wine_total:
            try:
                self.wine_total = int(self.wine_total)
            except ValueError:
                self.wine_total = None

        self.carrier_identifier = info_dict.get("Carrier ID", None) or info_dict.get("carrierid", None)
        if self.carrier_identifier:
            # Cast the carrier ID to upper case for consistency
            self.carrier_identifier = str(self.carrier_identifier).upper()

            # make sure it matches the regex
            if not CARRIER_ID_RE.fullmatch(self.carrier_identifier):
                raise ValueError(f"Incompatible carrier ID found: {self.carrier_identifier} - {self.carrier_name}")

        self.platform = "PC (Horizons + Odyssey)"

        # We no longer track whether a carrier is associated with PTN in an official capacity or not. Since the DB
        # still contains this field, set it to False for now and phase it out
        self.ptn_carrier = False

        self.discord_username = info_dict.get("Discord Username", None) or info_dict.get("discordusername", None)

        if self.discord_username:
            self.discord_username = str(self.discord_username)

        self.timestamp = info_dict.get("Timestamp", None) or info_dict.get("timestamp", None)

        # This being set that an unload is ongoing
        self.discord_unload_notification = info_dict.get("discord_unload_in_progress", None)
        # Discord unload poster ID, the user who posted the unload notification
        self.discord_unload_poster_id = info_dict.get("discord_unload_poster_id", None)

        # Track number of runs the carrier completed
        self.run_count = info_dict.get("run_count", None) or info_dict.get("runtotal", None)
        if self.carrier_name and not self.run_count:
            # Increment to 1 in the case of a carrier name without a run count defined
            self.run_count = 1

        # How many unloading operations are completed.
        self.total_unloads = info_dict.get("totalunloads", None)
        if self.carrier_name and not self.total_unloads:
            # Set to 0 in the case of a carrier name without a total unloads value defined
            self.total_unloads = 0

        # A UTC representation of when the user usually is available. We use UTC as we need a common reference time,
        # and game time works for that.
        self.timezone = info_dict.get("user_timezone_in_utc", None)

        # The faction state that the peak was in during the booze cruise, for historical records
        self.faction_state = info_dict.get("faction_state", None)

    def get_unload_stats(self, include_not_unloaded: bool = True) -> tuple[int, int]:
        if include_not_unloaded:
            return self.wine_total, self.run_count

        else:
            unloaded_wine = int(self.wine_total / self.run_count * self.total_unloads)
            return unloaded_wine, self.total_unloads

    def to_dictionary(self):
        """
        Formats the carrier data into a dictionary for easy access.

        :returns: A dictionary representation for the carrier data.
        :rtype: dict
        """
        response = {}
        for key, value in vars(self).items():
            if value is not None:
                response[key] = value
        return response

    def __str__(self):
        """
        Overloads str to return a readable object

        :rtype: str
        """
        return (
            'BoozeCarrier: CarrierName:"{0.carrier_name}" WineTotal:{0.wine_total} '
            'CarrierIdentifier:"{0.carrier_identifier}" Platform:{0.platform} '
            'DiscordUser:{0.discord_username} AddedAt:"{0.timestamp}" RunCount: {0.run_count} TotalUnloads: '
            '{0.total_unloads} TimeZone:{0.timezone} DiscordUnload: {0.discord_unload_notification}"'.format(self)
        )

    def __bool__(self):
        """
        Override boolean to check if any values are set, if yes then return True, else False, where false is an empty
        class.

        :rtype: bool
        """
        return any(
            [
                value
                for key, value in vars(self).items()
                if key not in ["timestamp", "platform", "discord_unload_poster_id"] and value
            ]
        )

    def __eq__(self, other):
        """
        Override for equality check.

        :returns: The boolean state
        :rtype: bool
        """
        if isinstance(other, BoozeCarrier):
            return all(getattr(self, key) == getattr(other, key) for key in self.COMPARISON_KEYS)
        return False
