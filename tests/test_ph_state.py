import unittest
from datetime import UTC, datetime, timedelta
from unittest import mock

from ptn_utils.enums.booze_enums import CruiseSystemState

from ptn.boozebot.botcommands.PublicHoliday import PublicHoliday


class PublicHolidayEndGuard(unittest.IsolatedAsyncioTestCase):
    async def _run_end_check(self, hours_since_start: float, automatic: bool) -> bool:
        now = datetime.now(tz=UTC)
        state = {"state": CruiseSystemState.ACTIVE, "updated_at": now - timedelta(days=1)}
        cruise = mock.Mock(ph_start=now - timedelta(hours=hours_since_start))

        with (
            mock.patch("ptn.boozebot.botcommands.PublicHoliday.booze_sheets_api") as api,
            mock.patch.object(PublicHoliday, "_set_holiday_end", new=mock.AsyncMock()) as set_end,
        ):
            api.get_current_cruise_state = mock.AsyncMock(return_value=state)
            api.get_cruise_with_stats = mock.AsyncMock(return_value=cruise)
            await PublicHoliday._set_public_holiday_state(False, now, automatic=automatic)
            return set_end.await_count == 1

    async def test_automatic_end_within_min_duration_ignored(self):
        self.assertFalse(await self._run_end_check(hours_since_start=6, automatic=True))

    async def test_automatic_end_after_min_duration_applied(self):
        self.assertTrue(await self._run_end_check(hours_since_start=13, automatic=True))

    async def test_manual_end_within_min_duration_applied(self):
        self.assertTrue(await self._run_end_check(hours_since_start=6, automatic=False))
