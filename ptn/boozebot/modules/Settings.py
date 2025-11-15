import json
from typing import Literal, TypedDict, overload
from loguru import logger

from ptn.boozebot.constants import SETTINGS_FILE_PATH

DepartureStatusType = Literal["Disabled", "Upwards", "All"]


class SettingsDict(TypedDict):
    departure_announcement_status: DepartureStatusType
    timed_unloads_allowed: bool
    timed_unload_hold_duration: float


class Settings:

    default_settings: SettingsDict = {
        "departure_announcement_status": "Disabled",
        "timed_unloads_allowed": False,
        "timed_unload_hold_duration": 5,
    }

    def __init__(self) -> None:
        logger.info("Initializing Settings module.")
        self.settings: SettingsDict = {}
        self._create_file_if_not_exists()
        self._load_settings()
        self._create_defaults()
        logger.info("Settings initialized successfully.")

    def _create_file_if_not_exists(self) -> None:
        logger.info("Checking if settings file exists.")
        if not SETTINGS_FILE_PATH.exists():
            logger.info("Settings file does not exist. Creating new settings file.")
            SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE_PATH.write_text(json.dumps({}, indent=4), "utf-8")
            logger.debug("Settings file created successfully.")

    def _load_settings(self) -> None:
        logger.info("Loading settings from file.")
        try:
            loaded_settings = json.loads(SETTINGS_FILE_PATH.read_text("utf-8"))
            self.settings = {k: v for k, v in loaded_settings.items() if k in self.default_settings}
            logger.debug("Settings loaded successfully.")
        except FileNotFoundError:
            logger.warning("Settings file not found.")
            self.settings = {}

    def _create_defaults(self) -> None:
        logger.info("Ensuring all default settings are present.")
        updated = False
        for key, value in self.default_settings.items():
            logger.debug(f"Checking setting '{key}'")
            if key not in self.settings:
                logger.debug(f"Setting default for missing setting '{key}': {value}, adding to settings.")
                self.settings[key] = value
                updated = True
        if updated:
            logger.info("New default settings added. Saving settings.")
            self._save_settings()
            logger.debug("Default settings saved successfully.")

    def _save_settings(self) -> None:
        logger.info("Saving settings to file.")
        SETTINGS_FILE_PATH.write_text(json.dumps(self.settings, indent=4), "utf-8")
        logger.debug("Settings saved successfully.")

    @overload
    def get_setting(self, key: Literal["departure_announcement_status"]) -> DepartureStatusType: ...

    @overload
    def get_setting(self, key: Literal["timed_unloads_allowed"]) -> bool: ...

    @overload
    def get_setting(self, key: Literal["timed_unload_hold_duration"]) -> float: ...

    def get_setting(self, key: str):
        """Get a setting value with proper type checking based on the key."""
        return self.settings.get(key)

    @overload
    def set_setting(self, key: Literal["departure_announcement_status"], value: DepartureStatusType) -> None: ...

    @overload
    def set_setting(self, key: Literal["timed_unloads_allowed"], value: bool) -> None: ...

    @overload
    def set_setting(self, key: Literal["timed_unload_hold_duration"], value: float) -> None: ...

    def set_setting(self, key: str, value) -> None:
        """Set a setting value based on the key."""
        logger.info(f"Setting '{key}' to '{value}'")
        self.settings[key] = value
        self._save_settings()


settings = Settings()
