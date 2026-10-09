# BrewNotes

A craft beer app that follows a beer from recipe to glass: design it, brew it, taste it, discover more.

BrewNotes combines a brewing calculator, a brewing and tasting log, and beer discovery into one app built around a single object: a beer. The calculator and style browser work without signing in; saving anything requires an account via GitHub or Google.

**Status:** Phases 1 to 3 complete in development (accounts, recipe designer, styles, catalog, batches with readings and a fermentation chart, private commercial beers, tastings, a brewery map from Open Brewery DB). Nothing is deployed yet.

## Stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2 (synchronous sessions), Alembic, PostgreSQL 18, psycopg 3
- **Frontend:** React + TypeScript, Vite, TanStack Query, React Router, Tailwind CSS
- **Contract:** the backend's OpenAPI spec generates the frontend's API types; no brewing math lives in TypeScript
- **Auth:** GitHub and Google OAuth only, server-side sessions. No passwords, no email.

## Local development

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 22, Docker.

```bash
cp .env.example .env
make db        # start Postgres 18 in Docker (creates dev and test databases)
make install   # backend and frontend dependencies
make migrate   # apply database migrations
make seed      # load BJCP 2021 styles and the built-in ingredient catalog (idempotent)
make sync-breweries  # load Open Brewery DB (idempotent; weekly from cron in production)
make dev       # FastAPI on :8000 and Vite on :5173 (proxies /api)
```

Open http://localhost:5173. The API's own docs are at http://localhost:8000/api/v1/docs in development.

### Sign-in providers

Sign-in uses GitHub and Google OAuth; there are no passwords. Register one app per provider
per environment (development and production use separate apps) and put the client ID and
secret in `.env`. Without credentials for a provider, its sign-in button is simply absent.

| Provider | Where | Callback / redirect URI (development) |
|---|---|---|
| GitHub | Settings → Developer settings → OAuth Apps → New OAuth App | `http://localhost:5173/api/v1/auth/callback/github` |
| Google | Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web application) | `http://localhost:5173/api/v1/auth/callback/google` |

The callback URL is always `PUBLIC_BASE_URL` + `/api/v1/auth/callback/<provider>`; in
production that is your real https origin. GitHub needs no scopes (public profile only);
Google needs the `openid` and `profile` scopes, which the app requests itself. No email is
requested or stored.

### Signed-in screens without OAuth apps

`make dev-fake-login` starts the backend with a fake GitHub standing in for the OAuth app
(`backend/tests/e2e/harness.py`): "Continue with GitHub" signs you in as a test account
immediately. Pair it with `make dev-frontend`. The browser smoke tests use the same harness.

### Breweries and the map

`make sync-breweries` loads Open Brewery DB's data dump (about 12,000 breweries, MIT licensed)
and is safe to re-run; in production the host's cron runs it weekly. Breweries that vanish
upstream are flagged, never deleted, so tastings logged there keep working.

Map tiles come from [MapTiler](https://www.maptiler.com/) (plan Section 14: a keyed,
domain-restricted provider). Put a key in `frontend/.env.local` as `VITE_MAP_TILE_KEY=...` and
restrict it to your site's origin in MapTiler Cloud (API keys → Allowed HTTP origins). Without a
key the map still shows markers on a blank background. Another raster provider only needs a
different URL template in `frontend/src/lib/map.ts` and its host in `MAP_TILE_HOST` for the
content security policy.

### Reference data

`backend/data/` holds the seed files. `styles_bjcp_2021.json` carries the codes, names and
numeric ranges of the BJCP 2021 Beer Style Guidelines with a link to each style's page;
the one-line summaries are written for BrewNotes and are not guideline text. The ingredient
files are hand-curated typical values from manufacturers' published specifications. `make seed`
upserts everything by slug or name, so it is safe to re-run after editing a file.

### Requests that change data

Every POST, PUT, PATCH and DELETE must carry an `Origin` header equal to `PUBLIC_BASE_URL`,
or it is rejected with 403. Browsers send it automatically; curl does not, so add
`-H "Origin: http://localhost:5173"` when poking at the API by hand. Swagger UI at
`/api/v1/docs` runs from the backend's own origin, so its "Try it out" works for reads only.

Other targets:

```bash
make test      # backend and frontend tests
make lint      # ruff, mypy, eslint, tsc
make types     # export OpenAPI and regenerate frontend API types
make check     # everything CI runs
make e2e       # Playwright smoke tests; needs make dev-fake-login and make dev-frontend running
```

## Repository layout

```
backend/   FastAPI app: api/ services/ repositories/ domain/ schemas/ models/ security/
frontend/  Vite + React + TypeScript app; src/api/ is generated from the OpenAPI spec
docker/    Postgres init scripts for docker-compose
.github/   CI workflows and Dependabot
```

## Security and privacy

See [SECURITY.md](SECURITY.md) for how to report a vulnerability and [PRIVACY.md](PRIVACY.md) for what the app stores.

## License

[MIT](LICENSE)
