# BrewNotes backend

FastAPI service. See the repository README for how to run it. Layers:

- `app/api/` HTTP only: parse input, call a service, shape the response. Plain `def` routes.
- `app/services/` use cases, transactions, authorization decisions.
- `app/repositories/` all SQLAlchemy queries; every query on user-owned data filters by user ID.
- `app/domain/` pure brewing logic: math, units, style matching, scaling. No ORM, no I/O.
- `app/schemas/` Pydantic request and response models; all numeric bounds live here.
- `app/models/` SQLAlchemy models.
- `app/security/` sessions, CSRF, headers, rate limiting, OAuth.
