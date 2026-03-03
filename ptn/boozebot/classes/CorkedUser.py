from datetime import datetime
from typing import override

from discord import Member
from ptn_utils.logger.logger import get_logger

from ptn.boozebot.constants import bot

logger = get_logger("boozebot.classes.corkeduser")


class CorkedUser:
    user_id: int | None
    timestamp: datetime | None

    def __init__(self, info_dict: dict[str, int | datetime] = None) -> None:
        """
        Class represents a corked user object as returned from the database.

        :param sqlite3.Row info_dict: A single row from the sqlite query.
        """

        info_dict = dict(info_dict) if info_dict else {}
        logger.debug(f"Initializing CorkedUser with info_dict: {info_dict}")

        self.user_id = info_dict.get("user_id")
        self.timestamp = info_dict.get("timestamp")

        logger.debug(f"CorkedUser initialized: user_id={self.user_id}, timestamp={self.timestamp}")

    async def get_member(self) -> Member | None:
        """
        Returns the discord.Member object for the corked user.

        :rtype: discord.Member | None
        """
        logger.debug(f"Fetching member for corked user ID: {self.user_id}. Database timestamp: {self.timestamp}")
        return await bot.get_or_fetch.member(self.user_id)

    @override
    def __str__(self) -> str:
        """
        Overloads str to return a readable object

        :rtype: str
        """
        return f"Corked User: {self.user_id} at {self.timestamp}"
