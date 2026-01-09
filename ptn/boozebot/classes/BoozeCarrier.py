from datetime import datetime, timezone

import discord
from ptn_utils.logger.logger import get_logger

logger = get_logger("boozebot.classes.boozecarrier")


class BoozeCarrier:
    def __init__(self, info_dict: dict):
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
        self.queue_timestamp = fc_data.get("queueTs", None)
        if self.queue_timestamp:
            self.queue_timestamp = datetime.fromisoformat(self.queue_timestamp.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        self.staff_comment = fc_data.get("staffComment", None)

        # Owner data
        self.owner_username = fc_data.get("owner", {}).get("username", None)
        self.owner_discord_id = fc_data.get("owner", {}).get("discordId", 0)
        if self.owner_discord_id:
            if self.owner_discord_id.startswith("&"):
                self.owner_discord_id = int(self.owner_discord_id[1:])
                self.owner_is_role = True
                self.owner_mention = f"<@&{self.owner_discord_id}>"
            else:
                self.owner_discord_id = int(self.owner_discord_id)
                self.owner_is_role = False
                self.owner_mention = f"<@{self.owner_discord_id}>"
        self.owner_display_name = fc_data.get("owner", {}).get("displayName", None)

        # Trip data
        self.cruise_id = int(info_dict.get("cruiseId", 0))
        self.trip_id = int(info_dict.get("tripId", 0))
        self.wine_total = int(info_dict.get("wineTotal", 0))
        self.wine_status = info_dict.get("wineStatus", None)
        self.status = info_dict.get("status", None)
        self.availability_start = info_dict.get("availabilityStart", None)
        self.availability_end = info_dict.get("availabilityEnd", None)
        self.unload_opened = info_dict.get("unloadOpened", None)
        if self.unload_opened:
            self.unload_opened = datetime.fromisoformat(self.unload_opened.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        self.unload_closed = info_dict.get("unloadClosed", None)
        if self.unload_closed:
            self.unload_closed = datetime.fromisoformat(self.unload_closed.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        self.unload_duration = info_dict.get("unloadDur", None)

        logger.debug(
            f"BoozeCarrier initialized: carrier_name={self.carrier_name}, carrier_identifier={self.carrier_identifier}, "
            f"system={self.system}, body={self.body}, in_queue={self.in_queue}, plotted_system={self.plotted_system}, "
            f"plotted_body={self.plotted_body}, swap_with={self.swap_with}, queue_timestamp={self.queue_timestamp}, "
            f"staff_comment={self.staff_comment}, owner_username={self.owner_username}, owner_discord_id={self.owner_discord_id}, "
            f"owner_display_name={self.owner_display_name}, cruise_id={self.cruise_id}, trip_id={self.trip_id}, "
            f"wine_total={self.wine_total}, wine_status={self.wine_status}, status={self.status}, "
            f"availability_start={self.availability_start}, availability_end={self.availability_end}, "
            f"unload_opened={self.unload_opened}, unload_closed={self.unload_closed}, unload_duration={self.unload_duration}"
        )

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

    def __str__(self):
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

        state = any([value for key, value in vars(self).items()])

        logger.debug(f"BoozeCarrier '{self.carrier_name}' boolean state: {state}")

        return state

    def is_owned_by(self, user: discord.Member) -> bool:
        """
        Check if the carrier is owned by the given Discord ID.

        :param user: The Discord member to check ownership against.
        :return: True if the carrier is owned by the given Discord ID, False otherwise.
        """

        logger.debug(f"Checking ownership of BoozeCarrier '{self.carrier_name}' by user: {user}.")

        if self.owner_is_role:
            is_owner = any(role.id == self.owner_discord_id for role in user.roles)
        else:
            is_owner = user.id == self.owner_discord_id

        logger.debug(f"BoozeCarrier '{self.carrier_name}' owned by user {user}: {is_owner}")
        return is_owner
