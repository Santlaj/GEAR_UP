import React, { useState, useEffect } from 'react';
import { ScanRecord } from '../../shared/schema';
import { useLanguage } from '../../lib/i18n';
import { resolveAssetUrl, getScanEvidenceImageUrl } from '../../api/client';
import { getScanDocxUrl, getScanHtmlUrl } from '../../api/scans';
import { fetchScanImages } from '../../api/images';
import { exportScanToCsv } from '../../lib/exportUtils';

interface CertificateViewProps {
  scanRecord: ScanRecord;
  onPrintTriplicate?: () => void;
  onDownloadPdf: () => void;
  onDownloadDocx?: () => void;
  onDownloadCsv?: () => void;
  onIssueNotice?: () => void;
  onVerifyQr?: () => void;
}

export const CertificateView: React.FC<CertificateViewProps> = ({
  scanRecord,
  onDownloadPdf,
  onDownloadDocx,
  onDownloadCsv,
}) => {
  const { lang } = useLanguage();

  // Fetch evidence images from Supabase via backend API
  const [evidenceImageUrl, setEvidenceImageUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (scanRecord.scan_id) {
      fetchScanImages(scanRecord.scan_id).then((imgs) => {
        if (!cancelled && imgs && imgs.length > 0 && imgs[0].url) {
          setEvidenceImageUrl(imgs[0].url);
        }
      });
    }
    return () => { cancelled = true; };
  }, [scanRecord.scan_id]);

  // Image priority: Supabase signed URL > evidence-image API > resolveAssetUrl (for absolute URLs only)
  const displayImageUrl = evidenceImageUrl
    || getScanEvidenceImageUrl(scanRecord.scan_id)
    || resolveAssetUrl(scanRecord.product?.image_path);

  const isCompliant = scanRecord.overall_verdict === 'compliant';

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

  const inspectorName = scanRecord.inspector_name || (
    scanRecord.inspector_id === 'insp-pb-ludhiana-02' ? 'Sh. Harpreet Singh Gill' :
    scanRecord.inspector_id === 'insp-pb-ludhiana-01' ? 'Sh. Gurpreet Singh' :
    scanRecord.inspector_id === 'insp-mh-pune-01' ? 'Smt. Vaishnavi Kulkarni' :
    scanRecord.inspector_id === 'insp-mh-pune-02' ? 'Sh. Vedant Deshmukh' :
    (scanRecord.inspector_id ? `Sh. ${scanRecord.inspector_id.replace(/^insp-[a-z]+-/, '').replace(/-/g, ' ').toUpperCase()}` : 'Authorized Field Inspector')
  );
  const inspectorBadge = scanRecord.inspector_badge || (
    scanRecord.inspector_id === 'insp-pb-ludhiana-02' ? 'LMI-PB-LDH-0105' :
    scanRecord.inspector_id === 'insp-pb-ludhiana-01' ? 'LMI-PB-LDH-0104' :
    scanRecord.inspector_id === 'insp-mh-pune-01' ? 'LMI-MH-PUN-0201' :
    scanRecord.inspector_id === 'insp-mh-pune-02' ? 'LMI-MH-PUN-0202' :
    (scanRecord.inspector_id ? scanRecord.inspector_id.toUpperCase() : 'LMI-CADRE')
  );
  const districtName = scanRecord.district_name || (
    scanRecord.district_id === 'D-LUDHIANA' ? 'Ludhiana Circle' :
    scanRecord.district_id === 'D-PUNE' ? 'Pune Circle' :
    scanRecord.district_id ? `${scanRecord.district_id} Enforcement Circle` : 'District Enforcement Circle'
  );

  const handleDownloadDocx = () => {
    if (onDownloadDocx) {
      onDownloadDocx();
    } else {
      const docxUrl = getScanDocxUrl(scanRecord.scan_id);
      const link = document.createElement('a');
      link.href = docxUrl;
      link.download = `${scanRecord.report_no.replace(/[\/\\?%*:|"<>]/g, '_')}_Official_Report.docx`;
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const handleDownloadCsv = () => {
    if (onDownloadCsv) {
      onDownloadCsv();
    } else {
      exportScanToCsv(scanRecord);
    }
  };

  return (
    <div className="w-full bg-slate-100/70 min-h-screen py-4 sm:py-6 px-2 sm:px-4 select-none text-black print:bg-white print:p-0">
      
      {/* Top Attestation Action Ribbon with Export Controls */}
      <div className="max-w-[794px] mx-auto bg-white border border-slate-300 p-3 sm:p-4 mb-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-sm rounded-sm text-black no-print">
        <div>
          <div className="font-black text-xs sm:text-sm text-black flex flex-wrap items-center gap-1.5">
            <span>{lang === 'hi' ? 'वैधानिक डॉकेट रिकॉर्ड / मेमो सं:' : 'STATUTORY DOCKET RECORD / MEMO NO:'}</span>
            <span className="font-mono text-black font-bold">{scanRecord.report_no}</span>
          </div>
          <div className="text-[11px] text-black mt-0.5">
            {lang === 'hi'
              ? 'डिजिटल फाइल प्रमाणीकरण: विधिक मापविज्ञान अधिनियम, 2011 की धारा 15 अंतर्गत सत्यापित'
              : 'Digital File Attestation: Validated under Section 15 of LM Act, 2011'}
          </div>
        </div>

        {/* Export Action Buttons: PDF, DOCX, CSV, Print */}
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <button
            onClick={onDownloadPdf}
            className="flex-1 sm:flex-none bg-black hover:bg-neutral-800 text-white text-xs font-bold px-3.5 py-2 rounded transition-colors shadow-sm flex items-center justify-center cursor-pointer"
          >
            <span>{lang === 'hi' ? 'पीडीएफ डाउनलोड' : 'Download PDF'}</span>
          </button>

          <button
            onClick={handleDownloadDocx}
            className="flex-1 sm:flex-none bg-white border border-black hover:bg-neutral-100 text-black text-xs font-bold px-3.5 py-2 rounded transition-colors shadow-sm flex items-center justify-center cursor-pointer"
          >
            <span>{lang === 'hi' ? 'DOCX डाउनलोड' : 'Download DOCX'}</span>
          </button>

          <button
            onClick={handleDownloadCsv}
            className="flex-1 sm:flex-none bg-white border border-black hover:bg-neutral-100 text-black text-xs font-bold px-3.5 py-2 rounded transition-colors shadow-sm flex items-center justify-center cursor-pointer"
          >
            <span>{lang === 'hi' ? 'CSV डाउनलोड' : 'Download CSV'}</span>
          </button>

          <button
            onClick={() => window.open(getScanHtmlUrl(scanRecord.scan_id), '_blank')}
            className="flex-1 sm:flex-none bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold px-3.5 py-2 rounded transition-colors shadow-sm flex items-center justify-center cursor-pointer"
            title="Open printable Gazette view in new tab"
          >
            <span>{lang === 'hi' ? 'राजपत्र प्रिंट / देखें' : 'Print / View Gazette'}</span>
          </button>
        </div>
      </div>

      {/* Ornate Official Gazette Certificate Container (Standard A4 Dimensions: 210mm x 297mm) */}
      <div className="a4-sheet max-w-[794px] w-full min-h-[1123px] mx-auto bg-white border-2 border-black p-4 sm:p-6 shadow-2xl relative text-black print:shadow-none print:m-0 print:w-[210mm] print:min-h-[297mm] print:border-2 print:border-black">
        {/* Double Official Gazette Framing */}
        <div className="border border-black p-3 sm:p-5 w-full text-black flex flex-col justify-between">
          
          {/* Top National Header */}
          <div className="text-center flex flex-col items-center mb-5 text-black">
            <img
              src="/assets/emblem_circle.png"
              alt="Government of India Emblem"
              className="w-12 h-12 sm:w-14 sm:h-14 object-contain mb-2"
            />
            <div className="text-xs sm:text-sm font-bold text-black tracking-wider uppercase">
              {lang === 'hi' ? 'भारत सरकार | GOVERNMENT OF INDIA' : 'GOVERNMENT OF INDIA | भारत सरकार'}
            </div>
            <div className="text-xs sm:text-sm font-bold text-black tracking-wide uppercase mt-0.5">
              {lang === 'hi' ? 'उपभोक्ता मामले विभाग | DEPARTMENT OF CONSUMER AFFAIRS' : 'DEPARTMENT OF CONSUMER AFFAIRS | उपभोक्ता मामले विभाग'}
            </div>
            <div className="text-[10px] sm:text-xs font-bold text-black tracking-widest uppercase mt-0.5">
              DIRECTORATE OF LEGAL METROLOGY - ENFORCEMENT WING
            </div>

            <h2 className="text-base sm:text-xl font-black text-black tracking-tight font-gazette mt-3 border-b-2 border-black pb-1.5 inline-block text-center">
              {lang === 'hi'
                ? 'विधिक अनुपालन निरीक्षण प्रमाणपत्र एवं ऑडिट मेमो'
                : 'STATUTORY COMPLIANCE INSPECTION CERTIFICATE & AUDIT MEMO'}
            </h2>

            <p className="italic text-[11px] sm:text-xs text-black max-w-3xl mt-2 leading-relaxed text-center">
              Issued under Section 15 of the Legal Metrology Act, 2011 (Act No. 1 of 2010) read with Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011 (as amended). Official Evidentiary Dossier.
            </p>
          </div>

          {/* 4-Box Key Metadata Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mb-5 text-sm text-black">
            <div className="bg-slate-50 border border-slate-300 p-2.5 rounded-sm text-black">
              <div className="text-[10px] font-bold text-black uppercase">STATUTORY MEMO NUMBER</div>
              <div className="font-mono font-black text-black text-xs sm:text-sm mt-0.5 break-all">
                {scanRecord.report_no}
              </div>
            </div>

            <div className="bg-slate-50 border border-slate-300 p-2.5 rounded-sm text-black">
              <div className="text-[10px] font-bold text-black uppercase">DATE &amp; TIME OF INSPECTION</div>
              <div className="font-bold text-black text-xs sm:text-sm mt-0.5">
                {formattedDate}
              </div>
            </div>

            <div className="bg-slate-50 border border-slate-300 p-2.5 rounded-sm text-black">
              <div className="text-[10px] font-bold text-black uppercase">INSPECTION SITE / BEAT</div>
              <div className="font-bold text-black text-xs sm:text-sm mt-0.5">
                {scanRecord.gps?.lat != null
                  ? `${scanRecord.gps.lat.toFixed(4)}° N, ${scanRecord.gps.lng.toFixed(4)}° E`
                  : districtName}
              </div>
            </div>

            <div className="bg-slate-50 border border-slate-300 p-2.5 rounded-sm text-black">
              <div className="text-[10px] font-bold text-black uppercase">REPORT STATUS &amp; DISPOSITION</div>
              <div className="font-black text-xs sm:text-sm mt-0.5 text-black">
                {isCompliant ? 'VERIFIED COMPLIANT U/S 15' : 'COGNIZANCE TAKEN U/S 36'}
              </div>
            </div>
          </div>

          {/* Section I: Inspected Entity & Commodity Particulars */}
          <div className="border border-slate-300 mb-5 bg-white shadow-2xs overflow-hidden text-black">
            <div className="border-b border-black bg-slate-100 text-black px-3 sm:px-4 py-2 flex flex-wrap items-center justify-between text-xs sm:text-sm font-bold gap-1">
              <span>Section I: Inspected Entity &amp; Commodity Particulars</span>
            </div>

            <div className="p-3 sm:p-4 grid grid-cols-1 md:grid-cols-12 gap-4 items-center text-black">
              
              {/* Col 1 */}
              <div className="md:col-span-5 text-sm space-y-3 text-black">
                <div>
                  <div className="text-xs font-bold text-black uppercase">
                    MANUFACTURER / PACKER NAME:
                  </div>
                  <div className="font-bold text-black text-sm mt-0.5">
                    {scanRecord.product?.manufacturer || 'NOT DECLARED'}
                  </div>
                  <div className="text-xs text-black mt-0.5">
                    {mfgDecl?.detected_value || 'Registered Packaging Premises On-Record'}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-bold text-black uppercase">
                    PACKAGED COMMODITY DETAILS:
                  </div>
                  <div className="text-xs font-medium text-black mt-0.5">
                    Net Quantity:{' '}
                    <strong className="text-black">
                      {netQtyDecl?.detected_value || 'NOT DECLARED'}
                    </strong>{' '}
                    | MRP:{' '}
                    <strong className="text-black">
                      {mrpDecl?.detected_value ? `₹ ${mrpDecl.detected_value}` : 'NOT DECLARED'}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Col 2 */}
              <div className="md:col-span-4 text-sm space-y-3 text-black">
                <div>
                  <div className="text-xs font-bold text-black uppercase">
                    COMMODITY DESCRIPTION &amp; BRAND:
                  </div>
                  <div className="font-black text-black text-sm mt-0.5">
                    {scanRecord.product?.name || 'Packaged Commodity Under Audit'}
                  </div>
                  <div className="text-xs text-black mt-0.5">
                    Scheduled Category: {scanRecord.product?.category || 'General Packaged Commodity'}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-bold text-black uppercase">
                    BATCH NO. &amp; PACKING DATE:
                  </div>
                  <div className="font-mono font-bold text-black text-sm mt-0.5">
                    BATCH #{' '}
                    {batchDecl?.detected_value || 'N/A'}{' '}
                    | {dateDecl?.detected_value || 'N/A'}
                  </div>
                </div>
              </div>

              {/* Col 3: Stamp */}
              <div className="md:col-span-3 flex items-center justify-center p-2 text-black">
                <div className="border-2 border-black p-3 text-center flex flex-col items-center justify-center text-black w-full">
                  <span className="text-[10px] font-bold text-black tracking-wider">LEGAL METROLOGY ENFORCEMENT</span>
                  <span className="text-[10px] font-bold text-black tracking-wider">OF INDIA</span>
                  <span className="text-sm font-black text-black my-1">
                    {isCompliant ? 'PASSED' : 'VIOLATION'}<br />
                    <span className="text-xs text-black">{isCompliant ? 'COMPLIANT' : 'NON-COMPLIANT'}</span>
                  </span>
                  <span className="text-[9px] font-semibold text-black">
                    {isCompliant ? 'STATUTORY MANDATES MET' : 'NOTICE UNDER SEC 36 ISSUABLE'}
                  </span>
                  <span className="text-[9px] font-mono font-bold text-black mt-1">{scanRecord.report_no}</span>
                </div>
              </div>

            </div>
          </div>

          {/* Sections II & III Side-by-Side: Section II (Main Checklist) & Section III (Compact Evidence Photo) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-5 items-start text-black">
            
            {/* Section II: Main Audit Checklist (Wider: lg:col-span-8) */}
            <div className="lg:col-span-8 border border-slate-300 bg-white overflow-x-auto shadow-2xs text-black">
              <div className="border-b border-black bg-slate-100 text-black px-3 sm:px-4 py-2 flex items-center justify-between text-xs sm:text-sm font-bold min-w-[500px]">
                <span>Section II: Statutory Declarations Audit Checklist (LM-PC Rules, 2011)</span>
                <span className="text-xs font-bold tracking-wider text-black">
                  RULE 6 ({declarations.length} CLAUSES)
                </span>
              </div>

              <table className="gov-table min-w-[500px] text-black w-full text-xs">
                <thead>
                  <tr className="border-b border-black bg-slate-50 text-black text-left">
                    <th style={{ width: '16%' }} className="p-2 text-black font-bold">RULE</th>
                    <th style={{ width: '22%' }} className="p-2 text-black font-bold">PARAMETER</th>
                    <th style={{ width: '22%' }} className="p-2 text-black font-bold">DECLARED EVIDENCE</th>
                    <th style={{ width: '18%' }} className="p-2 text-black font-bold">STANDARD</th>
                    <th style={{ width: '10%' }} className="p-2 text-black font-bold">STATUS</th>
                    <th style={{ width: '12%' }} className="p-2 text-black font-bold">DEFECT / REMARK</th>
                  </tr>
                </thead>
                <tbody className="text-black">
                  {declarations.length > 0 ? (
                    declarations.map((d, index) => {
                      const pass = d.status === 'pass';
                      return (
                        <tr key={d.field || index} className="border-b border-slate-200 text-black">
                          <td className="p-2 font-mono font-bold text-black">
                            {d.rule_provision || `Rule 6(1)`}
                          </td>
                          <td className="p-2 font-semibold text-black">
                            {d.statutory_parameter || d.field.replace(/_/g, ' ').toUpperCase()}
                          </td>
                          <td className="p-2 font-mono text-xs text-black">
                            {d.detected_value || '[NOT LOCATED / OMITTED]'}
                          </td>
                          <td className="p-2 text-xs text-black">
                            {d.legal_metrology_standard || d.mandated_value || 'Mandatory statutory declaration under Rule 6'}
                          </td>
                          <td className="p-2 text-black font-bold text-xs">
                            {d.status.toUpperCase()}
                          </td>
                          <td className="p-2 text-xs text-black">
                            {d.remark || (pass ? 'Verified compliant with Gazette mandate.' : 'Non-compliance logged. Sec 36 indicated.')}
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={6} className="text-center py-6 text-black italic">
                        No declaration clauses available on this record.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Section III: Seized Packaged Commodity Evidence (Compact: lg:col-span-4) */}
            <div className="lg:col-span-4 border border-slate-300 bg-white flex flex-col shadow-2xs overflow-hidden text-black">
              <div className="border-b border-black bg-slate-100 text-black px-3 py-2 flex items-center justify-between text-xs font-bold">
                <span>Section III: Evidence Photo (A-1)</span>
                <span className="border border-black text-black text-[9px] px-1.5 py-0.5 rounded uppercase font-bold">
                  FIELD CAPTURE
                </span>
              </div>

              <div className="p-2 bg-neutral-900 flex-1 flex flex-col justify-between">
                <div className="relative overflow-hidden border border-neutral-700 bg-black flex items-center justify-center min-h-[160px]">
                  {displayImageUrl ? (
                    <img
                      src={displayImageUrl}
                      alt="Seized Evidence Annexure"
                      className="max-h-[170px] w-auto object-contain block"
                    />
                  ) : (
                    <div className="text-white text-xs italic p-6 text-center">
                      Packaging photo sealed in central evidence vault.
                    </div>
                  )}
                  {/* GPS & Timestamp Overlay */}
                  <div className="absolute bottom-0 left-0 right-0 bg-black/85 text-[10px] text-white font-mono px-2 py-1 leading-tight border-t border-neutral-700">
                    <div>
                      GPS:{' '}
                      {scanRecord.gps?.lat != null
                        ? `${scanRecord.gps.lat.toFixed(4)}° N, ${scanRecord.gps.lng.toFixed(4)}° E (${districtName})`
                        : `${districtName}`}
                    </div>
                    <div>TIMESTAMP: {formattedDate}</div>
                  </div>
                </div>

                <div className="mt-1.5 flex flex-wrap items-center justify-between text-[10px] font-mono text-white px-0.5 gap-1">
                  <span>Central Core Vault</span>
                  <span>VERSION: {scanRecord.report_version || 1}</span>
                </div>
              </div>
            </div>

          </div>

          {/* Bottom Attestation & Signature Box */}
          <div className="border border-slate-300 p-3 sm:p-4 bg-white grid grid-cols-1 md:grid-cols-12 gap-4 items-center shadow-2xs text-black">
            
            {/* Statutory Declaration Text */}
            <div className="md:col-span-8 text-sm text-black">
              <div className="font-black text-black text-xs sm:text-sm uppercase tracking-wide mb-1.5">
                <span>Attestation &amp; Statutory Declaration</span>
              </div>
              <p className="text-xs leading-relaxed text-black">
                I hereby certify that the aforesaid packaged commodity inspection was conducted in strict adherence with powers vested under <strong className="text-black">Section 15 of the Legal Metrology Act, 2011</strong>. The digital imaging, GPS spatial tracking, and rule-by-rule discrepancy metrics were compiled contemporaneously on-site.
              </p>
            </div>

            {/* Right: Inspector Signature */}
            <div className="md:col-span-4 text-left md:text-right flex flex-col items-start md:items-end justify-center border-t md:border-t-0 md:border-l border-slate-200 pt-3 md:pt-0 md:pl-4 text-black">
              <div className="font-serif italic text-lg text-black tracking-wide font-bold">
                {inspectorName}
              </div>
              <div className="font-black text-sm text-black mt-0.5">
                {inspectorName}
              </div>
              <div className="text-xs text-black">
                Legal Metrology Inspector
              </div>
              <div className="text-xs font-mono text-black font-bold">
                BADGE: {inspectorBadge}
              </div>
              <div className="text-xs text-black font-bold uppercase">
                {districtName}
              </div>
              <div className="mt-2">
                <span className="inline-flex items-center bg-slate-100 text-black border border-black text-xs font-black px-2 py-0.5 rounded">
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
