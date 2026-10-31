"""Lighter, the writing companion: goals, streaks, pace and reminders."""

import datetime

from candle import coach, sync
from candle.db import Project

TODAY = datetime.date(2026, 10, 30)   # a Friday


def days(*counts, end=TODAY):
    """Starting word counts for consecutive days ending on `end`."""
    first = end - datetime.timedelta(days=len(counts) - 1)
    return {str(first + datetime.timedelta(days=i)): n for i, n in enumerate(counts) if n is not None}


def test_words_written_each_day():
    written = coach.written_by_day({"2026-10-27": 100, "2026-10-29": 400, "2026-10-30": 350}, 500, TODAY)
    assert written == {datetime.date(2026, 10, 27): 300, datetime.date(2026, 10, 29): -50, TODAY: 150}
    assert coach.written_by_day({"nonsense": 1, "2026-11-02": 9}, 10, TODAY) == {}


def test_daily_streak():
    daily = days(0, 100, 200, 300)                      # 100 a day for three days, today started
    s = coach.status(daily, 300, TODAY, daily_goal=100, hour=10)
    assert (s.streak, s.met_today, s.kind, s.mood) == (3, False, "morning", "glow")
    assert "100 words" in s.message
    s = coach.status(daily, 420, TODAY, daily_goal=100)
    assert (s.streak, s.met_today, s.kind, s.streak_text) == (4, True, "done_streak", "4 days")
    assert "4 days in a row" in s.message
    s = coach.status(daily, 300, TODAY, daily_goal=100, hour=20)
    assert s.kind == "at_risk" and s.mood == "flicker" and "3 days" in s.message
    s = coach.status(daily, 350, TODAY, daily_goal=100)
    assert s.kind == "close" and "50 words" in s.message
    # A day off breaks it; no goal means any writing counts.
    assert coach.status(days(0, 100, 100, 200), 200, TODAY, daily_goal=100).streak == 1
    assert coach.status(days(0, 1, 2, 3), 3, TODAY).streak == 3


def test_coming_back_and_starting_out():
    s = coach.status({}, 0, TODAY, daily_goal=500)
    assert (s.kind, s.mood) == ("first", "glow") and "500 words" in s.message   # a new project: a beginning
    long_ago = {"2026-10-01": 0, "2026-10-02": 900}
    s = coach.status(long_ago, 900, TODAY, daily_goal=500)
    assert (s.kind, s.mood, s.last_written) == ("comeback", "sleepy", datetime.date(2026, 10, 1))


def test_days_a_week():
    # Mon 26 – Fri 30 October: wrote Mon, Tue and Wed; three days a week is met.
    daily = days(0, 100, 200, 300, 300)
    s = coach.status(daily, 300, TODAY, daily_goal=100, goals={"week_days": 3}, hour=20)
    assert (s.week_met, s.kind, s.streak_unit, s.streak) == (3, "rest", "week", 1)
    assert [m for _, _, m in s.week] == [True, True, True, False, False, False, False]
    # Last week too (Mon 19 – Sun 25: four days): two weeks running.
    daily = days(0, 100, 200, 300, 400, 400, 400, 400, 500, 600, 700, 700, end=TODAY)
    s = coach.status(daily, 700, TODAY, daily_goal=100, goals={"week_days": 3})
    assert (s.streak, s.streak_text) == (2, "2 weeks")


def test_deadline_pace():
    daily = days(1000)
    s = coach.status(daily, 1000, TODAY, daily_goal=200, target=4000, goals={"deadline": "2026-11-01"})
    assert (s.days_left, s.pace, s.today_goal) == (3, 1000, 1000)      # 3,000 words in 3 days
    assert s.pace_text == "To reach 4,000 words by 1 November 2026: 1,000 words a day (3 days left)."
    s = coach.status(daily, 1000, TODAY, daily_goal=200, target=4000, goals={"deadline": "2026-10-01"})
    assert s.pace is None and s.kind == "deadline_passed" and "has passed" in s.pace_text
    s = coach.status(daily, 4100, TODAY, target=4000, goals={"deadline": "2026-10-01"})
    assert s.kind == "finished" and s.mood == "proud" and s.pace_text == ""


def test_pages():
    s = coach.status(days(0), 500, TODAY, daily_goal=750, goals={"unit": "pages"})
    assert "1 page more" in s.message and coach.amount(500, "pages") == "2 pages"
    assert [coach.amount(n, "pages") for n in (100, 250, 2600)] == ["0.4 pages", "1 page", "10 pages"]


def test_goal_settings_are_checked():
    assert coach.parse_goals("") == coach.DEFAULTS
    assert coach.parse_goals("not json") == coach.DEFAULTS
    bad = '{"unit": "lines", "week_days": 9, "deadline": "soon", "remind_at": "25:00"}'
    assert coach.parse_goals(bad) == coach.DEFAULTS
    good = {"unit": "pages", "week_days": 5, "deadline": "2027-01-31", "remind_at": "19:30"}
    assert coach.parse_goals(coach.dump_goals(good)) == good


def test_the_message_holds_for_the_day():
    daily = days(0, 100, 200)
    once = coach.status(daily, 200, TODAY, daily_goal=100, hour=9).message
    assert coach.status(daily, 200, TODAY, daily_goal=100, hour=11).message == once


def test_goals_travel_with_the_project(tmp_path):
    p = Project.create(tmp_path / "book.candle", "Storm")
    before = sync.fingerprint(p)
    p.set_meta("goals", "")
    assert sync.fingerprint(p) == before                 # files synced before goals existed still match
    p.set_meta("goals", coach.dump_goals({"unit": "pages"}))
    assert sync.fingerprint(p) != before
    s = coach.for_project(p)
    assert s.unit == "pages" and s.today_words == 0


def test_goals_page_and_reminder(tmp_path, qapp, monkeypatch):
    from candle import app as app_module
    from tests.test_ui import _open_window
    path = tmp_path / "book.candle"
    Project.create(path, "Storm").close()
    sent = []
    monkeypatch.setattr(app_module, "notify", lambda title, body: sent.append((title, body)))
    window = _open_window(path)
    try:
        view = window.goals_view
        assert view.locked.isVisible() is False or not view.goals.isVisible()
        window._set_premium(True)
        window.nav.setCurrentRow(window.views.index(("Goals", view)))
        assert view.goals.isVisibleTo(window) and not view.locked.isVisibleTo(window)
        view.unit.setCurrentIndex(view.unit.findData("pages"))
        view.daily.setValue(2)
        view.remind.setChecked(True)
        view.remind_at.setTime(view.remind_at.time().fromString("00:00", "HH:mm"))
        view.flush()
        p = window.project
        assert p.get_meta("daily_goal") == "500"
        assert coach.parse_goals(p.get_meta("goals"))["remind_at"] == "00:00"
        assert "2 pages" in view.today_bar.format() and view.message.text()
        window.remind()
        window.remind()                                   # once a day
        assert len(sent) == 1 and sent[0][0] == "Storm — Candle"
        window._set_premium(False)
        assert view.locked.isVisibleTo(window) and "🔥" not in window.words_label.text()
    finally:
        window.close_project()
        window.close()
