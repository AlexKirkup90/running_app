# Run Season Command

Production-ready multi-athlete running coaching platform with role-based coach + athlete experiences built on Streamlit + PostgreSQL.

## Features
- Coach admin surfaces: dashboard, clients, command center, analytics, integrations, tools.
- Athlete today-first UX with check-in, session briefing, completion flow.
- Plan generation for 12/24/36/48 weeks with race-specific running progression.
- Recommendation engine with risk/confidence, guardrails, action queue semantics.
- Full relational schema + Alembic migrations + idempotent seed data.
- Import adapter template for generic running CSV.
- Observability basics (runtime error logging + query profile stats).

## Tech
Python 3.11, Streamlit, PostgreSQL (Neon-compatible), SQLAlchemy, Alembic, Pandas, Altair, passlib+bcrypt, pytest.

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg2://USER:PASSWORD@HOST/DB?sslmode=require'
alembic upgrade head
python db/seed.py
streamlit run app.py
```

## Streamlit Community Cloud
1. Add app repo to Streamlit Cloud.
2. In **Secrets**, set:
```toml
DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST/DB?sslmode=require"
```
3. Deploy with `app.py` entrypoint.

## Data/Migrations
- Baseline schema in `db/schema.sql`
- Migrations in `alembic/versions`
- Seed script runs migrations then seeds:
  - 100+ session library rows
  - default coach + demo athlete
  - sample plan, events, checkins, logs

## Test
```bash
pytest
```

## Deployment checks
- `alembic current` equals head (`0002_policy_hardening`)
- Login and role routing works for coach + athlete demo users
- Dashboard/analytics render with no runtime errors

## Rollback
```bash
alembic downgrade -1
```

## Troubleshooting
- **Bad DATABASE_URL formatting**: ensure `postgresql+psycopg2://` and URL-encoded password.
- **Auth failures**: reseed users with `python db/seed.py` and rotate temporary passwords.
- **Migration mismatch**: run `alembic stamp head` only after validating schema parity.
- **Missing table errors**: confirm `alembic upgrade head` succeeded against the same DB target.

## Verification Checklist
- [x] Role-based coach/client navigation.
- [x] Password policy + lockout helpers.
- [x] Full schema entities including imports and observability logs.
- [x] Running taxonomy session library seeded with 100+ sessions.
- [x] Automated periodized plan generation with cutback weeks.
- [x] Intervention recommendations with guardrails.
- [x] Athlete today-first check-in flow.
- [x] Athlete and portfolio analytics foundations.
- [x] CSV adapter validation framework.
- [x] Runtime error safe handling and query profiling status widgets.
- [x] Pytest unit + migration + critical flow tests.
- [x] GitHub Actions CI pipeline.
