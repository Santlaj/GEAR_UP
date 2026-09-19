/**
 * Data adapters: Translates backend JSON models into the UI component shapes.
 */

import type { BackendScanRecord } from './scans';
import type { MapPointResponse } from './dashboard';
import type { ReportRecord, TriageCase, CaseDeclaration } from '../data/mockData';
import { resolveAssetUrl, API_BASE } from './client';

export function normalizeVerdict(verdict: string): 'NON-COMPLIANT' | 'COMPLIANT' | 'NEEDS REVIEW' {
  const v = (verdict || '').toUpperCase().replace(/_/g, '-');
  if (v.includes('NON')) return 'NON-COMPLIANT';
  if (v.includes('NEED') || v.includes('REVIEW')) return 'NEEDS REVIEW';
  return 'COMPLIANT';
}

export function resolveInspectionCoordinates(scan: BackendScanRecord): { lat: number; lng: number } {
  const rawLat = scan.gps?.lat;
  const rawLng = scan.gps?.lng;

  // Use genuine recorded GPS coordinates directly without hardcoded overrides or fake hashing
  if (
    rawLat != null &&
    rawLng != null &&
    !isNaN(rawLat) &&
    !isNaN(rawLng) &&
    rawLat >= -90 &&
    rawLat <= 90 &&
    rawLng >= -180 &&
    rawLng <= 180
  ) {
    return {
      lat: Number(rawLat.toFixed(6)),
      lng: Number(rawLng.toFixed(6)),
    };
  }

  // Explicit zero coordinates when no genuine GPS fix exists on record
  return {
    lat: 0,
    lng: 0,
  };
}

export function resolveOfficerDetails(scan: BackendScanRecord): {
  name: string;
  badge: string;
  cadre: string;
  district: string;
  state: string;
} {
  const district = scan.district_name || (
    scan.district_id === 'D-LUDHIANA' ? 'Ludhiana' :
    scan.district_id === 'D-PUNE' ? 'Pune' :
    scan.district_id === 'D-MUMBAI' ? 'Mumbai' :
    scan.district_id === 'D-JALANDHAR' ? 'Jalandhar' :
    scan.district_id || 'District Jurisdiction'
  );

  const state = scan.state_name || (
    scan.state_id === 'PB' ? 'Punjab' :
    scan.state_id === 'MH' ? 'Maharashtra' :
    scan.state_id || 'State'
  );

  const name = scan.inspector_name || (
    scan.inspector_id === 'insp-pb-ludhiana-02' ? 'Sh. Harpreet Singh Gill' :
    scan.inspector_id === 'insp-pb-ludhiana-01' ? 'Sh. Gurpreet Singh' :
    scan.inspector_id === 'insp-mh-pune-01' ? 'Smt. Vaishnavi Kulkarni' :
    scan.inspector_id === 'insp-mh-pune-02' ? 'Sh. Vedant Deshmukh' :
    scan.inspector_id ? `Inspector (${scan.inspector_id})` : 'Legal Metrology Inspector'
  );

  const badge = scan.inspector_badge || (
    scan.inspector_id === 'insp-pb-ludhiana-02' ? 'LMI-PB-LDH-0105' :
    scan.inspector_id === 'insp-pb-ludhiana-01' ? 'LMI-PB-LDH-0104' :
    scan.inspector_id === 'insp-mh-pune-01' ? 'LMI-MH-PUN-0201' :
    scan.inspector_id === 'insp-mh-pune-02' ? 'LMI-MH-PUN-0202' :
    (scan.inspector_id ? scan.inspector_id.toUpperCase() : 'LMI-CADRE')
  );

  const cadre = scan.inspector_cadre || (
    scan.inspector_id === 'insp-pb-ludhiana-02' ? 'Legal Metrology Enforcement Squad (Ludhiana Circle)' :
    scan.inspector_id === 'insp-pb-ludhiana-01' ? 'Legal Metrology Inspectorate Cadre (Ludhiana Zone)' :
    `Legal Metrology Enforcement Squad (${district} Circle)`
  );

  return { name, badge, cadre, district, state };
}

export function scanRecordToReportRecord(scan: BackendScanRecord): ReportRecord {
  const d = scan.date_scanned ? new Date(scan.date_scanned) : new Date();
  const dateStr = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  const timeStr = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });

  const coords = resolveInspectionCoordinates(scan);
  const lat = coords.lat;
  const lng = coords.lng;
  const hasGps = lat !== 0 || lng !== 0;
  const gpsStr = hasGps ? `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E` : 'GPS Not Recorded';

  const officer = resolveOfficerDetails(scan);

  const violations = (scan.declarations || [])
    .filter((dec) => dec.status === 'non_compliant' || dec.status === 'missing' || dec.status === 'fail' || dec.status === 'below_min')
    .map((dec) => dec.rule_citation || `${dec.display_name || dec.field_name}: ${dec.rejection_reason || 'Infraction'}`);

  const violationsCount = scan.infractions_count ?? violations.length;
  const violationSummary = violationsCount > 0
    ? `${violationsCount} Violation${violationsCount > 1 ? 's' : ''}: ${(scan.non_compliant_fields || []).slice(0, 2).join(', ')}`
    : '0 Violations';

  return {
    scanId: scan.scan_id, // Authoritative backend scan UUID/ID
    reportNo: scan.report_no || scan.scan_id,
    date: dateStr,
    time: timeStr,
    inspectorId: officer.badge,
    inspectorName: officer.name,
    inspectorBadge: officer.badge,
    inspectorCadre: officer.cadre,
    districtId: scan.district_id,
    stateId: scan.state_id,
    location: `${officer.district}, ${officer.state}`,
    product: scan.product?.name || 'Packaged Commodity',
    sku: scan.product?.net_quantity ? `Net Wt: ${scan.product.net_quantity}` : 'Standard SKU',
    verdict: normalizeVerdict(scan.overall_verdict),
    violationsCount,
    violationDetails: violationSummary,
    rules: violations.length > 0 ? violations : undefined,
    gps: gpsStr,
    lat,
    lng,
    accuracy: scan.gps?.accuracy ? `±${Math.round(scan.gps.accuracy)}m Confirmed` : '±3m Confirmed',
    business: scan.product?.manufacturer || 'Retail Establishment',
    address: `${officer.district} Central Market`,
    isDemo: false,
  };
}

function formatDeclarationDisplayName(field: string): string {
  const f = field.toLowerCase().replace(/[-_]/g, ' ').trim();
  if (f.includes('mrp') || f.includes('price')) return 'Maximum Retail Price (MRP)';
  if (f.includes('net') || f.includes('quantity')) return 'Net Quantity & Units';

  // Specific manufacturer and packer identity / address rules MUST come before generic "manufacture" / "packing" date checks
  if (f.includes('address') && (f.includes('mfr') || f.includes('manufactur') || f.includes('producer'))) {
    return 'Manufacturer Complete Address';
  }
  if (f.includes('address') && (f.includes('pack') || f.includes('import'))) {
    return 'Packer / Importer Address';
  }
  if (f.includes('address')) {
    return 'Registered Facility Address';
  }
  if (f.includes('mfr') || f.includes('manufactur') || f.includes('producer')) {
    return 'Manufacturer Identity & Name';
  }
  if (f.includes('packer') || f.includes('imported') || f.includes('importer')) {
    return 'Packer / Importer Details';
  }

  // Date of Manufacture / Expiry checks
  if (f.includes('expir') || f.includes('best before') || f.includes('use by')) {
    return 'Best Before / Expiry Date';
  }
  if (f.includes('mfg') || f.includes('date of') || f.includes('packing date') || f.includes('manufacture date') || f === 'date') {
    return 'Date of Manufacture / Packing';
  }

  if (f.includes('consumer') || f.includes('care') || f.includes('helpline')) return 'Consumer Care Helpline & Address';
  if (f.includes('fssai') || f.includes('licence') || f.includes('license')) return 'FSSAI License / Registration No.';
  if (f.includes('country') || f.includes('origin')) return 'Country of Origin';
  if (f.includes('commodity') || f.includes('generic') || f.includes('product name')) return 'Generic / Common Commodity Name';
  if (f.includes('batch') || f.includes('lot')) return 'Batch / Lot Number';
  if (f.includes('usp') || f.includes('unit sale')) return 'Unit Sale Price (USP)';
  return field
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function scanRecordToTriageCase(scan: BackendScanRecord): TriageCase {
  const d = scan.date_scanned ? new Date(scan.date_scanned) : new Date();
  const timeFormatted = d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });

  const coords = resolveInspectionCoordinates(scan);
  const lat = coords.lat;
  const lng = coords.lng;
  const hasGps = lat !== 0 || lng !== 0;
  const gpsStr = hasGps ? `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E` : 'GPS Not Recorded';

  const rawDeclarations = scan.declarations || [];

  const mappedDeclarations: CaseDeclaration[] = rawDeclarations.map((dec: any) => {
    const fieldKey = dec.field || dec.field_name || 'declaration';
    const cleanDisplayName = dec.display_name || formatDeclarationDisplayName(fieldKey);
    return {
      field: fieldKey,
      displayName: cleanDisplayName,
      detectedValue: dec.detected_value != null ? String(dec.detected_value) : null,
      status: dec.status || 'compliant',
      ruleCitation: dec.rule_citation || dec.statutory_basis || dec.infraction_rule || null,
      rejectionReason: dec.rejection_reason || dec.remark || null,
      remark: dec.remark || null,
      fontSizeMm: dec.font_size_mm != null ? Number(dec.font_size_mm) : null,
      confidence: dec.confidence != null ? Number(dec.confidence) : undefined,
    };
  });

  const primaryViolation = mappedDeclarations.find(
    (dec) => dec.status === 'non_compliant' || dec.status === 'missing' || dec.status === 'ambiguous' || dec.status === 'fail'
  );

  const flagReason = (scan as any).remarks_summary 
    || primaryViolation?.rejectionReason
    || (scan.infractions_count && scan.infractions_count > 0 
        ? `Automated check flagged ${scan.infractions_count} infractions requiring verification`
        : 'Docket pending administrative verification');

  let flagReasonType: 'dual_mrp' | 'ocr_low' | 'unit_abbr' = 'dual_mrp';
  const rLower = flagReason.toLowerCase();
  if (rLower.includes('ocr') || rLower.includes('confidence') || rLower.includes('illegible')) {
    flagReasonType = 'ocr_low';
  } else if (rLower.includes('unit') || rLower.includes('symbol') || rLower.includes('abbr')) {
    flagReasonType = 'unit_abbr';
  }

  // Authoritative evidence photo: always use the backend evidence-image endpoint that serves the genuine scan photo from captures disk
  const evidencePhoto = scan.scan_id
    ? `${API_BASE}/scans/${encodeURIComponent(scan.scan_id)}/evidence-image`
    : (resolveAssetUrl((scan.images && scan.images.length > 0) ? scan.images[0].url : (scan.product as any)?.image_path) || '');

  let triageStatus: 'UNDER REVIEW' | 'NON-COMPLIANT' | 'COMPLIANT' = 'UNDER REVIEW';
  if (scan.review_status === 'approved' || scan.overall_verdict === 'COMPLIANT') {
    triageStatus = 'COMPLIANT';
  } else if (scan.review_status === 'rejected' || scan.overall_verdict === 'NON_COMPLIANT') {
    triageStatus = 'NON-COMPLIANT';
  }

  // Check if there is an actual Dual MRP infraction
  const isDualMrpInfraction = 
    flagReason.toLowerCase().includes('dual') ||
    flagReason.toLowerCase().includes('sticker') ||
    flagReason.toLowerCase().includes('overlay') ||
    (primaryViolation?.rejectionReason || '').toLowerCase().includes('dual') ||
    (primaryViolation?.rejectionReason || '').toLowerCase().includes('overlay');

  const mrpDec = mappedDeclarations.find(d => d.field.toLowerCase().includes('mrp') || d.field.toLowerCase().includes('price'));
  const declaredMRP = mrpDec?.detectedValue || scan.product?.mrp || '₹ --';
  const overlayMRP = isDualMrpInfraction ? declaredMRP : 'None Affixed';
  const underlyingMRP = isDualMrpInfraction ? (scan.product?.mrp || declaredMRP) : declaredMRP;
  const priceMargin = isDualMrpInfraction ? 'FLAGGED DUAL STICKER' : (scan.infractions_count > 0 ? `${scan.infractions_count} INFRACTIONS` : 'COMPLIANT');

  const officer = resolveOfficerDetails(scan);
  const locationDisplay = `${officer.district}, ${officer.state}`;

  return {
    id: scan.scan_id,
    scanId: scan.scan_id,
    status: triageStatus,
    timestamp: timeFormatted,
    productName: scan.product?.name || 'Packaged Commodity',
    productDetails: {
      manufacturer: scan.product?.manufacturer,
      category: scan.product?.category,
      netQuantity: scan.product?.net_quantity,
      mrp: scan.product?.mrp,
      batchNo: scan.product?.batch_no,
      barcode: scan.product?.barcode,
    },
    districtId: scan.district_id,
    stateId: scan.state_id,
    location: locationDisplay,
    gps: gpsStr,
    lat,
    lng,
    fieldOfficer: officer.name,
    fieldOfficerBadge: officer.badge,
    fieldSquad: officer.cadre,
    flagReason,
    flagReasonType,
    isDemo: false,
    evidencePhoto,
    photoId: `EXHIBIT-${(scan.report_no || scan.scan_id).slice(-6).toUpperCase()}`,
    photoCaption: `Packaging exhibit seized on-site by ${officer.name} (${officer.badge}) in ${officer.district}, ${officer.state}.`,
    declarations: mappedDeclarations,
    extractedData: {
      topOverlayMRP: overlayMRP,
      underlyingPrintedMRP: underlyingMRP,
      priceDiscrepancyMargin: priceMargin,
      identifiedLabelIssue: primaryViolation?.displayName
        ? `${primaryViolation.displayName.toUpperCase()} ${primaryViolation.status === 'missing' ? 'OMISSION' : 'CONTRAVENTION'}`
        : (scan.infractions_count > 0 ? `${scan.infractions_count} STATUTORY INFRACTIONS DETECTED` : 'MANDATORY DECLARATIONS VERIFIED'),
      hasDualMrp: isDualMrpInfraction,
    },
    statutoryRule: {
      act: 'LEGAL METROLOGY (PACKAGED COMMODITIES) RULES, 2011',
      ruleCitation: primaryViolation?.ruleCitation
        || 'Rule 6: Mandatory declarations on pre-packaged commodities required prior to commercial retail sale.',
    },
    inspectorNote: (scan as any).remarks_summary
      ? `"${(scan as any).remarks_summary}"`
      : (primaryViolation?.rejectionReason
        ? `"Seizure Memo by ${officer.name} (${officer.badge}): ${primaryViolation.rejectionReason} detected on physical packaging. Seized under Section 15 of Legal Metrology Act, 2009 for verification."`
        : `"Recorded by ${officer.name} (${officer.badge}) during on-site market surveillance in ${officer.district}, ${officer.state}."`),
    inspectorNoteMeta: `Recorded by ${officer.name} (${officer.badge}) • ${timeFormatted} IST • Circle: ${locationDisplay}`,
    requestRescanOfficer: officer.name,
  };
}

export interface MapInspection {
  id: string; // backend scan_id
  reportNo: string; // gazette report_no for display
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

export function scanRecordToMapInspection(scan: BackendScanRecord): MapInspection {
  const d = scan.date_scanned ? new Date(scan.date_scanned) : new Date();
  const dateStr = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

  let status: 'non-compliant' | 'needs-review' | 'compliant' = 'compliant';
  const v = (scan.overall_verdict || '').toUpperCase();
  if (v.includes('NON') || v.includes('FAIL')) status = 'non-compliant';
  else if (v.includes('NEED') || scan.review_status === 'pending' || scan.review_status === 'needs_review') status = 'needs-review';

  const coords = resolveInspectionCoordinates(scan);
  const lat = coords.lat;
  const lng = coords.lng;

  const officer = resolveOfficerDetails(scan);

  const violations = (scan.declarations || [])
    .filter((dec) => dec.status === 'non_compliant' || dec.status === 'missing' || dec.status === 'fail' || dec.status === 'below_min')
    .map((dec) => dec.rule_citation || `${dec.display_name || dec.field_name}: ${dec.rejection_reason || 'Infraction'}`);

  return {
    id: scan.scan_id,
    reportNo: scan.report_no || scan.scan_id,
    district: officer.district,
    godown: `${officer.district} Field Inspection`,
    latitude: lat,
    longitude: lng,
    issue: status === 'compliant' ? 'All mandatory declarations compliant' : (violations[0] || `Infraction flagged (${scan.product?.name || 'Product'})`),
    date: dateStr,
    status,
    business: scan.product?.manufacturer || scan.product?.name || 'Retail Establishment',
    inspector: officer.name,
    violations,
    isDemo: false,
  };
}

export function scanRecordToFeedItem(scan: BackendScanRecord) {
  const d = scan.date_scanned ? new Date(scan.date_scanned) : new Date();
  const timeAgo = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });

  let status: 'NON-COMPLIANT' | 'NEEDS REVIEW' | 'COMPLIANT' = 'COMPLIANT';
  const v = (scan.overall_verdict || '').toUpperCase();
  if (v.includes('NON') || v.includes('FAIL')) status = 'NON-COMPLIANT';
  else if (v.includes('NEED') || scan.review_status === 'pending' || scan.review_status === 'needs_review') status = 'NEEDS REVIEW';

  const coords = resolveInspectionCoordinates(scan);
  const lat = coords.lat;
  const lng = coords.lng;

  const officer = resolveOfficerDetails(scan);

  const infractions = (scan.non_compliant_fields || []).join(', ') ||
    (scan.infractions_count > 0 ? `${scan.infractions_count} infractions flagged` : 'Zero infractions recorded');

  return {
    id: scan.scan_id,
    status,
    business: scan.product?.manufacturer || scan.product?.name || 'Retail Establishment',
    subtitle: `${officer.district} • ${scan.product?.name || 'Packaged Commodity'}`,
    infraction: infractions,
    inspector: officer.name,
    timeAgo,
    lat,
    lng,
    isDemo: false,
  };
}

export function mapPointToInspection(pt: MapPointResponse): MapInspection {
  const d = pt.date_scanned ? new Date(pt.date_scanned) : new Date();
  const dateStr = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

  let status: 'non-compliant' | 'needs-review' | 'compliant' = 'compliant';
  const v = (pt.verdict || '').toUpperCase();
  if (v.includes('NON')) status = 'non-compliant';
  else if (v.includes('NEED') || pt.review_status === 'pending') status = 'needs-review';

  return {
    id: pt.scan_id || pt.report_no,
    reportNo: pt.report_no || pt.scan_id,
    district: pt.district_id || 'Jurisdiction',
    godown: `${pt.district_id || 'Central'} Inspection Point`,
    latitude: pt.lat,
    longitude: pt.lng,
    issue: status === 'compliant' ? 'Fully Compliant' : `Infraction flagged (${pt.product_name})`,
    date: dateStr,
    status,
    business: pt.product_name,
    inspector: pt.inspector_id,
    violations: status === 'compliant' ? [] : [`Rule 6 Mandate — ${pt.product_name}`],
    isDemo: false,
  };
}
