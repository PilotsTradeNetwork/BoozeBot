import json
import os


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json.loads(json_data)
        self.status_code = status_code
        self.ok = status_code < 300

    def json(self):
        return self.json_data


dirname = os.path.dirname(__file__)


def load_response(filename):
    with open(f'{dirname}/{filename}.json', mode='r') as data:
        return data.read()


def mocked_requests_holiday_response(*args, **kwargs):
    if args[0]=='https://elitebgs.app/api/ebgs/v5/factions' \
            and kwargs['params']['name']=='Rackham Capital Investments':
        return MockResponse(load_response("peak_faction_holiday_response"), 200)


def mocked_requests_no_holiday_response(*args, **kwargs):
    if args[0]=='https://elitebgs.app/api/ebgs/v5/factions' \
            and kwargs['params']['name']=='Rackham Capital Investments':
        return MockResponse(load_response("peak_faction_no_holiday_response"), 200)
