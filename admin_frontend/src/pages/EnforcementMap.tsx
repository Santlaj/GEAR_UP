import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  Copy, 
  ArrowRight, 
  Layers, 
  Navigation, 
  MapPin 
} from 'lucide-react';
import type { ReportRecord, MapInspectionFeedItem } from '../data/mockData';
import L from 'leaflet';
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  CircleMarker,
  Popup,
  Polygon,
  useMap,
} from 'react-leaflet';
import type { FeatureCollection } from 'geojson';
import { fetchScans, scanRecordToReportRecord, scanRecordToMapInspection, scanRecordToFeedItem } from '../api';
import { getStoredScope } from '../api/auth';

/* ─── Types ─── */
interface EnforcementMapProps {
  onViewReport: (report: ReportRecord) => void;
}

interface Inspection {
  id: string;
  reportNo?: string;
  district: string;
  godown: string;
  latitude: number;
  longitude: number;
  issue: string;
  date: string;
  status: 'non-compliant' | 'needs-review' | 'compliant';
  business: string;
  inspector: string;
  violations: string[];
  isDemo?: boolean;
}



/* ─── Map Controller (zoom/fly to state on selection & open pin popup) ─── */
interface MapControllerProps {
  selectedState: string | null;
  districts: FeatureCollection | null;
  resetTrigger: number;
  flyToCoords: [number, number] | null;
  selectedPinId: string | null;
  highlightTrigger: number;
  markerRefs: React.MutableRefObject<Map<string, L.CircleMarker>>;
}

const MapController: React.FC<MapControllerProps> = ({
  selectedState,
  districts,
  resetTrigger,
  flyToCoords,
  selectedPinId,
  highlightTrigger,
  markerRefs,
}) => {
  const map = useMap();

  // Default Ludhiana-centered view (matching existing enforcement map center)
  useEffect(() => {
    if (!selectedState && resetTrigger === 0 && !flyToCoords) {
      map.setView([30.9010, 75.8573], 12);
    }
  }, [selectedState, map]);

  // When a state is selected, zoom to that state's districts
  useEffect(() => {
    if (!selectedState || !districts) return;
    const stateDistricts: FeatureCollection = {
      type: 'FeatureCollection',
      features: districts.features.filter(
        (feature) => feature.properties?.st_nm === selectedState
      ),
    };
    if (stateDistricts.features.length === 0) return;
    const stateLayer = L.geoJSON(stateDistricts);
    const stateBounds = stateLayer.getBounds();
    if (stateBounds.isValid()) {
      map.fitBounds(stateBounds, { padding: [20, 20] });
    }
  }, [selectedState, districts, map]);

  // Reset to default view
  useEffect(() => {
    if (resetTrigger > 0) {
      map.setView([30.9010, 75.8573], 12);
    }
  }, [resetTrigger, map]);

  // Fly to specific coordinates and OPEN POPUP every time an inspection is highlighted
  useEffect(() => {
    if (!selectedPinId || !flyToCoords) return;

    // Fly smoothly to target coordinates
    map.flyTo(flyToCoords, 14, { duration: 0.8 });

    const openTargetPopup = () => {
      const marker = markerRefs.current.get(selectedPinId);
      if (marker) {
        marker.openPopup();
      }
    };

    // Immediate attempt
    openTargetPopup();

    // Leaflet moveend event fires when flyTo animation completes
    const handleMoveEnd = () => {
      openTargetPopup();
    };
    map.once('moveend', handleMoveEnd);

    // Staggered timeouts to ensure popup opens even if Leaflet DOM is re-rendering
    const t1 = setTimeout(openTargetPopup, 150);
    const t2 = setTimeout(openTargetPopup, 450);
    const t3 = setTimeout(openTargetPopup, 900);

    return () => {
      map.off('moveend', handleMoveEnd);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [selectedPinId, flyToCoords, highlightTrigger, map, markerRefs]);

  return null;
};

/* ─── Main EnforcementMap Component ─── */
export const EnforcementMap: React.FC<EnforcementMapProps> = ({ onViewReport }) => {
  // Filter states
  const [showNonCompliant, setShowNonCompliant] = useState(true);
  const [showNeedsReview, setShowNeedsReview] = useState(true);
  const [showCompliant, setShowCompliant] = useState(false);
  const [showOnlyViolations, setShowOnlyViolations] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Selected pin for popup
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);
  const [highlightTrigger, setHighlightTrigger] = useState<number>(0);
  const markerRefs = useRef<Map<string, L.CircleMarker>>(new Map());

  // Leaflet map state
  const [states, setStates] = useState<FeatureCollection | null>(null);
  const [districts, setDistricts] = useState<FeatureCollection | null>(null);
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const [resetTrigger, setResetTrigger] = useState(0);
  const [flyToCoords, setFlyToCoords] = useState<[number, number] | null>(null);

  // Live inspections, feed items, and reports cache (initialized empty until live backend fetch)
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [feedItems, setFeedItems] = useState<MapInspectionFeedItem[]>([]);
  const [reportsMap, setReportsMap] = useState<Map<string, ReportRecord>>(() => new Map());
  const [isLive, setIsLive] = useState(false);
  const [isOfflineDemo, setIsOfflineDemo] = useState(false);
  const [_isLoading, setIsLoading] = useState(true);

  // Fetch live points from backend
  const loadBackendData = async () => {
    setIsLoading(true);
    try {
      const scope = getStoredScope();
      const stateParam = scope?.state_id || 'PB';
      const rawScans = await fetchScans({ stateId: stateParam });
      if (Array.isArray(rawScans)) {
        const liveInspections = rawScans.map(scanRecordToMapInspection);
        const liveFeed = rawScans.map(scanRecordToFeedItem);
        const nextReports = new Map<string, ReportRecord>();
        rawScans.forEach((scan) => {
          const adapted = scanRecordToReportRecord(scan);
          nextReports.set(scan.scan_id, adapted);
          if (scan.report_no) {
            nextReports.set(scan.report_no, adapted);
          }
        });

        setReportsMap(nextReports);
        setInspections(liveInspections);
        setFeedItems(liveFeed);
        setIsLive(true);
        setIsOfflineDemo(false);

        if (liveInspections.length > 0) {
          setSelectedPinId(liveInspections[0].id);
          setFlyToCoords([liveInspections[0].latitude, liveInspections[0].longitude]);
          setHighlightTrigger((p) => p + 1);
        }
      }
    } catch (err) {
      console.warn('Map live data load failed:', err);
      setIsOfflineDemo(true);
      setIsLive(false);
      setInspections([]);
      setFeedItems([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Load GeoJSON files & Live Backend Map Data
  useEffect(() => {
    fetch('/geojson/states.geojson')
      .then((r) => { if (!r.ok) throw new Error('states.geojson load failed'); return r.json(); })
      .then(setStates)
      .catch((e) => console.error('States GeoJSON error:', e));

    fetch('/geojson/states-and-districts.geojson')
      .then((r) => { if (!r.ok) throw new Error('districts.geojson load failed'); return r.json(); })
      .then(setDistricts)
      .catch((e) => console.error('Districts GeoJSON error:', e));

    loadBackendData();
  }, []);

  // Build India mask (grey out everything outside India)
  const indiaHoles: [number, number][][] = [];
  if (states) {
    states.features.forEach((feature) => {
      const geometry = feature.geometry;
      if (!geometry) return;
      if (geometry.type === 'Polygon') {
        indiaHoles.push(
          (geometry.coordinates[0] as [number, number][]).map(([lng, lat]) => [lat, lng] as [number, number])
        );
      }
      if (geometry.type === 'MultiPolygon') {
        (geometry.coordinates as [number, number][][][]).forEach((polygon) => {
          indiaHoles.push(
            polygon[0].map(([lng, lat]) => [lat, lng] as [number, number])
          );
        });
      }
    });
  }

  const world: [number, number][] = [
    [89.9, -179.9], [89.9, 179.9], [-89.9, 179.9], [-89.9, -179.9],
  ];

  // Filter inspections based on checkboxes (always keep selected pin visible so popup can be rendered)
  const filteredInspections = inspections.filter((insp) => {
    if (insp.id === selectedPinId || (insp.reportNo && insp.reportNo === selectedPinId)) return true;
    if (insp.status === 'non-compliant' && !showNonCompliant) return false;
    if (insp.status === 'needs-review' && !showNeedsReview) return false;
    if (insp.status === 'compliant' && !showCompliant) return false;
    if (showOnlyViolations && insp.status === 'compliant') return false;
    return true;
  });

  const handleHighlight = (id: string) => {
    let insp = inspections.find((i) => i.id === id || i.reportNo === id);
    if (!insp) {
      const feed = feedItems.find((f) => f.id === id);
      if (feed && feed.lat != null && feed.lng != null) {
        insp = {
          id: feed.id,
          reportNo: feed.id,
          district: 'Jurisdiction',
          godown: feed.subtitle,
          latitude: feed.lat,
          longitude: feed.lng,
          issue: feed.infraction,
          date: feed.timeAgo,
          status: feed.status === 'NON-COMPLIANT' ? 'non-compliant' : feed.status === 'NEEDS REVIEW' ? 'needs-review' : 'compliant',
          business: feed.business,
          inspector: feed.inspector,
          violations: [feed.infraction],
          isDemo: feed.isDemo,
        };
      }
    }
    if (insp) {
      // Auto-enable filter so highlighted pin is visible on map
      if (insp.status === 'compliant' && (!showCompliant || showOnlyViolations)) {
        setShowCompliant(true);
        setShowOnlyViolations(false);
      } else if (insp.status === 'needs-review' && !showNeedsReview) {
        setShowNeedsReview(true);
      } else if (insp.status === 'non-compliant' && !showNonCompliant) {
        setShowNonCompliant(true);
      }

      setSelectedPinId(insp.id);
      setFlyToCoords([insp.latitude, insp.longitude]);
      setHighlightTrigger((p) => p + 1);

      // Trigger immediate open if marker already mounted
      setTimeout(() => {
        const marker = markerRefs.current.get(insp!.id) || (insp!.reportNo ? markerRefs.current.get(insp!.reportNo) : undefined);
        if (marker) {
          marker.openPopup();
        }
      }, 50);
    }
  };

  const getMarkerColor = (status: string) => {
    switch (status) {
      case 'non-compliant': return '#dc2626';
      case 'needs-review': return '#f59e0b';
      case 'compliant': return '#16a34a';
      default: return '#dc2626';
    }
  };

  const getMarkerRadius = (id: string) => {
    return id === selectedPinId ? 10 : 7;
  };

  const nonCompliantCount = inspections.filter((i) => i.status === 'non-compliant').length;
  const needsReviewCount = inspections.filter((i) => i.status === 'needs-review').length;
  const compliantCount = inspections.filter((i) => i.status === 'compliant').length;


  return (
    <div className="max-w-[1720px] mx-auto px-4 sm:px-6 py-3 space-y-2.5 text-left">
      {/* Live Scope or Error Banners */}
      {isOfflineDemo && (
        <div className="bg-red-50 border border-red-300 px-4 py-2.5 rounded-sm text-xs text-red-900 flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <span className="bg-red-200 text-red-800 font-bold px-1.5 py-0.5 rounded-2xs text-[10px] uppercase">
              CONNECTION ERROR
            </span>
            <span>
              Failed to load live inspection coordinates from backend.
            </span>
          </div>
          <button
            onClick={loadBackendData}
            className="underline font-bold text-red-900 hover:text-red-950 cursor-pointer"
          >
            Retry Connection
          </button>
        </div>
      )}

      {isLive && inspections.length === 0 && (
        <div className="bg-blue-50 border border-blue-300 px-4 py-2.5 rounded-sm text-xs text-blue-900 flex items-center gap-2 shadow-2xs">
          <span className="bg-blue-200 text-blue-800 font-bold px-1.5 py-0.5 rounded-2xs text-[10px] uppercase">
            LIVE SCOPE
          </span>
          <span>
            0 scans recorded in your authorized state/district. No active enforcement pins to display.
          </span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-3 border border-slate-300 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          {/* Checkbox: Non-Compliant */}
          <label className="flex items-center gap-1.5 cursor-pointer font-medium text-black select-none">
            <input
              type="checkbox"
              checked={showNonCompliant}
              onChange={(e) => setShowNonCompliant(e.target.checked)}
              className="accent-red-600 rounded"
            />
            <span className="w-2.5 h-2.5 bg-red-600 rounded-2xs inline-block"></span>
            <span>Non-Compliant ({nonCompliantCount})</span>
          </label>

          {/* Checkbox: Needs Review */}
          <label className="flex items-center gap-1.5 cursor-pointer font-medium text-black select-none">
            <input
              type="checkbox"
              checked={showNeedsReview}
              onChange={(e) => setShowNeedsReview(e.target.checked)}
              className="accent-amber-500 rounded"
            />
            <span className="w-2.5 h-2.5 bg-amber-500 rounded-2xs inline-block"></span>
            <span>Needs Review ({needsReviewCount})</span>
          </label>

          {/* Checkbox: Compliant */}
          <label className="flex items-center gap-1.5 cursor-pointer font-medium text-black select-none">
            <input
              type="checkbox"
              checked={showCompliant}
              onChange={(e) => setShowCompliant(e.target.checked)}
              className="accent-emerald-600 rounded"
            />
            <span className="w-2.5 h-2.5 bg-emerald-600 rounded-2xs inline-block"></span>
            <span>Compliant ({compliantCount})</span>
          </label>

          {/* Checkbox: Show only violations */}
          <label className="flex items-center gap-1.5 cursor-pointer font-medium text-black select-none ml-1">
            <input
              type="checkbox"
              checked={showOnlyViolations}
              onChange={(e) => setShowOnlyViolations(e.target.checked)}
              className="accent-slate-900 rounded"
            />
            <span>Show only violations</span>
          </label>
        </div>

        {/* Right Filter Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Gill Road Mandi"
              className="pl-8 pr-2.5 py-1.5 text-xs bg-white border border-slate-300 focus:outline-none w-44 text-black"
            />
          </div>

          <button 
            onClick={() => {
              setSelectedState(null);
              setResetTrigger((p) => p + 1);
              setFlyToCoords([30.9010, 75.8573]);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-black border border-slate-300 text-[11px] font-medium cursor-pointer"
          >
            <span>RESET MAP VIEW</span>
            <Navigation className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* 5. Main Map & Sidebar Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-stretch">
        {/* Left: GIS Map Area (8 Columns) */}
        <div className="lg:col-span-8 bg-white border border-slate-300 relative overflow-hidden flex flex-col min-h-[580px] lg:min-h-[660px]">
          
          {/* Real Leaflet Map */}
          <div className="relative flex-1 w-full h-full">
            <MapContainer
              center={[30.9010, 75.8573]}
              zoom={12}
              scrollWheelZoom={true}
              className="w-full h-full"
              style={{ minHeight: '580px' }}
              zoomControl={false}
            >
              {/* OpenStreetMap Tile Layer */}
              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {/* Outside India Mask */}
              {states && (
                <Polygon
                  positions={[world, ...indiaHoles] as any}
                  pathOptions={{
                    stroke: false,
                    fillColor: '#d9d9d9',
                    fillOpacity: 0.8,
                  }}
                />
              )}

              {/* Map Controller */}
              <MapController
                selectedState={selectedState}
                districts={districts}
                resetTrigger={resetTrigger}
                flyToCoords={flyToCoords}
                selectedPinId={selectedPinId}
                highlightTrigger={highlightTrigger}
                markerRefs={markerRefs}
              />

              {/* State Boundaries */}
              {states && (
                <GeoJSON
                  data={states}
                  style={{
                    color: '#000000',
                    weight: 1,
                    fillColor: '#ffffff',
                    fillOpacity: 0,
                  }}
                  onEachFeature={(feature, layer) => {
                    const stateName = feature.properties?.shapeName;
                    layer.on({
                      click: () => {
                        if (stateName) setSelectedState(stateName);
                      },
                    });
                    layer.bindTooltip(stateName || 'State', { sticky: true });
                  }}
                />
              )}

              {/* District Boundaries when state selected */}
              {selectedState && districts && (
                <GeoJSON
                  key={selectedState}
                  data={{
                    type: 'FeatureCollection',
                    features: districts.features.filter(
                      (f) => f.properties?.st_nm === selectedState
                    ),
                  } as FeatureCollection}
                  style={{
                    color: '#333333',
                    weight: 0.8,
                    fillColor: '#ffffff',
                    fillOpacity: 0,
                  }}
                />
              )}

              {/* Inspection Markers */}
              {filteredInspections.map((insp) => (
                <CircleMarker
                  key={insp.id}
                  ref={(el) => {
                    if (el) {
                      markerRefs.current.set(insp.id, el);
                      if (insp.reportNo) markerRefs.current.set(insp.reportNo, el);
                    } else {
                      markerRefs.current.delete(insp.id);
                      if (insp.reportNo) markerRefs.current.delete(insp.reportNo);
                    }
                  }}
                  center={[insp.latitude, insp.longitude]}
                  radius={getMarkerRadius(insp.id)}
                  pathOptions={{
                    color: '#ffffff',
                    fillColor: getMarkerColor(insp.status),
                    fillOpacity: 1,
                    weight: 2,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedPinId(insp.id);
                    },
                  }}
                >
                  <Popup autoPan={true}>
                    <div className="w-[300px] text-left">
                      {/* Popup Top Bar */}
                      <div className="p-3 bg-white border-b border-slate-100 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 text-[10px] font-medium text-black border border-slate-300">
                            {insp.status === 'non-compliant' ? 'NON-COMPLIANT' :
                             insp.status === 'needs-review' ? 'NEEDS REVIEW' : 'COMPLIANT'}
                          </span>
                          {insp.isDemo && (
                            <span className="px-1.5 py-0.5 text-[8.5px] font-bold bg-amber-100 text-amber-800 border border-amber-300 rounded-2xs uppercase">
                              DEMO PIN
                            </span>
                          )}
                          <span className="text-xs font-bold text-black">
                            {insp.reportNo || insp.id}
                          </span>
                        </div>
                      </div>

                      {/* Popup Body */}
                      <div className="p-3.5 space-y-2 text-xs">
                        <div>
                          <h3 className="text-[13px] font-bold text-black leading-tight">
                            {insp.business}
                          </h3>
                          <div className="flex items-center gap-1 text-[11px] text-black mt-0.5">
                            <MapPin className="w-3 h-3 text-slate-400 flex-shrink-0" />
                            <span>{insp.godown}, {insp.district}</span>
                          </div>
                        </div>

                        {/* GPS & Accuracy */}
                        <div className="flex items-center justify-between text-[11px] text-black bg-white p-1.5 border border-slate-200">
                          <span>GPS: {insp.latitude.toFixed(4)}° N, {insp.longitude.toFixed(4)}° E</span>
                          <span className="text-black font-medium">(±2m Confirmed)</span>
                        </div>

                        {insp.violations.length > 0 && (
                          <div className="border-t border-slate-100 pt-2 space-y-1.5">
                            <div className="text-[11px]">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-black">VIOLATIONS:</span>
                                <span className="font-bold text-black">{insp.violations.length} Infractions</span>
                              </div>
                              <ul className="text-[11px] text-black space-y-0.5 mt-1 pl-1">
                                {insp.violations.map((v, i) => (
                                  <li key={i} className="flex items-start gap-1">
                                    <span className="text-black">•</span>
                                    <span>{v}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}

                        {/* Inspector & Date */}
                        <div className="border-t border-slate-100 pt-2 flex items-center justify-between text-[10.5px] text-black">
                          <span>Inspector: {insp.inspector}</span>
                          <span>{insp.date}</span>
                        </div>
                      </div>

                      {/* Popup Actions */}
                      <div className="p-3 bg-slate-50 border-t border-slate-200 flex items-center gap-2">
                        <button
                          onClick={() => {
                            const targetReport = reportsMap.get(insp.id) 
                              || (insp.reportNo ? reportsMap.get(insp.reportNo) : undefined);
                            if (targetReport) {
                              onViewReport(targetReport);
                            }
                          }}
                          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 text-black border border-slate-300 text-xs font-medium cursor-pointer"
                        >
                          <span>VIEW EXACT REPORT</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>

                        <button
                          onClick={() => {
                            navigator.clipboard?.writeText(`${insp.latitude.toFixed(4)}° N, ${insp.longitude.toFixed(4)}° E`);
                          }}
                          className="flex items-center gap-1 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-black text-xs font-medium cursor-pointer"
                        >
                          <Copy className="w-3.5 h-3.5" />
                          <span>COPY</span>
                        </button>
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>

          {/* Top-Right Map Zoom & Tool Controls */}
          <div className="absolute top-3 right-3 flex flex-col gap-1.5 z-[1000] pointer-events-auto">
            <button 
              onClick={() => {
                setSelectedState(null);
                setResetTrigger((p) => p + 1);
                setFlyToCoords([30.9010, 75.8573]);
              }}
              title="Recenter Map"
              className="p-2 bg-white border border-slate-300 hover:bg-slate-50 text-black cursor-pointer flex items-center justify-center"
            >
              <Navigation className="w-4 h-4" />
            </button>

            <button 
              title="Toggle Layers"
              className="p-2 bg-white border border-slate-300 hover:bg-slate-50 text-black cursor-pointer flex items-center justify-center"
            >
              <Layers className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Right: Inspection Feed Sidebar (4 Columns) */}
        <div className="lg:col-span-4 flex flex-col space-y-3">
          <div className="bg-white border border-slate-300 p-3 flex-1 flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-black">
                  Inspection Feed
                </h2>
                <p className="text-[11px] text-black">
                  {isLive ? `Authorized Jurisdiction (${feedItems.length} records)` : 'Active Viewport: Ludhiana East & Central (Demo)'}
                </p>
              </div>
              <span className="px-2 py-0.5 text-[10px] font-medium text-black border border-slate-300">
                {feedItems.length} IN VIEW
              </span>
            </div>

            <div className="space-y-2 overflow-y-auto max-h-[460px] pr-1">
              {feedItems.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500 border border-dashed border-slate-200">
                  No active inspection records in this viewport.
                </div>
              ) : (
                feedItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 border border-slate-300 bg-white space-y-2 text-left"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-xs text-black">
                          {item.id.length > 18 ? `${item.id.slice(0, 18)}...` : item.id}
                        </span>
                        {item.isDemo && (
                          <span className="px-1.5 py-0.5 text-[8.5px] font-bold bg-amber-100 text-amber-800 border border-amber-300 rounded-2xs uppercase">
                            DEMO
                          </span>
                        )}
                      </div>
                      <span className="px-2 py-0.5 text-[9.5px] font-medium text-black border border-slate-300">
                        {item.status}
                      </span>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold text-black">{item.business}</h4>
                      <p className="text-[11px] text-black mt-0.5">{item.subtitle}</p>
                    </div>

                    <div className="text-[11px] font-medium text-black">
                      {item.infraction}
                    </div>

                    <div className="flex items-center justify-between text-[10.5px] text-black pt-1 border-t border-slate-200">
                      <span>Inspector: {item.inspector}</span>
                      <span>{item.timeAgo}</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <button
                        onClick={() => handleHighlight(item.id)}
                        className="flex items-center justify-center gap-1 px-2.5 py-1 text-xs font-medium text-black bg-white hover:bg-slate-50 border border-slate-300 cursor-pointer"
                      >
                        <span>Highlight Map</span>
                      </button>

                      <button
                        onClick={() => {
                          const targetReport = reportsMap.get(item.id);
                          if (targetReport) {
                            onViewReport(targetReport);
                          }
                        }}
                        className="flex items-center justify-center gap-1 px-2.5 py-1 text-xs font-medium text-black bg-white hover:bg-slate-50 border border-slate-300 cursor-pointer"
                      >
                        <span>View Report</span>
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
