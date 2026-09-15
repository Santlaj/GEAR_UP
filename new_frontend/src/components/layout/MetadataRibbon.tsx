import React from 'react';
import { useLanguage } from '../../lib/i18n';

interface MetadataRibbonProps {
  secHash?: string;
  cadre?: string;
  isOnline?: boolean;
}

export const MetadataRibbon: React.FC<MetadataRibbonProps> = ({
  secHash = '9F2A-88D4-LM2011',
  cadre = 'Gazetted Enforcement',
  isOnline = true
}) => {
  const { t, lang } = useLanguage();

  return (
    <div className="bg-[#eef5fb] border-b border-slate-300 text-xs text-slate-700 py-1.5 w-full select-none">
      <div className="w-full px-4 sm:px-6 flex flex-wrap items-center justify-between gap-y-1.5 gap-x-4">
        
        {/* Item 1 */}
        <div className="flex items-center gap-1.5">
          <span className="font-bold text-slate-900 tracking-wider text-xs">{t('ribbon_cadre')}:</span>
          <span className="font-semibold">{lang === 'hi' ? 'राजपत्रित प्रवर्तन संवर्ग' : cadre}</span>
        </div>

        <div className="hidden sm:block text-slate-300">|</div>

        {/* Item 2 */}
        <div className="flex items-center gap-1.5">
          <span className="font-bold text-slate-900 tracking-wider text-xs">{t('ribbon_protocol')}:</span>
          <span className="font-semibold">NIC-GOI SSL Level 4</span>
        </div>

        <div className="hidden sm:block text-slate-300">|</div>

        {/* Item 3 */}
        <div className="flex items-center gap-1.5">
          <span className="font-bold text-slate-900 tracking-wider text-xs">{t('ribbon_act')}:</span>
          <span className="font-semibold">{t('ribbon_act_val')}</span>
        </div>

        <div className="hidden sm:block text-slate-300">|</div>

        {/* Item 4 */}
        <div className="flex items-center gap-1.5">
          <span className="font-bold text-slate-900 tracking-wider text-xs">{t('ribbon_hash')}:</span>
          <span className="font-mono font-bold text-slate-900 text-xs">{secHash}</span>
        </div>

        {/* Item 5 */}
        <div className="flex items-center gap-2">
          <span className="badge-docket-active">
            {t('ribbon_docket_active')}
          </span>
          {!isOnline && (
            <span className="bg-amber-100 text-amber-900 border border-amber-300 text-xs font-bold px-2.5 py-0.5 rounded">
              {t('ribbon_offline_mode')}
            </span>
          )}
        </div>

      </div>
    </div>
  );
};

