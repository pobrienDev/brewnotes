# BrewNotes

A craft beer app that follows a beer from recipe to glass: design it, brew it, taste it, discover more.

BrewNotes combines a brewing calculator, a brewing and tasting log, and beer discovery into one app built around a single object: a beer. The calculator and style browser work without signing in; saving anything requires an account via GitHub or Google.

**Status:** Phase 1b (brewing math, styles and catalog). Nothing is deployed yet.

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
