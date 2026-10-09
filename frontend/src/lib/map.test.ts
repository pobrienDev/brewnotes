import { describe, expect, it } from 'vitest'

import { bboxString, distanceKm, formatAddress, formatDistance, formatPlace, tileConfig, typeLabel } from './map'

describe('map helpers', () => {
  it('formats the bbox parameter the API expects', () => {
    expect(bboxString({ west: -122.75, south: 45.45, east: -122.55, north: 45.6 })).toBe('-122.7500,45.4500,-122.5500,45.6000')
  })
  it('builds keyed MapTiler tiles with attribution, or nothing without a key', () => {
    expect(tileConfig(undefined)).toBeNull()
    const tiles = tileConfig('abc 123')!
    expect(tiles.url).toBe('https://api.maptiler.com/maps/streets-v2/{z}/{x}/{y}.png?key=abc%20123')
    expect(tiles.attribution).toContain('MapTiler')
    expect(tiles.attribution).toContain('OpenStreetMap')
    expect(tiles.tileSize).toBe(512)
  })
  it('measures distance with the haversine formula', () => {
    const portland = { lat: 45.5152, lng: -122.6784 }
    const seattle = { lat: 47.6062, lng: -122.3321 }
    expect(distanceKm(portland, seattle)).toBeCloseTo(234, 0)
    expect(distanceKm(portland, portland)).toBe(0)
    expect(formatDistance(234.1, 'metric')).toBe('234 km')
    expect(formatDistance(2.345, 'imperial')).toBe('1.5 mi')
  })
  it('labels types and formats places', () => {
    expect(typeLabel('brewpub')).toBe('Brewpub')
    expect(typeLabel('something-new')).toBe('something-new')
    expect(formatPlace({ city: 'Portland', state_province: 'Oregon', country: 'United States' })).toBe('Portland, Oregon, United States')
    expect(formatPlace({ city: null, state_province: null, country: 'Fiji' })).toBe('Fiji')
    expect(
      formatAddress({
        id: 'x', obdb_id: 'x', name: 'B', brewery_type: 'micro', latitude: null, longitude: null, removed_at: null,
        address_1: '456 E Burnside St', address_2: 'Suite 2', address_3: null, city: 'Portland', state_province: 'Oregon',
        postal_code: '97214', country: 'United States', phone: null, website_url: null, synced_at: '',
      }),
    ).toBe('456 E Burnside St, Suite 2, Portland Oregon 97214, United States')
  })
})
