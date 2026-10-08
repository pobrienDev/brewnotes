# Security policy

BrewNotes is a personal project with a public repository and a public deployment. Security reports are welcome.

## Reporting a vulnerability

Please do not open a public issue for security problems.

Use GitHub's private vulnerability reporting on this repository ("Security" tab, "Report a vulnerability"). Include steps to reproduce and the impact you believe it has. You should hear back within a week.

## Scope

- The application code in this repository
- The public deployment, once one exists

Automated scanning that generates load against the deployment is out of scope; the app is run by one person on a small instance.

## What is already in place

- Sign-in only through GitHub and Google OAuth; no passwords are stored
- Server-side sessions with hashed tokens; logout revokes them
- CSRF protection via same-site cookies and an Origin check on every unsafe request
- Ownership enforced in every query and in the database schema
- Rate limits, input bounds, and request size limits on all endpoints
- Secret scanning, Dependabot, CodeQL, and dependency audits in CI
