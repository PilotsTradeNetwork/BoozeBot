import unittest
from unittest import mock

from ptn.boozebot.modules.PHcheck import api_ph_check
from tests.test_data import test_data


# noinspection PyUnusedLocal
class PublicHolidayChecks(unittest.TestCase):

    @mock.patch('requests.get', side_effect=test_data.mocked_requests_holiday_response)
    async def test_ph_check_holiday(self, _mock_request_get):
        self.assertTrue(await api_ph_check())

    @mock.patch('requests.get', side_effect=test_data.mocked_requests_no_holiday_response)
    async def test_ph_check(self, _mock_request_get):
        self.assertFalse(await api_ph_check())
