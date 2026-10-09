# Project state

Updated at the end of every phase or sub-phase. Newest at the top of each section.

## If you are starting a fresh session

1. Read `CLAUDE.md`, then this file, then the memory notes if any.
2. `git fetch` and check whether PR #11 (`phase-3-breweries`) has been merged. If not, it is
   waiting for the user's review; do not merge it yourself. If yes, `git checkout main && git
   pull`, then branch `phase-4-recommendations`.
3. Say the suggested effort for the step (Phase 4 recommendation logic: xhigh for the scoring
   and its tests, high for the screens) and begin. Local stack: `make db && make migrate &&
   make seed && make sync-breweries`, then the backend on 8001 and Vite on 5180 on Patrick's
   Mac (see `CLAUDE.md` quirks); `backend-fake-login` in the desktop app's launch config gives
   a signed-in session without OAuth apps. The harness does not auto-reload: restart it after
   backend changes.

## Next up: Phase 4 (plan Section 11)

Recommendations from the app's own data only (decision D7): compute the user's average rating
per style and style family on request (tastings of beers with a style, and of batches whose
snapshot names a target style); suggest untried styles whose stat ranges are closest to the
user's highest-rated styles, each with a reason ("because you rated X highly"); a cold start
with a few quick preference questions when a user has fewer than about 5 tastings.
`GET /recommendations/styles` (user). Done when a user with 10 or more tastings gets sensible,
explained style suggestions. Collaborative filtering waits (plan Section 13). Domain first:
a pure scoring function over (style ranges, user's style ratings) with property tests.

## Phase status

| Phase | Scope (plan Section 11) | Status | Where |
|---|---|---|---|
| 3 | Breweries from Open Brewery DB with a weekly sync command, public bbox/search/detail endpoints, Leaflet map with clustering, type filter and "near me", brewery pages, brewery links on beers and tastings | Built Oct 9, 2026 on `phase-3-breweries`, PR open for review | PR #11 |
| 2 | Batches with versioned JSONB snapshot and status workflow; readings with downsampled chart, apparent attenuation and current ABV; private beers; tastings; composite-key ownership; quotas; Playwright smoke tests in CI with a fake GitHub sign-in harness | Merged Oct 9, 2026 | PR #10 |
| 1c | Recipes and custom-ingredient CRUD with ownership, quotas, cross-user matrix; the Phase 1 frontend screens | Merged Oct 8, 2026 | PR #9 |
| 1b | Domain math, scaling, style matching, BJCP + ingredient seeds, public calc/styles/catalog API | Merged Oct 8, 2026 | PR #8 |
| 1a | GitHub + Google OAuth, sessions, CSRF, logout, profile, export, deletion, login rate limits | Merged Oct 8, 2026 | PR #7 |
| 0 | Repo, CI, Docker, app factory, problem details, security headers, SPA fallback | Merged Oct 7, 2026 | first 9 commits |

Not started: Phase 4 (recommendations), optional devices. BeerXML import/export is a
stretch goal, not started.
Phase 1 to 3 "done when" criteria are exercised by the API tests and, for the browser, by the
Playwright smoke tests against the fake GitHub sign-in (sign in, build the Appendix A style
recipe, save and reload it, brew a batch, log readings, see the chart, rate the batch and a
commercial beer, second user sees none of it, find a brewery and log a tasting there). The map
"loads quickly for any visible area": the bbox query uses the (latitude, longitude) index and
is capped at 500 rows. Only the real-provider sign-in itself is unverified in a browser until
OAuth apps are registered in `.env`; map tiles need a MapTiler key in `frontend/.env.local`.

## What exists (API)

Public: `GET /health/{live,ready}`, `GET /auth/providers`, `GET /auth/login/{provider}`,
`GET /auth/callback/{provider}`, `POST /calc`, `POST /calc/scale`, `GET /styles`,
`GET /styles/{slug}`, `GET /catalog/{fermentables|hops|yeasts}`, `GET /breweries?bbox=`
(`type=` repeatable, `include_closed=`; `{items, truncated, limit}`), `GET /breweries/search?q=`,
`GET /breweries/types`, `GET /breweries/{id}`.
Signed in: `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/link/{provider}`,
`GET|PATCH|DELETE /me`, `GET /me/export` (schema_version 3), `DELETE /me/identities/{provider}`,
`GET|POST /recipes`, `GET|PUT|DELETE /recipes/{id}`, `POST /catalog/{kind}`,
`PATCH|DELETE /catalog/{kind}/{id}` (kind = fermentables | hops | yeasts),
`GET|POST /batches` (`?status=`), `GET|PATCH|DELETE /batches/{id}`,
`GET|POST /batches/{id}/readings` (`?points=` returns the downsampled series oldest first),
`DELETE /batches/{id}/readings/{rid}`, `GET|POST /beers` (`?q=`, `?brewery_id=`),
`GET|PATCH|DELETE /beers/{id}`, `GET|POST /tastings` (`?batch_id=`, `?beer_id=`,
`?brewery_id=`), `GET|PATCH|DELETE /tastings/{id}`. Beers and tastings carry an optional
`brewery_id`; the export is schema_version 4.
All under `/api/v1`. The OpenAPI document is committed at `frontend/openapi.json` (36 paths).
Test-only, from the e2e harness: `GET /api/v1/fake-github/{authorize,become}`.

Database (Alembic head `f5cb7deb1af2`): users, oauth_identities, sessions, styles,
style_ranges, fermentables, hops, yeasts, recipes, recipe_fermentables, recipe_hops,
recipe_yeasts, batches, readings, beers, tastings, breweries (obdb_id unique, removed_at,
synced_at, index on (latitude, longitude); beers.brewery_id and tastings.brewery_id SET NULL). Recipe children reference
(recipe_id, user_id); batches reference (recipe_id, user_id) with `ON DELETE SET NULL
(recipe_id)`; readings and tastings reference (batch_id, user_id); tastings also
(beer_id, user_id). Seed data: 124 BJCP 2021 styles (incl. 16 variants under 21B and 27A) with
513 ranges; 53 fermentables, 50 hops, 61 yeasts. Breweries are loaded by `sync-breweries`
(about 12,000 rows from Open Brewery DB; the ten-row test fixture is
`backend/tests/data/breweries_sample.csv`).

Frontend (`frontend/src`): pages for home, sign in, recipes list, recipe designer (live calc,
catalog autocomplete, style match range bars, scale dialog, unit toggle, session-storage
draft across sign-in, "brew this recipe"), styles browser / detail / compare, custom
ingredients, batches list / new batch / batch page (progress panel, lazily loaded Chart.js
chart, reading entry, readings table, details, recipe as brewed, tastings), beers, tastings
list / form, account and privacy, discover (Leaflet map with MapTiler tiles, clustering, type
filter, search, "near me" via the browser's geolocation, list of what is in view) and brewery
pages (details, the user's tastings and beers there, "log a tasting here"). `lib/units.ts`
is the only brewing arithmetic (display conversion); `lib/map.ts` holds the haversine distance
for "near me" sorting.
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
- Breweries: map requests capped at `map_max_results` (500); bbox is west,south,east,north and
  may cross the antimeridian (west > east); closed breweries hidden unless asked for; dump
  download capped at 50 MB; sync refuses an empty file rather than flagging everything removed.

## Repo settings

GitHub repo `pobrienDev/brewnotes` (public). Branch protection as described in `CLAUDE.md`;
the "End to end (Playwright smoke tests)" check was added to the required list with PR #10.
Secret scanning with push protection, Dependabot alerts and security updates, private
vulnerability reporting are on. CodeQL runs from `.github/workflows/codeql.yml` with
`.github/codeql/codeql-config.yml` (excludes `py/unused-global-variable` for Alembic files).

## Deferred or open

- Hosting provider: decide before the first deploy (Render, Railway, Fly.io; needs Postgres 18).
- Node upgrade on the dev machine would unlock react-router 8 and jsdom 30.
- Swagger UI "Try it out" only works for reads because unsafe requests need the SPA's Origin.
- The account export builds one JSON document in memory; at the reading quota it gets large.
- Batches take their snapshot at creation and never refresh it; a "re-snapshot while planned"
  action would be easy to add if users ask.
- Device ingest (optional phase) adds `device_id` to readings and a devices table.
- Brewery queries are plain B-tree range scans; PostGIS only if they get slow (plan Section 13).
- The tastings and beers lists have no "near this brewery" search; linking happens through
  the picker (search by name or city).
