# myZiel

A small personal web app that helps you define goals, check in daily in natural language, and see whether your routine is moving you toward those goals.

Each check-in becomes structured, timestamped, tamper-proof data that powers a traffic-light calendar, a progress dashboard, completion forecasts and nudges when things drift.

> Status: requirements v0.2 (2026-10-29). Phase 1 (MVP) implemented; phases 2 and 3 to do.

## Table of contents

1. [Getting started](#getting-started)
1. [Key decisions](#key-decisions)
2. [Scope](#scope)
3. [Glossary](#glossary)
4. [Functional requirements](#functional-requirements)
5. [Non-functional requirements](#non-functional-requirements)
6. [Architecture](#architecture)
7. [Data model](#data-model)
8. [Roadmap](#roadmap)
9. [Open questions](#open-questions)

## Getting started

Needs Python 3.12. On Windows: `winget install Python.Python.3.12`.

```powershell
# one-time setup (on macOS/Linux use .venv/bin/ instead of .venv/Scripts/)
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
copy .env.example .env          # then set SECRET_KEY (and SMTP_URL for email reminders)
.venv/Scripts/alembic upgrade head

# run
.venv/Scripts/uvicorn myziel.main:app --factory --reload
```

Open http://localhost:8000. The first visit creates the single account.

Tests and lint:

```powershell
.venv/Scripts/python -m pytest --cov=myziel   # unit + integration
.venv/Scripts/ruff check src tests
```

Integration tests build each test database with the real Alembic migration and use a fixed clock,
so check-in windows, late and missed days and reminders are tested deterministically.

Docker: `docker build -t myziel . && docker run -p 8000:8000 -v myziel-data:/app/data --env-file .env myziel`
(migrations run on start). Backups: `scripts/backup.sh` (daily via cron), restore with `scripts/restore.sh`.

Email reminders: with `SMTP_URL` empty, reminders are written to the log only.

## Key decisions

* **Learning model is scoped down for v1.** One user with about 90 days of data is not enough to train a real model. v1 uses rules plus an LLM that reads your own history. A statistical per-user model comes once 30 to 60 days of data exist.
* **3 months is a view window, not a deletion rule.** Forecasts and long-term trends need older data, and the data is tiny. The calendar shows 3 months by default; raw data (or at least daily aggregates) is kept.
* **Non-editable check-ins have a correction path.** Natural language extraction can be wrong, so the user confirms extracted values before submitting. After submit the record is locked; later corrections are appended notes, never edits.
* **Pause credit and streaks have explicit formulas** (defaults below, all configurable).
* **Natural language needs an LLM**, which a small server cannot host. Use an external LLM API with a structured-form fallback.
* **Notifications:** email plus web push (PWA) in v1.

## Scope

* v1: single user, self-hosted, login protected.
* Every table carries a `user_id` so multi-user can be added later.
* Out of scope for v1: social features, sharing, native mobile apps, integrations with external calendars or trackers.

## Glossary

| Term | Meaning |
|---|---|
| Goal | A measurable outcome or habit with a target and optional deadline |
| Daily target | What "on track" means for one goal on one day, derived from the goal |
| Check-in | The daily survey; one per day, immutable once submitted |
| Day score | 0 to 100, how much of today's targets were met |
| Traffic light | Green / amber / red mapping of the day score, plus grey for missed |
| Streak | Consecutive qualifying days |
| Pause credit | Guilt-free break hours earned through progress |
| Drift | Sustained pace below what the goal deadline requires |

## Functional requirements

Priority uses MoSCoW: **M** must, **S** should, **C** could.

### FR-1 Profile and goals

| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | Onboarding interview: role or life situation, typical working hours, energy peaks, fixed commitments, what usually derails you | M |
| FR-1.2 | Create goals with title, why it matters, type (outcome or habit), metric and unit, target value, deadline (optional for habits), weekly time budget, priority, status (active, paused, achieved, abandoned) | M |
| FR-1.3 | System derives a daily or weekly target per goal (e.g. 5 applications per week becomes 1 per weekday); user can adjust it | M |
| FR-1.4 | Profile answers and goals are updatable. Every change creates a new version; past check-ins keep pointing at the version active that day | M |
| FR-1.5 | Limit active goals (default 3, max 5) so the check-in stays within 10 minutes | S |
| FR-1.6 | Periodic prompt (e.g. monthly) to review whether goals still matter | C |

**Acceptance:** editing or deleting a goal never changes historic check-ins, scores or charts.

### FR-2 Daily check-in

| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | One check-in per calendar day in the user's timezone. Configurable window (e.g. 18:00 to 10:00 next day). Late submissions are flagged; no submission means the day is recorded as missed | M |
| FR-2.2 | Questions generated from active goals: 1 to 2 per goal plus a core set (energy 1 to 5, sleep hours, mood, main blocker). Cap of about 8 questions, target 5 to 10 minutes | M |
| FR-2.3 | Natural language mode: free-text answers; system extracts structured values per goal (hours, counts, done or not done, blockers) | S |
| FR-2.4 | Before submit, user sees the extracted values and can correct them. Submit is the point of no return | M |
| FR-2.5 | On submit, store server timestamp (UTC), user timezone, raw text, extracted values, question set version, goal versions. No update or delete endpoint exists | M |
| FR-2.6 | Corrections after submit only as an appended, timestamped amendment linked to the original | S |
| FR-2.7 | Append-only storage enforced at database level (no UPDATE or DELETE permission, or a rejecting trigger). Optional hash chain per record | S |
| FR-2.8 | Structured fallback form when the LLM is unavailable or the user prefers it | M |

#### Day score and traffic light (FR-2.9, M)

* Per goal: `progress = min(actual / daily_target, 1.2)`
* Day score: weighted average across active goals (weight = goal priority), 0 to 100.
* Default mapping: green >= 80, amber 50 to 79, red < 50, grey = missed. Thresholds configurable.
* User also gives a self-rating. Both are stored; the calendar can show either.

#### Streaks (FR-2.10, S)

* **Check-in streak:** consecutive days with a submitted check-in.
* **Productivity streak:** consecutive days with day score at or above the green threshold.
* One freeze day per 7 days protects the streak (configurable).

#### Pause credit (FR-2.11, S)

* Earned only on days scoring 70 or above. Default: 0.5 h per 10 points above 70, capped at 1.5 h per day.
* Streak bonus: +0.5 h on every 7th day of a productivity streak.
* Balance capped (default 10 h).
* Stored as a ledger (earned, spent, balance). User logs a pause to spend credit.

### FR-3 Suggestions and drift detection

| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | Drift per goal: compare rolling 7-day pace to the pace required to hit the deadline. Flag drift when pace is more than 20% below required for 3 or more days | M |
| FR-3.2 | Extra drift signals: 2 consecutive red days, 2 consecutive missed check-ins, a blocker mentioned 3 or more times in a week | S |
| FR-3.3 | On drift, notify and show the gap, e.g. "You need 1.4 h/day, you are averaging 0.9 h/day" | M |
| FR-3.4 | Weekly review: LLM summarises the week from your own data, highlights patterns (best weekday, energy vs output, recurring blockers) and proposes 1 to 3 routine changes | S |
| FR-3.5 | Every suggestion states its data-based reason. User can accept, dismiss or snooze; feedback is stored | S |
| FR-3.6 | Learning model v2: after 30 to 60 days, fit a simple per-user model (e.g. regression of day score on sleep, energy, weekday, start time) to rank which habits matter most | C |

### FR-4 Calendar view

| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | Month view, each day coloured by its traffic light; grey for missed, blank for future | M |
| FR-4.2 | Clicking a day opens the read-only check-in, score breakdown per goal, and amendments | M |
| FR-4.3 | Default window: last 3 months, navigable month by month | M |
| FR-4.4 | Colour-blind safe: each state also has an icon or pattern | S |
| FR-4.5 | Optional year heatmap (GitHub style) | C |

**Retention:** keep all raw data (a year of check-ins is well under 1 MB). If a hard 3-month purge is required, keep daily aggregates so analytics and forecasts still work.

### FR-5 Analytics dashboard

| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Weekly and monthly views: progress per goal vs target, hours invested, day score trend, traffic light distribution, streak history | M |
| FR-5.2 | Filters: date range, goal, metric, weekday | S |
| FR-5.3 | Completion forecast per goal: remaining amount / recent pace (exponentially weighted, last 14 days), with optimistic and pessimistic range. Recomputed after every check-in | M |
| FR-5.4 | Forecast shows "on track" or "behind by N days" and how the forecast changed over time | S |
| FR-5.5 | Correlation cards (e.g. sleep vs day score) once enough data exists | C |
| FR-5.6 | CSV export of all data | S |

### FR-6 Notifications

| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Types: check-in reminder, missed check-in, drift alert, streak at risk, milestone reached, weekly review ready | M |
| FR-6.2 | Channels: email and web push (PWA) in v1. Channel is an interface so Telegram or others can be added | M |
| FR-6.3 | Per-type on or off, reminder time, quiet hours | M |
| FR-6.4 | Anti-nagging: max 3 notifications per day; drift alerts at most once per goal per 3 days | S |
| FR-6.5 | All scheduling is timezone aware | M |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 Footprint | Runs on 1 vCPU and 1 GB RAM alongside the database. App memory target under 300 MB |
| NFR-2 Performance | Dashboard and calendar load under 1 s with 1 year of data; check-in submit under 2 s excluding LLM time |
| NFR-3 Extensibility | Modular monolith with clear module boundaries. Goal types, question types, scoring strategies and notification channels plug in through interfaces |
| NFR-4 Data integrity | Check-ins append-only, enforced at database level; server timestamps in UTC |
| NFR-5 Security | Authentication, HTTPS only, secrets outside the repo, rate limited login |
| NFR-6 Privacy (GDPR) | Full data export and full account deletion. Account deletion is the only exception to immutability |
| NFR-7 LLM cost and resilience | External LLM API with monthly budget cap, timeouts, structured form fallback. Prompts and model configurable |
| NFR-8 Reliability | Single instance; automated daily database backup with tested restore |
| NFR-9 Usability | Mobile-first responsive UI, installable PWA, check-in usable one-handed on a phone |
| NFR-10 Observability | Structured logs, health endpoint, basic metrics (check-in count, LLM latency and errors) |
| NFR-11 Testability | Scoring, streak, pause and forecast logic are pure functions with unit tests |

## Architecture

### Modules

One deployable, separate packages:

```
src/myziel/
├── main.py              # FastAPI app factory
├── config.py            # settings from environment
├── core/                # db, event bus, security, logging, clock
├── modules/
│   ├── auth/            # user, login, export, account deletion
│   ├── profile_goals/   # profile, goals, versioning, target derivation
│   ├── checkin/         # survey generation, submission, amendments
│   ├── scoring/         # day score, streaks, pause ledger (pure functions)
│   ├── insights/        # drift detection, suggestions, forecasts
│   ├── analytics/       # calendar, dashboard queries, exports
│   ├── notifications/   # scheduling, policy, channels/
│   ├── llm_gateway/     # LLM client, prompts, budget, fallback
│   └── health/          # health endpoint, metrics
└── web/                 # Jinja2 templates + static (htmx, PWA)
migrations/              # Alembic
tests/unit/              # scoring, streak, pause, forecast, drift
tests/integration/       # e.g. check-in immutability
scripts/                 # backup and restore
```

### Event flow

```
CheckInSubmitted
   ├──> scoring        (day score, streak, pause credit)
   ├──> insights       (forecast, drift detection)
   └──> notifications  (milestone, drift alert)
```

Events go through an in-process event bus, keeping modules decoupled and making it easy to move to a real broker later.

### Stack options

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI, served by Uvicorn |
| Database | SQLite for smallest footprint, or PostgreSQL if multi-user is likely soon. SQLAlchemy 2 + Alembic migrations, repository layer to keep switching cheap |
| Frontend | Server-rendered Jinja2 templates with htmx. Chart.js for charts; custom calendar grid |
| Scheduling | APScheduler in-process for reminders and weekly reviews |
| Deployment | Single Docker container (plus Postgres if chosen) on a small VPS |

## Data model

| Entity | Key fields |
|---|---|
| `user` | id, email, timezone, settings |
| `profile_answer` | user_id, question_key, answer, version, created_at |
| `goal` / `goal_version` | goal_id, version, title, type, metric, unit, target, deadline, weekly_budget, priority, status, valid_from |
| `checkin` | id, user_id, local_date, submitted_at_utc, is_late, raw_text, question_set_version, self_rating, hash (append-only) |
| `checkin_value` | checkin_id, goal_version_id, metric, value |
| `checkin_amendment` | id, checkin_id, created_at, note, corrected_values |
| `day_score` | user_id, local_date, score, light, computed_at |
| `streak_event` | user_id, type, date, length |
| `pause_ledger` | user_id, date, delta_hours, reason, balance_after |
| `forecast_snapshot` | goal_id, computed_at, projected_date, low, high |
| `suggestion` | id, user_id, created_at, text, reason, status |
| `notification` / `notification_pref` | type, channel, scheduled_for, sent_at, enabled, quiet_hours |

## Roadmap

### Phase 1: MVP

- [x] Goals and profile with versioning
- [x] Structured check-in with free-text field, immutable storage
- [x] Day score, traffic light, calendar view
- [x] Basic weekly chart
- [x] Email reminder

### Phase 2: Intelligence

- [ ] Natural language extraction with confirmation step
- [ ] Streaks and pause credit ledger (logic and tests done; streaks on dashboard; ledger to do)
- [ ] Completion forecast (logic and tests done, not shown in UI yet)
- [ ] Drift detection and alerts (logic and tests done, not wired up yet)
- [ ] Web push, PWA

### Phase 3: Learning and polish

- [ ] Weekly LLM review and suggestions with feedback
- [ ] Per-user statistical model
- [ ] Filters, correlation cards, CSV export
- [ ] Multi-user readiness

## Open questions

- [ ] Single user only, or should others be able to sign up later?
- [ ] Traffic light: computed from the score, self-rated, or both with one as default?
- [ ] Data retention: keep everything, or hard delete after 3 months?
- [ ] What does spending pause credit do in practice?
- [ ] Which notification channels will actually be checked (email, browser push, Telegram)?
- [ ] Which LLM provider, and what monthly budget is acceptable?
- [ ] Should missed days break the streak immediately, or use freeze days?
- [ ] Is the check-in window evening only, or also next morning?
