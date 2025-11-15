import re
import sqlite3
from datetime import datetime, timedelta
from loguru import logger

from discord import Message
from ptn.boozebot.constants import (
    server_connoisseur_role_id, server_council_role_ids, server_mod_role_id,
    server_sommelier_role_id
)

class AutoResponse:
    """
    Class representing an auto response in the database.

    Attributes:
        name (str) - The name of the auto response.
        trigger (str | re.Pattern): The trigger phrase for the auto response.
        is_regex (bool): Whether the trigger is a regex pattern.
        response (str): The response message to send when the trigger is matched.
    """

    def __init__(self, info_dict: sqlite3.Row | dict):

        if isinstance(info_dict, sqlite3.Row):
            info_dict = dict(info_dict)
            
        logger.debug(f"Initializing AutoResponse with info_dict: {info_dict}")

        self.channel_cooldowns: dict[int, datetime] = {}

        self.name = info_dict.get("name", "")
        self.is_regex = bool(info_dict.get("is_regex", False))
        self.response = info_dict.get("response", "")
        self.trigger: str | re.Pattern = info_dict.get("trigger", "").lower()

        if self.is_regex:
            logger.debug(f"Compiling regex trigger for auto response '{self.name}': {self.trigger}")
            try:
                self.trigger = re.compile(info_dict.get("trigger", ""))
                logger.debug(f"Compiled regex trigger for auto response '{self.name}': {self.trigger.pattern}")
            except re.error:
                logger.error(f"Invalid regex pattern for auto response '{self.name}': {info_dict.get('trigger', '')}. Falling back to empty trigger.")
                self.trigger = info_dict.get("trigger", "")
                self.is_regex = False
                
        logger.debug(f"AutoResponse initialized: name={self.name}, is_regex={self.is_regex}, trigger={self.trigger}, response={self.response}")

    def to_tuple(self):
        """
        Convert the auto response to a tuple for pagination.

        :returns: A tuple containing the name, trigger and response.
        """

        trigger = self.trigger if isinstance(self.trigger, str) else self.trigger.pattern
        logger.debug(f"Converting AutoResponse '{self.name}' to tuple with trigger: {trigger} and response: {self.response}")
        return self.name, f"{trigger}\n{self.response}"

    def _on_cooldown(self, message: Message) -> bool:
        """
        Check if the auto response is on cooldown for the given message channel.

        :param Message message: The message to check.
        :returns: True if the auto response is on cooldown, False otherwise.
        """
        logger.debug(f"Checking cooldown for AutoResponse '{self.name}' in channel ID: {message.channel.id}")
        is_on_cooldown = datetime.now() < self.channel_cooldowns.get(message.channel.id, datetime.min)
        expires_at = self.channel_cooldowns.get(message.channel.id, 'N/A')
        logger.debug(f"AutoResponse '{self.name}' on cooldown: {is_on_cooldown}. Cooldown expires at: {expires_at}")
        return is_on_cooldown

    def _matches_name(self, message: Message) -> bool:
        """
        Check if the message content matches the auto response name.

        :param Message message: The message to check.
        :returns: True if the message matches the auto response name, False otherwise.
        """
        logger.debug(f"Checking name match for AutoResponse '{self.name}' in message content.")
        matches_name = f"!{self.name}" in message.content.lower()
        logger.debug(f"AutoResponse '{self.name}' name match: {matches_name}")
        return matches_name

    def _matches_trigger(self, message: Message) -> bool:
        """
        Check if the message content matches the auto response trigger and user is not wine staff.

        :param Message message: The message to check.
        :returns: True if the message matches the auto response trigger, False otherwise.
        """

        logger.debug(f"Checking trigger match for AutoResponse '{self.name}' in message content.")
        
        is_staff = {role.id for role in message.author.roles} & {
            *server_council_role_ids(),
            server_mod_role_id(),
            server_sommelier_role_id(),
            server_connoisseur_role_id(),
        }

        if is_staff:
            logger.debug(f"User {message.author.id} is wine staff; skipping AutoResponse '{self.name}' trigger match.")
            return False

        if isinstance(self.trigger, re.Pattern):
            matches_content = re.search(self.trigger, message.content.lower()) is not None
        else:
            matches_content =  self.trigger in message.content.lower()
            
        logger.debug(f"AutoResponse '{self.name}' trigger match: {matches_content}")
        return matches_content

    def matches(self, message: Message) -> bool:
        """
        Check if the message content matches the trigger.

        :param Message message: The content of the message to check.
        :returns: True if the message matches the trigger, False otherwise.
        """
        
        logger.debug(f"Checking if AutoResponse '{self.name}' matches message.")

        if not message.content:
            logger.debug(f"Message content is empty; AutoResponse '{self.name}' cannot match.")
            return False

        if self._on_cooldown(message):
            logger.debug(f"AutoResponse '{self.name}' is on cooldown for channel ID: {message.channel.id}.")
            return False

        if self._matches_name(message) or self._matches_trigger(message):
            logger.debug(f"AutoResponse '{self.name}' matches message.")
            cooldown_expires_at = datetime.now() + timedelta(seconds=60)
            self.channel_cooldowns[message.channel.id] = cooldown_expires_at
            logger.debug(f"Set cooldown for AutoResponse '{self.name}' in channel ID: {message.channel.id} until {cooldown_expires_at}.")
            return True
        
        logger.debug(f"AutoResponse '{self.name}' does not match message.")
        return False
