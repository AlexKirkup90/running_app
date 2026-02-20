# Streamlit → React Migration Roadmap

## Migration Status at a Glance

| Feature Area | Streamlit | React | Gap |
|---|---|---|---|
| **Login & Auth** | Full (lockout, force-change) | Basic login only | Medium |
| **Coach Dashboard** | Metrics + queue preview | Stat cards + bar chart | Small |
| **Client Roster** | Full table | Full table | Done |
| **Command Center — Queue** | Rich (metrics, SLA, batch, snoozed) | Basic card list + decide | **Large** |
| **Command Center — Casework** | Timeline, notes, tasks, context | Not started | **Large** |
| **Plan Builder — Create** | Full form + preview + publish | Not started | **Large** |
| **Plan Builder — Manage Weeks** | Lock/unlock, swap, regenerate | Not started | **Large** |
| **Session Library — Browse** | Filter, inspect, detail view | Not started | **Large** |
| **Session Library — CRUD** | Add / Edit / Delete tabs | Not started | **Large** |
| **Portfolio Analytics** | Per-athlete CTL/ATL/TSB table | Not started | **Large** |
| **VDOT Calculator** | Calculator + full pace table | Not started | **Medium** |
| **Integrations / Wearables** | Connection mgmt + sync history | Not started | **Large** |
| **Coach Community Mgmt** | Group/challenge creation | Not started | **Medium** |
| **Athlete Dashboard** | Readiness + load + session briefing | Readiness + recent activity | **Medium** |
| **Athlete Check-In** | Sliders + save | Buttons + save | Done |
| **Athlete Log Session** | Full form + plan-day update | Full form | Done |
| **Athlete Plans (view)** | Week/day detail | Week/day detail | Done |
| **Athlete Events** | Events + race predictions | Events only | Small |
| **Athlete Analytics** | Volume, CTL/ATL/TSB, VDOT, pace | Volume, intensity, readiness | **Medium** |
| **Athlete Profile** | Profile display + preferences | Not started | **Medium** |
| **Athlete Wearable Sync** | Connection list + sync button | Not started | **Medium** |
| **Athlete Community** | Groups, feed, challenges, streak, kudos | Groups + challenges (partial) | Small |

---

## Phase 1 — Coach Power Tools (Highest Impact)

These are the features that make the coach experience viable. Without them, a coach cannot operate from the React UI.

### 1.1 Plan Builder — Create Plans
**Streamlit reference:** `pages/coach.py` → `coach_plan_builder`, Build & Publish tab

What needs building:
- Form: athlete selector, race goal (5K/10K/Half/Marathon), plan length (12/24/36/48 weeks), sessions/week (3–6 slider), max session minutes (60–240), start date picker
- Preview generation: call `generate_plan_weeks()` + `assign_week_sessions()` via new API endpoint
- Preview tables: week summary (phase, dates, target_load, sessions) and day-by-day detail
- Publish action: archives old plans, creates Plan + PlanWeek + PlanDaySession records
- API endpoints needed: `POST /api/v1/plans/preview` (generate without saving), `POST /api/v1/plans` (publish)

### 1.2 Plan Builder — Manage Weeks
**Streamlit reference:** `pages/coach.py` → `coach_plan_builder`, Manage Plan Weeks tab

What needs building:
- Plan selector (active plans with athlete name, race goal)
- Week selector with phase + lock status display
- Day sessions table showing session_day, session_name, status
- Session swap: select day → pick replacement from session library dropdown → update
- Lock/unlock week toggle
- Regenerate week button (re-runs phase session assignment, replaces PlanDaySession rows)
- Lock guards: prevent swap/regenerate on locked weeks
- API endpoints needed: `PUT /api/v1/plans/{id}/weeks/{week}/lock`, `PUT /api/v1/plans/{id}/weeks/{week}/sessions/{day}` (swap), `POST /api/v1/plans/{id}/weeks/{week}/regenerate`

### 1.3 Session Library Browser
**Streamlit reference:** `pages/coach.py` → `coach_session_library`

What needs building:
- **Browse tab**: multi-select category filter, intent filter, treadmill toggle, duration range. Filtered results table. Session detail inspector showing: prescription, coaching notes, workout blocks table (phase/duration/pace/HR/RPE), interval detail for v3 sessions, progression/regression rules
- **Add tab**: form with name, category, intent, energy system, tier, treadmill flag, duration, structure JSON, targets JSON, progression/regression JSON, prescription, coaching notes. Validation + duplicate check
- **Edit tab**: template selector → pre-populated form → update
- **Delete tab**: template selector → confirmation → delete
- API endpoints needed: `GET /api/v1/sessions` (list/filter), `GET /api/v1/sessions/{id}` (detail), `POST /api/v1/sessions`, `PUT /api/v1/sessions/{id}`, `DELETE /api/v1/sessions/{id}`

### 1.4 Command Center — Full Queue
**Streamlit reference:** `pages/coach.py` → `coach_command_center`, Queue tab

What needs building beyond current React:
- Queue metrics dashboard: open count, high priority, actionable now, snoozed, SLA due 24h, SLA due 72h, median age, oldest age
- Snoozed queue: separate view of interventions in cooldown
- Batch actions: multi-select checkboxes on interventions → batch decision (accept_and_close, defer_24h, defer_72h, modify_action, dismiss) with note field
- Full intervention detail: why_factors list, expected_impact signals, guardrail_reason, cooldown_until, created_at, age in hours
- API endpoints needed: `GET /api/v1/interventions/stats` (queue metrics), `POST /api/v1/interventions/batch-decide`

### 1.5 Command Center — Casework Tab
**Streamlit reference:** `pages/coach.py` → `coach_command_center`, Casework tab

What needs building:
- Athlete selector (sorted by name, showing risk info)
- Focused view with: open interventions count, open notes/tasks, days since last log
- **Notes & Tasks panel**: add note/task with due date, task table, mark complete/reopen/delete
- **Timeline panel**: unified chronological feed of coach actions, training logs, check-ins, events, notes. Calls `build_case_timeline()` service
- **Recent Context panel**: training load analysis (monotony, strain, overtraining risk), plan adjustment recommendations (`assess_adherence_trend()`, `detect_pain_cluster()`, `recommend_adjustments()`), recent check-ins table, upcoming events
- API endpoints needed: `GET /api/v1/athletes/{id}/timeline`, `GET /api/v1/athletes/{id}/context` (load analysis + recommendations), `POST /api/v1/athletes/{id}/notes`, `GET /api/v1/athletes/{id}/notes`, `PUT /api/v1/athletes/{id}/notes/{id}`

---

## Phase 2 — Athlete Intelligence (Core Differentiator)

These features turn the athlete dashboard from a log viewer into an intelligent coaching surface.

### 2.1 Session Briefing (Adaptive Daily Workout)
**Streamlit reference:** `pages/athlete.py` → `athlete_dashboard`, Session Briefing section

What needs building:
- Athlete profile anchors display (max HR, resting HR, threshold pace, easy pace, VDOT)
- Planned session lookup: today's PlanDaySession → SessionLibrary template
- Session adaptation: call `adapt_session_structure()` with readiness, pain, A:C ratio, days to event, phase, VDOT → get adapted action + reason
- Rendered session detail: prescription, coaching notes, workout blocks table (phase/duration/pace/HR/RPE), interval detail for v3 sessions
- Progression/regression rules display
- A:C ratio computation from 28-day loads
- API endpoint needed: `GET /api/v1/athletes/{id}/session-briefing` (returns today's adapted session with full detail)

### 2.2 Training Load Summary on Dashboard
**Streamlit reference:** `pages/athlete.py` → `athlete_dashboard`, Training Load section

What needs building:
- Monotony, strain, overtraining risk metrics (from last 30 days of logs)
- Color-coded risk level (low/moderate/high)
- Only shown when 7+ days of data exist
- API: can use existing `compute_monotony_strain()` from `training_load.py`, expose via endpoint or embed in dashboard response

### 2.3 Advanced Analytics
**Streamlit reference:** `pages/athlete.py` → `athlete_analytics`

What needs building beyond current React:
- **Fitness & Fatigue chart**: CTL/ATL/TSB line chart with race readiness status. Uses `compute_fitness_fatigue()` service
- **VDOT Progression**: trend chart from benchmark/race logs. Uses `compute_vdot_history()`. Shows current VDOT, peak, trend, improvement rate
- **Pace Trends**: rolling average pace by session category over time
- API endpoint needed: `GET /api/v1/athletes/{id}/analytics/fitness` (CTL/ATL/TSB data), `GET /api/v1/athletes/{id}/analytics/vdot` (VDOT history)

### 2.4 Race Predictions on Events Page
**Streamlit reference:** `pages/athlete.py` → `athlete_events`

What needs building:
- From best recent benchmark/race log or athlete's vdot_score, call `predict_all_distances()`
- Display prediction table: distance, predicted_time, method (Riegel vs Daniels)
- API endpoint needed: `GET /api/v1/athletes/{id}/race-predictions`

### 2.5 Athlete Profile & Preferences
**Streamlit reference:** `pages/athlete.py` → `athlete_profile`

What needs building:
- Profile display: name, email, DOB, status
- Preferences editor: automation mode, auto-apply settings, reminder training days
- Connected wearables list with sync status, last sync time
- Sync Now button (trigger manual sync)
- Disconnect button
- Sync history (last 5 syncs)
- API endpoints needed: `GET /api/v1/athletes/{id}/profile`, `PUT /api/v1/athletes/{id}/preferences`, `GET /api/v1/athletes/{id}/wearables`, `POST /api/v1/athletes/{id}/wearables/{id}/sync`, `DELETE /api/v1/athletes/{id}/wearables/{id}`

---

## Phase 3 — Coach Analytics & Tools

### 3.1 Portfolio Analytics
**Streamlit reference:** `pages/coach.py` → `coach_portfolio_analytics`

What needs building:
- Portfolio summary table: per-athlete total sessions, total minutes, total load
- Athlete fitness overview: per-athlete CTL, ATL, TSB, race readiness, easy %, hard %
- API endpoint needed: `GET /api/v1/coach/portfolio-analytics`

### 3.2 VDOT Calculator
**Streamlit reference:** `pages/coach.py` → `coach_vdot_calculator`

What needs building:
- Calculator mode: enter VDOT directly (slider 30–85) OR estimate from race result (distance + time)
- Output: estimated VDOT + training paces table (E/M/T/I/R with pace, band, purpose)
- Full pace table mode: VDOT 30–85 lookup table
- This can be a pure client-side tool (the pace tables are static data) or call `estimate_vdot()` + `get_training_paces()` from `vdot.py`

### 3.3 Coach Integrations Management
**Streamlit reference:** `pages/coach.py` → `coach_integrations`

What needs building:
- Wearable connections overview table (athlete, service, status, last sync, external ID)
- Add connection form (athlete selector, service, tokens, external ID)
- Sync history table (last 20 syncs with details)
- CSV import runs list
- API endpoints needed: `GET /api/v1/wearables`, `POST /api/v1/wearables`, `GET /api/v1/wearables/sync-history`

### 3.4 Coach Community Management
**Streamlit reference:** `pages/coach.py` → `coach_community`

What needs building:
- Training groups list with create form (name, description, privacy, max members)
- Membership management (add athlete to group, set role)
- Challenges list with create form (name, type, target, dates, group)
- API endpoints already exist: `POST /api/v1/groups`, `POST /api/v1/groups/{id}/join`, `POST /api/v1/challenges`

---

## Phase 4 — Auth Hardening & Polish

### 4.1 Login Hardening
- Account lockout after 5 failed attempts (15-min lockdown) — backend supports this, React needs to display lockout messaging
- Force password change on first login (`must_change_password` flag) — backend supports this, React Login.tsx has partial flow but needs testing/completion

### 4.2 Coach Dashboard Enhancement
- Enrich weekly load chart (line chart matching Streamlit, not bar chart)
- Add top intervention queue preview with full detail (risk score, confidence, why factors)

### 4.3 Athlete Community Completion
- Training streak metric (consecutive days with logs)
- Kudos received count
- Quick message in group feed (currently partial)

---

## API Endpoints Needed (Summary)

The backend services exist for nearly everything — the main work is exposing them through new API endpoints and building the React UI.

| Endpoint | For |
|---|---|
| `POST /api/v1/plans/preview` | Plan builder preview |
| `POST /api/v1/plans` (enhanced) | Plan publish with full week/day creation |
| `PUT /api/v1/plans/{id}/weeks/{wk}/lock` | Week lock toggle |
| `PUT /api/v1/plans/{id}/weeks/{wk}/sessions/{day}` | Session swap |
| `POST /api/v1/plans/{id}/weeks/{wk}/regenerate` | Week regeneration |
| `GET/POST/PUT/DELETE /api/v1/sessions` | Session library CRUD |
| `GET /api/v1/interventions/stats` | Queue metrics |
| `POST /api/v1/interventions/batch-decide` | Batch decisions |
| `GET /api/v1/athletes/{id}/timeline` | Case timeline |
| `GET /api/v1/athletes/{id}/context` | Load analysis + recommendations |
| `POST/GET/PUT /api/v1/athletes/{id}/notes` | Coach notes CRUD |
| `GET /api/v1/athletes/{id}/session-briefing` | Adapted daily session |
| `GET /api/v1/athletes/{id}/analytics/fitness` | CTL/ATL/TSB data |
| `GET /api/v1/athletes/{id}/analytics/vdot` | VDOT history |
| `GET /api/v1/athletes/{id}/race-predictions` | Race time predictions |
| `GET/PUT /api/v1/athletes/{id}/profile` | Profile + preferences |
| `GET/POST/DELETE /api/v1/athletes/{id}/wearables` | Wearable connections |
| `POST /api/v1/athletes/{id}/wearables/{id}/sync` | Manual sync trigger |
| `GET /api/v1/coach/portfolio-analytics` | Portfolio overview |
| `GET/POST /api/v1/wearables` | Coach wearable management |
| `GET /api/v1/wearables/sync-history` | Sync history |

---

## Recommended Build Order

```
Phase 1 (Coach Power Tools)     ← Coach can't work without these
  1.1 Plan Builder Create
  1.2 Plan Builder Manage Weeks
  1.3 Session Library Browser
  1.4 Command Center Full Queue
  1.5 Command Center Casework

Phase 2 (Athlete Intelligence)  ← The coaching differentiator
  2.1 Session Briefing
  2.2 Training Load Summary
  2.3 Advanced Analytics
  2.4 Race Predictions
  2.5 Athlete Profile & Wearables

Phase 3 (Coach Analytics)       ← Nice-to-have coach tools
  3.1 Portfolio Analytics
  3.2 VDOT Calculator
  3.3 Integrations Management
  3.4 Community Management

Phase 4 (Polish)                ← Hardening & completeness
  4.1 Auth Hardening
  4.2 Dashboard Enhancement
  4.3 Community Completion
```

---

## What's Already Done Well

The good news: the **hard work is done**. The domain modeling, service layer, database schema, and core algorithms (VDOT tables, periodization, readiness scoring, TRIMP, recommendation engine, session adaptation) are all built and working. The Streamlit UI proves the full workflow end-to-end.

The React migration is primarily **UI + API endpoint wiring** — the business logic already exists in `core/services/`. Each item above is mostly:
1. Add 1–2 API endpoints in `api/routes.py` calling existing services
2. Build the React page/component consuming those endpoints
3. Add React Query hooks + TypeScript types

No new algorithms or domain logic are required for the migration itself.
