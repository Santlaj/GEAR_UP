import React from 'react';
import { UserContext } from '../../shared/schema';
import { useLanguage } from '../../lib/i18n';

interface GovHeaderProps {
  user: UserContext;
  isOnline: boolean;
  onToggleOnline: () => void;
  pendingCount: number;
  onOpenProfile?: () => void;
  isProfileActive?: boolean;
  onLogout?: () => void;
}

export const GovHeader: React.FC<GovHeaderProps> = ({
  user,
  isOnline,
  onToggleOnline,
  pendingCount,
  onOpenProfile,
  isProfileActive = false,
  onLogout,
}) => {
  const { t, lang } = useLanguage();

  return (
    <header className="bg-white border-b border-slate-300 select-none shadow-xs w-full z-10">
      <div className="w-full px-4 sm:px-6 py-3 grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] items-center gap-y-3 gap-x-6">
        
        {/* Left: National Emblem & Ministry Identity */}
        <div className="flex items-center gap-4 justify-self-start">
          <img
            src="/assets/emblem_circle.png"
            alt="National Emblem of India - State Emblem with Satyameva Jayate"
            className="w-14 h-14 object-contain drop-shadow-xs shrink-0"
          />
          <div className="flex flex-col border-l-2 border-[#ff9933] pl-3">
            <span className="text-[13px] font-bold text-slate-900 tracking-tight leading-tight">
              {lang === 'hi' ? 'भारत सरकार | Government of India' : 'Government of India | भारत सरकार'}
            </span>
            <span className="text-xs font-semibold text-slate-800 leading-tight mt-0.5">
              {t('dept_title')}
            </span>
            <span className="text-[11px] font-medium text-slate-600 leading-tight">
              {t('ministry_title')}
            </span>
            <span className="text-[10px] font-bold tracking-wider text-[#0a2540] uppercase mt-1 bg-slate-100 px-1.5 py-0.5 rounded w-fit border border-slate-200">
              {t('legal_metrology_div')}
            </span>
          </div>
        </div>

        {/* Center: Portal Identity (Strictly Centered in Middle) */}
        <div className="text-center flex flex-col items-center justify-self-center">
          <div className="flex items-center justify-center gap-2">
            <h1 className="text-2xl lg:text-3xl font-black text-[#0a2540] tracking-tight font-serif flex items-center gap-2">
              <span>{t('portal_title')}</span>
              <span className="text-amber-500 font-light text-xl">|</span>
              <span className="font-devanagari text-xl font-bold text-slate-800">{t('portal_hindi_title')}</span>
            </h1>
          </div>
          <p className="text-xs text-slate-700 font-semibold tracking-wide mt-0.5 text-center">
            {t('rules_subtitle')}
          </p>
        </div>

        {/* Right: Corner Inspector Profile Badge */}
        <div className="flex items-center justify-self-end">
          <button
            onClick={onOpenProfile}
            className={`group relative flex items-center gap-3 text-left transition-all p-2 pr-3 rounded-md border cursor-pointer ${
              isProfileActive
                ? 'bg-[#0a2540] text-white border-[#0a2540] shadow-md ring-2 ring-amber-400/80'
                : 'bg-slate-50 hover:bg-slate-100 text-slate-900 border-slate-300 hover:border-[#0a2540] shadow-2xs'
            }`}
            title="Click to view full Inspector Profile & Statutory Authority"
            aria-label="Inspector Profile and Cadre Dossier"
          >
            <div className="text-right">
              <div className="flex items-center justify-end gap-1.5">
                <span className={`w-2 h-2 rounded-full ${isProfileActive ? 'bg-amber-400 animate-pulse' : 'bg-emerald-600'}`}></span>
                <span className={`text-xs font-bold leading-none ${isProfileActive ? 'text-white' : 'text-slate-900'}`}>
                  {user.name}
                </span>
              </div>
              <div className={`text-[11px] font-medium mt-0.5 leading-tight ${isProfileActive ? 'text-slate-200' : 'text-slate-600'}`}>
                {t('inspector')} ({user.badge_number})
              </div>
              <div className={`text-[10px] font-bold tracking-wider uppercase mt-0.5 ${isProfileActive ? 'text-amber-300' : 'text-[#0a2540]'}`}>
                {lang === 'hi' ? 'राजपत्रित प्रवर्तन संवर्ग' : 'GAZETTED FIELD ENFORCEMENT'}
              </div>
            </div>
            
            {/* User Avatar Circle (Matching Image 5) */}
            <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center shrink-0 transition-transform group-hover:scale-105 shadow-inner overflow-hidden ${
              isProfileActive
                ? 'border-amber-400 ring-2 ring-amber-400/50 bg-[#e2e8f0]'
                : 'border-slate-300 bg-[#e2e8f0]'
            }`}>
              <svg
                viewBox="0 0 100 100"
                className="w-full h-full"
                aria-hidden="true"
              >
                <circle cx="50" cy="50" r="50" fill="#e2e8f0" />
                <circle cx="50" cy="38" r="17" fill="#718096" />
                <path d="M20 82 C20 65, 34 54, 50 54 C66 54, 80 65, 80 82 Z" fill="#718096" />
              </svg>
            </div>

            {/* Micro Badge */}
            <span className={`absolute -bottom-2 right-2 text-[9px] font-extrabold uppercase px-1 rounded transition-colors ${
              isProfileActive ? 'bg-amber-400 text-slate-950' : 'bg-slate-200 text-slate-700 group-hover:bg-[#0a2540] group-hover:text-white'
            }`}>
              {isProfileActive ? (lang === 'hi' ? 'सक्रिय' : 'ACTIVE') : t('profile_badge')}
            </span>
          </button>
        </div>

      </div>
    </header>
  );
};

