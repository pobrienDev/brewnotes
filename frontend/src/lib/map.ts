import type { components } from '../api/schema'

export type BrewerySummary = components['schemas']['BrewerySummary']
export type BreweryDetail = components['schemas']['BreweryDetail']
export type BreweryRef = components['schemas']['BreweryRef']

export interface Bounds {
  west: number
  south: number
  east: number
  north: number
}

export interface LatLng {
  lat: number
  lng: number
}

/** The API's bbox parameter: west,south,east,north, trimmed so query keys stay stable. */
export function bboxString(b: Bounds): string {
  return [b.west, b.south, b.east, b.north].map((v) => v.toFixed(4)).join(',')
}

const wrapLongitude = (lng: number) =>
  lng >= -180 && lng <= 180 ? lng : ((((lng + 180) % 360) + 360) % 360) - 180

/**
 * Leaflet reports the bounds of whatever is on screen, which past the antimeridian or when
 * zoomed out beyond one world run outside ±180. The API wants real coordinates: a view at
 * least a world wide becomes the whole world, anything else is wrapped (west > east then
 * means the box crosses the antimeridian, which the API understands).
 */
export function clampBounds(b: Bounds): Bounds {
  const south = Math.max(-90, Math.min(90, b.south))
  const north = Math.max(-90, Math.min(90, b.north))
  if (b.east - b.west >= 360) return { west: -180, south, east: 180, north }
  return { west: wrapLongitude(b.west), south, east: wrapLongitude(b.east), north }
}

export interface TileConfig {
  url: string
  attribution: string
  tileSize: number
  zoomOffset: number
  maxZoom: number
}

/**
 * MapTiler raster tiles (plan Section 14: a keyed, domain-restricted provider). Without a key
 * the map shows markers on a blank background and says why.
 */
export function tileConfig(key: string | undefined): TileConfig | null {
  if (!key) return null
  return {
    url: `https://api.maptiler.com/maps/streets-v2/{z}/{x}/{y}.png?key=${encodeURIComponent(key)}`,
    attribution:
      '&copy; <a href="https://www.maptiler.com/copyright/" target="_blank" rel="noopener">MapTiler</a> ' +
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>',
    tileSize: 512,
    zoomOffset: -1,
    maxZoom: 19,
  }
}

export const MAP_TILE_KEY: string | undefined = import.meta.env.VITE_MAP_TILE_KEY || undefined

export const BREWERY_TYPE_LABELS: Record<string, string> = {
  micro: 'Microbrewery',
  nano: 'Nanobrewery',
  regional: 'Regional brewery',
  brewpub: 'Brewpub',
  large: 'Large brewery',
  planning: 'In planning',
  bar: 'Bar',
  contract: 'Contract brewer',
  proprietor: 'Proprietor',
  taproom: 'Taproom',
  cidery: 'Cidery',
  beergarden: 'Beer garden',
  closed: 'Closed',
}

export const typeLabel = (type: string) => BREWERY_TYPE_LABELS[type] ?? type

export function formatPlace(b: Pick<BreweryRef, 'city' | 'state_province' | 'country'>): string {
  return [b.city, b.state_province, b.country].filter(Boolean).join(', ')
}

export function formatAddress(b: BreweryDetail): string {
  const street = [b.address_1, b.address_2, b.address_3].filter(Boolean).join(', ')
  const place = [b.city, b.state_province, b.postal_code].filter(Boolean).join(' ')
  return [street, place, b.country].filter(Boolean).join(', ')
}

const EARTH_RADIUS_KM = 6371.0088

/** Great-circle distance (haversine), for sorting what is near the user. */
export function distanceKm(a: LatLng, b: LatLng): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLng = toRad(b.lng - a.lng)
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h))
}

export function formatDistance(km: number, system: 'metric' | 'imperial'): string {
  if (system === 'imperial') {
    const miles = km / 1.609344
    return miles < 10 ? `${miles.toFixed(1)} mi` : `${Math.round(miles)} mi`
  }
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`
}

export interface MapView {
  center: [number, number]
  zoom: number
}

// Somewhere with plenty of breweries until the user moves the map or asks for "near me".
export const DEFAULT_VIEW: MapView = { center: [39.8, -98.6], zoom: 4 }
const VIEW_KEY = 'brewnotes.map.view'

export function readStoredView(): MapView {
  try {
    const raw = window.localStorage.getItem(VIEW_KEY)
    if (!raw) return DEFAULT_VIEW
    const parsed = JSON.parse(raw) as Partial<MapView>
    if (
      Array.isArray(parsed.center) &&
      parsed.center.length === 2 &&
      parsed.center.every((n) => typeof n === 'number' && Number.isFinite(n)) &&
      typeof parsed.zoom === 'number'
    ) {
      return { center: [parsed.center[0], parsed.center[1]], zoom: parsed.zoom }
    }
  } catch {
    // ignore: storage unavailable or corrupt
  }
  return DEFAULT_VIEW
}

export function storeView(view: MapView): void {
  try {
    window.localStorage.setItem(VIEW_KEY, JSON.stringify(view))
  } catch {
    // ignore
  }
}
