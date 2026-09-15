import React, { useState, useEffect } from 'react';
import { fetchRules, StatutoryRule } from '../../api/rules';

export const StatutoryRulesRepositoryView: React.FC = () => {
  const [rules, setRules] = useState<StatutoryRule[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [activeDomain, setActiveDomain] = useState<'all' | 'legal_metrology' | 'fssai'>('all');

  const loadRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const domainParam = activeDomain === 'all' ? undefined : activeDomain;
      const data = await fetchRules({ domain: domainParam, q: searchTerm.trim() || undefined });
      setRules(data || []);
    } catch (err: any) {
      console.error('Failed to load rules:', err);
      setError(err.message || 'Unable to load statutory rules compendium from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, [activeDomain]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadRules();
  };

  return (
    <div className="w-full px-4 sm:px-6 py-4 select-none">
      
      {/* Repository Header */}
      <div className="bg-white border border-slate-300 p-4 mb-4 shadow-sm rounded-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <span className="bg-[#0f2744] text-white text-xs font-bold px-2.5 py-1 rounded-sm uppercase tracking-wider">
            OFFICIAL STATUTORY GAZETTE COMPENDIUM
          </span>
          <h2 className="text-xl font-bold text-slate-900 font-serif mt-1.5 leading-tight">
            Central Statutory Rules Repository (360+ Normalized Provisions)
          </h2>
          <div className="text-xs font-semibold text-slate-600 mt-1">
            Authoritative legal mandates verified pursuant to powers conferred by Section 52 of Legal Metrology Act, 2011 &amp; Section 16 of Food Safety and Standards Act, 2006.
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold text-slate-700 bg-slate-100 px-3 py-1.5 rounded border border-slate-300">
            TOTAL RULES: {rules.length}
          </span>
        </div>
      </div>

      {/* Filter Tabs & Search */}
      <div className="bg-white border border-slate-300 p-4 mb-4 text-xs shadow-sm rounded-sm flex flex-wrap items-center justify-between gap-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setActiveDomain('all')}
            className={`px-3.5 py-2 rounded font-bold text-xs transition-colors cursor-pointer ${
              activeDomain === 'all'
                ? 'bg-[#0f2744] text-white shadow-sm'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            All Statutory Provisions
          </button>
          <button
            onClick={() => setActiveDomain('legal_metrology')}
            className={`px-3.5 py-2 rounded font-bold text-xs transition-colors cursor-pointer ${
              activeDomain === 'legal_metrology'
                ? 'bg-[#0f2744] text-white shadow-sm'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Legal Metrology (PC) Rules, 2011
          </button>
          <button
            onClick={() => setActiveDomain('fssai')}
            className={`px-3.5 py-2 rounded font-bold text-xs transition-colors cursor-pointer ${
              activeDomain === 'fssai'
                ? 'bg-[#0f2744] text-white shadow-sm'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            FSSAI (Packaging &amp; Labelling) Rules
          </button>
        </div>

        <form onSubmit={handleSearchSubmit} className="w-full sm:w-96 flex items-center gap-2">
          <input
            type="text"
            placeholder="Search rules, provisions, standards..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3.5 py-2 border border-slate-300 rounded text-xs focus:outline-none focus:border-[#0f2744]"
          />
          <button
            type="submit"
            className="bg-[#0f2744] hover:bg-[#1a385c] text-white font-bold text-xs px-3.5 py-2 rounded transition-colors cursor-pointer shrink-0"
          >
            Search
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-300 text-red-800 p-3 rounded mb-4 text-xs">
          {error}
        </div>
      )}

      {/* Rules Grid */}
      {loading ? (
        <div className="bg-white border border-slate-300 p-12 text-center rounded text-sm text-slate-600">
          <div className="inline-block w-6 h-6 border-2 border-[#0f2744] border-t-transparent rounded-full animate-spin mb-2" />
          <div>Loading authoritative statutory rules from backend...</div>
        </div>
      ) : rules.length === 0 ? (
        <div className="bg-white border border-slate-300 p-12 text-center rounded text-sm text-slate-500">
          No statutory rules match your search criteria.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
          {rules.map((rule) => (
            <div
              key={rule.rule_id}
              className="bg-white border border-slate-300 p-4 shadow-sm rounded-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-2.5">
                  <span className="bg-[#ebf3fb] text-[#0f2744] font-black text-xs px-2.5 py-1 rounded border border-blue-200">
                    {rule.legal_reference?.section_or_rule_number || rule.rule_id}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500 font-bold uppercase">
                    {rule.domain.replace(/_/g, ' ')} • {rule.evaluator_type.replace(/_/g, ' ')}
                  </span>
                </div>

                <h3 className="font-extrabold text-slate-900 text-xs sm:text-sm leading-snug">
                  {rule.description}
                </h3>

                <div className="mt-2.5 text-xs text-slate-700 bg-slate-50 border-l-3 border-[#0f2744] p-2.5 rounded-r">
                  <strong className="text-slate-900 text-xs">Source Statute &amp; Standard:</strong>
                  <p className="mt-0.5 text-slate-700 leading-relaxed text-xs">
                    {rule.legal_reference?.source_document}
                    {rule.expected_value_or_format ? ` — Expected: ${rule.expected_value_or_format}` : ''}
                  </p>
                </div>

                {rule.applicability?.commodity_categories && rule.applicability.commodity_categories.length > 0 && (
                  <div className="mt-2 text-[11px] text-slate-600">
                    <span className="font-semibold text-slate-800">Categories: </span>
                    {rule.applicability.commodity_categories.slice(0, 3).join(', ')}
                    {rule.applicability.commodity_categories.length > 3 ? ` (+${rule.applicability.commodity_categories.length - 3} more)` : ''}
                  </div>
                )}
              </div>

              <div className="mt-3.5 pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs">
                <span className="font-mono text-slate-500 text-[10px]">ID: {rule.rule_id}</span>
                <span className="text-emerald-700 font-black text-xs">✔ MANDATORY CLAUSE</span>
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
};

export default StatutoryRulesRepositoryView;
