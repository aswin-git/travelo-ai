/**
 * useGeolocation — custom hook for live GPS tracking.
 * Only activates on explicit startTracking() call ("Start Trip" mode).
 * Uses watchPosition for continuous updates.
 */
import { useState, useRef, useCallback, useEffect } from 'react';

export default function useGeolocation(options = {}) {
  const {
    enableHighAccuracy = true,
    maximumAge = 10000,      // Accept cached position up to 10s old
    timeout = 15000,         // 15s timeout per fix
  } = options;

  const [position, setPosition] = useState(null);  // { latitude, longitude, accuracy, heading, speed }
  const [error, setError] = useState(null);
  const [isTracking, setIsTracking] = useState(false);
  const watchIdRef = useRef(null);

  const startTracking = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser');
      return;
    }

    setError(null);
    setIsTracking(true);

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setPosition({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          heading: pos.coords.heading,
          speed: pos.coords.speed,
          timestamp: pos.timestamp,
        });
        setError(null);
      },
      (err) => {
        switch (err.code) {
          case err.PERMISSION_DENIED:
            setError('Location permission denied. Please enable location access in your browser settings.');
            break;
          case err.POSITION_UNAVAILABLE:
            setError('Location information is unavailable. Please check your device GPS.');
            break;
          case err.TIMEOUT:
            setError('Location request timed out. Retrying...');
            break;
          default:
            setError('An unknown error occurred getting your location.');
        }
      },
      { enableHighAccuracy, maximumAge, timeout }
    );
  }, [enableHighAccuracy, maximumAge, timeout]);

  const stopTracking = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setIsTracking(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, []);

  return {
    position,
    error,
    isTracking,
    startTracking,
    stopTracking,
  };
}
