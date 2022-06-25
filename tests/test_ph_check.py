import unittest
from unittest import mock

from ptn.boozebot.PHcheck import ph_check
from tests.test_data import test_data


# noinspection PyUnusedLocal
class PublicHolidayChecks(unittest.TestCase):

    @mock.patch('requests.get', side_effect=test_data.mocked_requests_holiday_response)
    def test_ph_check_holiday(self, mock_request_get):
        self.assertTrue(ph_check())

    @mock.patch('requests.get', side_effect=test_data.mocked_requests_no_holiday_response)
    def test_ph_check(self, mock_request_get):
        self.assertFalse(ph_check())
