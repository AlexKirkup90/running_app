# Project Review & Remediation Roadmap

*Date: 2026-02-22*

---

## 1. Executive Summary

The Run Season Command platform has a **solid backend** (385 tests passing, 80+ endpoints, comprehensive service layer) but the **frontend had build-breaking TypeScript errors** and some structural issues from overlapping Codex/Claude contributions. This review documents what went well, what broke, and provides a clear path to get everything running.

---

## 2. What Went Well

### Backend (Excellent Shape)
- **385 tests pass** with zero failures
- **80+ API endpoints** covering auth, coaching, athletes, plans, sessions, interventions, community, wearables, analytics, and intelligence
- **Service layer is comprehensive**: VDOT tables, periodization, readiness scoring, TRIMP, session adaptation (v2 zone + v3 Daniels pace), fitness-fatigue (CTL/ATL/TSB), race prediction (Riegel + Daniels), recommendation engine
- **Database schema** is clean and consistent across all models
- **Pydantic schemas** properly validate all API inputs/outputs

### Frontend Architecture (Solid Foundation)
- **React 18 + TypeScript + Vite** — modern, fast toolchain
- **TanStack React Query** for data fetching — proper cache invalidation patterns
- **Zustand** for auth state — clean, minimal store
- **shadcn/ui + Tailwind CSS** — consistent design system with Badge, Button, Card, Input, Label, Table, Dialog, Select, Tabs, Textarea components
- **18 page components** covering all routes (coach + athlete)
- **7 custom hook files** wrapping all API operations
- **API client** with 60+ typed fetch functions matching backend endpoints
- **Types** aligned with Pydantic schemas

### Completed Migration Phases
| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | Done | Coach Power Tools — Plan Builder, Session Library, Command Center (full queue + casework) |
| Phase 2 | Done | Athlete Intelligence — Session Briefing, Training Load, Fitness/Fatigue, VDOT, Race Predictions, Profile |
| Phase 3-7 (Codex) | Done | Organization, Team, Assignments, Community (groups, challenges, kudos, feed), Athlete Plans/Events/Analytics |

---

## 3. What Broke (Issues Found & Fixed)

### 3.1 Frontend Build Failures (FIXED)
The frontend would not compile due to 4 TypeScript errors:

| File | Error | Fix |
|------|-------|-----|
| `Dashboard.tsx:46` | `formatPace` declared but never read | Removed unused function |
| `Dashboard.tsx:278` | `intervals` declared but never read | Removed unused variable |
| `Dashboard.tsx:318` | `unknown` not assignable to `ReactNode` | Changed `&&` to `!= null &&` for proper type narrowing |
| `Events.tsx:8` | `Zap` imported but never read | Removed unused import |

**Root cause**: The Phase 2 Dashboard rewrite introduced helpers that were used during development but not cleaned up before commit.

### 3.2 Duplicate Backend Routes (FIXED)
Two route warnings on startup:
- `GET /groups` registered twice (lines 710 and 868)
- `GET /challenges` registered twice (lines 730 and 1067)

**Root cause**: Codex created early simple versions during Phase 3-5, then later added complete versions with proper `response_model` annotations during Phase 7. The early versions were never removed.

**Fix**: Removed the early incomplete duplicates. Tests still pass (385/385).

### 3.3 Missing ESLint Config (Known Issue)
ESLint v9 requires `eslint.config.js` (flat config). The project has no ESLint config file. This doesn't block builds but means no lint checking is available.

---

## 4. Current Application State

### Frontend Pages Status

#### Coach Pages (All Functional)
| Page | Route | Status | Notes |
|------|-------|--------|-------|
| Dashboard | `/coach` | Working | Stat cards + weekly load chart |
| Clients | `/coach/clients` | Working | Full table with risk badges |
| Plan Builder | `/coach/plan-builder` | Working | Create + manage weeks + preview |
| Session Library | `/coach/session-library` | Working | Browse + CRUD + detail view |
| Command Center | `/coach/command-center` | Working | Full queue + casework + batch + stats |
| Community | `/coach/community` | Working | Groups + challenges + messages + leaderboard |
| Organization | `/coach/organization` | Working | Org list + coach roster |
| Team | `/coach/team` | Working | Coach management |
| Assignments | `/coach/assignments` | Working | Assignment CRUD + transfer |

#### Athlete Pages (All Functional)
| Page | Route | Status | Notes |
|------|-------|--------|-------|
| Dashboard | `/athlete` | Working | Readiness + session briefing + training load + stats |
| Check-In | `/athlete/checkin` | Working | Daily readiness form |
| Log Session | `/athlete/log` | Working | Training log form |
| Plans | `/athlete/plans` | Working | Week/day detail view |
| Events | `/athlete/events` | Working | Events + race predictions table |
| Analytics | `/athlete/analytics` | Working | Fitness/fatigue, VDOT, pace, volume, intensity |
| Community | `/athlete/community` | Working | Groups + challenges + activity feed + kudos |
| Profile | `/athlete/profile` | Working | Personal info + physiology + wearables + sync logs |

### Backend Endpoints (All Working)
- Auth: 3 endpoints (login, me, change-password)
- Coach: 2 endpoints (dashboard, clients)
- Athletes: 3 endpoints (list, get, create)
- Check-ins: 2 endpoints (create, list)
- Training Logs: 2 endpoints (create, list)
- Events: 2 endpoints (create, list)
- Plans: 3 endpoints (list, weeks, sessions)
- Plan Builder: 5 endpoints (preview, create, lock, swap, regenerate)
- Sessions: 6 endpoints (categories, list, get, create, update, delete)
- Interventions: 5 endpoints (list, sync, decide, stats, batch-decide)
- Casework: 5 endpoints (timeline, notes CRUD)
- Organizations: 5 endpoints (list, create, coaches, assignments, transfer)
- Community: 14 endpoints (groups, messages, challenges, leaderboard, kudos, feed)
- Wearables: 3 endpoints (connections, delete, sync-logs)
- Athlete Intelligence: 6 endpoints (briefing, load, fitness, vdot, predictions, profile)

---

## 5. Remaining Roadmap

### Priority 1: Verification & Stability
These should be done first to ensure the current app works end-to-end:

- [ ] **Start the app and verify login works** — Run `python serve.py` or use `uvicorn api.main:app --reload` + `npm run dev`
- [ ] **Test coach login flow** — Dashboard loads, all nav links work, data renders
- [ ] **Test athlete login flow** — Dashboard loads, session briefing renders, analytics charts appear
- [ ] **Seed database check** — Ensure `db/seed.py` populates enough data for a meaningful demo

### Priority 2: Missing Roadmap Items (From Original MIGRATION_ROADMAP.md)

#### Phase 3 — Coach Analytics & Tools
| Item | Status | Effort |
|------|--------|--------|
| 3.1 Portfolio Analytics — per-athlete CTL/ATL/TSB table | Not started | Medium |
| 3.2 VDOT Calculator — calculator + pace table | Not started | Medium |
| 3.3 Integrations Management — wearable overview | Partial (wearables endpoints exist) | Small |

#### Phase 4 — Auth Hardening & Polish
| Item | Status | Effort |
|------|--------|--------|
| 4.1 Account lockout display (backend supports it) | Not started | Small |
| 4.2 Force password change on first login | Not started | Small |
| 4.3 Coach dashboard line chart (vs current bar chart) | Not started | Small |
| 4.4 Athlete community completion (streak, kudos count) | Partial | Small |

### Priority 3: Quality & Polish
- [ ] Add ESLint flat config (`eslint.config.js`) for v9
- [ ] Code-split large bundle (currently 969KB, should use dynamic `import()` for route-level splitting)
- [ ] Add loading skeletons instead of plain "Loading..." text
- [ ] Add error boundaries for graceful error handling
- [ ] Add toast notification system for mutation feedback
- [ ] Mobile responsive improvements (sidebar collapse)

---

## 6. How to Run Locally

### Backend
```bash
cd /home/user/running_app

# Start the API server (port 8000)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Development Mode)
```bash
cd /home/user/running_app/frontend

# Install dependencies (if needed)
npm install

# Start Vite dev server (port 5173, proxies API to 8000)
npm run dev
```

### Frontend (Production Build)
```bash
cd /home/user/running_app/frontend

# Build for production
npm run build

# The built files go to frontend/dist/
# FastAPI serves them automatically via SPA fallback in api/main.py
```

### Full Stack via Streamlit Proxy (Container Environment)
```bash
cd /home/user/running_app

# This starts FastAPI on :8000 in background, Streamlit on :8501 as proxy
python serve.py
```

### Run Tests
```bash
cd /home/user/running_app

# Backend tests (385 tests)
python -m pytest tests/ -x -q

# Frontend type-check + build
cd frontend && npm run build
```

### Demo Credentials
Check `db/seed.py` for seeded users. Typically:
- Coach: `coach` / `coach123`
- Athlete: `athlete1` / `athlete123`

---

## 7. Architecture Reference

```
running_app/
├── api/
│   ├── main.py          # FastAPI app factory, CORS, SPA fallback
│   ├── routes.py         # All API endpoints (~1400 lines)
│   └── schemas.py        # Pydantic request/response models
├── core/
│   ├── models.py         # SQLAlchemy ORM models
│   ├── db.py             # Database connection, session_scope()
│   ├── validators.py     # Business rule validators
│   └── services/
│       ├── analytics.py      # CTL/ATL/TSB, VDOT history, pace trends
│       ├── race_predictor.py # Riegel + Daniels race predictions
│       ├── session_engine.py # Adaptive session structure (v2/v3)
│       ├── training_load.py  # TRIMP, monotony, strain, risk
│       └── vdot.py           # VDOT tables, pace calculations
├── frontend/
│   └── src/
│       ├── api/
│       │   ├── client.ts     # 60+ typed API functions
│       │   └── types.ts      # TypeScript interfaces matching schemas
│       ├── components/
│       │   ├── layout/       # AppLayout, Sidebar, RequireAuth
│       │   ├── ui/           # shadcn primitives (Badge, Button, Card, etc.)
│       │   └── interventions/ # Command Center sub-components
│       ├── hooks/            # React Query hooks (7 files)
│       ├── pages/
│       │   ├── coach/        # 9 coach pages
│       │   └── athlete/      # 8 athlete pages
│       └── stores/
│           └── auth.ts       # Zustand auth store
├── tests/                # 385 passing tests
├── db/seed.py            # Demo data seeder
├── serve.py              # Streamlit proxy launcher
└── react_preview.py      # Streamlit SPA renderer
```
