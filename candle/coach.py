"""Lighter, the writing companion (Candle Premium): goals, streaks and nudges.

Everything here comes from what each project already records: its daily goal
and target length (project meta), the word count each day started with (the
`daily` table) and the words in the manuscript now. Goals live in the project
file, so they travel with it between Candle and Candle on the web.

The same rules run in three places; keep them in step:
- here (Candle, and its Goals page and reminders);
- candle_premium/server/app/coach.py, a copy, for the web's push reminders;
- candle_premium/server/app/static/coach.js, for Candle on the web, whose
  LINES are generated from the ones below.

Words written on a day are the difference between that day's starting count
and the next recorded one (or the manuscript now), so deleting counts too.
"""

import dataclasses
import datetime
import json
import math
import re

WORDS_PER_PAGE = 250   # a standard manuscript page
DEFAULTS = {"unit": "words", "week_days": 7, "deadline": "", "remind_at": ""}
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# What Lighter says. Picked by the writer's day; one line per kind per day, so
# the message doesn't change on every refresh. {goal}, {words}, {left},
# {streak} and {pace} are amounts in the writer's unit ("1,200 words", "3 pages").
LINES = {
    "finished": [
        "You reached your target. The whole book, on the page. Take a bow — then take a nap.",
        "Target reached! Every one of those words was yours. I'm glowing.",
        "That's the length you set out to write. Whatever comes next, this is done.",
    ],
    "done_streak": [
        "Goal met — {streak} in a row. Look at you, keeping the flame going.",
        "{words} today, {streak} in a row. This is how books get finished.",
        "Done for today: that's {streak} in a row. I'll be here tomorrow.",
        "Another one. {streak} without missing. Your story is lucky to have you.",
    ],
    "done": [
        "Goal met: {words} today. That's a good day's work.",
        "You did it — {words}. Close the laptop proudly, or keep going if it's flowing.",
        "Today's goal: done. Tomorrow's pages are already a little easier.",
        "{words} today. Small, steady, real. That's the whole trick.",
    ],
    "rest": [
        "You've written enough days this week. Rest without guilt — or write, I won't stop you.",
        "Week's goal met. Today is yours to rest, read, or sneak in a scene.",
    ],
    "close": [
        "{words} so far — only {left} to go. You're nearly there.",
        "Past halfway. {left} more and today counts.",
        "So close: {left} left. Finish the scene you're in.",
    ],
    "started": [
        "Good start: {words}. {left} more for today's goal.",
        "You've begun, and beginning is the hard part. {left} to go.",
        "The words are coming. {left} more and the day is yours.",
    ],
    "at_risk": [
        "{streak} in a row, and today still needs {goal}. You can do that before bed.",
        "Don't leave me burning alone: {streak} in a row so far, and today still needs {goal}.",
        "The evening's not over. {goal} keeps your streak alive — {streak} and counting.",
        "One scene. Even a short one. {streak} in a row is worth keeping.",
    ],
    "comeback": [
        "It's been a while. No guilt — just open a scene and write one sentence.",
        "Your story kept your place. Want to see where you left it?",
        "I saved you a seat. {goal} today and we start a new streak.",
        "Welcome back. The best day to restart is the one you're in.",
    ],
    "first": [
        "A new story! {goal} today and the first page is yours.",
        "Every book starts with one sentence. {goal} is today's goal.",
        "Welcome to a fresh page. Let's see where {goal} takes you today.",
    ],
    "morning": [
        "Good morning. {goal} today — a coffee's worth of writing.",
        "A fresh page and a whole day. {goal} is today's goal.",
        "Morning words are the easiest. {goal} before lunch?",
    ],
    "afternoon": [
        "Today's goal is {goal}. Ten minutes now beats an hour of wishing later.",
        "Still time for {goal} today. Where did your characters leave off?",
        "A quick session? {goal} and today counts.",
    ],
    "evening": [
        "There's still today. {goal} and you can sleep happy.",
        "Before the day ends: {goal}. Just the next scene.",
        "Write a little tonight — {goal} is today's goal.",
    ],
    "deadline_passed": [
        "Your deadline has passed. Set a new date on the Goals page and I'll work out the pace.",
    ],
}


def parse_goals(raw):
    """The project's goal settings (meta "goals", JSON), checked, with defaults."""
    try:
        goals = json.loads(raw) if raw else {}
    except ValueError:
        goals = {}
    if not isinstance(goals, dict):
        goals = {}
    out = dict(DEFAULTS)
    if goals.get("unit") in ("words", "pages"):
        out["unit"] = goals["unit"]
    if type(goals.get("week_days")) is int and 1 <= goals["week_days"] <= 7:
        out["week_days"] = goals["week_days"]
    if isinstance(goals.get("deadline"), str) and _date(goals["deadline"]):
        out["deadline"] = goals["deadline"]
    if isinstance(goals.get("remind_at"), str) and TIME.match(goals["remind_at"]):
        out["remind_at"] = goals["remind_at"]
    return out


def dump_goals(goals):
    return json.dumps(parse_goals(json.dumps(goals)), sort_keys=True)


def _date(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def amount(words, unit):
    """Words in the writer's unit: "1,250 words", "5 pages"."""
    if unit == "pages":
        pages = words / WORDS_PER_PAGE
        text = f"{pages:,.0f}" if pages >= 10 else f"{pages:.1f}".removesuffix(".0")
        return f"{text} page" + ("" if text == "1" else "s")
    return f"{words:,} word" + ("" if words == 1 else "s")


def written_by_day(daily, total, today):
    """{date: words written that day} from the days' starting counts."""
    days = sorted((d, int(n)) for d, n in ((_date(k), v) for k, v in daily.items()) if d and d <= today)
    written = {}
    for i, (day, start) in enumerate(days):
        end = days[i + 1][1] if i + 1 < len(days) else total
        written[day] = end - start
    return written


@dataclasses.dataclass
class Status:
    unit: str
    total: int                  # words in the manuscript
    today_words: int
    today_goal: int             # the daily goal, or the deadline's pace if that's more
    daily_goal: int
    met_today: bool
    streak: int                 # days (or weeks, when resting days are allowed) in a row
    streak_unit: str            # "day" or "week"
    week: list                  # this week, Monday first: (date, words, met)
    week_days: int              # days a week to write
    week_met: int
    target: int
    deadline: datetime.date | None
    pace: int | None            # words a day to reach the target by the deadline
    days_left: int | None
    last_written: datetime.date | None
    kind: str = ""              # which LINES
    mood: str = ""              # proud, glow, flicker or sleepy: how Lighter looks
    message: str = ""

    @property
    def streak_text(self):
        return f"{self.streak} {self.streak_unit}{'s' * (self.streak != 1)}"

    @property
    def pace_text(self):
        if self.deadline is None or not self.target:
            return ""
        if self.total >= self.target:
            return ""
        when = f"{self.deadline:%d %B %Y}".lstrip("0")
        if self.pace is None:
            return f"Your deadline, {when}, has passed."
        return (f"To reach {amount(self.target, self.unit)} by {when}: "
                f"{amount(self.pace, self.unit)} a day ({self.days_left} day{'s' * (self.days_left != 1)} left).")


def status(daily, total, today, daily_goal=0, target=0, goals=None, hour=12):
    """Where the writer stands today, and what Lighter says about it."""
    goals = parse_goals(json.dumps(goals) if isinstance(goals, dict) else goals)
    daily_goal, target = max(int(daily_goal or 0), 0), max(int(target or 0), 0)
    written = written_by_day(daily, total, today)
    today_words = written.get(today, 0)

    deadline, pace, days_left = _date(goals["deadline"]), None, None
    if deadline and target:
        if deadline >= today:
            days_left = (deadline - today).days + 1
            pace = math.ceil(max(target - (total - today_words), 0) / days_left)
    today_goal = max(daily_goal, pace or 0)

    def met(day):
        words = written.get(day, 0)
        goal = today_goal if day == today else daily_goal
        return words >= goal if goal else words > 0

    week_days = goals["week_days"]
    monday = today - datetime.timedelta(days=today.weekday())
    week = [(d, written.get(d, 0), met(d)) for d in (monday + datetime.timedelta(days=i) for i in range(7))]
    week_met = sum(1 for d, _, m in week if m and d <= today)
    first = min(written, default=today)

    if week_days == 7:
        streak_unit, streak, day = "day", 0, today - datetime.timedelta(days=1)
        while day >= first and met(day):
            streak, day = streak + 1, day - datetime.timedelta(days=1)
        streak += met(today)
    else:
        streak_unit, streak, start = "week", 0, monday - datetime.timedelta(days=7)
        while start + datetime.timedelta(days=6) >= first and \
                sum(met(start + datetime.timedelta(days=i)) for i in range(7)) >= week_days:
            streak, start = streak + 1, start - datetime.timedelta(days=7)
        streak += week_met >= week_days

    last = max((d for d, n in written.items() if n > 0), default=None)
    s = Status(goals["unit"], total, today_words, today_goal, daily_goal, met(today), streak, streak_unit,
               week, week_days, week_met, target, deadline, pace, days_left, last)
    s.kind, s.mood = _kind(s, today, hour)
    s.message = _say(s, today)
    return s


def _kind(s, today, hour):
    if s.target and s.total >= s.target:
        return "finished", "proud"
    if s.met_today:
        return ("done_streak" if s.streak >= 3 else "done"), "proud"
    if s.deadline and s.target and s.pace is None:
        return "deadline_passed", "flicker"
    if s.week_days < 7 and s.week_met >= s.week_days:
        return "rest", "glow"
    if s.today_words > 0 and s.today_goal:
        return ("close" if s.today_words * 2 >= s.today_goal else "started"), "glow"
    if s.last_written is None:
        return "first", "glow"            # nothing written yet: a beginning, not a comeback
    if (today - s.last_written).days >= 3:
        return "comeback", "sleepy"
    if s.streak and hour >= 17:
        return "at_risk", "flicker"
    return ("morning" if hour < 12 else "afternoon" if hour < 17 else "evening"), "glow"


def _say(s, today):
    lines = LINES[s.kind]
    line = lines[(today.toordinal() + len(s.kind)) % len(lines)]
    goal = s.today_goal or (WORDS_PER_PAGE if s.unit == "pages" else 100)
    return line.format(goal=amount(goal, s.unit), words=amount(max(s.today_words, 0), s.unit),
                       left=amount(max(goal - s.today_words, 0), s.unit), streak=s.streak_text,
                       pace=amount(s.pace or 0, s.unit))


def for_project(project, today=None, hour=None):
    """status() for an open Candle project."""
    now = datetime.datetime.now()
    project.start_day()
    daily = dict(project.conn.execute("SELECT day, start_words FROM daily").fetchall())
    return status(daily, project.total_words(), today or now.date(),
                  project.get_meta("daily_goal", 0) or 0, project.get_meta("target_words", 0) or 0,
                  parse_goals(project.get_meta("goals", "")), now.hour if hour is None else hour)
