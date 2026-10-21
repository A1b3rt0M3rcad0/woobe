import type { ReconciliationPreview } from '../../../packages/woobe-frontend/src/features/provider-models/api'

export const providerModelReconciliation: ReconciliationPreview = {
  expected_credential_revision: 1,
  expected_configuration_revision: 'synthetic-configuration-revision',
  items: [
    {
      model_id: 'catalog-language', label: 'Catalog language', installed_model_id: null,
      candidate_digest: 'synthetic-language-evidence', state: 'new', change_kind: 'new',
      proposed_spec: {
        operations: ['language.generate'], source: 'provider_catalog',
        pricing: { currency: 'USD', input_cost_per_1m_tokens: 0, output_cost_per_1m_tokens: 1.25 },
      },
    },
    {
      model_id: 'unclassified-model', label: 'Unclassified model', installed_model_id: null,
      state: 'unsupported/unclassified', change_kind: 'unsupported/unclassified', proposed_spec: null,
    },
  ],
}
