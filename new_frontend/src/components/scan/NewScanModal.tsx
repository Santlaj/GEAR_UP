import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ScanRecord, UserContext } from '../../shared/schema';
import { submitScan } from '../../api/scans';
import { ApiError } from '../../api/client';
import { acquireDeviceGps, DeviceGpsResult } from '../../lib/gps';
import { X, MapPin, MapPinOff, RefreshCw, AlertTriangle } from 'lucide-react';

interface NewScanModalProps {
  user: UserContext;
  isOnline: boolean;
  onClose: () => void;
  onScanCreated: (record: ScanRecord) => void;
}

export const NewScanModal: React.FC<NewScanModalProps> = ({
  user,
  isOnline,
  onClose,
  onScanCreated,
}) => {
  const [sourceType, setSourceType] = useState<'photo' | 'listing_url'>('photo');
  const [listingUrl, setListingUrl] = useState('');
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Real device GPS state — strictly required, no fake fallbacks
  const [gpsLoc, setGpsLoc] = useState<DeviceGpsResult | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [isAcquiringGps, setIsAcquiringGps] = useState<boolean>(true);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Acquire real-time GPS on mount & support manual reconnect
  const handleFetchGps = useCallback(async (force = false) => {
    setIsAcquiringGps(true);
    setGpsError(null);
    try {
      const loc = await acquireDeviceGps(force);
      setGpsLoc(loc);
      setGpsError(null);
    } catch (e: any) {
      console.warn('GPS acquisition failed:', e);
      setGpsLoc(null);
      setGpsError(e?.message || 'Location access is required to verify statutory inspection coordinates. Please grant location permissions in your browser and tap Reconnect.');
    } finally {
      setIsAcquiringGps(false);
    }
  }, []);

  useEffect(() => {
    handleFetchGps(false);
  }, [handleFetchGps]);

  const stopCameraStream = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t: MediaStreamTrack) => t.stop());
      mediaStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
  };

  useEffect(() => {
    if (isCameraActive && videoRef.current && mediaStreamRef.current) {
      if (videoRef.current.srcObject !== mediaStreamRef.current) {
        videoRef.current.srcObject = mediaStreamRef.current;
      }
      videoRef.current.play().catch((e) => console.error('Modal camera play error:', e));
    }
  }, [isCameraActive]);

  const handleStartCamera = async () => {
    setCameraError(null);
    stopCameraStream();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      });
      mediaStreamRef.current = stream;
      setIsCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err: any) {
      console.error('Camera access failed:', err);
      setCameraError('Camera access unavailable. Please use "Choose File" to select a photo.');
      setIsCameraActive(false);
    }
  };

  const handleCapturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.95);

      canvas.toBlob(
        (blob) => {
          if (blob) {
            const idx = imageFiles.length + 1;
            const file = new File([blob], `capture_${Date.now()}_${idx}.jpg`, { type: 'image/jpeg' });
            setImageFiles((prev) => [...prev, file].slice(0, 3));
            setImagePreviews((prev) => [...prev, dataUrl].slice(0, 3));
          }
        },
        'image/jpeg',
        0.95,
      );

      stopCameraStream();
    }
  };

  const handleImageFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    stopCameraStream();
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      const selected = files.slice(0, 3);
      setImageFiles(selected);
      const previews: string[] = [];
      let loaded = 0;
      selected.forEach((f, i) => {
        const reader = new FileReader();
        reader.onload = (event) => {
          previews[i] = event.target?.result as string;
          loaded++;
          if (loaded === selected.length) {
            setImagePreviews([...previews]);
          }
        };
        reader.readAsDataURL(f);
      });
    }
  };

  const removeImage = (index: number) => {
    setImageFiles((prev) => prev.filter((_, i) => i !== index));
    setImagePreviews((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!isOnline) {
      setSubmitError('You are offline. Scan submission requires a network connection to the backend server.');
      return;
    }

    // Validate inputs
    if (sourceType === 'photo' && imageFiles.length === 0) {
      setSubmitError('Please capture or select at least one photo of the product label before submitting.');
      return;
    }
    if (sourceType === 'listing_url' && !listingUrl.trim()) {
      setSubmitError('Please enter a valid e-commerce listing URL.');
      return;
    }

    setIsProcessing(true);

    try {
      // Strictly require genuine real-time location before submission
      let activeLoc = gpsLoc;
      if (!activeLoc) {
        try {
          activeLoc = await acquireDeviceGps(false);
          setGpsLoc(activeLoc);
        } catch (err: any) {
          setSubmitError('Mandatory Location Access: System cannot evaluate commodity without verified real-time location. Please click "Allow / Reconnect Location" above and grant browser permissions.');
          setIsProcessing(false);
          return;
        }
      }

      // Build FormData matching the backend contract (routes.py submit_scan)
      const formData = new FormData();
      formData.append('gps_lat', activeLoc.lat.toString());
      formData.append('gps_lng', activeLoc.lng.toString());
      formData.append('source', sourceType);
      formData.append('geometry_json', '{}');

      if (sourceType === 'photo') {
        for (const file of imageFiles) {
          formData.append('images', file);
        }
      } else if (sourceType === 'listing_url') {
        formData.append('source_url', listingUrl.trim());
      }

      // Call the real backend — ComplianceEngine processes the scan
      const record = await submitScan(formData);

      // Pass the backend-returned authoritative ScanRecord to the parent
      onScanCreated(record);
      onClose();
    } catch (err) {
      console.error('Scan submission failed:', err);

      if (err instanceof ApiError) {
        setSubmitError(`Submission failed (${err.status}): ${err.detail}`);
      } else if (err instanceof Error) {
        setSubmitError(`Submission failed: ${err.message}`);
      } else {
        setSubmitError('An unexpected error occurred during scan submission.');
      }
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white border border-slate-300 w-full max-w-2xl rounded shadow-2xl overflow-hidden select-none my-8">
        
        {/* Modal Header */}
        <div className="bg-[#0f2744] text-white px-5 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="font-black text-sm tracking-wide uppercase">
              FIELD ON-SITE COMMODITY CAPTURE &amp; AUDIT
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:text-slate-300 px-2 py-1 font-bold text-base cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Modal Body Form */}
        <form onSubmit={handleSubmit} className="p-6 text-sm space-y-4">
          
          {/* Source Type Selector */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
              CAPTURE SOURCE
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setSourceType('photo')}
                className={`py-2.5 px-4 border rounded text-xs font-bold flex items-center justify-center transition-colors cursor-pointer ${
                  sourceType === 'photo'
                    ? 'bg-[#0f2744] text-white border-[#0f2744] shadow-sm'
                    : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                }`}
              >
                <span>Camera / Photo Capture</span>
              </button>

              <button
                type="button"
                onClick={() => setSourceType('listing_url')}
                className={`py-2.5 px-4 border rounded text-xs font-bold flex items-center justify-center transition-colors cursor-pointer ${
                  sourceType === 'listing_url'
                    ? 'bg-[#0f2744] text-white border-[#0f2744] shadow-sm'
                    : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                }`}
              >
                <span>E-Commerce Listing URL</span>
              </button>
            </div>
          </div>

          {sourceType === 'photo' ? (
            <div className="border border-slate-300 bg-slate-50 p-4 rounded text-center space-y-3">
              <canvas ref={canvasRef} className="hidden" />

              {/* Action Switcher Buttons */}
              <div className="flex items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => (isCameraActive ? stopCameraStream() : handleStartCamera())}
                  className={`px-3.5 py-2 rounded text-xs font-bold flex items-center transition-all cursor-pointer ${
                    isCameraActive
                      ? 'bg-red-700 text-white'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs'
                  }`}
                >
                  <span>{isCameraActive ? 'Close Camera' : 'Open Live Camera'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-3.5 py-2 rounded text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 flex items-center transition-all shadow-xs cursor-pointer"
                >
                  <span>Choose File / Gallery</span>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageFileChange}
                  className="hidden"
                />
              </div>

              {cameraError && (
                <div className="text-xs text-red-700 bg-red-50 border border-red-200 p-2 rounded">
                  {cameraError}
                </div>
              )}

              {/* Live Camera Viewfinder */}
              {isCameraActive ? (
                <div className="relative bg-black rounded overflow-hidden max-h-56 flex flex-col items-center justify-center p-2">
                  <video
                    ref={(el) => {
                      videoRef.current = el;
                      if (el && mediaStreamRef.current && el.srcObject !== mediaStreamRef.current) {
                        el.srcObject = mediaStreamRef.current;
                        el.play().catch((e) => console.error('Modal camera play error:', e));
                      }
                    }}
                    autoPlay
                    playsInline
                    muted
                    className="max-h-48 w-full object-contain"
                  />
                  <div className="absolute bottom-2 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleCapturePhoto}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs px-4 py-2 rounded-full border border-white shadow flex items-center cursor-pointer"
                    >
                      <span>Capture Photo</span>
                    </button>
                    <button
                      type="button"
                      onClick={stopCameraStream}
                      className="bg-slate-800 text-white font-bold text-xs px-3 py-2 rounded-full cursor-pointer"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                /* Multi-Image Preview Cards */
                imagePreviews.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-center gap-3">
                      {imagePreviews.map((preview, idx) => {
                        const roleLabel = idx === 0 ? 'Front Label' : idx === 1 ? 'Back / Nutrition' : 'Side / Details';
                        return (
                          <div key={idx} className="relative group border border-slate-300 rounded bg-white p-1.5 shadow-xs flex flex-col items-center">
                            <img
                              src={preview}
                              alt={roleLabel}
                              className="w-24 h-24 rounded object-cover"
                            />
                            <span className="text-[10px] font-bold text-slate-700 mt-1">{roleLabel}</span>
                            <button
                              type="button"
                              onClick={() => removeImage(idx)}
                              className="absolute -top-1.5 -right-1.5 bg-red-600 hover:bg-red-700 text-white rounded-full p-0.5 shadow cursor-pointer"
                              title="Remove photo"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                    <span className="text-[11px] text-slate-500 block">
                      {imagePreviews.length} of 3 evidence photos attached for optical audit
                    </span>
                  </div>
                )
              )}

              {!isCameraActive && imagePreviews.length === 0 && (
                <div className="text-xs text-slate-500 py-4">
                  Open the camera or choose files (front, back, side panels) for statutory compliance scanning.
                </div>
              )}
            </div>
          ) : (
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
                E-COMMERCE PRODUCT URL (Amazon / Flipkart / Blinkit)
              </label>
              <input
                type="url"
                value={listingUrl}
                onChange={(e) => setListingUrl(e.target.value)}
                placeholder="https://www.amazon.in/dp/..."
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm font-mono focus:outline-none focus:border-[#0f2744]"
              />
            </div>
          )}

          {/* GPS Telemetry Banner with Mandatory Reconnect Button */}
          {!gpsLoc ? (
            <div className="p-3.5 bg-red-50 border border-red-300 rounded text-xs text-red-900 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs">
              <div className="flex items-start gap-2.5">
                <MapPinOff className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-red-800 uppercase tracking-wide flex items-center gap-1.5">
                    <span>MANDATORY STATUTORY LOCATION REQUIRED</span>
                  </div>
                  <p className="text-red-700 text-[11px] mt-0.5 leading-snug">
                    {gpsError || 'System will not let you scan without verified device location access. Tap Reconnect to allow browser permissions.'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleFetchGps(true)}
                disabled={isAcquiringGps}
                className="px-3.5 py-2 bg-red-700 hover:bg-red-800 text-white font-bold text-xs rounded flex items-center gap-1.5 shrink-0 cursor-pointer shadow-xs disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isAcquiringGps ? 'animate-spin' : ''}`} />
                <span>{isAcquiringGps ? 'Connecting GPS...' : 'Allow / Reconnect Location'}</span>
              </button>
            </div>
          ) : (
            <div className="text-xs bg-emerald-50 border border-emerald-300 p-2.5 rounded flex items-center justify-between gap-3 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 shrink-0 animate-pulse" />
                <div>
                  <div className="font-bold text-emerald-950 flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-emerald-700" />
                    <span>VERIFIED ON-SITE GPS:</span>
                    <span className="font-mono font-bold text-emerald-900">{gpsLoc.statusText}</span>
                  </div>
                  <div className="text-[10.5px] text-emerald-800 mt-0.5">
                    Statutory coordinates locked for Cadre Officer #{user.badge_number} (Accuracy: ±{gpsLoc.accuracy}m)
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleFetchGps(true)}
                disabled={isAcquiringGps}
                className="px-2.5 py-1 text-[11px] font-bold bg-white hover:bg-emerald-100 text-emerald-900 border border-emerald-300 rounded flex items-center gap-1 shrink-0 cursor-pointer shadow-2xs disabled:opacity-50"
                title="Refresh device coordinates"
              >
                <RefreshCw className={`w-3 h-3 ${isAcquiringGps ? 'animate-spin' : ''}`} />
                <span>{isAcquiringGps ? 'Locking...' : 'Refresh GPS'}</span>
              </button>
            </div>
          )}

          {/* Error Display */}
          {submitError && (
            <div className="text-xs text-red-700 bg-red-50 border border-red-300 p-3 rounded leading-relaxed flex items-center gap-2">
              <span><strong>SUBMISSION ERROR:</strong> {submitError}</span>
            </div>
          )}

          {/* Form Actions */}
          <div className="pt-3 flex items-center justify-end gap-3 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 rounded text-slate-700 font-bold hover:bg-slate-50 transition-colors text-sm cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isProcessing || !isOnline || !gpsLoc}
              className="bg-[#0f2744] hover:bg-[#1a385c] text-white font-bold text-sm px-5 py-2 rounded transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              <span>
                {isProcessing
                  ? 'Submitting to Backend...'
                  : !gpsLoc
                  ? 'Location Access Required to Scan'
                  : 'Submit Scan to Server'}
              </span>
            </button>
          </div>

        </form>

      </div>
    </div>
  );
};
