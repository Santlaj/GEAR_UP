/**
 * Device GPS & Geolocation Telemetry Utility
 * Strictly enforces real device geolocation without hardcoded or overpassed coordinates.
 */

export interface DeviceGpsResult {
  lat: number;
  lng: number;
  accuracy: number;
  method: 'high_accuracy_gps' | 'network';
  timestamp: number;
  statusText: string;
}

export class LocationAccessError extends Error {
  code: 'PERMISSION_DENIED' | 'POSITION_UNAVAILABLE' | 'TIMEOUT' | 'UNSUPPORTED';

  constructor(message: string, code: 'PERMISSION_DENIED' | 'POSITION_UNAVAILABLE' | 'TIMEOUT' | 'UNSUPPORTED') {
    super(message);
    this.name = 'LocationAccessError';
    this.code = code;
  }
}

let cachedGps: DeviceGpsResult | null = null;
const CACHE_TTL_MS = 30000; // 30 seconds cache validity

/**
 * Acquire genuine device GPS coordinates. Throws LocationAccessError if access fails or is denied.
 * Does NOT fallback to fake or hardcoded coordinates.
 */
export async function acquireDeviceGps(forceRefresh = false): Promise<DeviceGpsResult> {
  if (!forceRefresh && cachedGps && Date.now() - cachedGps.timestamp < CACHE_TTL_MS) {
    return cachedGps;
  }

  if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
    throw new LocationAccessError(
      'Geolocation is not supported by your browser or device environment.',
      'UNSUPPORTED'
    );
  }

  // Strategy 1: High-Accuracy GPS satellite fix
  try {
    const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 6000,
        maximumAge: forceRefresh ? 0 : 15000,
      });
    });

    const lat = Number(pos.coords.latitude.toFixed(6));
    const lng = Number(pos.coords.longitude.toFixed(6));
    const acc = Math.round(pos.coords.accuracy || 5);

    const result: DeviceGpsResult = {
      lat,
      lng,
      accuracy: acc,
      method: 'high_accuracy_gps',
      timestamp: Date.now(),
      statusText: `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E (±${acc}m GPS Fix)`,
    };
    cachedGps = result;
    return result;
  } catch (highErr: any) {
    // If explicitly denied, fail immediately without waiting for network fallback
    if (highErr && highErr.code === 1) {
      cachedGps = null;
      throw new LocationAccessError(
        'Location permission denied. Location access is mandatory to scan commodities. Please grant permission in your browser.',
        'PERMISSION_DENIED'
      );
    }
    console.warn('High-accuracy GPS fix failed; attempting standard network geolocation:', highErr);
  }

  // Strategy 2: Standard Network Geolocation (Wi-Fi / Cell fix)
  try {
    const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 8000,
        maximumAge: forceRefresh ? 0 : 30000,
      });
    });

    const lat = Number(pos.coords.latitude.toFixed(6));
    const lng = Number(pos.coords.longitude.toFixed(6));
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
  } catch (netErr: any) {
    cachedGps = null;
    let code: 'PERMISSION_DENIED' | 'POSITION_UNAVAILABLE' | 'TIMEOUT' = 'POSITION_UNAVAILABLE';
    let msg = 'Unable to acquire real-time device location. Please enable GPS/location on your device and tap Reconnect.';

    if (netErr?.code === 1) {
      code = 'PERMISSION_DENIED';
      msg = 'Location permission was denied. Location access is mandatory to scan commodities under statutory rules.';
    } else if (netErr?.code === 3) {
      code = 'TIMEOUT';
      msg = 'Location request timed out. Please ensure device GPS is turned on and tap Reconnect.';
    }

    throw new LocationAccessError(msg, code);
  }
}

/**
 * Returns cached coordinates if currently valid, or null.
 * Never returns hardcoded fake coordinates.
 */
export function getStoredGps(): DeviceGpsResult | null {
  if (cachedGps && Date.now() - cachedGps.timestamp < CACHE_TTL_MS) {
    return cachedGps;
  }
  return null;
}

export function clearGpsCache(): void {
  cachedGps = null;
}
