import createClient from 'openapi-fetch'

import type { paths } from './schema'

// Same-origin API. Types come from the backend's OpenAPI spec (see `npm run generate-api`).
// fetch is looked up per call so test doubles and polyfills installed later are honoured.
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => globalThis.fetch(request),
})
