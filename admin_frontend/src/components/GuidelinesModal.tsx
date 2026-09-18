import React from 'react';
import { X, BookOpen, Shield } from 'lucide-react';

interface GuidelinesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GuidelinesModal: React.FC<GuidelinesModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-300 w-full max-w-3xl overflow-hidden text-left">
        {/* Header */}
        <div className="bg-[#0B192C] text-white px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BookOpen className="w-5 h-5 text-blue-400" />
            <div>
              <h2 className="text-base font-bold text-white">
                Legal Metrology Enforcement Protocol Reference Manual
              </h2>
              <p className="text-xs text-white/80">
                Handbook for packaged commodities dual stickering, price smudging, and distributor waivers
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-white/70 hover:text-white rounded-lg hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto text-xs text-slate-700 leading-relaxed">
          <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-lg">
            <h4 className="font-bold text-blue-900 uppercase mb-1 flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-blue-700" />
              STATUTORY FOUNDATION: LEGAL METROLOGY ACT, 2009
            </h4>
            <p className="text-slate-700">
              The Legal Metrology (Packaged Commodities) Rules, 2011 are framed under Section 52 read with Section 18 of the Legal Metrology Act, 2009. Every manufacturer, packer, or importer of pre-packaged commodities is legally obligated to declare the Maximum Retail Price (MRP inclusive of all taxes) in a standard format.
            </p>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-bold text-slate-900 border-b pb-1">
              Section 1. Handling Dual MRP & Over-stickering Violations (Rule 18)
            </h3>
            
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg space-y-1">
              <div className="font-bold text-red-900">
                Rule 18(2) - Prohibition on Price Alteration:
              </div>
              <p className="text-red-950">
                "No person shall alter, obliterate or smudge the maximum retail price indicated by the manufacturer or packer on the pack."
              </p>
              <p className="text-slate-600 mt-1">
                Any over-sticker that increases the price above the original manufacturer's printed price is strictly illegal and constitutes a compoundable offense under Section 36 of the Act.
              </p>
            </div>

            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-1">
              <div className="font-bold text-amber-900">
                Distributor Price Revision Waivers:
              </div>
              <p className="text-slate-800">
                Price revisions downwards (discounts) are permissible without obliteration. Price upward revisions require explicit gazette notification or sanctioned factory re-labeling under Section 39. Over-stickering by retail shopkeepers or regional stockists is strictly invalid.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-bold text-slate-900 border-b pb-1">
              Section 2. Standard Units and Abbreviation Codes (Rule 13)
            </h3>
            <ul className="list-disc pl-5 space-y-1 text-slate-600">
              <li><strong>Gram / Kilogram:</strong> Must be written as <code>g</code> or <code>kg</code>. Pluralization such as <code>Kgs.</code>, <code>Gms.</code>, or capitalized <code>Kg.</code> is non-compliant.</li>
              <li><strong>Volume:</strong> Must be written as <code>mL</code> or <code>L</code> (or <code>l</code>).</li>
              <li><strong>Font Height:</strong> Minimum numeral height is governed by net quantity under Rule 12 Second Schedule.</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-slate-100 border-t border-slate-200 px-6 py-3 flex items-center justify-between">
          <span className="text-[11px] text-slate-500">
            DCA-LM-SOP-2026/V4.2 • Ludhiana Circle Enforcement Standard
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
          >
            Close Handbook
          </button>
        </div>
      </div>
    </div>
  );
};
