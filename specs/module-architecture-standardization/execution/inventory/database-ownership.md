# Database Ownership Inventory

Generated during spec 008 execution. Lists all ForeignKey constraints from model files,
classified as intra-module or cross-module.

## Cross-Module Foreign Keys (allowlisted)

| Source Module | Source Table | Source Column | Target Schema | Target Table | Removal Spec |
|---|---|---|---|---|---|
| agent | provider_credentials | project_id | core | projects | 134 |
| agent | agents | project_id | core | projects | 134 |
| agent | agent_prompts | project_id | core | projects | 134 |
| agent | agent_prompts | created_by | identity | users | 134 |
| agent | agent_contracts | project_id | core | projects | 134 |
| agent | agent_model_configs | project_id | core | projects | 134 |
| agent | agent_releases | project_id | core | projects | 134 |
| agent | agent_releases | created_by | identity | users | 134 |
| agent | agent_releases | promoted_by | identity | users | 134 |
| agent | agent_release_tests | project_id | core | projects | 134 |
| agent | document_collections | project_id | core | projects | 134 |
| agent | documents | project_id | core | projects | 134 |
| agent | document_chunks | project_id | core | projects | 134 |
| agent | knowledge_versions | project_id | core | projects | 134 |
| agent | sessions | project_id | core | projects | 134 |
| agent | messages | project_id | core | projects | 134 |
| agent | ask_jobs | project_id | core | projects | 134 |
| core | projects | organization_id | identity | organizations | 134 |
| core | api_keys | created_by_user_id | identity | users | 134 |
| billing | customers | organization_id | identity | organizations | 134 |
| billing | subscriptions | organization_id | identity | organizations | 134 |
| tools | tools | project_id | core | projects | 134 |
| tools | secrets | project_id | core | projects | 134 |
| tools | tools | agent_id | ai | agents | 134 |
| observability | traces | project_id | core | projects | 134 |
| observability | trace_events | project_id | core | projects | 134 |
| observability | traces | agent_id | ai | agents | 134 |
| observability | traces | session_id | runtime | sessions | 134 |
| metering | usage_events | project_id | core | projects | 134 |
| metering | usage_daily_project | project_id | core | projects | 134 |
| metering | usage_daily_agent | project_id | core | projects | 134 |
| metering | usage_events | agent_id | ai | agents | 134 |
| metering | usage_daily_agent | agent_id | ai | agents | 134 |

## Legacy Schema References (CRITICAL)

References to schemas `ai`, `knowledge`, or `runtime` that must be migrated to `agent`:

| Source Module | Source Table | Source Column | Legacy Schema | Target Table |
|---|---|---|---|---|
| agent | agents | agent_id | ai | agents |
| agent | agents | project_id | core | projects |
| agent | provider_credentials | provider_credential_id | ai | provider_credentials |
| agent | agent_prompts | prompt_id | ai | agent_prompts |
| agent | agent_contracts | contract_id | ai | agent_contracts |
| agent | agent_model_configs | model_config_id | ai | agent_model_configs |
| agent | agent_releases | release_id | ai | agent_releases |
| agent | agent_releases | contract_id | ai | agent_contracts |
| agent | document_collections | collection_id | knowledge | document_collections |
| agent | documents | document_id | knowledge | documents |
| agent | document_chunks | chunk_id | knowledge | ? |
| agent | sessions | session_id | runtime | sessions |
| agent | messages | session_id | runtime | sessions |
| tools | tools | agent_id | ai | agents |
| observability | traces | agent_id | ai | agents |
| observability | traces | session_id | runtime | sessions |
| metering | usage_events | agent_id | ai | agents |
| metering | usage_daily_agent | agent_id | ai | agents |

## Intra-Module Foreign Keys (allowed)

| Module | Source Table | Source Column | Target Table |
|---|---|---|---|
| identity | members | user_id | identity.users |
| identity | members | organization_id | identity.organizations |
| identity | organization_invites | organization_id | identity.organizations |
| identity | organization_invites | invited_by_user_id | identity.users |
| identity | organization_members | user_id | identity.users |
| core | projects | project_id | core.projects |
| core | api_keys | api_key_id | core.projects |
| billing | subscriptions | customer_id | billing.customers |
| billing | subscriptions | plan_id | billing.plans |
| observability | trace_events | trace_id | observability.traces |

## Summary

- Total FK declarations: 69
- Intra-module: ~16
- Cross-module (allowlisted): 33
- Legacy schema refs (critical): 18
- Modules without own UoW yet: 6 (all except agent)
