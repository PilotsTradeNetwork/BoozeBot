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


class AdminStateOverride(unittest.IsolatedAsyncioTestCase):
    HELPERS = (
        "_announce_holiday_start",
        "_announce_holiday_end",
        "_set_site_holiday_start",
        "_set_site_holiday_end",
    )

    async def _run_override(
        self, state: str, current: CruiseSystemState, force: bool = False, targets: str | None = None
    ) -> tuple[mock.MagicMock, dict[str, mock.AsyncMock], mock.AsyncMock]:
        interaction = mock.MagicMock()
        interaction.response.defer = mock.AsyncMock()
        interaction.followup.send = mock.AsyncMock()
        cog = PublicHoliday(mock.MagicMock())
        kwargs = {"targets": targets} if targets else {}

        with (
            mock.patch("ptn.boozebot.botcommands.PublicHoliday.booze_sheets_api") as api,
            mock.patch.object(
                PublicHoliday, "_set_public_holiday_state_locked", new=mock.AsyncMock(return_value=(True, "done"))
            ) as set_both,
        ):
            helpers = {}
            for name in self.HELPERS:
                patcher = mock.patch.object(PublicHoliday, name, new=mock.AsyncMock())
                helpers[name] = patcher.start()
                self.addCleanup(patcher.stop)
            api.last_applied_state = current
            api.get_current_cruise_state = mock.AsyncMock(return_value={"state": current})
            await PublicHoliday.admin_override_state.callback(cog, interaction, state, force, **kwargs)
            api_state = api.last_applied_state

        helpers["api_last_applied_state"] = api_state
        return interaction, helpers, set_both

    async def test_site_only_does_not_announce(self):
        _, helpers, set_both = await self._run_override("active", CruiseSystemState.PREP, targets="site")
        helpers["_set_site_holiday_start"].assert_awaited_once()
        helpers["_announce_holiday_start"].assert_not_awaited()
        set_both.assert_not_awaited()

    async def test_discord_only_announces_and_marks_applied(self):
        _, helpers, set_both = await self._run_override("ended", CruiseSystemState.ACTIVE, targets="discord")
        helpers["_announce_holiday_end"].assert_awaited_once()
        helpers["_set_site_holiday_end"].assert_not_awaited()
        set_both.assert_not_awaited()
        self.assertEqual(helpers["api_last_applied_state"], CruiseSystemState.ENDED)

    async def test_default_targets_both(self):
        _, helpers, set_both = await self._run_override("active", CruiseSystemState.PREP)
        set_both.assert_awaited_once()
        self.assertTrue(set_both.await_args.args[0])
        helpers["_announce_holiday_start"].assert_not_awaited()

    async def test_same_state_without_force_does_nothing(self):
        interaction, _helpers, set_both = await self._run_override("active", CruiseSystemState.ACTIVE)
        set_both.assert_not_awaited()
        self.assertIn("already", interaction.followup.send.await_args.args[0])

    async def test_same_state_with_force_applies(self):
        _, helpers, _set_both = await self._run_override("active", CruiseSystemState.ACTIVE, force=True, targets="site")
        helpers["_set_site_holiday_start"].assert_awaited_once()
