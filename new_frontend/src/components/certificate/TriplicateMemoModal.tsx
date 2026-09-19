import React, { useState } from 'react';
import { ScanRecord } from '../../shared/schema';

interface TriplicateMemoModalProps {
  scanRecord: ScanRecord;
  onClose: () => void;
}

export const TriplicateMemoModal: React.FC<TriplicateMemoModalProps> = ({ scanRecord, onClose }) => {
  const [activeCopy, setActiveCopy] = useState<'white' | 'pink' | 'yellow'>('white');

  const handlePrint = () => {
    window.print();
  };

  const formattedDate = (() => {
    try {
      const d = new Date(scanRecord.date_scanned);
      return !isNaN(d.getTime())
        ? d.toLocaleDateString('en-IN', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
          })
        : String(scanRecord.date_scanned);
    } catch {
      return String(scanRecord.date_scanned);
    }
  })();

  const declarations = scanRecord.declarations || [];
  const batchDecl = declarations.find((d) => d.field === 'batch_number');
  const netQtyDecl = declarations.find((d) => d.field === 'net_quantity');
  const nonCompliantDecls = declarations.filter((d) => d.status !== 'pass');
  const isCompliant = scanRecord.overall_verdict === 'compliant';

  const inspectorTitle = scanRecord.inspector_name || (
    scanRecord.inspector_id === 'insp-pb-ludhiana-02' ? 'Sh. Harpreet Singh Gill' :
    scanRecord.inspector_id === 'insp-pb-ludhiana-01' ? 'Sh. Gurpreet Singh' :
    scanRecord.inspector_id === 'insp-mh-pune-01' ? 'Smt. Vaishnavi Kulkarni' :
    scanRecord.inspector_id === 'insp-mh-pune-02' ? 'Sh. Vedant Deshmukh' :
    (scanRecord.inspector_id ? `Sh. ${scanRecord.inspector_id.replace(/^insp-[a-z]+-/, '').replace(/-/g, ' ').toUpperCase()}` : 'Authorized Legal Metrology Inspector')
  );
  const inspectorBadge = scanRecord.inspector_badge || (
    scanRecord.inspector_id === 'insp-pb-ludhiana-02' ? 'LMI-PB-LDH-0105' :
    scanRecord.inspector_id === 'insp-pb-ludhiana-01' ? 'LMI-PB-LDH-0104' :
    scanRecord.inspector_id === 'insp-mh-pune-01' ? 'LMI-MH-PUN-0201' :
    scanRecord.inspector_id === 'insp-mh-pune-02' ? 'LMI-MH-PUN-0202' :
    (scanRecord.inspector_id ? scanRecord.inspector_id.toUpperCase() : 'LMI-CADRE')
  );
  const circleName = scanRecord.district_name || (
    scanRecord.district_id === 'D-LUDHIANA' ? 'Ludhiana Circle' :
    scanRecord.district_id === 'D-PUNE' ? 'Pune Circle' :
    scanRecord.district_id ? `${scanRecord.district_id} Enforcement Circle` : 'District Enforcement Circle'
  );
  const stateAuthority = scanRecord.state_id
    ? `GOVERNMENT OF ${scanRecord.state_id.toUpperCase()} • DIRECTORATE OF LEGAL METROLOGY`
    : 'GOVERNMENT OF INDIA • DIRECTORATE OF LEGAL METROLOGY';

  const inspectionPlace = `${circleName}${
    scanRecord.gps?.lat != null ? ` (${scanRecord.gps.lat.toFixed(4)}° N, ${scanRecord.gps.lng.toFixed(4)}° E)` : ''
  }`;

  const commodityBatch = `${scanRecord.product?.name || 'Packaged Commodity'}${
    netQtyDecl?.detected_value ? ` ${netQtyDecl.detected_value}` : ''
  } (Batch: ${batchDecl?.detected_value || 'STANDARD LOT'})`;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white border border-slate-300 w-full max-w-3xl rounded shadow-2xl my-8 overflow-hidden select-none">
        
        {/* Modal Header */}
        <div className="bg-[#0f2744] text-white px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-bold text-xs">
              OFFICIAL FORM-V TRIPLICATE INSPECTION MEMO (ACT 1 OF 2010)
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Copy Selector */}
            <div className="flex items-center gap-1 bg-slate-800 p-1 rounded text-xs">
              <button
                onClick={() => setActiveCopy('white')}
                className={`px-2 py-0.5 rounded font-bold ${
                  activeCopy === 'white' ? 'bg-white text-slate-900' : 'text-slate-300 hover:text-white'
                }`}
              >
                ORIGINAL (Court)
              </button>
              <button
                onClick={() => setActiveCopy('pink')}
                className={`px-2 py-0.5 rounded font-bold ${
                  activeCopy === 'pink' ? 'bg-pink-200 text-pink-950' : 'text-slate-300 hover:text-white'
                }`}
              >
                DUPLICATE (Packer)
              </button>
              <button
                onClick={() => setActiveCopy('yellow')}
                className={`px-2 py-0.5 rounded font-bold ${
                  activeCopy === 'yellow' ? 'bg-amber-200 text-amber-950' : 'text-slate-300 hover:text-white'
                }`}
              >
                TRIPLICATE (Archive)
              </button>
            </div>

            <button
              onClick={onClose}
              className="text-slate-300 hover:text-white text-base font-bold ml-2 px-2"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Body: Styled as official paper memo */}
        <div
          className={`p-6 border-4 text-xs ${
            activeCopy === 'pink'
              ? 'bg-pink-50 border-pink-300'
              : activeCopy === 'yellow'
              ? 'bg-amber-50 border-amber-300'
              : 'bg-white border-slate-400'
          }`}
        >
          <div className="text-center pb-3 border-b-2 border-slate-900">
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-600">
              {activeCopy === 'white'
                ? 'ORIGINAL COPY: COURT OF ADJUDICATING OFFICER'
                : activeCopy === 'pink'
                ? 'DUPLICATE COPY: TO BE SERVED UPON PACKER / DEALER'
                : 'TRIPLICATE COPY: PRESERVED IN RECORD ARCHIVE'}
            </div>
            <div className="text-xs font-bold uppercase mt-1">
              {stateAuthority}
            </div>
            <div className="text-sm font-black uppercase tracking-tight mt-0.5">
              INSPECTION &amp; SEIZURE MEMO UNDER SECTION 15 OF LM ACT, 2011
            </div>
            <div className="text-[10px] text-slate-600 font-mono">
              MEMO NUMBER: {scanRecord.report_no} • DATE: {formattedDate}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 my-4">
            <div>
              <div className="font-bold text-[10.5px]">1. Place of Inspection:</div>
              <div className="text-slate-700 pl-3">{inspectionPlace}</div>

              <div className="font-bold text-[10.5px] mt-2">2. Entity Inspected:</div>
              <div className="text-slate-700 pl-3">{scanRecord.product?.manufacturer || 'Packer / Trader On-Record'}</div>
            </div>

            <div>
              <div className="font-bold text-[10.5px]">3. Inspecting Officer:</div>
              <div className="text-slate-700 pl-3">{inspectorTitle} ({inspectorBadge})</div>

              <div className="font-bold text-[10.5px] mt-2">4. Commodity &amp; Batch:</div>
              <div className="text-slate-700 pl-3">{commodityBatch}</div>
            </div>
          </div>

          <div className="border border-slate-400 p-2.5 bg-white/60 mb-4">
            <div className="font-bold text-[11px] text-red-900">
              5. SUMMARY OF FINDINGS &amp; STATUTORY ASSESSMENT:
            </div>
            <p className="mt-1 text-slate-800 text-[11px] leading-relaxed">
              {isCompliant
                ? 'Upon contemporary physical examination and spatial verification of pre-packaged commodity on-site, mandatory particulars under Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011 were found verified and compliant.'
                : `Upon contemporary examination of pre-packaged commodity, the following non-conformities were noted: ${
                    nonCompliantDecls.length > 0
                      ? nonCompliantDecls
                          .map((d) => `${d.statutory_parameter || d.field} (${d.rule_provision || 'Rule 6'})`)
                          .join(', ')
                      : 'Statutory non-compliance identified on Principal Display Panel.'
                  }. Notice issued for compounding action under Section 48 / Section 36(1) of the Act.`}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-6 pt-6 border-t-2 border-slate-900 mt-6">
            <div className="text-left">
              <div className="text-[10px] text-slate-500">Signature / Thumb Impression of Dealer / Packer</div>
              <div className="h-10 border-b border-dashed border-slate-400"></div>
              <div className="text-[9.5px] text-slate-600 mt-1">Date: {formattedDate}</div>
            </div>

            <div className="text-right">
              <div className="text-[10px] text-slate-500">Legal Metrology Inspector (Gazetted)</div>
              <div className="font-serif italic font-bold text-sm text-[#0f2744] mt-2">{inspectorTitle}</div>
              <div className="text-[9.5px] font-bold text-slate-800 font-mono">
                {inspectorBadge} • {circleName}
              </div>
            </div>
          </div>

        </div>

        {/* Modal Action Footer */}
        <div className="bg-slate-100 px-4 py-2.5 border-t border-slate-300 flex items-center justify-between">
          <div className="text-xs text-slate-600 font-mono">
            Form LM-V generated with DSC timestamp attestation • Ref: {scanRecord.report_no}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="bg-[#0f2744] hover:bg-[#1a385c] text-white text-xs font-semibold px-4 py-1.5 rounded transition-colors"
            >
              Print This Triplicate Memo
            </button>
            <button
              onClick={onClose}
              className="bg-white border border-slate-300 text-slate-700 text-xs font-semibold px-3 py-1.5 rounded hover:bg-slate-50 transition-colors"
            >
              Close
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
