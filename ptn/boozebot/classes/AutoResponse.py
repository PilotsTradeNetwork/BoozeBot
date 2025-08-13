import re
import sqlite3
from datetime import datetime, timedelta

import discord

from ptn.boozebot.constants import (
    bot, get_steve_says_channel, server_connoisseur_role_id, server_council_role_ids, server_mod_role_id,
    server_sommelier_role_id
)


class AutoResponse:
    """
    Class representing an auto response in the database.

    Attributes:
        name (str) - The name of the auto response.
        trigger (str): The trigger phrase for the auto response.
        is_regex (bool): Whether the trigger is a regex pattern.
        response (str): The response message to send when the trigger is matched.
    """

    def __init__(self, info_dict: sqlite3.Row | dict | None = None):

        self.channel_cooldowns: dict[int, datetime] = {}

        if isinstance(info_dict, sqlite3.Row):
            info_dict = dict(info_dict)

        self.name = info_dict.get("name", "")
        self.is_regex = bool(info_dict.get("is_regex", False))
        self.response = info_dict.get("response", "")

        if self.is_regex:
            try:
                self.trigger = re.compile(info_dict.get("trigger", ""))
            except re.error as e:
                print(
                    f"Invalid regex pattern: {info_dict.get('trigger', '')}. Error: {e}"
                )
                steve_says_channel = bot.get_channel(get_steve_says_channel())
                steve_says_channel.send(
                    f"Invalid regex pattern in auto response '{self.name}': {info_dict.get('trigger', '')}. Error: {e}"
                )
                self.is_regex = False
                self.trigger = info_dict.get("trigger", "").lower()
        else:
            self.trigger = info_dict.get("trigger", "").lower()

    def to_tuple(self):
        """
        Convert the auto response to a tuple for pagination.

        :returns: A tuple containing the name, trigger and response.
        """

        trigger = (
            self.trigger if isinstance(self.trigger, str) else self.trigger.pattern
        )

        return (self.name, f"{trigger}\n{self.response}")

    def _on_cooldown(self, message: discord.Message) -> bool:
        """
        Check if the auto response is on cooldown for the given message channel.

        :param discord.Message message: The message to check.
        :returns: True if the auto response is on cooldown, False otherwise.
        """
        return datetime.now() < self.channel_cooldowns.get(
            message.channel.id, datetime.min
        )

    def _matches_name(self, message: discord.Message) -> bool:
        """
        Check if the message content matches the auto response name.

        :param discord.Message message: The message to check.
        :returns: True if the message matches the auto response name, False otherwise.
        """
        return f"!{self.name}" in message.content.lower()

    def _matches_trigger(self, message: discord.Message) -> bool:
        """
        Check if the message content matches the auto response trigger and user is not wine staff.

        :param discord.Message message: The message to check.
        :returns: True if the message matches the auto response trigger, False otherwise.
        """

        is_staff = {role.id for role in message.author.roles} & {
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
        }

        if is_staff:
            return False

        if self.is_regex:
            return re.search(self.trigger, message.content.lower()) is not None
        else:
            return self.trigger in message.content.lower()

    def matches(self, message: discord.Message) -> bool:
        """
        Check if the message content matches the trigger.

        :param str message_content: The content of the message to check.
        :returns: True if the message matches the trigger, False otherwise.
        """

        if not message.content:
            return False

        if self._on_cooldown(message):
            return False

        if self._matches_name(message) or self._matches_trigger(message):
            self.channel_cooldowns[message.channel.id] = datetime.now() + timedelta(
                seconds=60
            )
            return True
