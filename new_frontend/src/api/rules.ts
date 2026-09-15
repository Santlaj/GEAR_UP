import { apiFetch } from './client';

export interface StatutoryRule {
  rule_id: string;
  domain: string;
  description: string;
  evaluator_type: string;
  expected_value_or_format: string;
  legal_reference: {
    source_document: string;
    section_or_rule_number: string;
    schedule_reference?: string | null;
  };
  mandatory: boolean;
  applicability: {
    commodity_categories: string[];
    package_type: string;
    exemption_conditions?: string | null;
  };
  capability?: string;
  effective_from?: string | null;
}

export async function fetchRules(params?: {
  domain?: string;
  q?: string;
}): Promise<StatutoryRule[]> {
  const searchParams = new URLSearchParams();
  if (params?.domain) searchParams.set('domain', params.domain);
  if (params?.q) searchParams.set('q', params.q);

  const query = searchParams.toString();
  const path = query ? `/rules?${query}` : '/rules';
  return apiFetch<StatutoryRule[]>(path);
}
