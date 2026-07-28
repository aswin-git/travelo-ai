/**
 * TripView — Full-screen overlay with 70% map / 30% itinerary panel.
 * Handles: map viewing, live trip tracking, Reached/Leaving buttons,
 * behind-schedule detection, and replan flow.
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ItineraryMap from './ItineraryMap';
import useGeolocation from '../lib/useGeolocation';
import useTripTracker from '../lib/useTripTracker';
import { API_BASE } from '../config';

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

export default function TripView({
  itineraryData,
  onClose,
  onItineraryUpdate,
  accessToken,
  startInTripMode = false,
}) {
  const [activeDay, setActiveDay] = useState(1);
  const [routeCoordinates, setRouteCoordinates] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [showReplanModal, setShowReplanModal] = useState(false);
  const [replanLoading, setReplanLoading] = useState(false);
  const [placesToRemove, setPlacesToRemove] = useState([]);
  const [highlightedSlot, setHighlightedSlot] = useState(null);
  const [isTripMode, setIsTripMode] = useState(startInTripMode);

  const API = API_BASE;
  const authHeaders = useCallback(() => {
    const h = { 'Content-Type': 'application/json' };
    if (accessToken) h['Authorization'] = `Bearer ${accessToken}`;
    return h;
  }, [accessToken]);

  // Geolocation (only active in trip mode)
  const { position: userPosition, error: geoError, isTracking, startTracking, stopTracking } = useGeolocation();

  // Get current day's slots
  const daySlots = useMemo(() => {
    if (!itineraryData?.days) return [];
    const day = itineraryData.days.find((d) => d.day_number === activeDay);
    return day?.slots || [];
  }, [itineraryData, activeDay]);

  // Trip tracker
  const {
    visitLog,
    currentSlotIndex,
    behindSchedule,
    delayMinutes,
    canReplan,
    currentTimeLabel,
    distanceToNext,
    markReached,
    markLeaving,
    isSlotVisited,
    markReplanned,
  } = useTripTracker({
    itineraryData,
    activeDay,
    userPosition: isTracking ? userPosition : null,
  });

  // Start/stop trip mode
  const handleStartTrip = useCallback(() => {
    setIsTripMode(true);
    startTracking();
  }, [startTracking]);

  const handleStopTrip = useCallback(() => {
    setIsTripMode(false);
    stopTracking();
  }, [stopTracking]);

  // Auto-start tracking if opened in trip mode
  useEffect(() => {
    if (startInTripMode && !isTracking) {
      startTracking();
    }
  }, [startInTripMode]);

  // Fetch route geometry when day changes
  useEffect(() => {
    const fetchRoute = async () => {
      const waypoints = daySlots
        .filter((s) => s.latitude && s.longitude)
        .map((s) => ({ lat: s.latitude, lon: s.longitude }));

      if (waypoints.length < 2) {
        setRouteCoordinates(null);
        return;
      }

      setRouteLoading(true);
      try {
        const res = await fetch(`${API}/itinerary/route-geometry`, {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ waypoints }),
        });
        if (res.ok) {
          const data = await res.json();
          setRouteCoordinates(data.coordinates || null);
        }
      } catch (err) {
        console.error('Failed to fetch route geometry:', err);
      } finally {
        setRouteLoading(false);
      }
    };

    fetchRoute();
  }, [daySlots, API, authHeaders]);

  // Handle replan
  const handleReplan = useCallback(async () => {
    if (!canReplan) return;
    setReplanLoading(true);
    try {
      const res = await fetch(`${API}/itinerary/replan`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          itinerary_data: itineraryData,
          current_day: activeDay,
          current_time: currentTimeLabel,
          user_lat: userPosition?.latitude || 0,
          user_lon: userPosition?.longitude || 0,
          places_to_remove: placesToRemove.length > 0 ? placesToRemove : null,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        onItineraryUpdate?.(updated);
        markReplanned();
        setShowReplanModal(false);
        setPlacesToRemove([]);
      }
    } catch (err) {
      console.error('Replan failed:', err);
    } finally {
      setReplanLoading(false);
    }
  }, [itineraryData, activeDay, currentTimeLabel, userPosition, placesToRemove, canReplan, authHeaders, API, onItineraryUpdate, markReplanned]);

  // Toggle place removal selection
  const togglePlaceRemoval = useCallback((name) => {
    setPlacesToRemove((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  }, []);

  // Get unvisited remaining slots for the replan modal
  const remainingSlots = useMemo(() => {
    return daySlots
      .map((s, i) => ({ ...s, index: i }))
      .filter((s, i) => !isSlotVisited(i));
  }, [daySlots, isSlotVisited]);

  if (!itineraryData) return null;

  return (
    <div className="trip-view-overlay">
      {/* Header bar */}
      <div className="trip-view-header">
        <div className="trip-view-header-left">
          <button className="trip-view-close-btn" onClick={onClose}>
            ← Back
          </button>
          <h2 className="trip-view-title">
            🗺️ {itineraryData.destination}
            {isTripMode && <span className="trip-mode-badge">LIVE</span>}
          </h2>
        </div>
        <div className="trip-view-header-right">
          {!isTripMode ? (
            <button className="trip-start-btn" onClick={handleStartTrip}>
              🚀 Start Trip
            </button>
          ) : (
            <button className="trip-stop-btn" onClick={handleStopTrip}>
              ⏹️ End Trip
            </button>
          )}
        </div>
      </div>

      {/* Behind-schedule banner */}
      {behindSchedule && isTripMode && (
        <div className="behind-schedule-banner">
          <div className="behind-schedule-text">
            <span className="behind-schedule-icon">⚠️</span>
            You're ~{delayMinutes} mins behind schedule.
            {distanceToNext && <> ({distanceToNext} km to next stop)</>}
          </div>
          <div className="behind-schedule-actions">
            <button
              className="replan-btn"
              onClick={() => setShowReplanModal(true)}
              disabled={!canReplan}
            >
              🔄 Replan
            </button>
            <button
              className="dismiss-btn"
              onClick={() => {/* User dismisses — will show again if still behind */}}
            >
              I'll catch up
            </button>
          </div>
        </div>
      )}

      {/* GPS error banner */}
      {geoError && isTripMode && (
        <div className="geo-error-banner">
          📍 {geoError}
        </div>
      )}

      {/* Main content: 70% map + 30% panel */}
      <div className="trip-view-content">
        {/* Map panel */}
        <div className="trip-view-map">
          <ItineraryMap
            slots={daySlots}
            userPosition={userPosition}
            isTracking={isTracking}
            visitLog={visitLog}
            routeCoordinates={routeCoordinates}
            onMarkerClick={(idx) => setHighlightedSlot(idx)}
            activeSlotIndex={isTripMode ? currentSlotIndex : null}
          />
          {routeLoading && (
            <div className="route-loading-indicator">Loading route...</div>
          )}
        </div>

        {/* Itinerary panel */}
        <div className="trip-view-panel">
          {/* Day tabs */}
          <div className="trip-day-tabs">
            {itineraryData.days.map((day) => (
              <button
                key={day.day_number}
                className={`trip-day-tab ${activeDay === day.day_number ? 'active' : ''}`}
                onClick={() => setActiveDay(day.day_number)}
              >
                <span className="trip-day-num">Day {day.day_number}</span>
                <span className="trip-day-theme">{day.theme}</span>
              </button>
            ))}
          </div>

          {/* Slot list */}
          <div className="trip-slot-list">
            {daySlots.map((slot, idx) => {
              const color = CATEGORY_COLORS[slot.category] || '#6b7280';
              const icon = CATEGORY_ICONS[slot.category] || '📍';
              const visited = isSlotVisited(idx);
              const isActive = isTripMode && currentSlotIndex === idx;
              const isHighlighted = highlightedSlot === idx;
              const reached = visitLog[idx]?.reachedAt;
              const left = visitLog[idx]?.leftAt;
              const timeSpent = visitLog[idx]?.timeSpentMinutes;

              return (
                <div
                  key={idx}
                  className={`trip-slot-card ${visited ? 'visited' : ''} ${isActive ? 'active-slot' : ''} ${isHighlighted ? 'highlighted' : ''}`}
                  id={`trip-slot-${idx}`}
                >
                  <div className="trip-slot-marker" style={{ background: color }}>
                    <span>{idx + 1}</span>
                  </div>
                  <div className="trip-slot-info">
                    <div className="trip-slot-time">
                      <span className="trip-slot-label">{slot.time_label}</span>
                      <span className="trip-slot-badge" style={{ background: color + '20', color }}>
                        {slot.time_slot}
                      </span>
                    </div>
                    <h4 className="trip-slot-name">{icon} {slot.activity_name}</h4>
                    <div className="trip-slot-meta">
                      <span>⏱️ {slot.duration_minutes}m</span>
                      {slot.rating && <span>⭐ {slot.rating}</span>}
                      {slot.travel_to_next && <span>{slot.travel_to_next}</span>}
                    </div>

                    {/* Visit tracking buttons (only in trip mode) */}
                    {isTripMode && !visited && (
                      <div className="trip-slot-actions">
                        {!reached ? (
                          <button
                            className="reach-btn"
                            onClick={() => markReached(idx)}
                          >
                            ✅ Reached
                          </button>
                        ) : !left ? (
                          <button
                            className="leave-btn"
                            onClick={() => markLeaving(idx)}
                          >
                            👋 Leaving Now
                          </button>
                        ) : null}
                      </div>
                    )}

                    {/* Visit log display */}
                    {visited && (
                      <div className="trip-slot-visited-info">
                        ✅ Visited • {timeSpent != null ? `${timeSpent} min spent` : 'Time not recorded'}
                      </div>
                    )}
                    {reached && !left && (
                      <div className="trip-slot-at-location">
                        📍 Currently here
                        {visitLog[idx]?.reachedAt && (
                          <span> • Arrived {visitLog[idx].reachedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Replan Modal */}
      {showReplanModal && (
        <div className="modal-overlay" onClick={() => setShowReplanModal(false)}>
          <div className="modal-content replan-modal" onClick={(e) => e.stopPropagation()}>
            <h3>🔄 Replan Day {activeDay}</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>
              You're ~{delayMinutes} mins behind schedule. Would you like to remove any places
              to make the remaining itinerary more feasible?
            </p>

            <div className="replan-place-list">
              {remainingSlots
                .filter((s) => s.category !== 'hotel')
                .map((slot) => (
                  <label
                    key={slot.index}
                    className={`replan-place-item ${placesToRemove.includes(slot.activity_name) ? 'selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={placesToRemove.includes(slot.activity_name)}
                      onChange={() => togglePlaceRemoval(slot.activity_name)}
                    />
                    <span className="replan-place-name">
                      {CATEGORY_ICONS[slot.category] || '📍'} {slot.activity_name}
                    </span>
                    <span className="replan-place-time">{slot.time_label}</span>
                  </label>
                ))}
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '12px 0' }}>
              {placesToRemove.length > 0
                ? `${placesToRemove.length} place(s) will be removed. Remaining places will be rescheduled.`
                : 'Select places to remove, or replan with all remaining places.'}
            </p>

            <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
              <button
                className="modal-btn replan-confirm-btn"
                onClick={handleReplan}
                disabled={replanLoading}
              >
                {replanLoading ? '⏳ Replanning...' : '🔄 Replan Now'}
              </button>
              <button
                className="modal-btn replan-cancel-btn"
                onClick={() => {
                  setShowReplanModal(false);
                  setPlacesToRemove([]);
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
