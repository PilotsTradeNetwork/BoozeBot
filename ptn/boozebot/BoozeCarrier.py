import re


class BoozeCarrier:

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
        self.carrier_name = info_dict.get('Carrier Name', None) or info_dict.get('carriername', None)
        self.wine_total = info_dict.get('Wine Total (tons)', None) or info_dict.get('winetotal', None)
        self.carrier_identifier = info_dict.get('Carrier ID', None) or info_dict.get('carrierid', None)
        if self.carrier_identifier:
            # Cast the carrier ID to upper case for consistency
            self.carrier_identifier = self.carrier_identifier.upper()

            # make sure it matches the regex
            if not re.match(r"\w{3}-\w{3}", self.carrier_identifier):
                raise ValueError(f'Incompatible carrier ID found: {self.carrier_identifier} - {self.carrier_name}')

        self.platform = info_dict.get("Carrier Owner's Platform", None) or info_dict.get('platform', None)

        # Assume we have a carrier name, then this is a False object, else None
        self.ptn_carrier = None if not self.carrier_name else False

        # This is a bit of a pain, but it is easier to read than embedding them.
        if info_dict.get('Carrier Affiliation', None) == 'P.T.N. Official Carrier' or \
                info_dict.get('officialcarrier', None):
            self.ptn_carrier = True

        self.discord_username = info_dict.get('Discord Username', None) or info_dict.get('discordusername', None)
        self.timestamp = info_dict.get('Timestamp', None) or info_dict.get('timestamp', None)

        # This being set that an unload is ongoing
        self.discord_unload_notification = info_dict.get('discord_unload_in_progress', None)

        # Track number of runs the carrier completed
        self.run_count = info_dict.get('run_count', 1)

        # How many unloading operations are completed.
        self.total_unloads = info_dict.get('totalunloads', 1)

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
        return 'BoozeCarrier: CarrierName:"{0.carrier_name}" WineTotal:{0.wine_total} ' \
               'CarrierIdentifier:"{0.carrier_identifier}" Platform:{0.platform} PTNCarrier:{0.ptn_carrier} ' \
               'DiscordUser:{0.discord_username} AddedAt:"{0.timestamp} RunCount: {0.run_count} ' \
               'DiscordUnload: {0.discord_unload_notification}"'.format(self)

    def __bool__(self):
        """
        Override boolean to check if any values are set, if yes then return True, else False, where false is an empty
        class.

        :rtype: bool
        """
        return any([value for key, value in vars(self).items() if value])

    def __eq__(self, other):
        """
        Override for equality check.

        :returns: The boolean state
        :rtype: bool
        """
        if isinstance(other, BoozeCarrier):
            return self.__dict__ == other.__dict__
        return False
