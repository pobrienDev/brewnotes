import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import { useEffect } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import { Link } from 'react-router'

import { type Bounds, type BrewerySummary, MAP_TILE_KEY, MAX_ZOOM, MIN_ZOOM, type MapView, clampBounds, formatPlace, tileConfig, typeLabel } from '../lib/map'

// Bundlers lose Leaflet's default icon paths. Leaflet derives them in _getIconUrl from the
// stylesheet's image path, ignoring the options, so drop that method and point at the images.
delete (L.Icon.Default.prototype as { _getIconUrl?: unknown })._getIconUrl
L.Icon.Default.mergeOptions({ iconRetinaUrl: markerIcon2x, iconUrl: markerIcon, shadowUrl: markerShadow })

function toBounds(map: L.Map): Bounds {
  const b = map.getBounds()
  return clampBounds({ west: b.getWest(), south: b.getSouth(), east: b.getEast(), north: b.getNorth() })
}

function toView(map: L.Map): MapView {
  return { center: [map.getCenter().lat, map.getCenter().lng], zoom: map.getZoom() }
}

function ViewWatcher({ onChange }: { onChange: (bounds: Bounds, view: MapView) => void }) {
  const map = useMapEvents({
    moveend: () => onChange(toBounds(map), toView(map)),
  })
  useEffect(() => {
    onChange(toBounds(map), toView(map))
    // Once, when the map is ready; later changes arrive through moveend.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return null
}

function FlyTo({ target }: { target: { lat: number; lng: number; zoom: number } | null }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lng], target.zoom)
  }, [map, target])
  return null
}

export function BreweryMap({
  breweries,
  initialView,
  flyTo,
  onViewChange,
  className = 'h-[60vh] min-h-96 w-full',
}: {
  breweries: BrewerySummary[]
  initialView: MapView
  flyTo?: { lat: number; lng: number; zoom: number } | null
  onViewChange?: (bounds: Bounds, view: MapView) => void
  className?: string
}) {
  const tiles = tileConfig(MAP_TILE_KEY)
  return (
    <div className={`relative ${className}`}>
      {/* Zoom limits on the map itself: the cluster plugin needs maxZoom even without tiles, and
          minZoom keeps the tile zoom (map zoom - 1 for 512px tiles) at or above 0. */}
      <MapContainer center={initialView.center} zoom={initialView.zoom} minZoom={MIN_ZOOM} maxZoom={MAX_ZOOM} className="h-full w-full rounded border border-stone-300" scrollWheelZoom>
        {tiles && (
          <TileLayer url={tiles.url} attribution={tiles.attribution} tileSize={tiles.tileSize} zoomOffset={tiles.zoomOffset} minZoom={MIN_ZOOM} maxZoom={tiles.maxZoom} />
        )}
        {onViewChange && <ViewWatcher onChange={onViewChange} />}
        <FlyTo target={flyTo ?? null} />
        <MarkerClusterGroup chunkedLoading maxClusterRadius={50}>
          {breweries
            .filter((b) => b.latitude !== null && b.longitude !== null)
            .map((b) => (
              <Marker key={b.id} position={[b.latitude!, b.longitude!]}>
                <Popup>
                  <strong>{b.name}</strong>
                  <br />
                  {typeLabel(b.brewery_type)} · {formatPlace(b)}
                  <br />
                  <Link to={`/breweries/${b.id}`}>Details</Link>
                </Popup>
              </Marker>
            ))}
        </MarkerClusterGroup>
      </MapContainer>
      {tiles ? (
        // Required by MapTiler's free plan: its logo on the map, linking to its site. Bottom-left
        // is free (Leaflet puts zoom top-left and attribution bottom-right).
        <a href={tiles.logoHref} target="_blank" rel="noopener" className="absolute bottom-2 left-2 z-[1000]">
          <img src={tiles.logoUrl} alt="MapTiler" width={67} height={20} className="h-6 w-auto" />
        </a>
      ) : (
        <p role="status" className="pointer-events-none absolute left-2 top-2 z-[1000] rounded bg-white/90 px-2 py-1 text-xs text-stone-700 shadow">
          No map tiles: set VITE_MAP_TILE_KEY (a MapTiler key restricted to this site) to see the base map.
        </p>
      )}
    </div>
  )
}
