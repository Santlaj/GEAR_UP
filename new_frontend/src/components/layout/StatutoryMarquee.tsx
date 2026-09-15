import React from 'react';
import { useLanguage } from '../../lib/i18n';
import { ShieldAlert } from 'lucide-react';

export const StatutoryMarquee: React.FC = () => {
  const { lang } = useLanguage();

  return (
    <div className="w-full bg-[#fdfaf2] border-b-2 border-amber-300/80 text-slate-900 py-2.5 sm:py-3 px-4 sm:px-6 flex items-center gap-3.5 overflow-hidden select-none z-10 shadow-xs">
      
      {/* Authoritative Badge Pill */}
      <div className="flex items-center gap-2 bg-[#0a2540] text-amber-300 px-3.5 py-1.5 rounded font-black text-xs tracking-wider uppercase shrink-0 shadow-xs border border-[#173a5e]">
        <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
        <span>{lang === 'hi' ? 'राजपत्र वैधानिक निर्देश' : 'STATUTORY GAZETTE DIRECTIVE'}</span>
      </div>

      {/* Marquee Content (Right to Left Scrolling Ticker) */}
      <div className="flex-1 overflow-hidden whitespace-nowrap">
        <div className={`inline-block animate-marquee font-bold text-slate-800 text-xs sm:text-sm tracking-wide ${lang === 'hi' ? 'font-devanagari' : ''}`}>
          <span>
            {lang === 'hi'
              ? 'विधिक मापविज्ञान अधिनियम 2011 एवं पैकेज्ड कमोडिटीज नियम 2011 के अंतर्गत निरीक्षण: नियम 6 के तहत अनिवार्य घोषणाएं (शुद्ध मात्रा, एमआरपी सभी कर सहित, निर्माण माह/वर्ष, निर्माता का पता, उपभोक्ता हेल्पलाइन, एवं इकाई विक्रय मूल्य) प्रदर्शित न होने पर धारा 36 के तहत ₹25,000/- तक का दंड प्रावधान है।'
              : 'STATUTORY ENFORCEMENT DIRECTIVE: All packaged commodities must declare Net Quantity (Rule 12), MRP inclusive of all taxes (Rule 6(1)(e)), Month/Year of Packing (Rule 6(1)(d)), Manufacturer Name & Postal Address (Rule 6(1)(a)), Consumer Care Helpline (Rule 6(1)(n)), and Unit Sale Price (Rule 6(1)(h)).'}
          </span>
          <span className="mx-6 text-amber-700 font-extrabold">• • •</span>
          <span className="text-[#8b2500] font-black">
            {lang === 'hi'
              ? 'उल्लंघन दर्ज होने पर फॉर्म-V अधिपत्र अथवा धारा 36/48 के तहत शमन नोटिस जारी किया जाएगा | राष्ट्रीय उपभोक्ता हेल्पलाइन: 1915 | विधिक मापविज्ञान प्रभाग, उपभोक्ता मामले विभाग, भारत सरकार'
              : 'PENALTY U/S 36(1): Fine up to ₹25,000 for first offence, or prosecution for recurring non-compliance. National Consumer Helpline: 1915 | Legal Metrology Division, Department of Consumer Affairs, Government of India.'}
          </span>
          <span className="mx-6 text-amber-700 font-extrabold">• • •</span>
          <span className="text-slate-900 font-bold">
            {lang === 'hi'
              ? 'डिजिटल साक्ष्य की सत्यता आईटी अधिनियम 2000 एवं भारतीय साक्ष्य अधिनियम के तहत मान्य है।'
              : 'Digital Inspection Dossiers are cryptographically sealed with SHA-256 ledger timestamps pursuant to the Information Technology Act, 2000.'}
          </span>
        </div>
      </div>

    </div>
  );
};
