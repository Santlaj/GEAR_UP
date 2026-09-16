import React from 'react';
import { useLanguage } from '../../lib/i18n';

export const GovFooter: React.FC = () => {
  const { t, lang } = useLanguage();

  return (
    <footer className="bg-[#0a1f38] text-slate-300 text-xs border-t-4 border-[#ff9933] mt-12 select-none w-full relative z-10">
      
      {/* Top Section: Government Departments & National Directives */}
      <div className="w-full px-4 sm:px-6 py-8 border-b border-slate-700/60">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          {/* Col 1: Portal & Authority */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <img
                src="/assets/emblem_circle.png"
                alt="National Emblem of India"
                className="w-10 h-10 object-contain brightness-125"
              />
              <div>
                <div className="font-bold text-white text-sm">
                  {t('portal_title')} <span className="text-amber-400 font-devanagari font-bold">| {t('portal_hindi_title')}</span>
                </div>
                <div className="text-[11px] text-slate-400">
                  {lang === 'hi' ? 'विधिक मापविज्ञान अनुपालन एवं प्रवर्तन प्रणाली' : 'Legal Metrology Enforcement Portal'}
                </div>
              </div>
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed">
              {lang === 'hi'
                ? 'विधिक मापविज्ञान (पैकेज्ड कमोडिटीज) नियमावली, 2011 के अंतर्गत भारत के सभी राज्यों एवं संघ राज्य क्षेत्रों में अनिवार्य वैधानिक अनुपालन निगरानी।'
                : 'Official statutory portal for field enforcement of the Legal Metrology (Packaged Commodities) Rules, 2011 across all States & Union Territories of India.'}
            </p>
          </div>

          {/* Col 2: Government Portals Network */}
          <div className="space-y-2">
            <h4 className="text-white font-bold text-xs uppercase tracking-wider border-b border-slate-700/80 pb-1.5 flex items-center">
              <span>{lang === 'hi' ? 'राष्ट्रीय सरकारी पोर्टल' : 'National Portals'}</span>
            </h4>
            <ul className="space-y-1.5 text-[11px] text-slate-300">
              <li>
                <a href="https://india.gov.in" target="_blank" rel="noreferrer" className="hover:text-amber-300 transition-colors flex items-center gap-1">
                  <span>›</span>
                  <span>{lang === 'hi' ? 'भारत का राष्ट्रीय पोर्टल (india.gov.in)' : 'National Portal of India (india.gov.in)'}</span>
                </a>
              </li>
              <li>
                <a href="https://consumeraffairs.nic.in" target="_blank" rel="noreferrer" className="hover:text-amber-300 transition-colors flex items-center gap-1">
                  <span>›</span>
                  <span>{lang === 'hi' ? 'उपभोक्ता मामले विभाग' : 'Department of Consumer Affairs'}</span>
                </a>
              </li>
              <li>
                <a href="https://consumerhelpline.gov.in" target="_blank" rel="noreferrer" className="hover:text-amber-300 transition-colors flex items-center gap-1">
                  <span>›</span>
                  <span>{lang === 'hi' ? 'राष्ट्रीय उपभोक्ता हेल्पलाइन (1915)' : 'National Consumer Helpline (1915)'}</span>
                </a>
              </li>
              <li>
                <a href="https://pgportal.gov.in" target="_blank" rel="noreferrer" className="hover:text-amber-300 transition-colors flex items-center gap-1">
                  <span>›</span>
                  <span>{lang === 'hi' ? 'सीपीजीआरएएमएस लोक शिकायत पोर्टल' : 'CPGRAMS Public Grievance Portal'}</span>
                </a>
              </li>
            </ul>
          </div>

          {/* Col 3: Statutory Legal Framework */}
          <div className="space-y-2">
            <h4 className="text-white font-bold text-xs uppercase tracking-wider border-b border-slate-700/80 pb-1.5 flex items-center">
              <span>{lang === 'hi' ? 'वैधानिक विधिक रूपरेखा' : 'Statutory Framework'}</span>
            </h4>
            <ul className="space-y-1.5 text-[11px] text-slate-300">
              <li>
                <span className="text-white font-semibold">{lang === 'hi' ? 'विधिक मापविज्ञान अधिनियम, 2011' : 'The Legal Metrology Act, 2011'}</span>
                <span className="block text-[10px] text-slate-400">{lang === 'hi' ? '2010 का अधिनियम सं. 1' : 'Act No. 1 of 2010'}</span>
              </li>
              <li>
                <span className="text-white font-semibold">{lang === 'hi' ? 'पीसीआर 2011 (अनिवार्य घोषणाएं)' : 'PCR 2011 (Mandatory Declarations)'}</span>
                <span className="block text-[10px] text-slate-400">Rule 6, Rule 9, Rule 18 &amp; Second Schedule</span>
              </li>
              <li>
                <span className="text-white font-semibold">{lang === 'hi' ? 'जब्ती एवं शमन शक्तियां' : 'Seizure & Compounding'}</span>
                <span className="block text-[10px] text-slate-400">Section 15 (Powers) &amp; Section 48 (Compounding)</span>
              </li>
            </ul>
          </div>

        </div>
      </div>

      {/* Middle Bar: Official Policy Links */}
      <div className="w-full px-4 sm:px-6 py-3 bg-[#071629] border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-y-2 text-[11px]">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-slate-300">
          <a href="#terms" className="hover:text-amber-300 transition-colors">{t('footer_terms')}</a>
          <span>•</span>
          <a href="#help" className="hover:text-amber-300 transition-colors">{t('footer_manual')}</a>
          <span>•</span>
          <a href="#disclaimer" className="hover:text-amber-300 transition-colors">{t('footer_gazette')}</a>
          <span>•</span>
          <a href="#privacy" className="hover:text-amber-300 transition-colors">{t('footer_privacy')}</a>
          <span>•</span>
          <a href="#accessibility" className="hover:text-amber-300 transition-colors">{t('footer_accessibility')}</a>
        </div>
      </div>

      {/* Bottom Sub-footer: Copyright & Sovereign Attribution */}
      <div className="w-full px-4 sm:px-6 py-3 bg-[#040f1c] flex flex-col sm:flex-row items-center justify-between gap-2 text-[10px] text-slate-400">
        <div>
          {t('footer_copyright')}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-slate-500">{t('node_name')}</span>
          <span>•</span>
          <span className="text-amber-400 font-devanagari">{t('satyamev_jayate')}</span>
        </div>
      </div>

    </footer>
  );
};

