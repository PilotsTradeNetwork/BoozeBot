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

with open(f'{dirname}/peak_faction_holiday_response.json', mode='r') as data:
    holiday_response = data.read()

with open(f'{dirname}/peak_faction_workingday_response.json', mode='r') as data:
    workingday_response = data.read()


def mocked_requests_holiday_response(*args, **kwargs):
    if args[0] == 'https://elitebgs.app/api/ebgs/v5/factions' \
            and kwargs['params']['name'] == 'Rackham Capital Investments':
        return MockResponse(holiday_response, 200)
    return MockResponse(None, 404)


def mocked_requests_workingday_response(*args, **kwargs):
    if args[0] == 'https://elitebgs.app/api/ebgs/v5/factions' \
            and kwargs['params']['name'] == 'Rackham Capital Investments':
        return MockResponse(workingday_response, 200)
    return MockResponse(None, 404)
