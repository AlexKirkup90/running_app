# Run Season Command

Production-ready Streamlit coaching platform for running (coach + athlete experiences) backed by PostgreSQL/Neon.

## Features
- Role-based auth (`coach`, `client`) with lockout, password policy, and forced password change.
- Running-specific taxonomy and seeded library (120 structured sessions).
- Canonical running session contract with warmup/main/cooldown blocks, pace/HR/RPE targets, and progression/regression rules.
- Plan Builder v2 with preview-before-publish, persisted day-level sessions, and week management (swap/lock/regenerate).
- Athlete Today flow enforcement: check-in -> adaptive session briefing -> single daily log (upsert) with planned-session completion tracking.
- Plan generation (12/24/36/48 weeks), cutback weeks, phases (Base/Build/Peak/Taper/Recovery).
- Recommendation engine with risk/confidence, explainable factors, guardrails, and automation modes.
- Coach command center + athlete today-first flow.
- Analytics (weekly rollups), observability status strip, runtime error logging.
- Import adapter scaffold and item/run audit tables.

## Stack
- Python 3.11
- Streamlit
- PostgreSQL (Neon-compatible)
- SQLAlchemy + Alembic
- Pandas + Altair
- passlib+bcrypt
- pytest + GitHub Actions

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg2://USER:PASSWORD@HOST:5432/DB?sslmode=require'
alembic upgrade head
python db/seed.py
streamlit run app.py
```

## Streamlit Community Cloud
1. Add app from repo.
2. Set secrets in app settings based on `.streamlit/secrets.toml.example`.
3. Ensure `DATABASE_URL` points to Neon.
4. Deploy.

## Demo Credentials
- Coach: `coach` / `CoachPass!234`
- Athlete: `athlete1` / `AthletePass!234`

## Migrations & Seed
- Baseline migration: `alembic/versions/20260101_0001_initial.py`
- Session quality schema migration: `alembic/versions/20260211_0002_session_quality_schema.py`
- Plan day-session migration: `alembic/versions/20260211_0003_plan_day_sessions.py`
- Idempotent seed: `db/seed.py` (runs migrations, seeds sessions + users + demo plans/events/logs)

## Tests
```bash
pytest -q
```

## CI
- GitHub Actions workflow at `.github/workflows/ci.yml` runs lint + tests.

## Deployment checks
- `alembic current` equals `head`
- `SELECT count(*) FROM sessions_library` >= 100
- Login succeeds for coach and athlete
- Dashboard loads without runtime error entries increasing unexpectedly

## Rollback
- Use migration downgrade carefully:
```bash
alembic downgrade -1
```
- Restore DB snapshot from Neon if needed for production incidents.

## Troubleshooting
- **Bad DATABASE_URL**: verify dialect prefix `postgresql+psycopg2://` and include `sslmode=require` for Neon.
- **Auth failures**: verify seeded users exist and password policy-compliant resets.
- **Migration mismatch**: run `alembic history` and `alembic upgrade head`.
- **Missing table errors**: run migrations before launching Streamlit.
- **Reset demo login**:
```bash
python -m scripts.reset_demo_auth
```

## Verification Checklist
- [x] Coach and athlete role-separated navigation.
- [x] Password policy + lockout + forced password change paths.
- [x] Running taxonomy with 100+ session templates.
- [x] Plan generation with phases and cutback logic.
- [x] Recommendation generation with guardrails and automation check.
- [x] Analytics rollups and charts.
- [x] Import framework scaffold with validations.
- [x] Runtime observability + safe error handling.
- [x] Alembic migration + idempotent seed.
- [x] Unit/integration/e2e-style tests.
- [x] CI pipeline.
