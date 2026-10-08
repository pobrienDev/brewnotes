# Project state

Updated at the end of every phase or sub-phase. Newest at the top of each section.

## Phase status

| Phase | Scope (plan Section 11) | Status | Where |
|---|---|---|---|
| 1c | Recipes and custom-ingredient CRUD with ownership, quotas, cross-user matrix; the Phase 1 frontend screens | Built Oct 8, 2026 on `phase-1c-recipes`, PR open for review | PR #9 |
| 1b | Domain math, scaling, style matching, BJCP + ingredient seeds, public calc/styles/catalog API | Merged Oct 8, 2026 | PR #8 |
| 1a | GitHub + Google OAuth, sessions, CSRF, logout, profile, export, deletion, login rate limits | Merged Oct 8, 2026 | PR #7 |
| 0 | Repo, CI, Docker, app factory, problem details, security headers, SPA fallback | Merged Oct 7, 2026 | first 9 commits |

Not started: Phase 2 (batches, readings, beers, tastings), Phase 3 (brewery map), Phase 4
(recommendations), optional devices. BeerXML import/export is a stretch goal, not started.
Phase 1 "done when" still to confirm by hand with real OAuth apps: a user signs in with
GitHub, builds the Appendix A recipe, sees 18B as a fit, scales to 10 gal, saves and reloads
it; a second user gets 404; deleting the first account removes everything. The API tests cover
each of these steps; the browser walk-through needs registered OAuth apps in `.env`.

## What exists (API)

Public: `GET /health/{live,ready}`, `GET /auth/providers`, `GET /auth/login/{provider}`,
`GET /auth/callback/{provider}`, `POST /calc`, `POST /calc/scale`, `GET /styles`,
`GET /styles/{slug}`, `GET /catalog/{fermentables|hops|yeasts}`.
Signed in: `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/link/{provider}`,
`GET|PATCH|DELETE /me`, `GET /me/export`, `DELETE /me/identities/{provider}`,
`GET|POST /recipes`, `GET|PUT|DELETE /recipes/{id}`, `POST /catalog/{kind}`,
`PATCH|DELETE /catalog/{kind}/{id}` (kind = fermentables | hops | yeasts).
All under `/api/v1`. The OpenAPI document is committed at `frontend/openapi.json`.

Database (Alembic head): users, oauth_identities, sessions, styles, style_ranges,
fermentables, hops, yeasts, recipes, recipe_fermentables, recipe_hops, recipe_yeasts.
Recipe children carry user_id and reference (recipe_id, user_id). Seed data: 124 BJCP 2021 styles (incl. 16 variants under 21B and
27A) with 513 ranges; 53 fermentables, 50 hops, 61 yeasts.

Frontend (`frontend/src`): pages for home, sign in, recipes list, recipe designer (live calc,
catalog autocomplete, style match range bars, scale dialog, unit toggle, session-storage
draft across sign-in), styles browser / detail / compare, custom ingredients, account and
privacy. `lib/units.ts` is the only arithmetic (display conversion). Hooks wrap the typed
client; `RequireAuth` guards signed-in routes.

## Numbers worth remembering

- Appendix A (American Pale Ale): GU 55.18, OG 1.055, FG 1.014, ABV 5.43, SRM 8.1; IBU 32.5
  (OG mode) or 33.8 (average-of-pre-boil mode). Fixture in `backend/tests/fixtures.py`.
- Sessions: idle 14 days, absolute 30 days, last_seen written at most hourly. OAuth state
  cookie 10 minutes. Rate limits: login 10/min/IP, calc 60/min/IP, public reads 120/min/IP,
  writes 120/min/user. Quotas: 500 recipes, 200 custom ingredients (all types together).
- Steep efficiency default 50%, brewhouse 72%, assumed attenuation 75%, whirlpool factor 0.5,
  first-wort bonus 10%, OG cap 1.200.

## Repo settings

GitHub repo `pobrienDev/brewnotes` (public). Branch protection as described in `CLAUDE.md`.
Secret scanning with push protection, Dependabot alerts and security updates, private
vulnerability reporting are on. CodeQL runs from `.github/workflows/codeql.yml` with
`.github/codeql/codeql-config.yml` (excludes `py/unused-global-variable` for Alembic files).

## Deferred or open

- Hosting provider: decide before the first deploy (Render, Railway, Fly.io; needs Postgres 18).
- Map tile provider: decide at the start of Phase 3.
- Node upgrade on the dev machine would unlock react-router 8 and jsdom 30.
- Swagger UI "Try it out" only works for reads because unsafe requests need the SPA's Origin.
