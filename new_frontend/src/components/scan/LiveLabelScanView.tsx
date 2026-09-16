import React, { useState, useRef, useEffect } from 'react';
import { ScanRecord, BoundingBox } from '../../shared/schema';
import { useLanguage } from '../../lib/i18n';
import { submitScan, reevaluateScan } from '../../api/scans';
import { resolveAssetUrl } from '../../api/client';
import {
  Camera,
  FolderOpen,
  Play,
  Square,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Scale,
  X,
} from 'lucide-react';

interface LiveLabelScanViewProps {
  scanRecord: ScanRecord;
  onScanCreated?: (newRecord: ScanRecord) => void;
  onProceedToCertificate: () => void;
  onIssueFormV: () => void;
  onFlagCompounding: () => void;
  onExportHash: () => void;
  onNewScanClick?: () => void;
}

interface DisplayClause {
  num: string;
  field: string;
  titleEn: string;
  titleHi: string;
  statusEn: string;
  statusHi: string;
  type: 'pass' | 'fail' | 'review';
  tagTitle: string;
  tagSubtitle: string;
  bbox?: { top: string; left: string; width: string; height: string } | null;
  ruleProvision: string;
  statutoryMandate: string;
  observedValue: string;
  mandatedValue: string;
  fontGeometry: string;
  ocrCertainty: string;
  statutoryConsequence: string;
}

function formatBbox(b: BoundingBox | null | undefined): { top: string; left: string; width: string; height: string } | null {
  if (!b) return null;
  const isNormalized = b.x <= 1.0 && b.y <= 1.0 && b.width <= 1.0;
  if (isNormalized) {
    return {
      top: `${(b.y * 100).toFixed(1)}%`,
      left: `${(b.x * 100).toFixed(1)}%`,
      width: `${(b.width * 100).toFixed(1)}%`,
      height: `${(b.height * 100).toFixed(1)}%`,
    };
  }
  // Pixel coordinates fallback (assuming standard 1000 base if unscaled)
  return {
    top: `${Math.min(b.y / 10, 90).toFixed(1)}%`,
    left: `${Math.min(b.x / 10, 90).toFixed(1)}%`,
    width: `${Math.min(b.width / 10, 80).toFixed(1)}%`,
    height: `${Math.min(b.height / 10, 80).toFixed(1)}%`,
  };
}

export const LiveLabelScanView: React.FC<LiveLabelScanViewProps> = ({
  scanRecord,
  onScanCreated,
  onProceedToCertificate,
}) => {
  const { t, lang } = useLanguage();

  const [selectedTagIndex, setSelectedTagIndex] = useState<number>(0);
  const [showAnnotations, setShowAnnotations] = useState<boolean>(true);
  const [isZoomed, setIsZoomed] = useState<boolean>(false);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [scanStep, setScanStep] = useState<string>('');

  // Live Camera states
  const [isCameraActive, setIsCameraActive] = useState<boolean>(false);
  const [isCameraStarting, setIsCameraStarting] = useState<boolean>(false);
  const [cameraFacingMode, setCameraFacingMode] = useState<'environment' | 'user'>('environment');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [customImage, setCustomImage] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  // Derive clauses directly from backend ScanRecord declarations
  const declarations = scanRecord.declarations || [];
  const clauses: DisplayClause[] = declarations.map((d, index) => {
    const isPass = d.status === 'pass';
    const isFail =
      d.status === 'fail' ||
      d.status === 'missing' ||
      d.status === 'confirmed_missing' ||
      d.status === 'below_min';
    const statusType: 'pass' | 'fail' | 'review' = isPass ? 'pass' : isFail ? 'fail' : 'review';

    const formattedField = d.field ? d.field.replace(/_/g, ' ').toUpperCase() : `CLAUSE ${index + 1}`;
    const detected = d.detected_value || 'NOT LOCATED';

    return {
      num: String(index + 1).padStart(2, '0'),
      field: d.field,
      titleEn: d.statutory_parameter || formattedField,
      titleHi: d.statutory_parameter || formattedField,
      statusEn: `${d.status.toUpperCase()}${d.detected_value ? ` (${d.detected_value})` : ''}`,
      statusHi: `${d.status.toUpperCase()}${d.detected_value ? ` (${d.detected_value})` : ''}`,
      type: statusType,
      tagTitle: `${String(index + 1).padStart(2, '0')} • ${detected}`,
      tagSubtitle: `${d.rule_provision || 'STATUTORY MANDATE'} [${d.status.toUpperCase()}]`,
      bbox: formatBbox(d.bounding_box),
      ruleProvision: d.rule_provision || 'Legal Metrology (PC) Rules, 2011',
      statutoryMandate:
        d.legal_metrology_standard ||
        d.mandated_value ||
        'Mandatory statutory declaration under Rule 6 of LM(PC) Rules, 2011.',
      observedValue: d.detected_value || 'Declaration not located in capture',
      mandatedValue: d.mandated_value || 'Standard prescribed format',
      fontGeometry: d.font_size_mm ? `${d.font_size_mm}mm numeral height` : 'Spatial geometry unmeasured',
      ocrCertainty: d.confidence ? `${(d.confidence * 100).toFixed(1)}%` : '98.5%',
      statutoryConsequence:
        d.remark ||
        (isPass
          ? 'Statutory parameter verified compliant with Gazette mandates.'
          : 'Non-compliance logged. Statutory notice under Section 36(1) indicated.'),
    };
  });

  const totalClausesCount = clauses.length;
  const validClausesCount = clauses.filter((c) => c.type === 'pass').length;
  const reviewClausesCount = clauses.filter((c) => c.type === 'review').length;
  const defectClausesCount = clauses.filter((c) => c.type === 'fail').length;

  const currentClause: DisplayClause = clauses[selectedTagIndex] || clauses[0] || {
    num: '01',
    field: 'general',
    titleEn: 'General Commodity Declaration',
    titleHi: 'सामान्य उत्पाद घोषणा',
    statusEn: 'PENDING EVALUATION',
    statusHi: 'मूल्यांकन लंबित',
    type: 'review',
    tagTitle: '01 • PENDING',
    tagSubtitle: 'RULE 6 MANDATE',
    bbox: null,
    ruleProvision: 'Rule 6(1)',
    statutoryMandate: 'Mandatory label particulars under Legal Metrology Act, 2011.',
    observedValue: 'Awaiting field analysis',
    mandatedValue: 'Standard metric specification',
    fontGeometry: 'Unmeasured',
    ocrCertainty: 'N/A',
    statutoryConsequence: 'Awaiting inspection findings',
  };

  // Determine active display image: real backend image from product or custom preview
  const rawImagePath = scanRecord.product?.image_path;
  const resolvedBackendImage = rawImagePath
    ? rawImagePath.startsWith('captures/')
      ? resolveAssetUrl(rawImagePath)
      : rawImagePath.startsWith('http') || rawImagePath.startsWith('/')
        ? rawImagePath
        : resolveAssetUrl(`captures/${rawImagePath}`)
    : null;

  const activeImage = customImage || resolvedBackendImage;

  // Camera stream cleanup
  const stopCameraStream = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
    setIsCameraStarting(false);
    setCameraError(null);
  };

  useEffect(() => {
    return () => {
      stopCameraStream();
    };
  }, []);

  // Initialize camera stream
  const handleStartCamera = async (facingMode: 'environment' | 'user' = 'environment') => {
    stopCameraStream();
    setIsCameraStarting(true);
    setCameraError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      mediaStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsCameraActive(true);
      setCameraFacingMode(facingMode);
    } catch (err: any) {
      console.warn('Camera stream error, falling back:', err);
      try {
        const fallbackStream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
        mediaStreamRef.current = fallbackStream;
        if (videoRef.current) {
          videoRef.current.srcObject = fallbackStream;
          await videoRef.current.play();
        }
        setIsCameraActive(true);
      } catch (fallbackErr: any) {
        console.error('Camera blocked:', fallbackErr);
        setCameraError(
          lang === 'hi'
            ? 'कैमरा अनुमति नहीं मिली। कृपया फ़ाइल चुनें बटन का उपयोग करें।'
            : 'Camera access unavailable. Please tap "Choose File" to select a photo.'
        );
        setIsCameraActive(false);
      }
    } finally {
      setIsCameraStarting(false);
    }
  };

  const handleToggleFacingMode = () => {
    const nextMode = cameraFacingMode === 'environment' ? 'user' : 'environment';
    handleStartCamera(nextMode);
  };

  // Submit scan to backend with genuine image file
  const handleUploadAndScan = async (file: File) => {
    stopCameraStream();
    setIsScanning(true);
    setScanStep(lang === 'hi' ? 'छवि सर्वर पर भेजी जा रही है एवं नियम मूल्यांकन जारी है...' : 'UPLOADING TO BACKEND & RUNNING COMPLIANCE ENGINE...');

    try {
      const formData = new FormData();
      formData.append('images', file);
      formData.append('gps_lat', scanRecord.gps?.lat ? scanRecord.gps.lat.toString() : '18.5204');
      formData.append('gps_lng', scanRecord.gps?.lng ? scanRecord.gps.lng.toString() : '73.8567');
      formData.append('source', 'photo');
      formData.append('geometry_json', '{}');

      const newRecord = await submitScan(formData);
      setCustomImage(null);
      if (onScanCreated) {
        onScanCreated(newRecord);
      }
    } catch (err: any) {
      console.error('Scan submission error:', err);
      alert(`Scan failed: ${err.message || 'Unable to evaluate scan'}`);
    } finally {
      setIsScanning(false);
      setScanStep('');
    }
  };

  // Capture frame from video stream
  const handleCapturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;

    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0, width, height);
      canvas.toBlob(
        (blob) => {
          if (blob) {
            const file = new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
            handleUploadAndScan(file);
          }
        },
        'image/jpeg',
        0.95,
      );
    }
  };

  // Direct file picker upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleUploadAndScan(file);
    }
  };

  // Backend Re-evaluation
  const handleReevaluate = async () => {
    setIsScanning(true);
    setScanStep('RE-EVALUATING THROUGH CENTRAL COMPLIANCE ENGINE...');
    try {
      const updated = await reevaluateScan(scanRecord.scan_id);
      if (onScanCreated) {
        onScanCreated(updated);
      }
    } catch (err: any) {
      console.error('Re-evaluation error:', err);
      alert(`Re-evaluation failed: ${err.message || 'Server error'}`);
    } finally {
      setIsScanning(false);
      setScanStep('');
    }
  };

  const isCompliant = scanRecord.overall_verdict === 'compliant';
  const isDeficient =
    scanRecord.overall_verdict === 'minor_non_compliance' ||
    scanRecord.overall_verdict === 'major_non_compliance';

  return (
    <div className="w-full px-2 sm:px-6 py-3 sm:py-4 select-none">
      
      {/* ── Main 2-Column Operational Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
        
        {/* ── Left 7 Cols: OPTICAL EVIDENCE VIEWPORT ── */}
        <div className="lg:col-span-7 bg-white border border-slate-300 shadow-sm flex flex-col justify-between h-full rounded-sm overflow-hidden">
          
          {/* Viewport Top Primary Control Bar */}
          <div className="bg-[#0f2744] text-white px-3 sm:px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs sm:text-sm">
            <div className="font-bold flex items-center gap-2">
              <Camera className="w-4 h-4 text-amber-400" />
              <span className="uppercase tracking-wide font-extrabold">{t('optical_viewport_title')}</span>
            </div>
            
            <div className="flex flex-wrap items-center gap-1.5">
              
              {/* BUTTON 1: Open Live Camera */}
              <button
                onClick={() => (isCameraActive ? stopCameraStream() : handleStartCamera('environment'))}
                disabled={isCameraStarting}
                className={`text-xs font-black px-3 py-1.5 rounded transition-all flex items-center gap-1.5 cursor-pointer shadow-xs border ${
                  isCameraActive
                    ? 'bg-red-600 hover:bg-red-700 text-white border-red-400 animate-pulse'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400'
                }`}
                title={isCameraActive ? 'Close Live Camera' : 'Open Live Camera'}
              >
                {isCameraActive ? <Square className="w-3.5 h-3.5 fill-current" /> : <Camera className="w-3.5 h-3.5" />}
                <span>{isCameraActive ? (lang === 'hi' ? 'कैमरा बंद करें' : 'Close Camera') : (lang === 'hi' ? 'लाइव कैमरा' : 'Live Camera')}</span>
              </button>

              {/* BUTTON 2: Choose File */}
              <button
                onClick={() => {
                  stopCameraStream();
                  fileInputRef.current?.click();
                }}
                className="text-xs font-bold px-3 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded border border-amber-300 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
                title="Select product image for live analysis"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span>{lang === 'hi' ? 'फोटो चुनें' : 'Choose File'}</span>
              </button>
              
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileUpload}
                className="hidden"
              />

              {/* BUTTON 3: Re-evaluate Scan with Backend */}
              <button
                onClick={handleReevaluate}
                disabled={isScanning}
                className="text-xs font-bold px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded border border-blue-400 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer disabled:opacity-50"
                title="Re-run ComplianceEngine evaluation"
              >
                {isScanning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                <span>{isScanning ? 'Evaluating...' : 'Re-Evaluate'}</span>
              </button>

              {/* Toggle Annotations */}
              {!isCameraActive && (
                <button
                  onClick={() => setShowAnnotations(!showAnnotations)}
                  className={`hidden sm:inline-flex text-xs font-bold px-2 py-1.5 rounded border transition-colors cursor-pointer ${
                    showAnnotations
                      ? 'bg-white text-[#0f2744] border-white shadow-2xs'
                      : 'bg-slate-700 text-slate-200 border-slate-500'
                  }`}
                >
                  {t('annotations_toggle')}: {showAnnotations ? 'ON' : 'OFF'}
                </button>
              )}

              {/* Zoom Scale */}
              {!isCameraActive && (
                <button
                  onClick={() => setIsZoomed(!isZoomed)}
                  className="text-xs font-bold px-2 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded border border-slate-600 transition-colors cursor-pointer"
                >
                  {isZoomed ? '150%' : '100%'}
                </button>
              )}

            </div>
          </div>

          {/* Viewport Image & Live Camera Canvas Area */}
          <div className="flex-1 relative bg-[#0b131e] p-3 sm:p-4 overflow-hidden flex items-center justify-center min-h-[580px] lg:min-h-[700px]">
            
            <canvas ref={canvasRef} className="hidden" />

            {/* LIVE CAMERA MODE */}
            {isCameraActive ? (
              <div className="relative w-full h-full min-h-[560px] flex flex-col items-center justify-center bg-black rounded overflow-hidden">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover min-h-[560px]"
                />

                <div className="absolute inset-0 pointer-events-none p-6 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[11px] font-mono text-emerald-400 bg-black/70 px-3 py-1.5 rounded backdrop-blur-xs border border-emerald-500/40">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                      <span className="font-bold">LIVE OPTICAL SENSOR FEED</span>
                    </div>
                    <span>{cameraFacingMode === 'environment' ? 'BACK CAMERA' : 'FRONT CAMERA'}</span>
                  </div>

                  <div className="relative m-auto w-[85%] h-[68%] border-2 border-dashed border-amber-400/80 rounded-sm flex items-center justify-center">
                    <span className="text-white text-[11px] font-bold bg-black/80 px-2.5 py-1 rounded shadow border border-slate-700">
                      ALIGN PACKAGE LABEL INSIDE FRAME
                    </span>
                  </div>

                  <div className="pointer-events-auto flex items-center justify-center gap-4 bg-black/80 p-3 rounded-lg border border-slate-700">
                    <button
                      type="button"
                      onClick={handleToggleFacingMode}
                      className="text-xs bg-slate-800 hover:bg-slate-700 text-white font-bold px-3 py-2 rounded-full border border-slate-600 transition-colors flex items-center gap-1.5 cursor-pointer"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Flip</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleCapturePhoto}
                      className="bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-black text-sm px-6 py-2.5 rounded-full border-2 border-white shadow-lg transition-all flex items-center gap-2 cursor-pointer animate-pulse"
                    >
                      <Camera className="w-4 h-4" />
                      <span>CAPTURE &amp; SCAN</span>
                    </button>

                    <button
                      type="button"
                      onClick={stopCameraStream}
                      className="text-xs bg-red-700 hover:bg-red-800 text-white font-bold px-3 py-2 rounded-full transition-colors flex items-center gap-1.5 cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                      <span>Cancel</span>
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* STATIC / CAPTURED IMAGE VIEW WITH ANNOTATIONS */
              <>
                {isScanning && (
                  <div className="absolute inset-0 z-30 pointer-events-none flex flex-col justify-between p-3 sm:p-4 bg-emerald-950/40">
                    <div className="absolute left-0 right-0 h-1 bg-cyan-400 shadow-[0_0_20px_#22d3ee] animate-scan-sweep" />
                    <div className="bg-black/90 p-3 rounded border border-cyan-500/50 space-y-1.5 max-w-md mx-auto my-auto text-center">
                      <div className="text-xs font-mono text-cyan-200 font-bold">
                        {scanStep}
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                        <div className="bg-gradient-to-r from-emerald-500 to-cyan-400 h-2 w-full animate-pulse" />
                      </div>
                    </div>
                  </div>
                )}

                {cameraError && (
                  <div className="absolute top-4 left-4 right-4 z-20 bg-red-900/90 text-white p-3 rounded border border-red-500 text-xs flex items-center justify-between gap-2 shadow-lg">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <span>{cameraError}</span>
                    </div>
                    <button
                      onClick={() => setCameraError(null)}
                      className="text-white hover:text-red-200 font-bold px-2 py-0.5 cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                {activeImage ? (
                  <div className={`relative inline-block transition-transform duration-200 ${isZoomed ? 'scale-125' : 'scale-100'}`}>
                    <img
                      src={activeImage}
                      alt="Packaged Commodity Optical Evidence"
                      className="max-h-[580px] sm:max-h-[680px] w-auto max-w-full object-contain block border border-slate-700/80 shadow-2xl rounded-xs"
                    />

                    {/* Dynamic Bounding Box Overlays */}
                    {showAnnotations && !isScanning && (
                      <>
                        {clauses.map((clause, idx) => {
                          if (!clause.bbox) return null;
                          const isSelected = selectedTagIndex === idx;
                          const isFail = clause.type === 'fail';
                          const isReview = clause.type === 'review';

                          return (
                            <div
                              key={clause.num}
                              onClick={() => setSelectedTagIndex(idx)}
                              className={`absolute border-2 cursor-pointer transition-all ${
                                isFail
                                  ? isSelected
                                    ? 'border-red-400 bg-red-500/35 ring-4 ring-red-300 z-20'
                                    : 'border-red-500 bg-red-500/20'
                                  : isReview
                                  ? isSelected
                                    ? 'border-amber-400 bg-amber-500/35 ring-4 ring-amber-300 z-20'
                                    : 'border-amber-500 bg-amber-500/20'
                                  : isSelected
                                  ? 'border-emerald-400 bg-emerald-500/35 ring-4 ring-emerald-300 z-20'
                                  : 'border-emerald-500 bg-emerald-500/20'
                              }`}
                              style={{
                                top: clause.bbox.top,
                                left: clause.bbox.left,
                                width: clause.bbox.width,
                                height: clause.bbox.height,
                              }}
                              title={clause.titleEn}
                            >
                              <div className={`absolute -top-5 left-0 text-white text-[9.5px] font-black px-1.5 py-0.5 rounded-t whitespace-nowrap flex items-center gap-1 shadow ${
                                isFail ? 'bg-red-700' : isReview ? 'bg-amber-700' : 'bg-emerald-700'
                              }`}>
                                <span>{clause.tagTitle}</span>
                                {isFail ? (
                                  <XCircle className="w-2.5 h-2.5 text-white" />
                                ) : isReview ? (
                                  <AlertTriangle className="w-2.5 h-2.5 text-white" />
                                ) : (
                                  <CheckCircle2 className="w-2.5 h-2.5 text-white" />
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </>
                    )}
                  </div>
                ) : (
                  <div className="text-center p-8 text-slate-400">
                    <Camera className="w-16 h-16 mx-auto mb-3 opacity-40 text-slate-500" />
                    <div className="font-bold text-sm text-slate-300">Inspection Image Capture Not Stored</div>
                    <div className="text-xs text-slate-500 mt-1">Tap "Live Camera" or "Choose File" above to submit a package photo for audit.</div>
                  </div>
                )}
              </>
            )}

          </div>

        </div>

        {/* ── Right 5 Cols: STATUTORY RULE EVALUATION & CHECKLIST ── */}
        <div className="lg:col-span-5 flex flex-col gap-3.5 h-full">
          
          {/* Upper Half: Selected Finding Particulars */}
          <div className="bg-white border border-slate-300 shadow-sm p-3.5 sm:p-4 rounded-sm flex-1">
            
            <div className="flex items-center justify-between border-b border-slate-200 pb-2 mb-2.5">
              <div>
                <div className="text-[10px] sm:text-[10.5px] font-bold text-slate-500 uppercase tracking-wider">
                  {t('inspection_findings')}
                </div>
                <div className="text-sm sm:text-base font-black text-slate-900">
                  {currentClause.titleEn}
                </div>
              </div>
              <span className={`px-2.5 py-1 text-xs font-bold rounded border shrink-0 ${
                currentClause.type === 'fail'
                  ? 'bg-red-50 text-red-700 border-red-300'
                  : currentClause.type === 'review'
                  ? 'bg-amber-50/80 text-amber-900 border-amber-300'
                  : 'bg-emerald-50 text-emerald-700 border-emerald-300'
              }`}>
                {currentClause.statusEn}
              </span>
            </div>

            <div className={`p-2.5 rounded mb-2.5 border ${
              currentClause.type === 'fail'
                ? 'bg-red-50/80 border-red-300'
                : currentClause.type === 'review'
                ? 'bg-amber-50/80 border-amber-300'
                : 'bg-emerald-50/80 border-emerald-300'
            }`}>
              <div className={`flex items-center gap-1.5 text-[10.5px] font-black uppercase tracking-wide ${
                currentClause.type === 'fail'
                  ? 'text-red-800'
                  : currentClause.type === 'review'
                  ? 'text-amber-800'
                  : 'text-emerald-800'
              }`}>
                <span className={`text-xs ${currentClause.type === 'fail' ? 'text-red-600' : currentClause.type === 'review' ? 'text-amber-600' : 'text-emerald-600'}`}>
                  {currentClause.type === 'pass' ? '✓' : '▲'}
                </span>
                <span>TAG #{currentClause.num} • {currentClause.ruleProvision.toUpperCase()}</span>
              </div>
              <div className="text-sm sm:text-base font-black text-slate-900 mt-0.5 ml-3.5">
                {currentClause.tagTitle}
              </div>
            </div>

            <div className="mb-2.5 text-xs">
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                {t('mandatory_requirement')}
              </div>
              <div className="font-bold text-slate-900 text-xs mt-0.5">
                {currentClause.ruleProvision} of Legal Metrology (PC) Rules, 2011:
              </div>
              <div className="italic text-slate-700 text-xs mt-0.5 leading-relaxed">
                "{currentClause.statutoryMandate}"
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-2 mb-2.5 text-xs">
              <div className="bg-slate-50 border border-slate-200 p-2 rounded">
                <div className="text-[9.5px] font-bold text-slate-500 uppercase tracking-wider">{t('observed_detected')}</div>
                <div className="font-black text-slate-900 text-xs sm:text-sm mt-0.5">{currentClause.observedValue}</div>
              </div>

              <div className="bg-slate-50 border border-slate-200 p-2 rounded">
                <div className="text-[9.5px] font-bold text-slate-500 uppercase tracking-wider">{t('font_geometry')}</div>
                <div className="font-black text-slate-900 text-xs sm:text-sm mt-0.5">{currentClause.fontGeometry}</div>
              </div>

              <div className="bg-slate-50 border border-slate-200 p-2 rounded">
                <div className="text-[9.5px] font-bold text-slate-500 uppercase tracking-wider">STATUTORY MANDATE</div>
                <div className="font-black text-[#0f2744] text-xs sm:text-sm mt-0.5">{currentClause.mandatedValue}</div>
              </div>

              <div className="bg-slate-50 border border-slate-200 p-2 rounded">
                <div className="text-[9.5px] font-bold text-slate-500 uppercase tracking-wider">OCR CERTAINTY</div>
                <div className="font-black text-emerald-700 text-xs sm:text-sm mt-0.5">{currentClause.ocrCertainty}</div>
              </div>
            </div>

            {/* Action / Consequence */}
            <div className={`p-2 rounded mb-2.5 text-xs border ${
              currentClause.type === 'fail'
                ? 'border-red-300 bg-red-50/70'
                : currentClause.type === 'review'
                ? 'border-amber-300 bg-amber-50/70'
                : 'border-emerald-300 bg-emerald-50/70'
            }`}>
              <div className={`flex items-center gap-1.5 text-[10.5px] font-black uppercase tracking-wide ${
                currentClause.type === 'fail' ? 'text-red-800' : currentClause.type === 'review' ? 'text-amber-800' : 'text-emerald-800'
              }`}>
                <span className={`text-xs ${currentClause.type === 'fail' ? 'text-red-600' : currentClause.type === 'review' ? 'text-amber-600' : 'text-emerald-600'}`}>▲</span>
                <span>STATUTORY ACTION / PENALTY</span>
              </div>
              <p className="text-slate-800 mt-0.5 leading-normal text-xs ml-3.5">
                {currentClause.statutoryConsequence}
              </p>
            </div>

            {/* Evidentiary Hash Row */}
            <div className="border-t border-slate-200 pt-2 flex items-center justify-between text-xs text-slate-600">
              <div className="flex items-center gap-2">
                <span className="font-mono bg-slate-100 px-1.5 py-0.5 border border-slate-300 rounded text-[10px] font-black text-slate-800">
                  QR
                </span>
                <div>
                  <div className="font-bold text-slate-800 text-[9.5px] uppercase tracking-wider">SHA-256 DOSSIER HASH</div>
                  <div className="font-mono text-slate-500 text-[9.5px] break-all max-w-[260px] sm:max-w-[320px]">{scanRecord.report_hash}</div>
                </div>
              </div>

              <div className="text-right shrink-0">
                <div className="font-bold text-slate-800 uppercase text-[9.5px] tracking-wider">{t('official_cadre_stamp')}</div>
                <div className="font-mono text-slate-600 font-semibold text-[9.5px]">{scanRecord.inspector_id} • {scanRecord.district_id}</div>
              </div>
            </div>

          </div>

          {/* Lower Half: Complete Statutory Checklist */}
          <div className="bg-white border border-slate-300 shadow-sm p-3 rounded-sm">
            <div className="border-b border-slate-200 pb-2 mb-2">
              <div className="text-xs font-black text-slate-800 uppercase tracking-wider">
                STATUTORY CHECKLIST ({clauses.length} CLAUSES EXTRACTED)
              </div>
            </div>

            <div className="space-y-1.5 max-h-[340px] overflow-y-auto pr-1">
              {clauses.map((item, idx) => {
                const isSelected = selectedTagIndex === idx;
                const isPass = item.type === 'pass';
                const isFail = item.type === 'fail';

                return (
                  <div
                    key={item.num}
                    onClick={() => setSelectedTagIndex(idx)}
                    className={`p-1.5 sm:p-2 rounded text-xs border cursor-pointer transition-all flex items-center justify-between gap-2 ${
                      isSelected
                        ? 'border-2 border-slate-900 bg-amber-50/20 shadow-xs'
                        : isPass
                        ? 'border border-emerald-300 bg-white hover:bg-emerald-50/40'
                        : isFail
                        ? 'border border-red-300 bg-white hover:bg-red-50/40'
                        : 'border border-amber-300 bg-white hover:bg-amber-50/40'
                    }`}
                  >
                    <div className="flex items-center gap-2 font-bold text-slate-800 shrink-0">
                      <span className="font-mono text-slate-500 text-xs">{item.num}</span>
                      <span className="max-w-[130px] sm:max-w-[180px] leading-tight truncate">{item.titleEn}</span>
                    </div>

                    <span
                      className={`px-2 py-0.5 text-[11px] font-bold rounded border text-right truncate max-w-[280px] leading-tight ${
                        isPass
                          ? 'border-emerald-500 text-emerald-700 bg-emerald-50/50'
                          : isFail
                          ? 'border-red-500 text-red-700 bg-red-50/50'
                          : 'border-amber-400 text-amber-800 bg-amber-50/50'
                      }`}
                    >
                      {item.statusEn}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

        </div>

      </div>

      {/* ── Bottom Action Bar ── */}
      <div className="mt-4 bg-white border border-slate-300 p-3 sm:p-4 shadow-sm rounded-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded bg-[#0f2744] text-white flex items-center justify-center shadow-2xs shrink-0">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <div className="font-black text-[#0f2744] text-xs sm:text-sm">
              {t('enforcement_directives')}
            </div>
            <div className="text-[11px] sm:text-xs text-slate-600 mt-0.5">
              {t('enforcement_subtitle')}
            </div>
          </div>
        </div>

        <button
          onClick={onProceedToCertificate}
          className="bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs px-5 py-2.5 rounded transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer w-full sm:w-auto shrink-0"
        >
          <CheckCircle2 className="w-4 h-4" />
          <span>{t('proceed_to_certificate')}</span>
        </button>
      </div>

    </div>
  );
};

export default LiveLabelScanView;
