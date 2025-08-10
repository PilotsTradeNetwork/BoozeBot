import re
import sqlite3

class AutoResponse:
    """
    Class representing an auto response in the database.
    
    Attributes:
        name (str) - The name of the auto response.
        trigger (str): The trigger phrase for the auto response.
        is_regex (bool): Whether the trigger is a regex pattern.
        response (str): The response message to send when the trigger is matched.
    """

    def __init__(self, info_dict: sqlite3.Row|dict|None = None):
        if info_dict:

            if isinstance(info_dict, sqlite3.Row):
                info_dict = dict(info_dict)

            self.name = info_dict.get('name', '')
            self.is_regex = bool(info_dict.get('is_regex', False))
            self.response = info_dict.get('response', '')

            if self.is_regex:
                try:
                    self.trigger = re.compile(info_dict.get('trigger', ''))
                except re.error as e:
                    print(f"Invalid regex pattern: {info_dict.get('trigger', '')}. Error: {e}")
                    self.is_regex = False
                    self.trigger = info_dict.get('trigger', '').lower()
            else:
                self.trigger = info_dict.get('trigger', '').lower()

        else:
            self.trigger = ''
            self.is_regex = False
            self.conn_only = False
            self.response = ''

    def to_tuple(self):
        """
        Convert the auto response to a tuple for pagination.
        
        :returns: A tuple containing the name, trigger and response.
        """

        trigger = self.trigger if isinstance(self.trigger, str) else self.trigger.pattern

        return (self.name, f"{trigger}\n{self.response}")

    def matches(self, message_content: str, is_staff: bool = False) -> bool:
        """
        Check if the message content matches the trigger.
        
        :param str message_content: The content of the message to check.
        :returns: True if the message matches the trigger, False otherwise.
        """

        if not message_content:
            return False

        if not self.trigger or not self.response:
            return False

        if "!"+self.name in message_content.lower():
            return True

        if is_staff:
            return False

        if self.is_regex:
            return re.search(self.trigger, message_content.lower()) is not None
        else:
            return self.trigger.lower() in message_content.lower()
