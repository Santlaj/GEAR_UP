// ============================================================================
// DEMO / REFERENCE DATA: For offline interface fallback only. Not live official records.
// ============================================================================

export interface ReportRecord {
  scanId?: string; // Authoritative backend scan UUID/ID (absent on demo/mock items)
  reportNo: string;
  date: string;
  time: string;
  inspectorId: string;
  inspectorName: string;
  inspectorBadge?: string;
  inspectorCadre?: string;
  districtId?: string;
  stateId?: string;
  location: string;
  product: string;
  sku: string;
  verdict: 'NON-COMPLIANT' | 'COMPLIANT' | 'NEEDS REVIEW';
  violationsCount: number;
  violationDetails: string;
  rules?: string[];
  gps: string;
  lat: number;
  lng: number;
  accuracy?: string;
  business: string;
  address: string;
  isDemo?: boolean;
}

export interface CaseDeclaration {
  field: string;
  displayName: string;
  detectedValue: string | null;
  status: 'compliant' | 'non_compliant' | 'missing' | 'ambiguous' | string;
  ruleCitation?: string | null;
  rejectionReason?: string | null;
  remark?: string | null;
  fontSizeMm?: number | null;
  confidence?: number;
}

export interface TriageCase {
  id: string;
  scanId?: string; // Authoritative backend scan UUID/ID
  status: 'UNDER REVIEW' | 'NON-COMPLIANT' | 'COMPLIANT';
  timestamp: string;
  productName: string;
  productDetails?: {
    manufacturer?: string;
    category?: string;
    netQuantity?: string;
    mrp?: string;
    batchNo?: string;
    barcode?: string;
  };
  districtId?: string;
  stateId?: string;
  location: string;
  gps: string;
  lat: number;
  lng: number;
  fieldOfficer: string;
  fieldOfficerBadge?: string;
  fieldSquad?: string;
  flagReason: string;
  flagReasonType: 'dual_mrp' | 'ocr_low' | 'unit_abbr';
  evidencePhoto: string;
  photoId: string;
  photoCaption: string;
  declarations?: CaseDeclaration[];
  extractedData: {
    topOverlayMRP: string;
    underlyingPrintedMRP: string;
    priceDiscrepancyMargin: string;
    identifiedLabelIssue: string;
    hasDualMrp?: boolean;
  };
  statutoryRule: {
    act: string;
    ruleCitation: string;
  };
  inspectorNote: string;
  inspectorNoteMeta: string;
  requestRescanOfficer: string;
  isDemo?: boolean;
}

export interface MapInspectionFeedItem {
  id: string;
  status: 'NON-COMPLIANT' | 'NEEDS REVIEW' | 'COMPLIANT';
  business: string;
  subtitle: string;
  infraction: string;
  inspector: string;
  timeAgo: string;
  lat: number;
  lng: number;
  isDemo?: boolean;
}

export interface MapMarkerPin {
  id: string;
  name: string;
  status: 'NON-COMPLIANT' | 'NEEDS REVIEW' | 'COMPLIANT';
  lat: number;
  lng: number;
  areaLabel: string;
  hasPopupData?: boolean;
  isDemo?: boolean;
}

export const MOCK_REPORTS: ReportRecord[] = [
  {
    reportNo: 'LM-2026-00456',
    date: '15 Sep',
    time: '10:42 AM',
    inspectorId: 'INS-014',
    inspectorName: 'Sh. R. K. Sharma',
    location: 'Gill Road Mandi, Ludhiana',
    product: 'Fortune Sunlite Refined Oil',
    sku: 'SKU: 1L Poly Pouch',
    verdict: 'NON-COMPLIANT',
    violationsCount: 2,
    violationDetails: '2 Violations: USP missing, Font size',
    rules: [
      'Rule 6(1)(h) Unit Sale Price Missing',
      'Rule 12 Font Height Deficit on Mandatory Declarations'
    ],
    gps: '30.8942° N, 75.8611° E',
    lat: 30.8942,
    lng: 75.8611,
    accuracy: '±2m Confirmed',
    business: 'Singla Wholesale & Kirana',
    address: 'Gill Road Mandi, Sector 22, Ludhiana'
  },
  {
    reportNo: 'LM-2026-00451',
    date: '15 Sep',
    time: '09:15 AM',
    inspectorId: 'INS-008',
    inspectorName: 'Sh. Gurpreet Singh',
    location: 'Focal Point Phase-V, Ludhiana',
    product: 'Britannia Marie Gold',
    sku: 'SKU: 300g Biscuit Pack',
    verdict: 'NON-COMPLIANT',
    violationsCount: 1,
    violationDetails: '1 Violation: Date missing',
    rules: [
      'Rule 24 Declaration Obscured with Secondary Barcode'
    ],
    gps: '30.8835° N, 75.9124° E',
    lat: 30.8835,
    lng: 75.9124,
    accuracy: '±3m Confirmed',
    business: 'Britannia Marie Warehouse Depot',
    address: 'Focal Point Phase-V, Ludhiana'
  },
  {
    reportNo: 'LM-2026-00448',
    date: '14 Sep',
    time: '04:30 PM',
    inspectorId: 'INS-008',
    inspectorName: 'Assigned Inspector',
    location: 'Jagraon Bridge Market, Ludhiana',
    product: 'Tata Iodised Salt',
    sku: 'SKU: 1kg Food Grade Poly',
    verdict: 'COMPLIANT',
    violationsCount: 0,
    violationDetails: '0 Violations',
    gps: '30.9082° N, 75.8450° E',
    lat: 30.9082,
    lng: 75.8450,
    business: 'Shree Ganesh Trading Co.',
    address: 'Jagraon Bridge Market, Ludhiana'
  },
  {
    reportNo: 'LM-2026-00442',
    date: '14 Sep',
    time: '02:10 PM',
    inspectorId: 'INS-014',
    inspectorName: 'Assigned Inspector',
    location: 'Chaura Bazaar, Ludhiana',
    product: 'Dhara Kachi Ghani Mustard Oil',
    sku: 'SKU: 1L Bottle',
    verdict: 'NEEDS REVIEW',
    violationsCount: 1,
    violationDetails: 'Density check required',
    gps: '30.9125° N, 75.8542° E',
    lat: 30.9125,
    lng: 75.8542,
    business: 'Gupta Super Store',
    address: 'Chaura Bazaar, Ludhiana'
  },
  {
    reportNo: 'LM-2026-00439',
    date: '13 Sep',
    time: '11:22 AM',
    inspectorId: 'INS-014',
    inspectorName: 'Assigned Inspector',
    location: 'Clock Tower Market, Ludhiana',
    product: 'Colgate Strong Teeth',
    sku: 'SKU: 200g Lami-tube',
    verdict: 'NON-COMPLIANT',
    violationsCount: 1,
    violationDetails: 'Dual MRP sticker',
    gps: '30.9150° N, 75.8505° E',
    lat: 30.9150,
    lng: 75.8505,
    business: 'Capital Chemist & Provisions',
    address: 'Clock Tower Market, Ludhiana'
  },
  {
    reportNo: 'LM-2026-00435',
    date: '12 Sep',
    time: '03:55 PM',
    inspectorId: 'INS-008',
    inspectorName: 'Assigned Inspector',
    location: 'Gill Road, Ludhiana',
    product: 'Aashirvaad Shudh Chakki Atta',
    sku: 'SKU: 5kg Woven Bag',
    verdict: 'COMPLIANT',
    violationsCount: 0,
    violationDetails: '0 Violations',
    gps: '30.8910° N, 75.8600° E',
    lat: 30.8910,
    lng: 75.8600,
    business: 'Punjab Agro Mega Outlet',
    address: 'Gill Road, Ludhiana'
  }
];

export const MOCK_TRIAGE_CASES: TriageCase[] = [
  {
    id: 'LM-2026-00472',
    status: 'UNDER REVIEW',
    timestamp: '14 Sep, 04:30 PM',
    productName: 'Confectionery & Sweets Box (500g)',
    location: 'Model Town Market, Ludhiana',
    gps: '30.8990° N, 75.8320° E',
    lat: 30.8990,
    lng: 75.8320,
    fieldOfficer: 'INS-012 (H. Grewal)',
    flagReason: 'Ambiguous Dual MRP sticker detected on pack',
    flagReasonType: 'dual_mrp',
    evidencePhoto: '/evidence_dual_mrp.jpg',
    photoId: 'IMG-472-EVID-A Captured 16:28:11',
    photoCaption: 'Packaged box showing dual price sticker overlaid over original MRP.',
    extractedData: {
      topOverlayMRP: '₹ 180.00',
      underlyingPrintedMRP: '₹ 140.00',
      priceDiscrepancyMargin: '+ ₹ 40.00 (+28.5%)',
      identifiedLabelIssue: 'ALTERATION / SMUDGING OF RETAIL PRICE'
    },
    statutoryRule: {
      act: 'LEGAL METROLOGY (PACKAGED COMMODITIES) RULES, 2011',
      ruleCitation: 'Rule 18(2): No person shall alter, obliterate or smudge the maximum retail price indicated by the manufacturer or packer. Revised declarations require sanctioned affixation.'
    },
    inspectorNote: '"Store owner stated price revision notice from distributor, but oversticker does not comply with Rule 18(2)."',
    inspectorNoteMeta: 'Recorded by INS-012 at 16:32 IST',
    requestRescanOfficer: 'INS-012'
  },
  {
    id: 'LM-2026-00461',
    status: 'UNDER REVIEW',
    timestamp: '15 Sep, 09:15 AM',
    productName: 'Personal Care Lotion (200ml)',
    location: 'Civil Lines Ward 4, Ludhiana',
    gps: '30.9065° N, 75.8390° E',
    lat: 30.9065,
    lng: 75.8390,
    fieldOfficer: 'INS-008 (S. Bhatia)',
    flagReason: 'Low OCR confidence on manufacturer address',
    flagReasonType: 'ocr_low',
    evidencePhoto: '/evidence_dual_mrp.jpg',
    photoId: 'IMG-461-EVID-B Captured 09:05:40',
    photoCaption: 'Bottle reverse side label showing faint dot matrix imprint of packer address.',
    extractedData: {
      topOverlayMRP: '₹ 299.00',
      underlyingPrintedMRP: '₹ 299.00',
      priceDiscrepancyMargin: '₹ 0.00 (0.0%)',
      identifiedLabelIssue: 'ILLEGIBLE / INCOMPLETE MANDATORY PACKER DETAILS'
    },
    statutoryRule: {
      act: 'LEGAL METROLOGY (PACKAGED COMMODITIES) RULES, 2011',
      ruleCitation: 'Rule 6(1)(a): Every package shall bear the name and complete address of the manufacturer, packer or importer with minimum legible font height.'
    },
    inspectorNote: '"Manufacturer pin code smudged due to conveyor roller contact. Automated OCR gave 38% confidence score."',
    inspectorNoteMeta: 'Recorded by INS-008 at 09:20 IST',
    requestRescanOfficer: 'INS-008'
  },
  {
    id: 'LM-2026-00479',
    status: 'UNDER REVIEW',
    timestamp: '14 Sep, 02:10 PM',
    productName: 'Fabric Detergent (1kg)',
    location: 'Focal Point, Ludhiana',
    gps: '30.8870° N, 75.9180° E',
    lat: 30.8870,
    lng: 75.9180,
    fieldOfficer: 'INS-014 (K. Sharma)',
    flagReason: 'Net Quantity unit abbreviation non-standard',
    flagReasonType: 'unit_abbr',
    evidencePhoto: '/evidence_dual_mrp.jpg',
    photoId: 'IMG-479-EVID-C Captured 14:02:18',
    photoCaption: "Front poly bag package displaying 'Net Wt: 1 Kgs.' instead of statutory '1 kg'.",
    extractedData: {
      topOverlayMRP: '₹ 125.00',
      underlyingPrintedMRP: '₹ 125.00',
      priceDiscrepancyMargin: '₹ 0.00 (0.0%)',
      identifiedLabelIssue: 'NON-STANDARD SYMBOL OF UNIT (PLURALIZED S)'
    },
    statutoryRule: {
      act: 'LEGAL METROLOGY (PACKAGED COMMODITIES) RULES, 2011',
      ruleCitation: "Rule 13(2): The symbols for units shall not be followed by any punctuation or pluralized (e.g. 'kg', not 'kgs' or 'Kg.')."
    },
    inspectorNote: '"Package displays \'1 Kgs.\' printed prominently. Clear violation of Second Schedule standard units."',
    inspectorNoteMeta: 'Recorded by INS-014 at 14:15 IST',
    requestRescanOfficer: 'INS-014'
  }
];

export const MOCK_FEED_ITEMS: MapInspectionFeedItem[] = [
  {
    id: 'LM-2026-00456',
    status: 'NON-COMPLIANT',
    business: 'Singla Wholesale & Kirana',
    subtitle: 'Gill Road Mandi • Fortune Sunlite Refined Oil',
    infraction: '2 Infractions: Rule 6(1)(h) USP missing, Rule 12 Height deficit',
    inspector: 'INS-014',
    timeAgo: '10 mins ago',
    lat: 30.8942,
    lng: 75.8611,
    isDemo: true
  },
  {
    id: 'LM-2026-00451',
    status: 'NON-COMPLIANT',
    business: 'Britannia Marie Warehouse Depot',
    subtitle: 'Focal Point Phase-V • Britannia Marie Gold 300g',
    infraction: '1 Infraction: Rule 24 Declaration Obscured with Secondary Barcode',
    inspector: 'INS-008',
    timeAgo: '24 mins ago',
    lat: 30.8835,
    lng: 75.9124,
    isDemo: true
  },
  {
    id: 'LM-2026-00472',
    status: 'NEEDS REVIEW',
    business: 'Imperial Confectionery Pack',
    subtitle: 'Model Town Extension • Imported Wafers 250g',
    infraction: 'Flagged: Potential Dual MRP Smudge (₹180 vs ₹220)',
    inspector: 'INS-014',
    timeAgo: '1 hr ago',
    lat: 30.8990,
    lng: 75.8320,
    isDemo: true
  }
];

export const MOCK_MAP_PINS: MapMarkerPin[] = [
  {
    id: 'LM-2026-00456',
    name: 'Singla Wholesale & Kirana',
    status: 'NON-COMPLIANT',
    lat: 30.8942,
    lng: 75.8611,
    areaLabel: 'Gill Road Mandi',
    hasPopupData: true,
    isDemo: true
  },
  {
    id: 'LM-2026-00439',
    name: 'Capital Provisions',
    status: 'NON-COMPLIANT',
    lat: 30.9150,
    lng: 75.8505,
    areaLabel: 'Clock Tower Chowk',
    isDemo: true
  },
  {
    id: 'LM-2026-00451',
    name: 'Britannia Marie Depot',
    status: 'NON-COMPLIANT',
    lat: 30.8835,
    lng: 75.9124,
    areaLabel: 'Focal Point Phase-V',
    isDemo: true
  },
  {
    id: 'LM-2026-00472',
    name: 'Imperial Confectionery',
    status: 'NEEDS REVIEW',
    lat: 30.8990,
    lng: 75.8320,
    areaLabel: 'Model Town Extension',
    isDemo: true
  },
  {
    id: 'LM-2026-00442',
    name: 'Gupta Super Store',
    status: 'NEEDS REVIEW',
    lat: 30.9065,
    lng: 75.8390,
    areaLabel: 'Civil Lines',
    isDemo: true
  },
  {
    id: 'LM-2026-00481',
    name: 'Khanna Regional Depot',
    status: 'NEEDS REVIEW',
    lat: 30.8650,
    lng: 75.8750,
    areaLabel: 'Khanna Grain Market Outer',
    isDemo: true
  },
  {
    id: 'LM-2026-00448',
    name: 'Shree Ganesh Trading',
    status: 'COMPLIANT',
    lat: 30.9082,
    lng: 75.8450,
    areaLabel: 'Jagraon Bridge',
    isDemo: true
  },
  {
    id: 'LM-2026-00435',
    name: 'Punjab Agro Outlet',
    status: 'COMPLIANT',
    lat: 30.8870,
    lng: 75.7950,
    areaLabel: 'Bhai Randhir Singh Nagar',
    isDemo: true
  },
  {
    id: 'LM-2026-00430',
    name: 'Meharban Cooperative Store',
    status: 'COMPLIANT',
    lat: 30.9380,
    lng: 75.8850,
    areaLabel: 'Meharban',
    isDemo: true
  },
  {
    id: 'LM-2026-00425',
    name: 'Dugri Retail Depot',
    status: 'NON-COMPLIANT',
    lat: 30.8750,
    lng: 75.8450,
    areaLabel: 'Dugri',
    isDemo: true
  }
];
