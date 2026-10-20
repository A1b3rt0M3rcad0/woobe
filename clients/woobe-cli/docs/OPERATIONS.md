# Executable command catalog

Generated from current discovery: 369 executable entries, including 203 HTTP operations. Route advertisement does not grant authority. See [USAGE.md](USAGE.md) for workflows, [PAGINATION.md](PAGINATION.md) for reviewed pagination and [AGENT_SKILL.md](AGENT_SKILL.md) for embedded assistant skill setup.

Regenerate with `python3 scripts/command_catalog.py --binary bin/woobe --write`. Assistant installation uses local `skills` commands, not HTTP operations. The optional npm `woobe-skill` executable uses the same payload and receipts.

| Command | Kind | HTTP | Availability | Permission hint | Pagination |
| --- | --- | --- | --- | --- | --- |
| `agent` | `alias` | — | `local` | — | — |
| `auth credential import` | `local` | — | `local` | — | — |
| `auth credential list` | `local` | — | `local` | — | — |
| `auth credential remove` | `local` | — | `local` | — | — |
| `auth invite accept` | `http` | `POST /identity/invites/{invite_id}/accept` | `observed` | — | — |
| `auth invite list` | `http` | `GET /identity/invites/pending` | `observed` | — | — |
| `auth key inspect` | `http` | `GET /identity/control-key/me` | `observed` | — | — |
| `auth login` | `http` | `POST /identity/auth/login` | `observed` | — | — |
| `auth logout` | `http-session` | — | `observed` | — | — |
| `auth refresh` | `http` | `POST /identity/auth/refresh` | `observed` | — | — |
| `auth register` | `http` | `POST /identity/auth/register` | `observed` | — | — |
| `auth status` | `http` | `GET /identity/users/me` | `observed` | — | — |
| `completion bash` | `shell-completion` | — | `local` | — | — |
| `completion fish` | `shell-completion` | — | `local` | — | — |
| `completion powershell` | `shell-completion` | — | `local` | — | — |
| `completion zsh` | `shell-completion` | — | `local` | — | — |
| `config check` | `local` | — | `local` | — | — |
| `config show` | `local` | — | `local` | — | — |
| `context create` | `local` | — | `local` | — | — |
| `context credential attach` | `local` | — | `local` | — | — |
| `context credential detach` | `local` | — | `local` | — | — |
| `context delete` | `local` | — | `local` | — | — |
| `context list` | `local` | — | `local` | — | — |
| `context project select` | `local` | — | `local` | — | — |
| `context runtime-credential attach` | `local` | — | `local` | — | — |
| `context runtime-credential detach` | `local` | — | `local` | — | — |
| `context set` | `local` | — | `local` | — | — |
| `context show` | `local` | — | `local` | — | — |
| `context unset` | `local` | — | `local` | — | — |
| `context update` | `local` | — | `local` | — | — |
| `context use` | `local` | — | `local` | — | — |
| `control-key` | `alias` | — | `local` | — | — |
| `develop agent activate` | `development` | — | `local` | — | — |
| `develop agent archive` | `development` | — | `local` | — | — |
| `develop agent bindings` | `development` | — | `local` | — | — |
| `develop agent candidate` | `development` | — | `local` | — | — |
| `develop agent checkout` | `development` | — | `local` | — | — |
| `develop agent create` | `development` | — | `local` | — | — |
| `develop agent current` | `development-http` | — | `server-dependent` | — | — |
| `develop agent delete` | `development` | — | `local` | — | — |
| `develop agent deploy` | `deployment-orchestration` | — | `server-dependent` | — | — |
| `develop agent deployment` | `development` | — | `local` | — | — |
| `develop agent diff` | `development` | — | `local` | — | — |
| `develop agent draft` | `development` | — | `local` | — | — |
| `develop agent evaluation` | `development` | — | `local` | — | — |
| `develop agent git-attest` | `development` | — | `local` | — | — |
| `develop agent git-proof` | `development` | — | `local` | — | — |
| `develop agent heads` | `development` | — | `local` | — | — |
| `develop agent history` | `development` | — | `local_or_server-dependent` | — | — |
| `develop agent lease` | `development` | — | `local` | — | — |
| `develop agent publication` | `development` | — | `local` | — | — |
| `develop agent publish` | `development` | — | `local` | — | — |
| `develop agent pull` | `development-http` | — | `server-dependent` | — | — |
| `develop agent push` | `development-http` | — | `server-dependent` | — | — |
| `develop agent rebase` | `development` | — | `local` | — | — |
| `develop agent receipt` | `development` | — | `local` | — | — |
| `develop agent reconcile` | `development` | — | `local` | — | — |
| `develop agent revision` | `development` | — | `local` | — | — |
| `develop agent rollback` | `development` | — | `local` | — | — |
| `develop agent stage` | `development` | — | `local` | — | — |
| `develop agent status` | `development` | — | `local_or_server-dependent` | — | — |
| `develop agent test` | `development` | — | `local` | — | — |
| `develop agent validate` | `development` | — | `local` | — | — |
| `develop network activate` | `development` | — | `local` | — | — |
| `develop network bindings` | `development` | — | `local` | — | — |
| `develop network candidate` | `development` | — | `local` | — | — |
| `develop network checkout` | `development` | — | `local` | — | — |
| `develop network create` | `development` | — | `local` | — | — |
| `develop network current` | `development-http` | — | `server-dependent` | — | — |
| `develop network deploy` | `deployment-orchestration` | — | `server-dependent` | — | — |
| `develop network deployment` | `development` | — | `local` | — | — |
| `develop network diff` | `development` | — | `local` | — | — |
| `develop network draft` | `development` | — | `local` | — | — |
| `develop network evaluation` | `development` | — | `local` | — | — |
| `develop network git-attest` | `development` | — | `local` | — | — |
| `develop network git-proof` | `development` | — | `local` | — | — |
| `develop network heads` | `development` | — | `local` | — | — |
| `develop network history` | `development` | — | `local_or_server-dependent` | — | — |
| `develop network lease` | `development` | — | `local` | — | — |
| `develop network publication` | `development` | — | `local` | — | — |
| `develop network publish` | `development` | — | `local` | — | — |
| `develop network pull` | `development-http` | — | `server-dependent` | — | — |
| `develop network push` | `development-http` | — | `server-dependent` | — | — |
| `develop network rebase` | `development` | — | `local` | — | — |
| `develop network receipt` | `development` | — | `local` | — | — |
| `develop network reconcile` | `development` | — | `local` | — | — |
| `develop network revision` | `development` | — | `local` | — | — |
| `develop network rollback` | `development` | — | `local` | — | — |
| `develop network stage` | `development` | — | `local` | — | — |
| `develop network status` | `development` | — | `local_or_server-dependent` | — | — |
| `develop network test` | `development` | — | `local` | — | — |
| `develop network validate` | `development` | — | `local` | — | — |
| `develop surface create` | `development` | — | `local` | — | — |
| `develop surface diff` | `development` | — | `local` | — | — |
| `develop surface pull` | `development-http` | — | `server-dependent` | — | — |
| `develop surface push` | `development-http` | — | `server-dependent` | — | — |
| `develop surface status` | `development` | — | `local_or_server-dependent` | — | — |
| `develop surface validate` | `development` | — | `local` | — | — |
| `doctor` | `diagnostic-http` | — | `server-dependent` | — | — |
| `export` | `http-projection` | — | `observed` | — | — |
| `help` | `local` | — | `local` | — | — |
| `init` | `local` | — | `local` | — | — |
| `instance bootstrap` | `http` | `POST /identity/instance/bootstrap` | `observed` | — | — |
| `instance status` | `http` | `GET /identity/instance/status` | `observed` | — | — |
| `knowledge` | `local` | — | `local` | — | — |
| `manifest apply` | `composition` | — | `local` | — | — |
| `manifest capture` | `http-projection` | — | `observed` | — | — |
| `manifest compile` | `local` | — | `local` | — | — |
| `manifest diff` | `composition` | — | `server-dependent` | — | — |
| `manifest export` | `http-projection` | — | `observed` | — | — |
| `manifest kinds` | `local` | — | `local` | — | — |
| `manifest plan` | `local` | — | `local` | — | — |
| `manifest preflight` | `diagnostic-http` | — | `server-dependent` | — | — |
| `manifest reconcile` | `composition` | — | `local` | — | — |
| `manifest status` | `local` | — | `local` | — | — |
| `manifest validate` | `local` | — | `local` | — | — |
| `model` | `local` | — | `local` | — | — |
| `network` | `alias` | — | `local` | — | — |
| `package bindings` | `local` | — | `local` | — | — |
| `package cancel` | `package-http` | — | `server-dependent` | — | — |
| `package doctor` | `diagnostic-http` | — | `server-dependent` | — | — |
| `package edit` | `local` | — | `local` | — | — |
| `package export agent` | `package-http` | — | `server-dependent` | — | — |
| `package export network` | `package-http` | — | `server-dependent` | — | — |
| `package import` | `package-http` | — | `server-dependent` | — | — |
| `package plan` | `package-http` | — | `server-dependent` | — | — |
| `package resume` | `package-http` | — | `server-dependent` | — | — |
| `package seal` | `local` | — | `local` | — | — |
| `package status` | `package-http` | — | `server-dependent` | — | — |
| `package validate` | `local` | — | `local` | — | — |
| `permission check` | `http` | `POST /identity/access/check` | `proposed` | — | — |
| `permission effective` | `http` | `GET /identity/access/me` | `proposed` | — | — |
| `permission explain` | `http` | `POST /identity/access/check` | `proposed` | — | — |
| `permission list` | `http` | `GET /identity/permissions` | `proposed` | — | — |
| `project access grant` | `http` | `POST /core/projects/{project_id}/access` | `observed` | — | — |
| `project access revoke` | `http` | `DELETE /core/projects/{project_id}/access/{subject_type}/{subject_id}` | `observed` | — | — |
| `project agent contract create` | `http` | `POST /ai/agents/{agent_id}/contracts` | `observed` | agent:write | — |
| `project agent contract get` | `http` | `GET /ai/agents/{agent_id}/contracts/{contract_id}` | `observed` | agent:read | — |
| `project agent contract list` | `http` | `GET /ai/agents/{agent_id}/contracts` | `observed` | agent:read | — |
| `project agent contract update` | `http` | `PATCH /ai/agents/{agent_id}/contracts/{contract_id}` | `observed` | agent:write | — |
| `project agent create` | `http` | `POST /ai/agents` | `observed` | agent:write | — |
| `project agent delete` | `http` | `DELETE /ai/agents/{agent_id}` | `observed` | agent:delete | — |
| `project agent environment list` | `http` | `GET /ai/agents/{agent_id}/runtime-environments` | `observed` | agent:read | — |
| `project agent environment update` | `http` | `PATCH /ai/agents/{agent_id}/runtime-environments/{environment}` | `observed` | agent:write | — |
| `project agent export` | `http-projection` | — | `observed` | — | — |
| `project agent get` | `http` | `GET /ai/agents/{agent_id}` | `observed` | agent:read | — |
| `project agent git-attestation create` | `http` | `POST /projects/{project_id}/agents/{resource_id}/asac/git-attestations` | `proposed` | agent:version | — |
| `project agent git-attestation get` | `http` | `GET /projects/{project_id}/agents/{resource_id}/asac/git-attestations/{attestation_id}` | `proposed` | agent:read | — |
| `project agent knowledge bind` | `http` | `POST /knowledge/agent-collections` | `observed` | agent:write | — |
| `project agent knowledge list` | `http` | `GET /knowledge/agent-collections` | `observed` | agent:read | — |
| `project agent knowledge unbind` | `http` | `DELETE /knowledge/agent-collections/{link_id}` | `observed` | agent:delete | — |
| `project agent knowledge version-create` | `http` | `POST /knowledge/agents/{agent_id}/knowledge-versions` | `observed` | agent:write | — |
| `project agent knowledge version-list` | `http` | `GET /knowledge/agents/{agent_id}/knowledge-versions` | `observed` | agent:read | — |
| `project agent list` | `http` | `GET /ai/agents` | `observed` | agent:read | — |
| `project agent model-config create` | `http` | `POST /ai/agents/{agent_id}/model-configs` | `observed` | agent:write | — |
| `project agent model-config get` | `http` | `GET /ai/agents/{agent_id}/model-configs/{config_id}` | `observed` | agent:read | — |
| `project agent model-config list` | `http` | `GET /ai/agents/{agent_id}/model-configs` | `observed` | agent:read | — |
| `project agent prompt create` | `http` | `POST /ai/agents/{agent_id}/prompts` | `observed` | agent:write | — |
| `project agent prompt get` | `http` | `GET /ai/agents/{agent_id}/prompts/{version_id}` | `observed` | agent:read | — |
| `project agent prompt list` | `http` | `GET /ai/agents/{agent_id}/prompts` | `observed` | agent:read | — |
| `project agent release activations` | `http` | `GET /ai/agents/{agent_id}/release-activations` | `observed` | agent:read | — |
| `project agent release create` | `http` | `POST /ai/agents/{agent_id}/releases` | `observed` | agent:version | — |
| `project agent release delete` | `http` | `DELETE /ai/agents/{agent_id}/releases/{release_id}` | `observed` | agent:delete | — |
| `project agent release get` | `http` | `GET /ai/agents/{agent_id}/releases/{release_id}` | `observed` | agent:read | — |
| `project agent release list` | `http` | `GET /ai/agents/{agent_id}/releases` | `observed` | agent:read | — |
| `project agent release promote` | `http` | `POST /ai/agents/{agent_id}/releases/{release_id}/promote` | `observed` | agent:production | — |
| `project agent release rollback` | `http` | `POST /ai/agents/{agent_id}/releases/{release_id}/rollback` | `observed` | agent:production | — |
| `project agent release run-test` | `http` | `POST /ai/agents/{agent_id}/release-tests/run` | `observed` | agent:write | — |
| `project agent release test` | `http` | `POST /ai/agents/{agent_id}/release-tests` | `observed` | agent:version | — |
| `project agent release tests` | `http` | `GET /ai/agents/{agent_id}/releases/{release_id}/tests` | `observed` | agent:read | — |
| `project agent signed-receipt get` | `http` | `GET /projects/{project_id}/agents/{resource_id}/asac/signed-receipts/{category}/{receipt_id}` | `proposed` | agent:read | — |
| `project agent tool list` | `http` | `GET /tools/agents/{agent_id}/tools` | `observed` | agent:read | — |
| `project agent update` | `http` | `PATCH /ai/agents/{agent_id}` | `observed` | agent:write | — |
| `project agent usage daily` | `http` | `GET /metering/agents/{agent_id}/daily` | `observed` | agent:read | — |
| `project api-key create` | `http` | `POST /core/projects/{project_id}/api-keys` | `observed` | api_key:write | — |
| `project api-key list` | `http` | `GET /core/projects/{project_id}/api-keys` | `observed` | api_key:read | — |
| `project api-key revoke` | `http` | `POST /core/projects/{project_id}/api-keys/{api_key_id}/revoke` | `observed` | api_key:write | — |
| `project api-key rotate` | `http` | `POST /core/projects/{project_id}/api-keys/{api_key_id}/rotate` | `observed` | api_key:write | — |
| `project api-key update` | `http` | `PATCH /core/projects/{project_id}/api-keys/{api_key_id}` | `observed` | api_key:write | — |
| `project catalog context-assemblers` | `http` | `GET /ai/context-assemblers` | `observed` | — | — |
| `project catalog execution-strategies` | `http` | `GET /ai/execution-strategies` | `observed` | — | — |
| `project catalog knowledge-strategies` | `http` | `GET /ai/knowledge-strategies` | `observed` | — | — |
| `project catalog rag-strategies` | `http` | `GET /ai/rag-strategies` | `observed` | — | — |
| `project configuration bind` | `local` | — | `local` | — | — |
| `project configuration check` | `local` | — | `local` | — | — |
| `project configuration declare` | `local` | — | `local` | — | — |
| `project configuration list` | `local` | — | `local` | — | — |
| `project configuration summary` | `local` | — | `local` | — | — |
| `project configuration test` | `local` | — | `local` | — | — |
| `project configuration usage` | `local` | — | `local` | — | — |
| `project create` | `http` | `POST /core/projects` | `observed` | — | — |
| `project env list` | `http` | `GET /core/projects/{project_id}/environment-keys` | `observed` | project:environment:read | — |
| `project env set` | `http` | `PUT /core/projects/{project_id}/environment-keys/{key}` | `observed` | project:environment:write | — |
| `project env unset` | `http` | `DELETE /core/projects/{project_id}/environment-keys/{key}` | `observed` | project:environment:delete | — |
| `project get` | `http` | `GET /core/projects/{resource_id}` | `observed` | — | — |
| `project knowledge collection create` | `http` | `POST /knowledge/collections` | `observed` | knowledge:write | — |
| `project knowledge collection get` | `http` | `GET /knowledge/collections/{collection_id}` | `observed` | knowledge:read | — |
| `project knowledge collection list` | `http` | `GET /knowledge/collections` | `observed` | knowledge:read | — |
| `project knowledge collection overview` | `http` | `GET /agent/knowledge/collections/{collection_id}/overview` | `observed` | knowledge:read | — |
| `project knowledge collection update` | `http` | `PATCH /knowledge/collections/{collection_id}` | `observed` | knowledge:write | — |
| `project knowledge collection vector-preview` | `http` | `POST /agent/knowledge/collections/{collection_id}/vector-preview` | `observed` | knowledge:write | — |
| `project knowledge document create` | `http` | `POST /knowledge/documents` | `observed` | knowledge:write | — |
| `project knowledge document delete` | `http` | `DELETE /knowledge/documents/{document_id}` | `observed` | knowledge:delete | — |
| `project knowledge document get` | `http` | `GET /knowledge/documents/{document_id}` | `observed` | knowledge:read | — |
| `project knowledge document list` | `http` | `GET /knowledge/documents` | `observed` | knowledge:read | — |
| `project knowledge document upload` | `multipart-http` | — | `observed` | — | — |
| `project knowledge search` | `http` | `POST /knowledge/search` | `observed` | knowledge:write | — |
| `project knowledge snapshot create` | `http` | `POST /agent/knowledge/collections/{collection_id}/vector-snapshots` | `observed` | knowledge:write | — |
| `project knowledge snapshot get` | `http` | `GET /agent/knowledge/vector-snapshots/{snapshot_id}` | `observed` | knowledge:read | — |
| `project knowledge snapshot list` | `http` | `GET /agent/knowledge/collections/{collection_id}/vector-snapshots` | `observed` | knowledge:read | — |
| `project knowledge snapshot prepare` | `http` | `POST /agent/knowledge/vector-snapshots/{snapshot_id}/prepare` | `proposed` | knowledge:write | — |
| `project lifecycle operation` | `http` | `GET /core/projects/{project_id}/lifecycle-policy/operations/{operation_id}` | `proposed` | project:read | — |
| `project lifecycle show` | `http` | `GET /core/projects/{project_id}/lifecycle-policy` | `proposed` | project:read | — |
| `project lifecycle update` | `http` | `PUT /core/projects/{project_id}/lifecycle-policy` | `proposed` | project:access:write | — |
| `project list` | `http` | `GET /core/projects` | `observed` | — | — |
| `project member grant` | `http` | `POST /core/projects/{project_id}/members` | `observed` | — | — |
| `project member list` | `http` | `GET /core/projects/{project_id}/members` | `observed` | — | — |
| `project member revoke` | `http` | `DELETE /core/projects/{project_id}/members/{user_id}` | `observed` | — | — |
| `project network activation create` | `http` | `POST /network/{network_id}/production/activations` | `observed` | network:production | — |
| `project network activation list` | `http` | `GET /network/{network_id}/management/activations` | `observed` | network:read | — |
| `project network create` | `http` | `POST /network/projects/{project_id}/networks` | `observed` | network:write | — |
| `project network draft update` | `http` | `PATCH /network/{network_id}/draft` | `observed` | network:write | — |
| `project network environment list` | `http` | `GET /network/{network_id}/runtime-environments` | `observed` | network:read | — |
| `project network environment update` | `http` | `PATCH /network/{network_id}/runtime-environments/{environment}` | `observed` | network:write | — |
| `project network execution cancel` | `http` | `POST /network/executions/{execution_id}/cancel` | `observed` | network:write | — |
| `project network execution diagnostics` | `http` | `GET /network/executions/{execution_id}/diagnostics` | `observed` | network:read | — |
| `project network execution events` | `http` | `GET /network/executions/{execution_id}/events` | `observed` | network:read | — |
| `project network execution snapshot` | `http` | `GET /network/executions/{execution_id}/snapshot` | `observed` | network:read | — |
| `project network get` | `http` | `GET /network/projects/{project_id}/networks/{network_id}` | `observed` | network:read | — |
| `project network git-attestation create` | `http` | `POST /projects/{project_id}/networks/{resource_id}/asac/git-attestations` | `proposed` | network:version | — |
| `project network git-attestation get` | `http` | `GET /projects/{project_id}/networks/{resource_id}/asac/git-attestations/{attestation_id}` | `proposed` | network:read | — |
| `project network list` | `http` | `GET /network/projects/{project_id}/networks` | `observed` | network:read | — |
| `project network management external-context` | `http` | `GET /network/{network_id}/management/external-context-contract` | `observed` | network:read | — |
| `project network management versions` | `http` | `GET /network/{network_id}/management/versions` | `observed` | network:read | — |
| `project network promotion create` | `http` | `POST /network/{network_id}/promotions` | `observed` | network:production | — |
| `project network promotion preview` | `http` | `POST /network/{network_id}/promotions/preview` | `observed` | network:write | — |
| `project network rollback` | `http` | `POST /network/{network_id}/rollback` | `observed` | network:production | — |
| `project network session create` | `http` | `POST /network/{network_id}/sessions` | `observed` | network:write | — |
| `project network session list` | `http` | `GET /network/{network_id}/sessions` | `observed` | network:read | — |
| `project network session messages` | `http` | `GET /network/{network_id}/sessions/{session_id}/messages` | `observed` | network:read | — |
| `project network session reset-context` | `http` | `POST /network/{network_id}/sessions/{session_id}/reset-context` | `observed` | network:write | — |
| `project network signed-receipt get` | `http` | `GET /projects/{project_id}/networks/{resource_id}/asac/signed-receipts/{category}/{receipt_id}` | `proposed` | network:read | — |
| `project network update` | `http` | `PATCH /network/projects/{project_id}/networks/{network_id}` | `observed` | network:write | — |
| `project network version list` | `http` | `GET /network/{network_id}/versions` | `observed` | network:read | — |
| `project overview` | `http` | `GET /core/projects/{project_id}/overview` | `observed` | — | — |
| `project provider-credential create` | `http` | `POST /ai/credentials` | `observed` | provider:write | — |
| `project provider-credential list` | `http` | `GET /ai/credentials` | `observed` | provider:read | — |
| `project provider-credential revoke` | `http` | `POST /ai/credentials/{credential_id}/revoke` | `observed` | provider:credential:revoke | — |
| `project provider-credential rotate` | `http` | `POST /ai/credentials/{credential_id}/rotate` | `observed` | provider:credential:rotate | — |
| `project provider-credential update` | `http` | `PATCH /ai/credentials/{credential_id}` | `observed` | provider:write | — |
| `project provider-credential usage` | `http` | `GET /ai/credentials/{credential_id}/usage` | `observed` | provider:read | — |
| `project provider-model create` | `http` | `POST /ai/provider-models` | `observed` | model:write | — |
| `project provider-model get` | `http` | `GET /ai/provider-models/{provider_model_id}` | `observed` | model:read | — |
| `project provider-model list` | `http` | `GET /ai/provider-models` | `observed` | model:read | — |
| `project provider-model update` | `http` | `PATCH /ai/provider-models/{provider_model_id}` | `observed` | model:write | — |
| `project provider-model usage` | `http` | `GET /ai/provider-models/{provider_model_id}/usage` | `observed` | model:read | — |
| `project run list` | `http` | `GET /core/projects/{project_id}/runs` | `observed` | — | — |
| `project runtime-key create` | `http` | `POST /core/projects/{project_id}/runtime-keys` | `observed` | api_key:write | — |
| `project skill create` | `http` | `POST /ai/projects/{project_id}/skills` | `observed` | skill:write | — |
| `project skill list` | `http` | `GET /ai/projects/{project_id}/skills` | `observed` | skill:read | — |
| `project skill version create` | `http` | `POST /ai/projects/{project_id}/skills/{skill_id}/versions` | `observed` | skill:write | — |
| `project skill version get` | `http` | `GET /ai/projects/{project_id}/skills/versions/{skill_version_id}` | `observed` | skill:read | — |
| `project skill version list` | `http` | `GET /ai/projects/{project_id}/skills/{skill_id}/versions` | `observed` | skill:read | — |
| `project surface access-key create` | `http` | `POST /chat-surfaces/{surface_id}/access-keys` | `observed` | chat_surface:write | — |
| `project surface access-key list` | `http` | `GET /chat-surfaces/{surface_id}/access-keys` | `observed` | chat_surface:read | — |
| `project surface access-key revoke` | `http` | `POST /chat-surfaces/{surface_id}/access-keys/{api_key_id}/revoke` | `observed` | chat_surface:write | — |
| `project surface access-key rotate` | `http` | `POST /chat-surfaces/{surface_id}/access-keys/{api_key_id}/rotate` | `observed` | chat_surface:write | — |
| `project surface activate` | `http` | `POST /chat-surfaces/{surface_id}/activate` | `observed` | chat_surface:release | — |
| `project surface activity` | `http` | `GET /chat-surfaces/{surface_id}/activity` | `observed` | chat_surface:read | — |
| `project surface archive` | `http` | `POST /chat-surfaces/{surface_id}/archive` | `observed` | chat_surface:write | — |
| `project surface create` | `http` | `POST /chat-surfaces/projects/{project_id}` | `observed` | chat_surface:write | — |
| `project surface disable` | `http` | `POST /chat-surfaces/{surface_id}/disable` | `observed` | chat_surface:write | — |
| `project surface get` | `http` | `GET /chat-surfaces/{surface_id}` | `observed` | chat_surface:read | — |
| `project surface list` | `http` | `GET /chat-surfaces/projects/{project_id}` | `observed` | chat_surface:read | — |
| `project surface release` | `http` | `POST /chat-surfaces/{surface_id}/release` | `observed` | chat_surface:release | — |
| `project surface sessions` | `http` | `GET /chat-surfaces/{surface_id}/sessions` | `observed` | chat_surface:read | — |
| `project surface test-sessions` | `http` | `POST /chat-surfaces/{surface_id}/test-sessions` | `observed` | chat_surface:write | — |
| `project surface update` | `http` | `PATCH /chat-surfaces/{surface_id}` | `observed` | chat_surface:write | — |
| `project tool create` | `http` | `POST /tools/tools` | `observed` | tool:write | — |
| `project tool delete` | `http` | `DELETE /tools/tools/{tool_id}` | `observed` | tool:delete | — |
| `project tool execute` | `http` | `POST /tools/tools/execute` | `observed` | tool:write | — |
| `project tool list` | `http` | `GET /tools/tools` | `observed` | tool:read | — |
| `project tool mcp bulk` | `http` | `POST /tools/mcp/permissions/bulk` | `observed` | tool:write | — |
| `project tool mcp discover` | `http` | `POST /tools/mcp/discover` | `observed` | tool:write | — |
| `project tool mcp oauth complete` | `http` | `POST /tools/mcp/oauth/complete` | `observed` | tool:write | — |
| `project tool mcp oauth device-poll` | `http` | `POST /tools/mcp/oauth/device/poll` | `observed` | tool:write | — |
| `project tool mcp oauth device-start` | `http` | `POST /tools/mcp/oauth/device/start` | `observed` | tool:write | — |
| `project tool mcp oauth disconnect` | `http` | `POST /tools/mcp/oauth/disconnect` | `observed` | tool:write | — |
| `project tool mcp oauth start` | `http` | `POST /tools/mcp/oauth/start` | `observed` | tool:write | — |
| `project tool mcp oauth status` | `http` | `POST /tools/mcp/oauth/status` | `observed` | tool:write | — |
| `project tool mcp refresh` | `http` | `POST /tools/mcp/refresh` | `observed` | tool:write | — |
| `project tool mcp set` | `http` | `PATCH /tools/mcp/permissions` | `observed` | tool:write | — |
| `project tool status` | `http` | `PATCH /tools/tools/{tool_id}/status` | `observed` | tool:write | — |
| `project tool test` | `http` | `POST /tools/tools/test` | `observed` | tool:write | — |
| `project tool update` | `http` | `PATCH /tools/tools/{tool_id}` | `observed` | tool:write | — |
| `project tool usage-impact` | `http` | `GET /tools/tools/{tool_id}/usage-impact` | `observed` | tool:read | — |
| `project trace get` | `http` | `GET /observability/traces/{trace_id}` | `observed` | observability:read | — |
| `project trace list` | `http` | `GET /observability/traces` | `observed` | observability:read | — |
| `project update` | `http` | `PATCH /core/projects/{resource_id}` | `observed` | — | — |
| `project usage daily` | `http` | `GET /metering/projects/{project_id}/daily` | `observed` | usage:read | — |
| `project usage summary` | `http` | `GET /metering/projects/{project_id}/usage` | `observed` | usage:read | — |
| `provider` | `local` | — | `local` | — | — |
| `receipt verify` | `local` | — | `local` | — | — |
| `request` | `generic-http` | — | `server-dependent` | — | — |
| `request-pages` | `generic-http` | — | `server-dependent` | — | — |
| `resources alias` | `local` | — | `local` | — | — |
| `resources bind` | `local` | — | `local` | — | — |
| `resources clone` | `local` | — | `local` | — | — |
| `resources create` | `local` | — | `local` | — | — |
| `resources diff` | `local` | — | `local` | — | — |
| `resources list` | `local` | — | `local` | — | — |
| `resources move` | `local` | — | `local` | — | — |
| `resources prune` | `local` | — | `local` | — | — |
| `resources push` | `local` | — | `local` | — | — |
| `resources register` | `local` | — | `local` | — | — |
| `resources unregister` | `local` | — | `local` | — | — |
| `resources used-by` | `local` | — | `local` | — | — |
| `resources validate` | `local` | — | `local` | — | — |
| `runtime agent sessions` | `http` | `GET /runtime/agents/{agent_id}/sessions` | `observed` | — | cursor-has-next |
| `runtime run cancel` | `http` | `POST /runtime/runs/{run_id}/cancel` | `observed` | — | — |
| `runtime run get` | `http` | `GET /runtime/runs/{run_id}` | `observed` | — | — |
| `runtime run invocations` | `http` | `GET /runtime/runs/{run_id}/model-invocations` | `observed` | — | — |
| `runtime run list` | `http` | `GET /runtime/runs` | `observed` | — | — |
| `runtime run rerun` | `http` | `POST /runtime/runs/{run_id}/rerun` | `observed` | — | — |
| `runtime session create` | `http` | `POST /runtime/sessions` | `observed` | — | — |
| `runtime session messages` | `http` | `GET /runtime/sessions/{session_id}/messages` | `observed` | — | — |
| `runtime target active` | `runtime-sdk` | — | `server-dependent` | — | — |
| `runtime target cancel` | `runtime-sdk` | — | `server-dependent` | — | — |
| `runtime target observe` | `runtime-sdk` | — | `server-dependent` | — | — |
| `runtime target run` | `runtime-sdk` | — | `server-dependent` | — | — |
| `runtime target stream` | `runtime-sdk` | — | `server-dependent` | — | — |
| `schema` | `local` | — | `local` | — | — |
| `server-schema` | `diagnostic-http` | — | `server-dependent` | — | — |
| `skill` | `local` | — | `local` | — | — |
| `skills agents` | `local` | — | `local` | — | — |
| `skills install` | `local` | — | `local` | — | — |
| `skills status` | `local` | — | `local` | — | — |
| `skills uninstall` | `local` | — | `local` | — | — |
| `surface` | `local` | — | `local` | — | — |
| `tool` | `local` | — | `local` | — | — |
| `trust pin` | `local` | — | `local` | — | — |
| `trust refresh` | `local` | — | `local` | — | — |
| `validate-input` | `diagnostic-http` | — | `server-dependent` | — | — |
| `version` | `local` | — | `local` | — | — |
| `workspace authority audit` | `http` | `GET /identity/workspaces/{workspace_id}/authority-audit` | `proposed` | — | cursor-complete |
| `workspace authority category archive` | `http` | `POST /identity/workspaces/{workspace_id}/authority-categories/{category_id}/archive` | `proposed` | — | — |
| `workspace authority category clone` | `http` | `POST /identity/workspaces/{workspace_id}/authority-categories/{category_id}/clone` | `proposed` | — | — |
| `workspace authority category create` | `http` | `POST /identity/workspaces/{workspace_id}/authority-categories` | `proposed` | — | — |
| `workspace authority category delete` | `http` | `DELETE /identity/workspaces/{workspace_id}/authority-categories/{category_id}` | `proposed` | — | — |
| `workspace authority category diff` | `composition` | — | `server-dependent` | — | — |
| `workspace authority category get` | `http` | `GET /identity/workspaces/{workspace_id}/authority-categories/{category_id}` | `proposed` | — | — |
| `workspace authority category history` | `http` | `GET /identity/workspaces/{workspace_id}/authority-categories/{category_id}/versions` | `proposed` | — | revision-complete |
| `workspace authority category list` | `http` | `GET /identity/workspaces/{workspace_id}/authority-categories` | `proposed` | — | cursor-complete |
| `workspace authority category update` | `http` | `PATCH /identity/workspaces/{workspace_id}/authority-categories/{category_id}` | `proposed` | — | — |
| `workspace control-key create` | `http` | `POST /core/workspaces/{workspace_id}/control-keys` | `branch-dependent` | keys:create | — |
| `workspace control-key list` | `http` | `GET /core/workspaces/{workspace_id}/control-keys` | `branch-dependent` | keys:read | — |
| `workspace control-key revoke` | `http` | `POST /core/workspaces/{workspace_id}/control-keys/{control_key_id}/revoke` | `branch-dependent` | keys:revoke | — |
| `workspace control-key rotate` | `http` | `POST /core/workspaces/{workspace_id}/control-keys/{control_key_id}/rotate` | `branch-dependent` | keys:rotate | — |
| `workspace control-key update` | `http` | `PATCH /core/workspaces/{workspace_id}/control-keys/{control_key_id}` | `branch-dependent` | keys:update | — |
| `workspace create` | `http` | `POST /identity/workspaces` | `observed` | — | — |
| `workspace get` | `http` | `GET /identity/workspaces/{workspace_id}` | `observed` | — | — |
| `workspace invite cancel` | `http` | `DELETE /identity/workspaces/{workspace_id}/invites/{invite_id}` | `observed` | — | — |
| `workspace invite create` | `http` | `POST /identity/workspaces/{workspace_id}/invites` | `observed` | — | — |
| `workspace invite list` | `http` | `GET /identity/workspaces/{workspace_id}/invites` | `observed` | — | — |
| `workspace list` | `http` | `GET /identity/workspaces` | `observed` | — | — |
| `workspace member list` | `http` | `GET /identity/workspaces/{workspace_id}/members` | `observed` | — | — |
| `workspace member remove` | `http` | `DELETE /identity/workspaces/{workspace_id}/members/{user_id}` | `observed` | — | — |
| `workspace project-access list` | `http` | `GET /core/workspaces/{workspace_id}/project-access` | `observed` | — | — |
| `workspace update` | `http` | `PATCH /identity/workspaces/{workspace_id}` | `observed` | — | — |
