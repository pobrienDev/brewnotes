# Project state

Updated at the end of every phase or sub-phase. Newest at the top of each section.

## If you are starting a fresh session

1. Read `CLAUDE.md`, then this file, then the memory notes if any.
2. `git fetch` and check whether PR #10 (`phase-2-batches`) has been merged. If not, it is
   waiting for the user's review; do not merge it yourself. If yes, `git checkout main && git
   pull`, then branch `phase-3-breweries`.
3. Say the suggested effort for the step (Phase 3 data sync and map queries: high; the brewery
   seed/sync CLI and the bbox endpoint touch the data model, so xhigh for the migration) and
   begin. Local stack: `make db && make migrate && make seed`, then the backend on 8001 and
   Vite on 5180 on Patrick's Mac (see `CLAUDE.md` quirks); `backend-fake-login` in the desktop
   app's launch config gives a signed-in session without OAuth apps.

## Next up: Phase 3 (plan Section 11)

Discover (brewery map): initial load from the Open Brewery DB data dump into a `breweries`
table (obdb_id unique, type, address, lat/long nullable, website, phone, removed_at,
synced_at; index on (latitude, longitude)); a `sync-breweries` CLI run weekly by cron, upserting
by obdb_id and marking vanished rows removed; `GET /breweries?bbox=` (public, at most 500,
rate limited as a public read) and `GET /breweries/{id}`; a map with a keyed, domain-restricted
tile provider (decide the provider first, plan Section 14), clustering, type filter, "near me"
computed in the browser; brewery page; log a tasting at a brewery (tastings gain a nullable
`brewery_id`, beers gain `brewery_id` next to `brewery_name`). Check Open Brewery DB's licence
before committing any of its data (plan Appendix B). Done when the map loads quickly for any
visible area and a tasting can be logged from a brewery page.

## Phase status

| Phase | Scope (plan Section 11) | Status | Where |
|---|---|---|---|
| 2 | Batches with versioned JSONB snapshot and status workflow; readings with downsampled chart, apparent attenuation and current ABV; private beers; tastings; composite-key ownership; quotas; Playwright smoke tests in CI with a fake GitHub sign-in harness | Built Oct 9, 2026 on `phase-2-batches`, PR open for review | PR #10 |
| 1c | Recipes and custom-ingredient CRUD with ownership, quotas, cross-user matrix; the Phase 1 frontend screens | Merged Oct 8, 2026 | PR #9 |
| 1b | Domain math, scaling, style matching, BJCP + ingredient seeds, public calc/styles/catalog API | Merged Oct 8, 2026 | PR #8 |
| 1a | GitHub + Google OAuth, sessions, CSRF, logout, profile, export, deletion, login rate limits | Merged Oct 8, 2026 | PR #7 |
| 0 | Repo, CI, Docker, app factory, problem details, security headers, SPA fallback | Merged Oct 7, 2026 | first 9 commits |

Not started: Phase 3 (brewery map), Phase 4 (recommendations), optional devices. BeerXML
import/export is a stretch goal, not started.
Phase 1 and 2 "done when" criteria are exercised by the API tests and, for the browser, by the
Playwright smoke tests against the fake GitHub sign-in (sign in, build the Appendix A style
recipe, save and reload it, brew a batch, log readings, see the chart, rate the batch and a
commercial beer, second user sees none of it). Only the real-provider sign-in itself is
unverified in a browser until OAuth apps are registered in `.env`.

## What exists (API)

Public: `GET /health/{live,ready}`, `GET /auth/providers`, `GET /auth/login/{provider}`,
`GET /auth/callback/{provider}`, `POST /calc`, `POST /calc/scale`, `GET /styles`,
`GET /styles/{slug}`, `GET /catalog/{fermentables|hops|yeasts}`.
Signed in: `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/link/{provider}`,
`GET|PATCH|DELETE /me`, `GET /me/export` (schema_version 3), `DELETE /me/identities/{provider}`,
`GET|POST /recipes`, `GET|PUT|DELETE /recipes/{id}`, `POST /catalog/{kind}`,
`PATCH|DELETE /catalog/{kind}/{id}` (kind = fermentables | hops | yeasts),
`GET|POST /batches` (`?status=`), `GET|PATCH|DELETE /batches/{id}`,
`GET|POST /batches/{id}/readings` (`?points=` returns the downsampled series oldest first),
`DELETE /batches/{id}/readings/{rid}`, `GET|POST /beers` (`?q=`), `GET|PATCH|DELETE /beers/{id}`,
`GET|POST /tastings` (`?batch_id=`, `?beer_id=`), `GET|PATCH|DELETE /tastings/{id}`.
All under `/api/v1`. The OpenAPI document is committed at `frontend/openapi.json` (32 paths).
Test-only, from the e2e harness: `GET /api/v1/fake-github/{authorize,become}`.

Database (Alembic head `ed1a0d7dac28`): users, oauth_identities, sessions, styles,
style_ranges, fermentables, hops, yeasts, recipes, recipe_fermentables, recipe_hops,
recipe_yeasts, batches, readings, beers, tastings. Recipe children reference
(recipe_id, user_id); batches reference (recipe_id, user_id) with `ON DELETE SET NULL
(recipe_id)`; readings and tastings reference (batch_id, user_id); tastings also
(beer_id, user_id). Seed data: 124 BJCP 2021 styles (incl. 16 variants under 21B and 27A) with
513 ranges; 53 fermentables, 50 hops, 61 yeasts.

Frontend (`frontend/src`): pages for home, sign in, recipes list, recipe designer (live calc,
catalog autocomplete, style match range bars, scale dialog, unit toggle, session-storage
draft across sign-in, "brew this recipe"), styles browser / detail / compare, custom
ingredients, batches list / new batch / batch page (progress panel, lazily loaded Chart.js
chart, reading entry, readings table, details, recipe as brewed, tastings), beers, tastings
list / form, account and privacy. `lib/units.ts` is the only arithmetic (display conversion).
Hooks wrap the typed client; `RequireAuth` guards signed-in routes. Playwright specs live in
`frontend/e2e/` (`playwright.config.ts`, base URL 5180 locally, 8000 in CI).

## Numbers worth remembering

- Appendix A (American Pale Ale): GU 55.18, OG 1.055, FG 1.014, ABV 5.43, SRM 8.1; IBU 32.5
  (OG mode) or 33.8 (average-of-pre-boil mode). Fixture in `backend/tests/fixtures.py`.
- Sessions: idle 14 days, absolute 30 days, last_seen written at most hourly. OAuth state
  cookie 10 minutes. Rate limits: login 10/min/IP, calc 60/min/IP, public reads 120/min/IP,
  writes 120/min/user. Quotas: 500 recipes, 200 custom ingredients (all types together).
- Steep efficiency default 50%, brewhouse 72%, assumed attenuation 75%, whirlpool factor 0.5,
  first-wort bonus 10%, OG cap 1.200.
- Phase 2 quotas: 1,000 batches, 20,000 readings per batch, 5,000 beers, 5,000 tastings.
  Readings: gravity 0.980–1.200, temperature −10 to 110 °C, at least one of the two, timestamp
  must carry an offset and may not be more than a day in the future. Ratings 0.5–5 in half
  steps; tasting fields ≤2,000 chars each, notes ≤10,000. Chart `?points=` 2–1000 (UI asks
  for 200). Apparent attenuation = (OG − SG)/(OG − 1); OG is the measured one if recorded,
  else the snapshot's; current SG is the recorded FG if set, else the latest gravity reading.
- The e2e harness raises the login rate limit to 1000/min; the real one stays 10/min/IP.

## Repo settings

GitHub repo `pobrienDev/brewnotes` (public). Branch protection as described in `CLAUDE.md`;
the "End to end (Playwright smoke tests)" check was added to the required list with PR #10.
Secret scanning with push protection, Dependabot alerts and security updates, private
vulnerability reporting are on. CodeQL runs from `.github/workflows/codeql.yml` with
`.github/codeql/codeql-config.yml` (excludes `py/unused-global-variable` for Alembic files).

## Deferred or open

- Hosting provider: decide before the first deploy (Render, Railway, Fly.io; needs Postgres 18).
- Map tile provider: decide at the start of Phase 3.
- Node upgrade on the dev machine would unlock react-router 8 and jsdom 30.
- Swagger UI "Try it out" only works for reads because unsafe requests need the SPA's Origin.
- The account export builds one JSON document in memory; at the reading quota it gets large.
- Batches take their snapshot at creation and never refresh it; a "re-snapshot while planned"
  action would be easy to add if users ask.
- Device ingest (optional phase) adds `device_id` to readings and a devices table.
