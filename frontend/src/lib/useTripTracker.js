/**
 * useTripTracker — combines geolocation with itinerary schedule awareness.
 * Tracks which slot the user should be at, detects behind-schedule,
 * and manages the Reached/Leaving visit tracking per place.
 */
import { useState, useMemo, useCallback, useEffect, useRef } from 'react';

// Haversine distance in km
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Parse "09:00 AM" to minutes since midnight
function parseTimeLabel(label) {
  if (!label) return 0;
  const match = label.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
  if (!match) return 0;
  let hours = parseInt(match[1]);
  const mins = parseInt(match[2]);
  const ampm = match[3].toUpperCase();
  if (ampm === 'PM' && hours !== 12) hours += 12;
  if (ampm === 'AM' && hours === 12) hours = 0;
  return hours * 60 + mins;
}

// Current time as minutes since midnight
function nowMinutes() {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
}

// Format minutes to "HH:MM AM/PM"
function minutesToLabel(totalMins) {
  let h = Math.floor(totalMins / 60);
  const m = totalMins % 60;
  const ampm = h >= 12 ? 'PM' : 'AM';
  if (h > 12) h -= 12;
  if (h === 0) h = 12;
  return `${h}:${String(m).padStart(2, '0')} ${ampm}`;
}

export default function useTripTracker({ itineraryData, activeDay, userPosition }) {
  // visitLog: { [slotIndex]: { reachedAt: Date|null, leftAt: Date|null, timeSpentMinutes: number|null } }
  const [visitLog, setVisitLog] = useState({});
  const [behindSchedule, setBehindSchedule] = useState(false);
  const [delayMinutes, setDelayMinutes] = useState(0);
  const lastReplanRef = useRef(null); // Timestamp of last replan to enforce 15-min cooldown

  // Get today's slots
  const daySlots = useMemo(() => {
    if (!itineraryData?.days) return [];
    const day = itineraryData.days.find((d) => d.day_number === activeDay);
    return day?.slots || [];
  }, [itineraryData, activeDay]);

  // Determine the expected current slot based on system time
  const currentSlotIndex = useMemo(() => {
    const now = nowMinutes();
    let bestIdx = 0;
    for (let i = 0; i < daySlots.length; i++) {
      const slotStart = parseTimeLabel(daySlots[i].time_label);
      if (now >= slotStart) {
        bestIdx = i;
      }
    }
    return bestIdx;
  }, [daySlots]);

  // Check if behind schedule
  useEffect(() => {
    if (!userPosition || daySlots.length === 0) {
      setBehindSchedule(false);
      return;
    }

    const now = nowMinutes();
    const currentSlot = daySlots[currentSlotIndex];
    if (!currentSlot) return;

    const slotStart = parseTimeLabel(currentSlot.time_label);
    const slotEnd = slotStart + (currentSlot.duration_minutes || 60);

    // Check if user hasn't reached the current slot's location
    const slotLat = currentSlot.latitude;
    const slotLon = currentSlot.longitude;

    if (slotLat && slotLon) {
      const distKm = haversineKm(
        userPosition.latitude,
        userPosition.longitude,
        slotLat,
        slotLon
      );
      // Behind if: >2km from expected location AND >15 mins past end of slot
      // AND the user hasn't marked "Reached" for this slot
      const hasReached = visitLog[currentSlotIndex]?.reachedAt;
      if (distKm > 2 && now > slotEnd + 15 && !hasReached) {
        setBehindSchedule(true);
        setDelayMinutes(now - slotEnd);
      } else {
        setBehindSchedule(false);
        setDelayMinutes(0);
      }
    }
  }, [userPosition, daySlots, currentSlotIndex, visitLog]);

  // Mark a place as "Reached"
  const markReached = useCallback((slotIndex) => {
    setVisitLog((prev) => ({
      ...prev,
      [slotIndex]: {
        ...prev[slotIndex],
        reachedAt: new Date(),
        leftAt: prev[slotIndex]?.leftAt || null,
        timeSpentMinutes: prev[slotIndex]?.timeSpentMinutes || null,
      },
    }));
  }, []);

  // Mark a place as "Leaving Now"
  const markLeaving = useCallback((slotIndex) => {
    setVisitLog((prev) => {
      const reached = prev[slotIndex]?.reachedAt;
      const spent = reached
        ? Math.round((Date.now() - reached.getTime()) / 60000)
        : null;
      return {
        ...prev,
        [slotIndex]: {
          ...prev[slotIndex],
          leftAt: new Date(),
          timeSpentMinutes: spent,
        },
      };
    });
  }, []);

  // Check if a slot is visited (both reached and left)
  const isSlotVisited = useCallback(
    (slotIndex) => {
      const log = visitLog[slotIndex];
      return log?.reachedAt && log?.leftAt;
    },
    [visitLog]
  );

  // Check replan cooldown (15 min)
  const canReplan = useMemo(() => {
    if (!lastReplanRef.current) return true;
    const elapsed = Date.now() - lastReplanRef.current;
    return elapsed > 15 * 60 * 1000; // 15 minutes
  }, [behindSchedule]); // Re-evaluate when behind status changes

  const markReplanned = useCallback(() => {
    lastReplanRef.current = Date.now();
  }, []);

  // Get current time as a formatted string
  const currentTimeLabel = useMemo(() => minutesToLabel(nowMinutes()), [behindSchedule]);

  // Distance from user to next unvisited slot
  const distanceToNext = useMemo(() => {
    if (!userPosition || daySlots.length === 0) return null;
    // Find next unvisited slot
    for (let i = 0; i < daySlots.length; i++) {
      if (!visitLog[i]?.reachedAt) {
        const slot = daySlots[i];
        if (slot.latitude && slot.longitude) {
          return haversineKm(
            userPosition.latitude,
            userPosition.longitude,
            slot.latitude,
            slot.longitude
          ).toFixed(1);
        }
      }
    }
    return null;
  }, [userPosition, daySlots, visitLog]);

  return {
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
  };
}
