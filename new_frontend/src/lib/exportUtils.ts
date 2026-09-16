import { ScanRecord } from '../shared/schema';

/**
 * Escapes a cell value for RFC 4180 compliant CSV output.
 */
function escapeCsv(val: any): string {
  if (val === null || val === undefined) return '""';
  const str = String(val).replace(/"/g, '""');
  return `"${str}"`;
}

/**
 * Generates and downloads a CSV export of the ScanRecord and its Rule 6 declaration clauses.
 */
export function exportScanToCsv(scanRecord: ScanRecord): void {
  const headers = [
    'STATUTORY_MEMO_NO',
    'INSPECTION_DATE_TIME',
    'OVERALL_VERDICT',
    'INSPECTOR_CADRE_ID',
    'ENFORCEMENT_DISTRICT',
    'GPS_COORDINATES',
    'COMMODITY_NAME',
    'COMMODITY_BRAND',
    'SCHEDULED_CATEGORY',
    'MANUFACTURER_PACKER',
    'NET_QUANTITY',
    'MAXIMUM_RETAIL_PRICE',
    'BATCH_NUMBER',
    'PACKING_OR_MFG_DATE',
    'BARCODE_DETECTED',
    'RULE_PROVISION',
    'STATUTORY_PARAMETER',
    'DECLARED_ON_LABEL',
    'LEGAL_METROLOGY_STANDARD',
    'COMPLIANCE_STATUS',
    'INSPECTOR_REMARK',
  ];

  const gpsCoord =
    scanRecord.gps?.lat != null
      ? `${scanRecord.gps.lat.toFixed(5)}, ${scanRecord.gps.lng.toFixed(5)}`
      : 'N/A';

  const declarations = scanRecord.declarations || [];
  const netQtyDecl = declarations.find((d) => d.field === 'net_quantity');
  const mrpDecl = declarations.find((d) => d.field === 'mrp');
  const dateDecl = declarations.find((d) => d.field === 'date_of_manufacture' || d.field === 'month_year_packing');
  const batchDecl = declarations.find((d) => d.field === 'batch_number');
  const barcodeDecl = declarations.find((d) => d.field === 'barcode');

  const rows: string[][] = [];

  const baseData = [
    scanRecord.report_no || 'N/A',
    scanRecord.date_scanned ? new Date(scanRecord.date_scanned).toISOString() : 'N/A',
    (scanRecord.overall_verdict || 'non_compliant').toUpperCase(),
    scanRecord.inspector_id || 'LMI-CADRE',
    scanRecord.district_id || 'ENFORCEMENT-CIRCLE',
    gpsCoord,
    scanRecord.product?.name || 'Packaged Commodity Under Audit',
    (scanRecord.product as any)?.brand || 'N/A',
    scanRecord.product?.category || 'General Packaged Commodity',
    scanRecord.product?.manufacturer || 'NOT DECLARED',
    netQtyDecl?.detected_value || 'NOT DECLARED',
    mrpDecl?.detected_value ? `INR ${mrpDecl.detected_value}` : 'NOT DECLARED',
    batchDecl?.detected_value || 'N/A',
    dateDecl?.detected_value || 'N/A',
    barcodeDecl?.detected_value || (scanRecord.product as any)?.barcode || 'NOT DECLARED',
  ];

  if (declarations.length > 0) {
    for (const d of declarations) {
      rows.push([
        ...baseData,
        d.rule_provision || 'Rule 6(1)',
        d.statutory_parameter || d.field.replace(/_/g, ' ').toUpperCase(),
        d.detected_value || '[NOT LOCATED / OMITTED]',
        d.legal_metrology_standard || d.mandated_value || 'Mandatory statutory declaration under Rule 6',
        d.status.toUpperCase(),
        d.remark || (d.status === 'pass' ? 'Verified compliant with Gazette mandate.' : 'Non-compliance logged. Sec 36 indicated.'),
      ]);
    }
  } else {
    rows.push([
      ...baseData,
      'N/A',
      'N/A',
      'N/A',
      'N/A',
      'NO_CLAUSES',
      'No declaration clauses evaluated.',
    ]);
  }

  // Prepend UTF-8 BOM so Excel on Windows/Mac parses special characters and commas properly
  const csvContent =
    '\uFEFF' +
    [
      headers.map(escapeCsv).join(','),
      ...rows.map((row) => row.map(escapeCsv).join(',')),
    ].join('\r\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  const safeFilename = (scanRecord.report_no || 'Audit_Report').replace(/[\/\\?%*:|"<>]/g, '_');
  link.download = `${safeFilename}_Compliance_Audit.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
