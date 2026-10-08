# BrewNotes frontend

Vite + React + TypeScript. See the repository README for how to run it.

- `src/api/schema.d.ts` is generated from the backend's OpenAPI document (`make types` at the
  repository root). Never hand-write API types; components import `api` from `src/api/client.ts`.
- No brewing formulas live here. The only math is unit display conversion.
- `dangerouslySetInnerHTML` is banned by lint; notes are rendered as plain text.
