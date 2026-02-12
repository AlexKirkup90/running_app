# Run Season Command — Project Review & Roadmap

## 1. Executive Summary

**Run Season Command** is a full-stack coaching platform for running training, built with Streamlit, SQLAlchemy, and PostgreSQL. It enables coaches to build periodized training plans, monitor athlete readiness, manage interventions through a command-center workflow, and deliver adaptive session recommendations — while athletes check in daily, log sessions, and track progress toward race goals.

The codebase is **4,038 lines of Python** across 19 database models, 13 service modules, and a monolithic Streamlit UI layer. It has a clean architecture (models → services → UI), comprehensive type hints, proper database migrations (Alembic), and 29 passing tests. The domain modeling is sophisticated and running-specific.

**Current state: functional MVP with strong foundations, but several gaps stand between it and a production-grade, industry-leading product.**

---

## 2. What the App Does

### Core Workflow

```
Coach creates Plan → Athlete checks in daily → System scores readiness
    → Adaptive session briefing → Athlete logs session → System tracks adherence
    → Command Center surfaces interventions → Coach acts on recommendations
```

### Feature Inventory

| Feature Area | Description | Status |
|---|---|---|
| **Authentication & Security** | Role-based login (coach/client), bcrypt password hashing, account lockout after 5 failed attempts, forced password change | Complete |
| **Session Library** | 120+ structured running session templates across 11 categories (Easy Run, Tempo, VO2 Intervals, Hill Repeats, etc.) with warmup/main/cooldown blocks, pace/HR zones, RPE targets | Complete |
| **Plan Builder** | Generate 12–48 week periodized plans with automatic phase progression (Base → Build → Peak → Taper → Recovery), cutback weeks every 4th week, day-level session assignment | Complete |
| **Athlete Daily Flow** | Check-in (sleep/energy/recovery/stress on 1–5 scales), adaptive session briefing based on readiness, session logging with HR/pace/RPE/pain tracking | Complete |
| **Readiness Scoring** | Composite score from check-in data, color-banded (Green/Amber/Red), drives session adaptation | Complete |
| **Recommendation Engine** | Risk/confidence scoring, explainable factors, guardrails blocking high-risk (>0.85) actions, configurable automation modes (manual/assisted/automatic) | Complete |
| **Command Center** | Intervention queue with risk-priority ordering, coach action logging, SLA tracking (24h/72h aging), cooldown periods | Complete |
| **Case Management** | Athlete risk bucketing (at-risk/watch/stable), timeline view (logs, check-ins, events, notes, coach actions), notes/tasks with due dates | Complete |
| **Analytics** | Weekly load rollups, duration/load aggregation, Altair charts, multi-week trend visualization | Complete |
| **Import Framework** | CSV parser scaffold with import run tracking | Scaffold only |
| **Observability** | Runtime error logging to DB, system status monitoring | Basic |

### Technical Profile

- **Language:** Python 3.11
- **UI:** Streamlit 1.41.1
- **Database:** PostgreSQL (Neon-compatible) via SQLAlchemy 2.0
- **Migrations:** Alembic (4 revisions)
- **Testing:** pytest (29 tests, all passing)
- **Linting:** ruff (all checks passing)
- **CI:** GitHub Actions (lint + test)

---

## 3. Steps to Ensure It Works Fully

### 3.1 Critical Fixes

#### A. `app.py` monolith decomposition risk
`app.py` is **1,681 lines** containing all Streamlit page functions, authentication, database session management, and UI rendering. While it works today, any concurrent development will create merge conflicts and make debugging difficult.

**Action:** Refactor into a multi-page Streamlit app structure:
```
pages/
  01_coach_dashboard.py
  02_coach_command_center.py
  03_coach_plan_builder.py
  04_athlete_dashboard.py
  05_athlete_checkin.py
  ...
```

#### B. Increase test coverage
The test-to-code ratio is ~7%. Critical paths that need test coverage:

| Gap | Risk |
|---|---|
| `app.py` UI logic (authentication flow, form handling) | Regression in user-facing flows |
| Plan day-session assignment edge cases | Incorrect schedules for athletes |
| Database transaction rollback paths | Data corruption on failure |
| CSV import pipeline | Bad data entering the system |
| Readiness → recommendation → intervention full chain | Incorrect coaching recommendations |

**Action:** Target 60%+ line coverage. Add integration tests that exercise the full check-in → readiness → recommendation → intervention pipeline against a test database.

#### C. Structured logging
Currently errors only go to the `AppRuntimeError` database table. If the database is down, errors are silently swallowed.

**Action:** Add Python `logging` module with structured JSON output to stdout. This is essential for any production deployment (Streamlit Cloud, Docker, or otherwise).

#### D. Environment configuration
Hardcoded defaults are scattered across modules (e.g., category lists in `seed.py`, risk thresholds in `interventions.py`).

**Action:** Centralize all configurable values into `core/config.py` with environment-variable overrides and validation. Add separate configs for dev/staging/production.

#### E. Input validation at boundaries
Streamlit provides basic type constraints on widgets, but there's no validation layer between UI input and database writes.

**Action:** Add Pydantic models (or equivalent) for all user-facing data entry points: check-in values, training log data, plan parameters, session library entries.

### 3.2 Operational Readiness

| Area | Current State | Required State |
|---|---|---|
| **Database backups** | Not documented | Automated daily backups with tested restore procedure |
| **Monitoring** | Basic DB error table | External monitoring (uptime checks, error alerting) |
| **Secrets management** | `.streamlit/secrets.toml` | Proper secrets manager (e.g., cloud provider KMS) |
| **SSL/TLS** | Enforced for Neon | Documented and enforced for all environments |
| **Rate limiting** | None | Rate limiting on login endpoint (beyond account lockout) |
| **Data export** | None | GDPR-style athlete data export capability |
| **Audit trail** | `CoachActionLog` + `AppWriteLog` | Complete audit trail for all data mutations |

### 3.3 Development Process

| Area | Current State | Recommended |
|---|---|---|
| **CI coverage gate** | Tests run but no coverage threshold | `pytest --cov --cov-fail-under=60` |
| **Pre-commit hooks** | None | ruff + type checking on commit |
| **Database migrations testing** | Schema shape tests exist | Add upgrade/downgrade round-trip tests |
| **Dependency scanning** | None | Dependabot or equivalent for vulnerability alerts |
| **Docker** | None | `Dockerfile` + `docker-compose.yml` for reproducible local dev |

---

## 4. Roadmap to Industry-Leading App

### Phase 1: Foundation Hardening (Immediate)

**Goal:** Make the existing features production-solid.

- [ ] **Decompose `app.py`** into Streamlit multi-page architecture
- [ ] **Add structured logging** (Python `logging` → JSON to stdout)
- [ ] **Increase test coverage to 60%+** with integration tests
- [ ] **Add input validation** (Pydantic models at service boundaries)
- [ ] **Centralize configuration** (environment-specific settings)
- [ ] **Dockerize** the application (Dockerfile + docker-compose for local dev)
- [ ] **Add pre-commit hooks** (ruff, type checking)
- [ ] **Document API contracts** for every service function (docstrings)

### Phase 2: API Layer & Multi-Client Support

**Goal:** Break free from Streamlit-only access. Enable mobile apps, wearable integrations, and third-party tools.

- [ ] **Build a REST API** (FastAPI alongside Streamlit, sharing the same service/model layer)
  - Authentication endpoints (JWT tokens)
  - Athlete CRUD, check-in, logging endpoints
  - Coach plan management, intervention endpoints
  - Session library endpoints
- [ ] **API documentation** (auto-generated OpenAPI/Swagger)
- [ ] **Webhook support** for real-time notifications (e.g., new intervention, plan update)
- [ ] **Rate limiting and API key management** for external consumers

### Phase 3: Wearable & Data Integrations

**Goal:** Eliminate manual data entry. Pull real training data automatically.

- [ ] **Garmin Connect API** integration (HR, pace, distance, GPS tracks auto-sync)
- [ ] **Strava API** integration (activity import, social features)
- [ ] **Apple Health / Google Fit** bridges
- [ ] **Polar, COROS, Suunto** support
- [ ] **Automatic training log population** from device data
- [ ] **HR zone auto-calibration** from max HR tests and threshold sessions
- [ ] **Sleep/recovery data** from wearables (Whoop, Oura Ring)
- [ ] Complete the **CSV import framework** for bulk historical data migration

### Phase 4: Intelligent Coaching Engine

**Goal:** Move from rule-based recommendations to data-driven adaptive coaching.

- [ ] **Machine learning readiness model** trained on check-in → performance correlation
- [ ] **Injury risk prediction** using training load patterns, pain flag history, and acute:chronic workload ratios
- [ ] **Adaptive plan modification** — automatically adjust upcoming weeks based on actual vs. planned load
- [ ] **Race time prediction** using recent training data and established models (Riegel, VDOT)
- [ ] **Natural language session feedback** — AI-generated post-session analysis
- [ ] **Periodization optimization** — learn which phase durations and load progressions produce best outcomes per athlete profile
- [ ] **Weather-adjusted session recommendations** (heat, altitude, humidity factors)

### Phase 5: Native Mobile App

**Goal:** Meet athletes where they are — on their phones, mid-run.

- [ ] **React Native or Flutter mobile app** consuming the Phase 2 API
- [ ] **Push notifications** (session reminders, coach messages, intervention alerts)
- [ ] **Offline-first check-in and logging** with background sync
- [ ] **GPS tracking** for outdoor runs (map view, splits, elevation)
- [ ] **Live session mode** — real-time pace/HR guidance during workouts
- [ ] **Photo/media attachments** on training logs

### Phase 6: Team & Organization Scale

**Goal:** Support coaching businesses, running clubs, and elite programs.

- [ ] **Multi-coach support** — assign athletes to coaches, transfer caseloads
- [ ] **Organization accounts** with admin/coach/athlete hierarchies
- [ ] **Group training plans** — template plans applied across squads
- [ ] **Billing integration** (Stripe) — coach subscription tiers, per-athlete pricing
- [ ] **White-label capability** — custom branding per organization
- [ ] **Role-based permissions** — granular access control beyond coach/client
- [ ] **Athlete self-service plan marketplace** — purchase pre-built plans

### Phase 7: Community & Social

**Goal:** Build network effects that drive retention and growth.

- [ ] **Athlete-to-athlete social features** (activity feed, kudos, comments)
- [ ] **Coach profiles and discovery** — athletes find coaches by specialty, location, rating
- [ ] **Group challenges and leaderboards** (weekly distance, streak tracking)
- [ ] **Training log sharing** (public/private toggle)
- [ ] **Forum / knowledge base** for running topics
- [ ] **Coach certification and review system**

### Phase 8: Advanced Analytics & Reporting

**Goal:** Provide world-class insight that coaches and athletes can't get elsewhere.

- [ ] **Training load dashboard** with acute:chronic workload ratio charts, monotony, strain
- [ ] **Longitudinal athlete development tracking** (VO2max trends, threshold pace trends over months/years)
- [ ] **Comparative analytics** — anonymized benchmarking against similar athletes
- [ ] **Coach portfolio reporting** — aggregate outcomes, retention rates, PR frequency
- [ ] **PDF/Excel report export** for athletes and coaches
- [ ] **Real-time race-day dashboards** for coaches monitoring multiple athletes

---

## 5. Competitive Landscape & Differentiation

### Current Market Leaders

| Platform | Strengths | Weaknesses |
|---|---|---|
| **TrainingPeaks** | Industry standard, deep analytics, WKO integration | Expensive, complex UI, cycling-focused heritage |
| **Final Surge** | Good plan marketplace, free tier | Limited coaching tools, basic analytics |
| **Strava** | Massive community, GPS tracking | Not a coaching platform, limited planning |
| **Garmin Connect** | Hardware integration, free | Poor coaching workflow, device-locked |
| **VDOT O2** | Jack Daniels methodology, race predictions | Limited to one methodology, basic UX |

### Differentiation Opportunities

1. **Coaching-first, not tracking-first** — Most platforms are built for self-coached athletes. Run Season Command is built around the coach-athlete relationship, with the command center and intervention system as core differentiators.

2. **Adaptive intelligence with guardrails** — The recommendation engine with explainable factors and risk guardrails is a genuinely novel feature. Most platforms either give no recommendations or give opaque AI suggestions.

3. **Operational coaching tools** — SLA tracking, caseload management, and intervention queues treat coaching as a professional service operation, not a hobby. This appeals to coaching businesses.

4. **Open integration model** — With a proper API layer (Phase 2), this platform can sit at the center of an athlete's ecosystem rather than being a walled garden.

---

## 6. Technical Debt Register

| Item | Severity | Location | Description |
|---|---|---|---|
| Monolithic UI | High | `app.py` (1,681 lines) | All pages in one file; hinders maintainability and concurrent development |
| Low test coverage | High | `tests/` | ~7% test-to-code ratio; critical paths may regress undetected |
| No structured logging | Medium | Entire app | Errors only logged to DB; silent failure if DB is down |
| Hardcoded thresholds | Medium | `interventions.py`, `readiness.py` | Risk thresholds, scoring weights baked into code |
| No input validation layer | Medium | Service boundaries | UI widgets provide minimal validation; no Pydantic models |
| Incomplete import framework | Low | `core/services/imports.py` | Scaffold only; CSV parser exists but no real adapters |
| Minimal simulation service | Low | `core/services/simulation.py` | 5-line module with no real functionality |
| `passlib` deprecation warning | Low | Auth module | `crypt` module deprecated in Python 3.13 |
| No pagination | Low | Coach caseload views | Athlete tables load all records; will degrade at scale |
| No database connection retry | Low | `core/db.py` | Single connection attempt; no retry with backoff |

---

## 7. Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    STREAMLIT UI LAYER                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │  Coach    │ │  Athlete │ │  Auth    │ │  Admin     │ │
│  │  Pages    │ │  Pages   │ │  Panel   │ │  Tools     │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘ │
│       │             │            │              │        │
├───────┴─────────────┴────────────┴──────────────┴────────┤
│                   SERVICE LAYER                           │
│  ┌──────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ │
│  │ Planning  │ │ Session   │ │ Command   │ │ Case     │ │
│  │          │ │ Engine    │ │ Center    │ │ Mgmt     │ │
│  ├──────────┤ ├───────────┤ ├───────────┤ ├──────────┤ │
│  │Readiness │ │Intervene  │ │ Analytics │ │ Workload │ │
│  ├──────────┤ ├───────────┤ ├───────────┤ ├──────────┤ │
│  │ Events   │ │ Imports   │ │ Security  │ │ Cache    │ │
│  └────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────┬─────┘ │
│       │              │             │             │        │
├───────┴──────────────┴─────────────┴─────────────┴───────┤
│                   DATA LAYER                              │
│  ┌───────────────────────────────────────────────────┐   │
│  │  SQLAlchemy ORM (19 Models)                        │   │
│  │  Alembic Migrations (4 Revisions)                  │   │
│  └──────────────────────┬────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────┴────────────────────────────┐   │
│  │  PostgreSQL (Neon)                                 │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Summary Scorecard

| Dimension | Score | Notes |
|---|---|---|
| **Domain Modeling** | 9/10 | Sophisticated, running-specific, well-normalized |
| **Architecture** | 7/10 | Clean separation, but UI monolith is a liability |
| **Code Quality** | 8/10 | Strong typing, clean services, good error handling |
| **Security** | 7/10 | Solid auth, but needs input validation and rate limiting |
| **Testing** | 5/10 | 29 passing tests, but low coverage for the codebase size |
| **DevOps/CI** | 5/10 | Basic CI exists, no Docker, no coverage gates |
| **Documentation** | 6/10 | Good README, but functions lack docstrings |
| **Scalability** | 4/10 | No API layer, no pagination, Streamlit-only |
| **Production Readiness** | 5/10 | Works but lacks logging, monitoring, backups |
| **Feature Completeness** | 7/10 | Core coaching loop is complete; integrations missing |
| **Overall** | **6.3/10** | **Strong MVP foundation; needs hardening and expansion to compete** |

---

*Generated: 2026-02-12*
*Branch: claude/project-review-roadmap-JJZCL*
