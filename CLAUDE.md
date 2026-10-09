# BrewNotes: working notes for Claude Code

Read this first in every session, then `docs/STATE.md` for where the project stands. Together
they are the portable version of what matters; the full plan lives outside the repo (below).

## The plan is the contract

- The agreed reference is **BrewNotes Project Plan Rev. 2** (Oct 7, 2026), a PDF kept outside
  the repo at `~/Desktop/Projects/BrewNotes_Project_Plan_v2.pdf` on Patrick's Mac. Copy it to
  any new machine; do not commit it. Sections to re-read before changing anything structural:
  2 (decision log), 4 (architecture rules), 5 (security, input limits), 6 (data model),
  11 (roadmap), 15 (handoff rules).
- Decision log (raise with the user before changing): public repo and deployment with open
  signup; GitHub and Google OAuth only, no passwords, no email stored; server-side opaque
  sessions hashed in Postgres; PostgreSQL 18 with database-generated UUIDv7 keys; commercial
  beers private per user; recommendations use only the app's own data; FastAPI + SQLAlchemy 2
  (sync) + Alembic backend, React + TypeScript (Vite) frontend; security items in, enterprise
  operations deferred (plan Section 13).
- Open decisions were confirmed at Phase 0 with the defaults: name BrewNotes, MIT, imperial
  display with metric toggle, Tailwind, BeerXML as a stretch goal.

## How we work

- Work one phase (or sub-phase) at a time on a branch `phase-<n>-<topic>`, open a PR, stop
  for review. **Never merge a PR without a fresh yes from the user, Dependabot's included.**
- `main` is protected: eight required checks (five CI jobs, two CodeQL analyses, the CodeQL
  alert gate), linear history, enforce_admins. Merge phase PRs with `--rebase` to keep the
  small commits; Dependabot PRs with `--squash`.
- Say the suggested effort level at the start of each step. Rough map: xhigh for brewing math,
  security, data model and migrations, ownership/CRUD; high for ordinary implementation and
  UI; medium for scaffolding, seed data, docs; low for mechanical regeneration.
- Commit in small, descriptive steps. No secrets; only `.env.example`. Never commit third-party
  data without checking its license (plan Appendix B). BJCP numbers are facts; summaries are ours.

## Conventions that CI and review enforce

- Layers: `api/` (HTTP only, plain `def` routes) → `services/` (use cases, one transaction per
  request, receives the user explicitly) → `repositories/` (all SQLAlchemy; every query on
  user-owned data takes `user_id`) → `domain/` (pure dataclasses, no I/O). `schemas/` hold
  every numeric bound (Section 5), with `allow_inf_nan=False` and `extra="forbid"` via
  `app.schemas.Schema`. Exception on record: the two OAuth routes are `async def` because
  Authlib is async; their DB work runs in `run_in_threadpool`.
- Every error is RFC 9457 problem details; validation errors never echo submitted values.
- Another user's resource is a 404, never a 403. Child rows carry `user_id` so composite
  foreign keys enforce same-owner references in the database.
- Lists use cursor (keyset) pagination `{items, next_cursor}`, default 50, max 100.
- Every POST/PUT/PATCH/DELETE must carry `Origin == PUBLIC_BASE_URL` (403 otherwise). Tests use
  the `CSRF` header dict from `tests/conftest.py`.
- Constraint names come from the metadata naming convention in `app/db.py`; name every CHECK.
- Tests: API tests run against the real Postgres test database inside a rolled-back
  transaction (`db_connection` fixture, savepoint sessions). Reference data comes from the
  session-scoped `seeded` fixture. Fake OAuth providers live in `tests/fakes.py`; drive flows
  with `tests/helpers.py` (`login_as`, `make_client`).
- CodeQL gotchas that fail the PR gate: no HTTP calls inside `assert`; check URLs with
  `startswith`, not `in`; never log a raw request path segment (map it to a constant first);
  `cast()` with real types, not strings.
- Regenerate the frontend contract after any schema change: `make types` (writes
  `frontend/openapi.json` and `frontend/src/api/schema.d.ts`; CI fails if stale). No brewing
  math in TypeScript; `dangerouslySetInnerHTML` is lint-banned.
- Partial updates (PATCH) subclass `app.schemas.PartialUpdate`: omitted fields stay, explicit
  null is rejected unless the field is listed in `nullable`. Body references to another user's
  rows (a recipe to brew, a batch or beer to rate) are 422 "unknown …", not 404.
- Batches freeze the recipe in `recipe_snapshot` (JSONB, `schema_version`); read it only through
  `app.schemas.snapshot.parse_snapshot`, and add a new version there rather than editing V1.
- Browser smoke tests: `backend/tests/e2e/harness.py` serves the real app with the API tests'
  fake GitHub behind "Continue with GitHub" (`make dev-fake-login` + `make dev-frontend`, then
  `make e2e`). CI runs them against the built frontend. Use it for any signed-in walk-through on
  a machine without registered OAuth apps; `GET /api/v1/fake-github/become?subject=1002&name=…`
  switches accounts (returns 204, so call it with curl, not by navigating a browser to it).

## Data provenance

`backend/tools/bjcp_2021_vitals.py` rebuilds `backend/data/styles_bjcp_2021.json` from the BJCP
2021 style pages (sequential fetch with a pause, cached locally) and keeps our summaries. It
reproduces the committed file byte for byte; run it only when the guideline numbers need
re-checking. Ingredient files are hand-curated and edited directly.

## Commands

```bash
make db && make install && make migrate && make seed && make dev   # local stack
make check                                                        # everything CI runs
cd backend && uv run pytest -q                                    # backend tests only
cd backend && uv run python -m app.cli --help                     # seed, cleanup-sessions, export-openapi
make dev-fake-login                                               # backend with fake GitHub sign-in (port 8000)
make e2e                                                          # Playwright smoke tests against the dev stack
```

## Environment quirks (Patrick's Mac, Oct 2026)

- `uv` is at `~/.local/bin/uv` (installed with the standalone installer; `brew install uv` tried
  to build LLVM from source). Prefix `PATH="$HOME/.local/bin:$PATH"` in non-login shells.
- Node is 22.14, so `react-router` stays on 7.x and `jsdom` on 29 until Node is upgraded;
  Dependabot ignores those majors on purpose.
- Ports 8000 (uvicorn) and 5173 (Vite) are held by month-old dev servers from another project
  (dartmetrics); 5174 is Docker's. Run this backend on 8001 and Vite on 5180:
  `frontend/.env.local` carries `VITE_API_PROXY_TARGET=http://localhost:8001` (gitignored), and
  the Claude desktop app's dev-server config `.claude/launch.json` (gitignored, per machine)
  starts both with `PUBLIC_BASE_URL=http://localhost:5180` so the CSRF origin check passes; a
  third entry `backend-fake-login` runs `tests.e2e.harness:app` the same way for signed-in
  checks. On another machine use the standard 8000/5173 and skip both files.
- Playwright's Chromium is installed per machine (`npx playwright install chromium`, ~100 MB).
- Authlib 1.8 runs on `httpx2` and validates ID tokens with `joserfc`; Starlette 1.7's
  TestClient also wants `httpx2`. Tests talk to the app over `https://testserver` so the
  `__Host-` cookies behave as in production.
- Docker Desktop accepts connections before the container listens; smoke tests should retry on
  any error, not only on connection refused.
