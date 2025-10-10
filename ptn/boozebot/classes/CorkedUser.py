from ptn.boozebot.constants import bot


class CorkedUser:
    def __init__(self, info_dict=None):
        """
        Class represents a corked user object as returned from the database.

        :param sqlite3.Row info_dict: A single row from the sqlite query.
        """

        if info_dict:
            # Convert the sqlite3.Row object to a dictionary
            info_dict = dict(info_dict)
        else:
            info_dict = dict()

        self.user_id = info_dict.get("user_id", None)
        self.timestamp = info_dict.get("timestamp", None)

    def get_member(self):
        """
        Returns the discord.Member object for the corked user.

        :rtype: discord.Member | None
        """
        return bot.get_user(int(self.user_id))

    def __str__(self):
        """
        Overloads str to return a readable object

        :rtype: str
        """
        return f"Corked User: {self.user_id} at {self.timestamp}"
