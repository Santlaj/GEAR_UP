import React, { useState, useRef, useEffect } from 'react';
import { ScanRecord, UserContext } from '../../shared/schema';
import { submitScan } from '../../api/scans';
import { ApiError } from '../../api/client';
import { Camera, ShoppingBag, FolderOpen, Square, AlertTriangle, RefreshCw, X } from 'lucide-react';

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
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // GPS state
  const [gpsLat, setGpsLat] = useState<number>(18.5204);
  const [gpsLng, setGpsLng] = useState<number>(73.8567);
  const [gpsStatus, setGpsStatus] = useState<string>('Acquiring GPS...');

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Acquire GPS on mount
  useEffect(() => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setGpsLat(pos.coords.latitude);
          setGpsLng(pos.coords.longitude);
          setGpsStatus(`${pos.coords.latitude.toFixed(4)}° N, ${pos.coords.longitude.toFixed(4)}° E`);
        },
        (err) => {
          console.warn('Geolocation error:', err);
          setGpsLat(18.5204);
          setGpsLng(73.8567);
          setGpsStatus('GPS permission denied — standard beat coordinates applied');
        },
        { enableHighAccuracy: true, timeout: 10000 },
      );
    } else {
      setGpsLat(18.5204);
      setGpsLng(73.8567);
      setGpsStatus('GPS not supported — standard beat coordinates applied');
    }
  }, []);

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

  const handleStartCamera = async () => {
    setCameraError(null);
    stopCameraStream();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      });
      mediaStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsCameraActive(true);
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
      setImagePreview(dataUrl);

      // Convert canvas to File for backend upload
      canvas.toBlob(
        (blob) => {
          if (blob) {
            const file = new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
            setImageFile(file);
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
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setImagePreview(event.target.result as string);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!isOnline) {
      setSubmitError('You are offline. Scan submission requires a network connection to the backend server.');
      return;
    }

    // Validate inputs
    if (sourceType === 'photo' && !imageFile) {
      setSubmitError('Please capture or select a photo of the product label before submitting.');
      return;
    }
    if (sourceType === 'listing_url' && !listingUrl.trim()) {
      setSubmitError('Please enter a valid e-commerce listing URL.');
      return;
    }

    setIsProcessing(true);

    try {
      // Build FormData matching the backend contract (routes.py submit_scan)
      const formData = new FormData();
      formData.append('gps_lat', gpsLat.toString());
      formData.append('gps_lng', gpsLng.toString());
      formData.append('source', sourceType);
      formData.append('geometry_json', '{}');

      if (sourceType === 'photo' && imageFile) {
        formData.append('images', imageFile);
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
            <Camera className="w-4 h-4 text-amber-400" />
            <span className="font-black text-sm tracking-wide uppercase">
              FIELD ON-SITE COMMODITY CAPTURE &amp; AUDIT
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:text-slate-300 p-1 cursor-pointer"
          >
            <X className="w-4 h-4" />
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
                className={`py-2.5 px-4 border rounded text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer ${
                  sourceType === 'photo'
                    ? 'bg-[#0f2744] text-white border-[#0f2744] shadow-sm'
                    : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                }`}
              >
                <Camera className="w-4 h-4" />
                <span>Camera / Photo Capture</span>
              </button>

              <button
                type="button"
                onClick={() => setSourceType('listing_url')}
                className={`py-2.5 px-4 border rounded text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer ${
                  sourceType === 'listing_url'
                    ? 'bg-[#0f2744] text-white border-[#0f2744] shadow-sm'
                    : 'bg-slate-50 text-slate-700 border-slate-300 hover:bg-slate-100'
                }`}
              >
                <ShoppingBag className="w-4 h-4" />
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
                  className={`px-3.5 py-2 rounded text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                    isCameraActive
                      ? 'bg-red-700 text-white'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs'
                  }`}
                >
                  {isCameraActive ? <Square className="w-3.5 h-3.5 fill-current" /> : <Camera className="w-3.5 h-3.5" />}
                  <span>{isCameraActive ? 'Close Camera' : 'Open Live Camera'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-3.5 py-2 rounded text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 flex items-center gap-1.5 transition-all shadow-xs cursor-pointer"
                >
                  <FolderOpen className="w-3.5 h-3.5" />
                  <span>Choose File / Gallery</span>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
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
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="max-h-48 w-full object-contain"
                  />
                  <div className="absolute bottom-2 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleCapturePhoto}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs px-4 py-2 rounded-full border border-white shadow flex items-center gap-1.5 cursor-pointer"
                    >
                      <Camera className="w-3.5 h-3.5" />
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
                /* Static Image Preview */
                imagePreview && (
                  <div className="flex flex-col items-center justify-center">
                    <img
                      src={imagePreview}
                      alt="Preview"
                      className="max-h-32 rounded border border-slate-300 object-contain shadow-xs"
                    />
                    <span className="text-[11px] text-slate-500 mt-1">Package photo ready for optical audit</span>
                  </div>
                )
              )}

              {!isCameraActive && !imagePreview && (
                <div className="text-xs text-slate-500 py-4">
                  Open the camera or choose a file to capture the product label image.
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

          {/* GPS Telemetry Notice */}
          <div className="text-xs text-slate-600 bg-blue-50 border border-blue-200 p-2.5 rounded leading-relaxed">
            <strong>EVIDENTIARY ATTESTATION:</strong> Captured under Gazetted Cadre ({user.badge_number}) with GPS telemetry ({gpsStatus}) and backend ComplianceEngine evaluation.
          </div>

          {/* Error Display */}
          {submitError && (
            <div className="text-xs text-red-700 bg-red-50 border border-red-300 p-3 rounded leading-relaxed flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
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
              disabled={isProcessing || !isOnline}
              className="bg-[#0f2744] hover:bg-[#1a385c] text-white font-bold text-sm px-5 py-2 rounded transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {isProcessing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
              <span>{isProcessing ? 'Submitting to Backend...' : 'Submit Scan to Server'}</span>
            </button>
          </div>

        </form>

      </div>
    </div>
  );
};
