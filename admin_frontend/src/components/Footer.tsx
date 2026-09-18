import React from 'react';

interface FooterProps {
  detailed?: boolean;
}

export const Footer: React.FC<FooterProps> = ({ detailed = false }) => {
  if (detailed) {
    return (
      <footer className="bg-white border-t border-slate-200 mt-auto py-5 text-slate-500 text-xs">
        <div className="max-w-[1720px] mx-auto px-4 sm:px-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div className="flex flex-col space-y-0.5 text-left">
            <span className="font-semibold text-slate-800">
              PRAMAAN — Legal Metrology Compliance Portal
            </span>
            <span className="text-[11px] text-slate-500">
              Official Regulatory Platform of District Enforcement Authority, Ludhiana Circle • Government of India
            </span>
          </div>

          <div className="flex flex-col md:items-end space-y-0.5 text-left md:text-right">
            <span className="text-[11px] text-slate-500">
              © 2026 Department of Consumer Affairs. All statutory rights reserved.
            </span>
          </div>
        </div>
      </footer>
    );
  }

  return (
    <footer className="bg-white border-t border-slate-200 mt-auto py-4 text-slate-500 text-xs">
      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
        <span className="font-medium text-slate-700">
          PRAMAAN — Legal Metrology Compliance System | Department of Consumer Affairs
        </span>
        <span className="text-slate-500">
          © 2026 Government of India. All rights reserved.
        </span>
      </div>
    </footer>
  );
};
