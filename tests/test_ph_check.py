import unittest
from unittest import mock

from ptn.boozebot.modules.PHcheck import ph_check
from tests.test_data import test_data


# noinspection PyUnusedLocal
class PublicHolidayChecks(unittest.TestCase):

    @mock.patch('requests.get', side_effect=test_data.mocked_requests_holiday_response)
    async def test_ph_check_holiday(self, _mock_request_get):
        self.assertTrue(await ph_check())

    @mock.patch('requests.get', side_effect=test_data.mocked_requests_no_holiday_response)
    async def test_ph_check(self, _mock_request_get):
        self.assertFalse(await ph_check())
