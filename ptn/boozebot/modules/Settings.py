import json
from typing import Literal, TypedDict, overload

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
        self.settings: SettingsDict = {}
        self._create_file_if_not_exists()
        self._load_settings()
        self._create_defaults()

    def _create_file_if_not_exists(self) -> None:
        if not SETTINGS_FILE_PATH.exists():
            SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE_PATH.write_text(json.dumps({}, indent=4), "utf-8")

    def _load_settings(self) -> None:
        try:
            loaded_settings = json.loads(SETTINGS_FILE_PATH.read_text("utf-8"))
            self.settings = {k: v for k, v in loaded_settings.items() if k in self.default_settings}
        except FileNotFoundError:
            self.settings = {}

    def _create_defaults(self) -> None:
        updated = False
        for key, value in self.default_settings.items():
            if key not in self.settings:
                self.settings[key] = value
                updated = True
        if updated:
            self._save_settings()

    def _save_settings(self) -> None:
        SETTINGS_FILE_PATH.write_text(json.dumps(self.settings, indent=4), "utf-8")

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
        self.settings[key] = value
        self._save_settings()


settings = Settings()
