# Project state

Updated at the end of every phase or sub-phase. Newest at the top of each section.

## If you are starting a fresh session

1. Read `CLAUDE.md`, then this file, then the memory notes if any.
2. `git fetch` and check whether PR #12 (`phase-4-recommendations`) has been merged. If not,
   it is waiting for the user's review; do not merge it yourself. If yes, `git checkout main
   && git pull`. Every numbered phase of plan Section 11 is then built; what remains is below.
3. Ask the user what comes next rather than starting something: the plan's remaining items
   are the optional device-ingest phase, the BeerXML stretch goal, and the first deployment
   (hosting provider still to be chosen, plan Section 14). Say the suggested effort for the
   step and begin. Local stack: `make db && make migrate && make seed && make
   sync-breweries`, then the backend on 8001 and Vite on 5180 on Patrick's Mac (see
   `CLAUDE.md` quirks); `backend-fake-login` in the desktop app's launch config gives a
   signed-in session without OAuth apps. The harness does not auto-reload: restart it after
   backend changes.

## Next up: nothing scheduled (plan Section 11 is complete)

Candidates, in the plan's order: the optional fermentation-device phase (per-device tokens,
`POST /devices/ingest`, `device_id` on readings; plan Section 9), the BeerXML import/export
stretch goal, and the first deployment (choose the host, register the OAuth apps, add the
MapTiler key, schedule `sync-breweries` weekly). Collaborative-filtering recommendations
stay deferred until the app's own data supports them (plan Section 13).

## Phase status

| Phase | Scope (plan Section 11) | Status | Where |
|---|---|---|---|
| 4 | Style recommendations from the user's own tastings: average rating per style and family, untried styles closest in vital statistics to the ones rated well with reasons and differences, cold-start questions below 5 styled tastings, the "For you" page | Built Oct 9, 2026 on `phase-4-recommendations`, PR open for review | PR #12 |
| 3 | Breweries from Open Brewery DB with a weekly sync command, public bbox/search/detail endpoints, Leaflet map with clustering, type filter and "near me", brewery pages, brewery links on beers and tastings | Merged Oct 9, 2026 | PR #11 |
| 2 | Batches with versioned JSONB snapshot and status workflow; readings with downsampled chart, apparent attenuation and current ABV; private beers; tastings; composite-key ownership; quotas; Playwright smoke tests in CI with a fake GitHub sign-in harness | Merged Oct 9, 2026 | PR #10 |
| 1c | Recipes and custom-ingredient CRUD with ownership, quotas, cross-user matrix; the Phase 1 frontend screens | Merged Oct 8, 2026 | PR #9 |
| 1b | Domain math, scaling, style matching, BJCP + ingredient seeds, public calc/styles/catalog API | Merged Oct 8, 2026 | PR #8 |
| 1a | GitHub + Google OAuth, sessions, CSRF, logout, profile, export, deletion, login rate limits | Merged Oct 8, 2026 | PR #7 |
| 0 | Repo, CI, Docker, app factory, problem details, security headers, SPA fallback | Merged Oct 7, 2026 | first 9 commits |

Not started: the optional device phase. BeerXML import/export is a stretch goal, not
started. Nothing is deployed.
Phase 1 to 4 "done when" criteria are exercised by the API tests and, for the browser, by the
Playwright smoke tests against the fake GitHub sign-in (sign in, build the Appendix A style
recipe, save and reload it, brew a batch, log readings, see the chart, rate the batch and a
commercial beer, second user sees none of it, find a brewery and log a tasting there, answer
the cold-start questions and see explained suggestions). The map "loads quickly for any
visible area": the bbox query uses the (latitude, longitude) index and is capped at 500 rows.
"A user with 10 or more tastings gets sensible, explained style suggestions" is the unit test
`test_ten_tastings_give_sensible_explained_suggestions` against the real BJCP data plus the
API test with eleven styled tastings. Only the real-provider sign-in itself is unverified in a
browser until OAuth apps are registered in `.env`; map tiles need a MapTiler key in
`frontend/.env.local`.

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
`brewery_id`; the export is schema_version 4. `GET /recommendations/styles` (`?limit=` 1–50,
`?strength=`, `?bitterness=`, `?color=` for the cold start) returns `{tastings_with_style,
min_tastings, cold_start, answered, styles, families, suggestions}`; nothing is stored, the
answers travel as query parameters.
All under `/api/v1`. The OpenAPI document is committed at `frontend/openapi.json` (37 paths).
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
pages (details, the user's tastings and beers there, "log a tasting here"), and "For you"
(`/for-you`: cold-start questions whose answers live in the URL and in localStorage per user,
suggestion cards with the reason and the differences in words, the rating table per style and
per family). `lib/units.ts` is the only brewing arithmetic (display conversion); `lib/map.ts`
holds the haversine distance for "near me" sorting; `lib/recommendations.ts` only words the
API's metric directions ("stronger, less bitter and darker").
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
- Recommendations (`app/domain/recommend.py`): two styles are |Δmidpoint| + ½|Δhalf-width|
  apart per metric, nearest pair of labelled ranges, IBU and SRM on a square-root scale,
  normalised by SCALE (og 0.10, fg 0.05, abv 12, ibu √ 10, srm √ 5), combined as a weighted
  RMS (og and fg 0.5, the rest 1). Affinity = clamp((mean − 3)/2) · n/(n+1); the answers are
  one preference at 0.75. Score = Σ affinity · exp(−distance/0.12); only positive scores are
  suggested; at most two reasons; a midpoint difference ≥ 8% of the metric's spread is
  "higher"/"lower". Median nearest-neighbour distance across the 102 styles with ranges is
  0.052. Cold start below `recommendation_min_tastings` (5) styled tastings; limit 1–50,
  default 10. The 22 styles without ranges (specialty, historical, fruit, smoked, wood-aged
  and the like) are never suggested but do show in the rating table.

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
- Recommendations use vital statistics only; flavour descriptors (hop character, yeast,
  sourness) are not in the data, so a Berliner Weisse and a cream ale can look alike. The
  cold-start answers are not stored server-side; if users want them kept across devices a
  small `style_preferences` column on users would do it.
