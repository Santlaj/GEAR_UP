import React, { useState, useEffect } from 'react';
import { ScanRecord } from '../../shared/schema';
import { useLanguage } from '../../lib/i18n';

interface CertificateViewProps {
  scanRecord: ScanRecord;
  onPrintTriplicate: () => void;
  onDownloadPdf: () => void;
  onIssueNotice: () => void;
  onVerifyQr: () => void;
}

export const CertificateView: React.FC<CertificateViewProps> = ({
  scanRecord,
  onPrintTriplicate,
  onDownloadPdf,
  onIssueNotice,
  onVerifyQr,
}) => {
  const { t, lang } = useLanguage();
  const qrVerificationUrl =
    scanRecord.qr_payload ||
    `https://consumeraffairs.nic.in/verify?docket=${encodeURIComponent(scanRecord.report_no)}&hash=${encodeURIComponent(scanRecord.report_hash)}`;

  const isCompliant = scanRecord.overall_verdict === 'compliant';
  const isDeficient = !isCompliant;

  const formattedDate = (() => {
    try {
      const d = new Date(scanRecord.date_scanned);
      return !isNaN(d.getTime())
        ? d.toLocaleString('en-IN', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
          }) + ' IST'
        : String(scanRecord.date_scanned);
    } catch {
      return String(scanRecord.date_scanned);
    }
  })();

  const declarations = scanRecord.declarations || [];
  const mfgDecl = declarations.find((d) => d.field === 'manufacturer_address' || d.field === 'manufacturer_name');
  const netQtyDecl = declarations.find((d) => d.field === 'net_quantity');
  const mrpDecl = declarations.find((d) => d.field === 'mrp');
  const dateDecl = declarations.find((d) => d.field === 'date_of_manufacture' || d.field === 'month_year_packing');
  const batchDecl = declarations.find((d) => d.field === 'batch_number');
  const barcodeVal = declarations.find((d) => d.field === 'barcode')?.detected_value || (scanRecord.product as any)?.barcode || 'NOT DECLARED';

  const nonCompliantDecls = declarations.filter((d) => d.status !== 'pass');
  const inspectorName = scanRecord.inspector_id ? `Insp. ${scanRecord.inspector_id.toUpperCase()}` : 'Authorized Field Inspector';
  const inspectorBadge = scanRecord.inspector_id ? scanRecord.inspector_id.toUpperCase() : 'LMI-CADRE';
  const districtName = scanRecord.district_id ? `${scanRecord.district_id} Enforcement Circle` : 'District Enforcement Circle';

  return (
    <div className="w-full px-2 sm:px-6 py-3 sm:py-4 select-none">
      
      {/* Top Attestation Action Ribbon - Responsive Wrap */}
      <div className="bg-white border border-slate-300 p-3 sm:p-4 mb-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-sm rounded-sm">
        
        <div className="flex items-center gap-3">
          <div
            className={`w-8 h-8 rounded-full border flex items-center justify-center font-bold text-base shrink-0 ${
              isCompliant
                ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                : 'bg-red-100 border-red-300 text-red-700'
            }`}
          >
            {isCompliant ? '✔' : '⚖'}
          </div>
          <div>
            <div className="font-black text-xs sm:text-sm text-slate-900 flex flex-wrap items-center gap-1.5">
              <span>{lang === 'hi' ? 'वैधानिक डॉकेट रिकॉर्ड / मेमो सं:' : 'STATUTORY DOCKET RECORD / MEMO NO:'}</span>
              <span className="font-mono text-slate-900 font-bold">{scanRecord.report_no}</span>
            </div>
            <div className="text-[11px] text-slate-600 mt-0.5">
              {lang === 'hi'
                ? 'डिजिटल फाइल प्रमाणीकरण: विधिक मापविज्ञान अधिनियम, 2011 की धारा 15 अंतर्गत सत्यापित'
                : 'Digital File Attestation: Validated under Section 15 of LM Act, 2011'}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <button
            onClick={onPrintTriplicate}
            className="flex-1 sm:flex-none bg-white border border-slate-300 hover:bg-slate-50 text-slate-800 text-xs font-bold px-3.5 py-2 rounded transition-colors shadow-sm flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <span>🖨️</span>
            <span>{lang === 'hi' ? 'ट्रिप्लिकेट मेमो प्रिंट' : 'Print Triplicate Memo'}</span>
          </button>

          <button
            onClick={onDownloadPdf}
            className="flex-1 sm:flex-none bg-[#0f2744] hover:bg-[#1a385c] text-white text-xs font-bold px-3.5 py-2 rounded transition-colors shadow-sm flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <span>📥</span>
            <span>{lang === 'hi' ? 'पीडीएफ डाउनलोड करें' : 'Download Gazette PDF'}</span>
          </button>

          {isDeficient && (
            <button
              onClick={onIssueNotice}
              className="w-full sm:w-auto bg-red-700 hover:bg-red-800 text-white text-xs font-bold px-3.5 py-2 rounded transition-colors shadow-sm flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <span>⚡</span>
              <span>{lang === 'hi' ? 'धारा 36 अंतर्गत नोटिस (₹25,000)' : 'Issue Notice U/S 36 (₹25,000)'}</span>
            </button>
          )}
        </div>

      </div>

      {/* Ornate Official Gazette Certificate Container */}
      <div className="gazette-outer-border w-full">
        {/* Four Traditional Filigree Corner Accents */}
        <div className="gazette-corner gazette-corner-tl"></div>
        <div className="gazette-corner gazette-corner-tr"></div>
        <div className="gazette-corner gazette-corner-bl"></div>
        <div className="gazette-corner gazette-corner-br"></div>

        <div className="gazette-inner-border w-full">
          
          {/* Top National Header */}
          <div className="text-center flex flex-col items-center mb-5">
            <img
              src="/assets/emblem_circle.png"
              alt="Government of India Emblem"
              className="w-12 h-12 sm:w-14 sm:h-14 object-contain mb-2"
            />
            <div className="text-xs sm:text-sm font-bold text-slate-900 tracking-wider uppercase">
              {lang === 'hi' ? 'भारत सरकार | GOVERNMENT OF INDIA' : 'GOVERNMENT OF INDIA | भारत सरकार'}
            </div>
            <div className="text-xs sm:text-sm font-bold text-slate-800 tracking-wide uppercase mt-0.5">
              {lang === 'hi' ? 'उपभोक्ता मामले विभाग | DEPARTMENT OF CONSUMER AFFAIRS' : 'DEPARTMENT OF CONSUMER AFFAIRS | उपभोक्ता मामले विभाग'}
            </div>
            <div className="text-[10px] sm:text-xs font-bold text-slate-600 tracking-widest uppercase mt-0.5">
              DIRECTORATE OF LEGAL METROLOGY - ENFORCEMENT WING
            </div>

            <h2 className="text-base sm:text-xl font-black text-[#0f2744] tracking-tight font-gazette mt-3 border-b-2 border-[#0f2744] pb-1.5 inline-block text-center">
              {lang === 'hi'
                ? 'विधिक अनुपालन निरीक्षण प्रमाणपत्र एवं ऑडिट मेमो'
                : 'STATUTORY COMPLIANCE INSPECTION CERTIFICATE & AUDIT MEMO'}
            </h2>

            <p className="italic text-[11px] sm:text-xs text-slate-700 max-w-3xl mt-2 leading-relaxed text-center">
              Issued under Section 15 of the Legal Metrology Act, 2011 (Act No. 1 of 2010) read with Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011 (as amended). Official Evidentiary Dossier.
            </p>
          </div>

          {/* 4-Box Key Metadata Grid - Mobile Responsive */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mb-5 text-sm">
            <div className="bg-[#ebf3fb] border border-blue-200 p-2.5 rounded-sm">
              <div className="text-[10px] font-bold text-slate-600 uppercase">STATUTORY MEMO NUMBER</div>
              <div className="font-mono font-black text-slate-900 text-xs sm:text-sm mt-0.5 break-all">
                {scanRecord.report_no}
              </div>
            </div>

            <div className="bg-[#ebf3fb] border border-blue-200 p-2.5 rounded-sm">
              <div className="text-[10px] font-bold text-slate-600 uppercase">DATE &amp; TIME OF INSPECTION</div>
              <div className="font-bold text-slate-900 text-xs sm:text-sm mt-0.5">
                {formattedDate}
              </div>
            </div>

            <div className="bg-[#ebf3fb] border border-blue-200 p-2.5 rounded-sm">
              <div className="text-[10px] font-bold text-slate-600 uppercase">INSPECTION SITE / BEAT</div>
              <div className="font-bold text-slate-900 text-xs sm:text-sm mt-0.5">
                {scanRecord.gps?.lat != null
                  ? `${scanRecord.gps.lat.toFixed(4)}° N, ${scanRecord.gps.lng.toFixed(4)}° E`
                  : districtName}
              </div>
            </div>

            <div className="bg-[#ebf3fb] border border-blue-200 p-2.5 rounded-sm">
              <div className="text-[10px] font-bold text-slate-600 uppercase">REPORT STATUS &amp; DISPOSITION</div>
              <div
                className={`font-black text-xs sm:text-sm mt-0.5 ${
                  isCompliant ? 'text-emerald-700' : 'text-red-700'
                }`}
              >
                {isCompliant ? 'VERIFIED COMPLIANT U/S 15' : 'COGNIZANCE TAKEN U/S 36'}
              </div>
            </div>
          </div>

          {/* Section I: Inspected Entity & Commodity Particulars */}
          <div className="border border-slate-300 mb-5 bg-white shadow-2xs overflow-hidden">
            <div className="bg-[#0f2744] text-white px-3 sm:px-4 py-2 flex flex-wrap items-center justify-between text-xs sm:text-sm font-bold gap-1">
              <span>Section I: Inspected Entity &amp; Commodity Particulars</span>
              <span className="font-mono text-xs text-amber-300">BARCODE: {barcodeVal}</span>
            </div>

            <div className="p-3 sm:p-4 grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
              
              {/* Col 1 */}
              <div className="md:col-span-5 text-sm space-y-3">
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase">
                    MANUFACTURER / PACKER NAME:
                  </div>
                  <div className="font-bold text-slate-900 text-sm mt-0.5">
                    {scanRecord.product?.manufacturer || 'NOT DECLARED'}
                  </div>
                  <div className="text-xs text-slate-600 mt-0.5">
                    {mfgDecl?.detected_value || 'Registered Packaging Premises On-Record'}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase">
                    PACKAGED COMMODITY DETAILS:
                  </div>
                  <div className="text-xs font-medium text-slate-800 mt-0.5">
                    Net Quantity:{' '}
                    <strong className="text-slate-900">
                      {netQtyDecl?.detected_value || 'NOT DECLARED'}
                    </strong>{' '}
                    | MRP:{' '}
                    <strong className="text-slate-900">
                      {mrpDecl?.detected_value ? `₹ ${mrpDecl.detected_value}` : 'NOT DECLARED'}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Col 2 */}
              <div className="md:col-span-4 text-sm space-y-3">
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase">
                    COMMODITY DESCRIPTION &amp; BRAND:
                  </div>
                  <div className="font-black text-slate-900 text-sm mt-0.5">
                    {scanRecord.product?.name || 'Packaged Commodity Under Audit'}
                  </div>
                  <div className="text-xs text-slate-600 mt-0.5">
                    Scheduled Category: {scanRecord.product?.category || 'General Packaged Commodity'}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase">
                    BATCH NO. &amp; PACKING DATE:
                  </div>
                  <div className="font-mono font-bold text-slate-900 text-sm mt-0.5">
                    BATCH #{' '}
                    {batchDecl?.detected_value || 'N/A'}{' '}
                    | {dateDecl?.detected_value || 'N/A'}
                  </div>
                </div>
              </div>

              {/* Col 3: Rubber Stamp */}
              <div className="md:col-span-3 flex items-center justify-center p-2">
                <div className={isCompliant ? 'compliant-rubber-stamp' : 'violation-rubber-stamp'}>
                  <span className="stamp-sub">LEGAL METROLOGY ENFORCEMENT</span>
                  <span className="stamp-sub">OF INDIA</span>
                  <div className="text-sm my-0.5">⚖</div>
                  <span className="stamp-main">
                    {isCompliant ? 'PASSED' : 'VIOLATION'}<br />
                    <span className="text-xs">{isCompliant ? 'COMPLIANT' : 'NON-COMPLIANT'}</span>
                  </span>
                  <span className="stamp-sub">
                    {isCompliant ? 'STATUTORY MANDATES MET' : 'NOTICE UNDER SEC 36 ISSUABLE'}
                  </span>
                  <span className="stamp-ref">{scanRecord.report_no}</span>
                </div>
              </div>

            </div>
          </div>

          {/* Section II: Statutory Declarations Audit Checklist (LM-PC Rules, 2011) */}
          <div className="border border-slate-300 mb-5 bg-white overflow-x-auto shadow-2xs">
            <div className="bg-[#0f2744] text-white px-3 sm:px-4 py-2 flex items-center justify-between text-xs sm:text-sm font-bold min-w-[680px]">
              <span>Section II: Statutory Declarations Audit Checklist (LM-PC Rules, 2011)</span>
              <span className="text-xs font-bold tracking-wider text-slate-200">
                MANDATORY DECLARATIONS RULE 6 ({declarations.length} CLAUSES)
              </span>
            </div>

            <table className="gov-table min-w-[680px]">
              <thead>
                <tr>
                  <th style={{ width: '14%' }}>RULE PROVISION</th>
                  <th style={{ width: '22%' }}>STATUTORY PARAMETER</th>
                  <th style={{ width: '20%' }}>DECLARED ON LABEL EVIDENCE</th>
                  <th style={{ width: '20%' }}>LEGAL METROLOGY STANDARD</th>
                  <th style={{ width: '12%' }}>STATUS</th>
                  <th style={{ width: '12%' }}>DEFECT / REMARK</th>
                </tr>
              </thead>
              <tbody>
                {declarations.length > 0 ? (
                  declarations.map((d, index) => {
                    const pass = d.status === 'pass';
                    const fail =
                      d.status === 'fail' ||
                      d.status === 'missing' ||
                      d.status === 'confirmed_missing' ||
                      d.status === 'below_min';
                    return (
                      <tr key={d.field || index}>
                        <td className="font-mono font-bold text-slate-900">
                          {d.rule_provision || `Rule 6(1)`}
                        </td>
                        <td className="font-semibold text-slate-800">
                          {d.statutory_parameter || d.field.replace(/_/g, ' ').toUpperCase()}
                        </td>
                        <td className="font-mono text-xs">
                          {d.detected_value || (
                            <span className="text-red-700 font-bold">[NOT LOCATED / OMITTED]</span>
                          )}
                        </td>
                        <td className="text-xs text-slate-600">
                          {d.legal_metrology_standard || d.mandated_value || 'Mandatory statutory declaration under Rule 6'}
                        </td>
                        <td>
                          <span
                            className={
                              pass
                                ? 'badge-compliant'
                                : fail
                                ? 'badge-non-compliant'
                                : 'badge-review'
                            }
                          >
                            {d.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="text-xs text-slate-600">
                          {d.remark || (pass ? 'Verified compliant with Gazette mandate.' : 'Non-compliance logged. Sec 36 indicated.')}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={6} className="text-center py-6 text-slate-500 italic">
                      No declaration clauses available on this record.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Section III: Seized Packaged Commodity Evidence */}
          <div className="mb-5">
            <div className="border border-slate-300 bg-white flex flex-col shadow-2xs overflow-hidden">
              <div className="bg-[#0f2744] text-white px-3 sm:px-4 py-2 flex items-center justify-between text-xs sm:text-sm font-bold">
                <span>Section III: Packaged Commodity Evidence (Photo Annexure A-1)</span>
                <span className="bg-slate-700 text-white text-[10px] px-2 py-0.5 rounded uppercase">
                  FIELD CAPTURE
                </span>
              </div>

              <div className="p-3 bg-slate-900 flex-1 flex flex-col justify-between">
                <div className="relative overflow-hidden border border-slate-700 bg-black flex items-center justify-center min-h-[180px]">
                  {evidenceUrl || scanRecord.product?.image_path ? (
                    <img
                      src={
                        evidenceUrl ||
                        (scanRecord.product.image_path.startsWith('captures/')
                          ? resolveAssetUrl(scanRecord.product.image_path) || scanRecord.product.image_path
                          : scanRecord.product.image_path.startsWith('http') || scanRecord.product.image_path.startsWith('/') || scanRecord.product.image_path.startsWith('data:')
                            ? scanRecord.product.image_path
                            : scanRecord.product.image_path)
                      }
                      alt="Seized Evidence Annexure"
                      className="max-h-[220px] w-auto object-contain block"
                    />
                  ) : (
                    <div className="text-slate-500 text-xs italic p-8 text-center">
                      Packaging photo sealed in central evidence vault.
                    </div>
                  )}
                  {/* GPS & Timestamp Overlay */}
                  <div className="absolute bottom-0 left-0 right-0 bg-black/85 text-[11px] text-emerald-400 font-mono px-3 py-1.5 leading-tight border-t border-slate-700">
                    <div>
                      GPS:{' '}
                      {scanRecord.gps?.lat != null
                        ? `${scanRecord.gps.lat.toFixed(4)}° N, ${scanRecord.gps.lng.toFixed(4)}° E (${districtName})`
                        : `${districtName}`}
                    </div>
                    <div className="text-slate-300">TIMESTAMP: {formattedDate}</div>
                  </div>
                </div>

                <div className="mt-2 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 px-1 gap-1">
                  <span>Evidentiary Engine: Central Compliance Core</span>
                  <span>VERSION: {scanRecord.report_version || 1}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Attestation & Signature Box */}
          <div className="border border-slate-300 p-3 sm:p-4 bg-white grid grid-cols-1 md:grid-cols-12 gap-4 items-center shadow-2xs">
            
            {/* Statutory Declaration Text */}
            <div className="md:col-span-8 text-sm text-slate-700">
              <div className="font-black text-[#0f2744] text-xs sm:text-sm uppercase tracking-wide mb-1.5 flex items-center gap-2">
                <span>⚖</span>
                <span>Attestation &amp; Statutory Declaration</span>
              </div>
              <p className="text-xs leading-relaxed text-slate-600">
                I hereby certify that the aforesaid packaged commodity inspection was conducted in strict adherence with powers vested under <strong className="text-slate-900">Section 15 of the Legal Metrology Act, 2011</strong>. The digital imaging, GPS spatial tracking, and rule-by-rule discrepancy metrics were compiled contemporaneously on-site.
              </p>
            </div>

            {/* Right: Inspector Signature */}
            <div className="md:col-span-4 text-left md:text-right flex flex-col items-start md:items-end justify-center border-t md:border-t-0 md:border-l border-slate-200 pt-3 md:pt-0 md:pl-4">
              <div className="font-serif italic text-lg text-[#0f2744] tracking-wide font-bold">
                {inspectorName}
              </div>
              <div className="font-black text-sm text-slate-900 mt-0.5">
                {inspectorName}
              </div>
              <div className="text-xs text-slate-600">
                Legal Metrology Inspector
              </div>
              <div className="text-xs font-mono text-slate-700 font-bold">
                BADGE: {inspectorBadge}
              </div>
              <div className="text-xs text-slate-500 font-bold uppercase">
                {districtName}
              </div>
              <div className="mt-2">
                <span className="inline-flex items-center gap-1.5 bg-emerald-100 text-emerald-800 border border-emerald-300 text-xs font-black px-2 py-0.5 rounded">
                  <span>✔</span>
                  <span>E-SIGN AADHAAR VALIDATED</span>
                </span>
              </div>
            </div>

          </div>

        </div>
      </div>

    </div>
  );
};
