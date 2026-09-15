import React, { useState, useEffect } from 'react';
import { useLanguage } from '../../lib/i18n';

interface GovTopBarProps {
  fontSizeLevel?: number; // -1, 0, 1
  onFontSizeChange?: (level: number) => void;
  lang?: 'en' | 'hi';
  onLangChange?: (lang: 'en' | 'hi') => void;
}

export const GovTopBar: React.FC<GovTopBarProps> = ({
  fontSizeLevel = 0,
  onFontSizeChange,
  lang: propLang,
  onLangChange: propOnLangChange,
}) => {
  const { lang: contextLang, setLang: contextSetLang, t } = useLanguage();
  const currentLang = propLang || contextLang;
  const setLanguage = (newLang: 'en' | 'hi') => {
    propOnLangChange?.(newLang);
    contextSetLang(newLang);
  };

  const [currentIstTime, setCurrentIstTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      // Format in Indian Standard Time (IST)
      const options: Intl.DateTimeFormatOptions = {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      };
      setCurrentIstTime(new Intl.DateTimeFormat(currentLang === 'hi' ? 'hi-IN' : 'en-IN', options).format(now) + ' IST');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, [currentLang]);

  return (
    <div className="w-full select-none z-20">
      {/* Official Tiranga (Tricolor) National Top Stripe */}
      <div className="w-full flex h-1.5">
        <div className="w-1/3 bg-[#FF9933]" title="Saffron (Kesari)"></div>
        <div className="w-1/3 bg-white border-y border-slate-200" title="White (Shweta)"></div>
        <div className="w-1/3 bg-[#138808]" title="India Green (Hara)"></div>
      </div>

      {/* Official Government Accessibility & National Identity Bar */}
      <div className="w-full bg-[#0a1f38] text-slate-200 text-xs py-1 px-4 sm:px-6 border-b border-slate-700/60 flex flex-wrap items-center justify-between gap-y-1 gap-x-4">
        
        {/* Left: Sovereign Entity Inscription */}
        <div className="flex items-center gap-2.5 font-medium tracking-wide">
          <span className="text-amber-400 font-bold">{t('gov_india')}</span>
          <span className="text-slate-400">|</span>
          <span className="text-slate-100 font-semibold tracking-wider text-[11px] uppercase">
            {t('gov_india_hindi')}
          </span>
          <span className="hidden md:inline text-slate-500">•</span>
          <span className="hidden md:inline text-slate-300 text-[11px]">
            {t('ministry_title')}
          </span>
        </div>

        {/* Center: Live IST Official Clock & Motto */}
        <div className="hidden lg:flex items-center gap-3 text-[11px] text-slate-300">
          <span className="font-serif italic text-amber-300/90 font-bold">
            {t('satyamev_jayate')}
          </span>
          <span className="text-slate-500">•</span>
          <span className="font-mono text-slate-200 bg-black/30 px-2 py-0.5 rounded border border-slate-700/50">
            {currentIstTime || '13 Sep 2026, 17:35 IST'}
          </span>
        </div>

        {/* Right: Accessibility Tools & Language Switcher (Skip to Main Content removed per directive) */}
        <div className="flex items-center gap-3 text-[11px]">


          {/* Language Switcher */}
          <div className="flex items-center gap-1.5 bg-slate-900/60 border border-slate-700/60 rounded px-2 py-0.5">
            <button
              onClick={() => setLanguage('en')}
              className={`font-bold transition-all cursor-pointer ${currentLang === 'en' ? 'text-amber-400 underline font-black scale-105' : 'text-slate-300 hover:text-white'}`}
              title="Switch to English"
            >
              English
            </button>
            <span className="text-slate-500">/</span>
            <button
              onClick={() => setLanguage('hi')}
              className={`font-devanagari font-bold transition-all cursor-pointer ${currentLang === 'hi' ? 'text-amber-400 underline font-black scale-105' : 'text-slate-300 hover:text-white'}`}
              title="हिन्दी में बदलें (राजभाषा)"
            >
              हिन्दी
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
