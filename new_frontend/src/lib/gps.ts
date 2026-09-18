/**
 * Device GPS & Geolocation Telemetry Utility
 * Ensures reliable on-site geolocation capture during statutory commodity inspections.
 *
 * Strategies:
 * 1. High-accuracy GPS (satellite fix with 5s timeout)
 * 2. Low-accuracy network / Wi-Fi triangulation (fast fallback for laptops / indoor beats)
 * 3. IP-based location lookup fallback (when browser geolocation is denied or unavailable)
 * 4. Standard Beat Default Coordinates (Ludhiana PB)
 */

export interface DeviceGpsResult {
  lat: number;
  lng: number;
  accuracy: number;
  method: 'high_accuracy_gps' | 'network' | 'ip_lookup' | 'beat_fallback';
  timestamp: number;
  statusText: string;
}

let cachedGps: DeviceGpsResult | null = null;
const CACHE_TTL_MS = 45000; // 45 seconds cache validity

/**
 * Robustly acquire device GPS coordinates.
 */
export async function acquireDeviceGps(forceRefresh = false): Promise<DeviceGpsResult> {
  if (!forceRefresh && cachedGps && Date.now() - cachedGps.timestamp < CACHE_TTL_MS) {
    return cachedGps;
  }

  // Strategy 1: High-Accuracy GPS
  if (typeof navigator !== 'undefined' && 'geolocation' in navigator) {
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 4500,
          maximumAge: 15000,
        });
      });

      const lat = Number(pos.coords.latitude.toFixed(5));
      const lng = Number(pos.coords.longitude.toFixed(5));
      const acc = Math.round(pos.coords.accuracy || 5);

      const result: DeviceGpsResult = {
        lat,
        lng,
        accuracy: acc,
        method: 'high_accuracy_gps',
        timestamp: Date.now(),
        statusText: `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E (±${acc}m GPS Locked)`,
      };
      cachedGps = result;
      return result;
    } catch (highErr) {
      console.warn('High-accuracy GPS fix timed out/failed; trying network fallback:', highErr);
    }

    // Strategy 2: Fast Low-Accuracy Network Geolocation (Wi-Fi / Cell tower)
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: false,
          timeout: 4000,
          maximumAge: 60000,
        });
      });

      const lat = Number(pos.coords.latitude.toFixed(5));
      const lng = Number(pos.coords.longitude.toFixed(5));
      const acc = Math.round(pos.coords.accuracy || 25);

      const result: DeviceGpsResult = {
        lat,
        lng,
        accuracy: acc,
        method: 'network',
        timestamp: Date.now(),
        statusText: `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E (±${acc}m Network Fix)`,
      };
      cachedGps = result;
      return result;
    } catch (netErr) {
      console.warn('Standard geolocation failed/denied; attempting IP fallback:', netErr);
    }
  }

  // Strategy 3: Fast IP-based Location (for desktop testing or denied browser permission)
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    const res = await fetch('https://ipwho.is/', { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      if (data && data.success && typeof data.latitude === 'number' && typeof data.longitude === 'number') {
        const lat = Number(data.latitude.toFixed(5));
        const lng = Number(data.longitude.toFixed(5));

        const result: DeviceGpsResult = {
          lat,
          lng,
          accuracy: 500,
          method: 'ip_lookup',
          timestamp: Date.now(),
          statusText: `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E (${data.city || 'Regional'}, ${data.region_code || ''})`,
        };
        cachedGps = result;
        return result;
      }
    }
  } catch (ipErr) {
    console.warn('IP geolocation lookup skipped or timed out:', ipErr);
  }

  // Strategy 4: Standard Beat Fallback (Ludhiana Commercial Beat, Punjab)
  const defaultResult: DeviceGpsResult = {
    lat: 30.9010,
    lng: 75.8573,
    accuracy: 10,
    method: 'beat_fallback',
    timestamp: Date.now(),
    statusText: '30.9010° N, 75.8573° E (Ludhiana Jurisdiction Beat)',
  };
  cachedGps = defaultResult;
  return defaultResult;
}

/**
 * Returns cached coordinates if available, or beat defaults synchronously.
 */
export function getStoredOrFallbackGps(): { lat: number; lng: number; statusText: string } {
  if (cachedGps) {
    return {
      lat: cachedGps.lat,
      lng: cachedGps.lng,
      statusText: cachedGps.statusText,
    };
  }
  return {
    lat: 30.9010,
    lng: 75.8573,
    statusText: '30.9010° N, 75.8573° E (Acquiring device GPS...)',
  };
}
