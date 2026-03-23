import json
from pathlib import Path
from typing import Any


class MockResponse:
    def __init__(self, json_data: str, status_code: int):
        self.json_data: dict[str, Any] = json.loads(json_data)
        self.status_code: int = status_code
        self.ok: bool = status_code < 300

    def json(self):
        return self.json_data


dirname = Path(__file__).parent


def load_response(filename: str):
    with (dirname / f"{filename}.json").open() as data:
        return data.read()


def mocked_requests_holiday_response(*args: Any, **kwargs: Any):
    if (
        args[0] == "https://elitebgs.app/api/ebgs/v5/factions"
        and kwargs["params"]["name"] == "Rackham Capital Investments"
    ):
        return MockResponse(load_response("peak_faction_holiday_response"), 200)
    return None


def mocked_requests_no_holiday_response(*args: Any, **kwargs: Any):
    if (
        args[0] == "https://elitebgs.app/api/ebgs/v5/factions"
        and kwargs["params"]["name"] == "Rackham Capital Investments"
    ):
        return MockResponse(load_response("peak_faction_no_holiday_response"), 200)
    return None
