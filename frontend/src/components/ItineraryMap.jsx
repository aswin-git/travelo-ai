/**
 * ItineraryMap — Leaflet map component showing itinerary places,
 * route polylines, and user location.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon path issue with bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const CATEGORY_COLORS = {
  attraction: '#14b8a6',
  restaurant: '#f59e0b',
  hotel: '#3b82f6',
  travel: '#8b5cf6',
  activity: '#ec4899',
};

const CATEGORY_ICONS = {
  attraction: '🏛️',
  restaurant: '🍽️',
  hotel: '🏨',
  travel: '🚗',
  activity: '🎯',
};

// Create a numbered colored marker icon
function createMarkerIcon(number, category, isVisited) {
  const color = CATEGORY_COLORS[category] || '#6b7280';
  const opacity = isVisited ? 0.4 : 1;
  return L.divIcon({
    className: 'custom-marker-icon',
    html: `
      <div style="
        width: 32px; height: 32px; border-radius: 50%;
        background: ${color}; border: 3px solid white;
        display: flex; align-items: center; justify-content: center;
        color: white; font-weight: 700; font-size: 13px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        opacity: ${opacity}; transition: opacity 0.3s;
      ">${number}</div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -20],
  });
}

// Component to auto-fit map bounds to all markers
function FitBounds({ positions }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 0) {
      const bounds = L.latLngBounds(positions);
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [positions, map]);
  return null;
}

export default function ItineraryMap({
  slots = [],
  userPosition = null,
  isTracking = false,
  visitLog = {},
  routeCoordinates = null,
  onMarkerClick = null,
  activeSlotIndex = null,
}) {
  // Extract valid positions for bounds fitting
  const markerPositions = useMemo(() => {
    const positions = [];
    slots.forEach((slot) => {
      if (slot.latitude && slot.longitude) {
        positions.push([slot.latitude, slot.longitude]);
      }
    });
    if (userPosition?.latitude && userPosition?.longitude) {
      positions.push([userPosition.latitude, userPosition.longitude]);
    }
    return positions;
  }, [slots, userPosition]);

  // Default center (first marker or world center)
  const defaultCenter = markerPositions.length > 0 ? markerPositions[0] : [20, 78];

  if (markerPositions.length === 0) {
    return (
      <div className="map-no-data">
        <div style={{ fontSize: '3rem', marginBottom: '12px' }}>🗺️</div>
        <p>No location data available for this day's places.</p>
      </div>
    );
  }

  return (
    <MapContainer
      center={defaultCenter}
      zoom={13}
      style={{ width: '100%', height: '100%', borderRadius: '12px' }}
      scrollWheelZoom={true}
      zoomControl={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <FitBounds positions={markerPositions} />

      {/* Route polyline */}
      {routeCoordinates && routeCoordinates.length > 0 && (
        <Polyline
          positions={routeCoordinates}
          pathOptions={{
            color: '#6366f1',
            weight: 4,
            opacity: 0.7,
            dashArray: '8, 4',
            lineCap: 'round',
          }}
        />
      )}

      {/* Place markers */}
      {slots.map((slot, idx) => {
        if (!slot.latitude || !slot.longitude) return null;
        const isVisited = visitLog[idx]?.reachedAt && visitLog[idx]?.leftAt;
        const isActive = activeSlotIndex === idx;
        const icon = createMarkerIcon(idx + 1, slot.category, isVisited);

        return (
          <Marker
            key={idx}
            position={[slot.latitude, slot.longitude]}
            icon={icon}
            eventHandlers={{
              click: () => onMarkerClick?.(idx),
            }}
          >
            <Popup>
              <div style={{ minWidth: '180px' }}>
                <div style={{ fontWeight: '700', fontSize: '14px', marginBottom: '4px' }}>
                  {CATEGORY_ICONS[slot.category] || '📍'} {slot.activity_name}
                </div>
                <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                  {slot.time_label} • {slot.time_slot}
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>
                  ⏱️ {slot.duration_minutes} min
                  {slot.rating && <> • ⭐ {slot.rating}</>}
                  {slot.cost_estimate && <> • 💰 {slot.cost_estimate}</>}
                </div>
                {isVisited && (
                  <div style={{ fontSize: '11px', color: '#10b981', marginTop: '4px', fontWeight: '600' }}>
                    ✅ Visited ({visitLog[idx]?.timeSpentMinutes || '?'} min)
                  </div>
                )}
                {slot.crowd_status && slot.crowd_status.toLowerCase() !== 'unknown' && (
                  <div style={{ fontSize: '11px', color: '#f59e0b', marginTop: '2px' }}>
                    👥 {slot.crowd_status}
                  </div>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}

      {/* User location pulsing dot */}
      {isTracking && userPosition?.latitude && userPosition?.longitude && (
        <>
          {/* Accuracy circle */}
          <CircleMarker
            center={[userPosition.latitude, userPosition.longitude]}
            radius={Math.min(userPosition.accuracy || 50, 100) / 5}
            pathOptions={{
              color: '#3b82f6',
              fillColor: '#3b82f6',
              fillOpacity: 0.1,
              weight: 1,
            }}
          />
          {/* Center dot */}
          <CircleMarker
            center={[userPosition.latitude, userPosition.longitude]}
            radius={8}
            pathOptions={{
              color: 'white',
              fillColor: '#3b82f6',
              fillOpacity: 1,
              weight: 3,
            }}
          >
            <Popup>
              <div style={{ fontWeight: '600' }}>📍 You are here</div>
              <div style={{ fontSize: '11px', color: '#666' }}>
                Accuracy: ±{Math.round(userPosition.accuracy || 0)}m
              </div>
            </Popup>
          </CircleMarker>
        </>
      )}
    </MapContainer>
  );
}
