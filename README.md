# BrewNotes

A craft beer app that follows a beer from recipe to glass: design it, brew it, taste it, discover more.

BrewNotes combines a brewing calculator, a brewing and tasting log, and beer discovery into one app built around a single object: a beer. The calculator and style browser work without signing in; saving anything requires an account via GitHub or Google.

**Status:** Phase 0 (foundation). Nothing is deployed yet.

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
make dev       # FastAPI on :8000 and Vite on :5173 (proxies /api)
```

Open http://localhost:5173. The API's own docs are at http://localhost:8000/api/v1/docs in development.

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
