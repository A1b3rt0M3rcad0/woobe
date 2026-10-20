# Complete command output audit

Every discovered command is listed: 359 entries, 228 successful measured scenarios.

Measurements are UTF-8 bytes from the real executable, comparing full JSON to compact. HTTP commands use a loopback presentation fixture; except the Agent records, response shapes are generic probes, not authoritative Woobe DTOs. These numbers are illustrative and do not qualify actual backend writes or estimate production token counts. Local scenarios use temporary state. All remote writes go only to the fixture API. Blank sizes mean not measured, never zero. Scripts, aliases and streams have explicit classifications.

[Download CSV](OUTPUT_AUDIT.csv). More realistic six-command examples are in [OUTPUT_EXAMPLES.md](OUTPUT_EXAMPLES.md).

| Command | Previous bytes | Compact bytes | Reduction | Scenario / limitation |
| --- | ---: | ---: | ---: | --- |
| `agent` | — | — | — | delegated: Alias; use the corresponding canonical operation row |
| `auth credential import` | 142 | 35 | 75.4% | local/diagnostic scenario |
| `auth credential list` | 143 | 36 | 74.8% | local/diagnostic scenario |
| `auth credential remove` | 142 | 35 | 75.4% | local/diagnostic scenario |
| `auth invite accept` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `auth invite list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `auth key inspect` | 796 | 240 | 69.8% | HTTP presentation fixture |
| `auth login` | 450 | 247 | 45.1% | HTTP presentation fixture |
| `auth logout` | 170 | 63 | 62.9% | local/diagnostic scenario |
| `auth refresh` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `auth register` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `auth status` | 1027 | 437 | 57.4% | HTTP presentation fixture |
| `completion bash` | — | — | — | preserved script: Shell script, not a JSON response; compact does not apply |
| `completion fish` | — | — | — | preserved script: Shell script, not a JSON response; compact does not apply |
| `completion powershell` | — | — | — | preserved script: Shell script, not a JSON response; compact does not apply |
| `completion zsh` | — | — | — | preserved script: Shell script, not a JSON response; compact does not apply |
| `config check` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `config show` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `context create` | 153 | 46 | 69.9% | local/diagnostic scenario |
| `context credential attach` | 154 | 47 | 69.5% | local/diagnostic scenario |
| `context credential detach` | 154 | 47 | 69.5% | local/diagnostic scenario |
| `context delete` | 154 | 47 | 69.5% | local/diagnostic scenario |
| `context list` | 311 | 183 | 41.2% | local/diagnostic scenario |
| `context project select` | 202 | 95 | 53.0% | local/diagnostic scenario: Dry-run selection; authentication/project mutation is not executed |
| `context runtime-credential attach` | 154 | 47 | 69.5% | local/diagnostic scenario |
| `context runtime-credential detach` | 154 | 47 | 69.5% | local/diagnostic scenario |
| `context set` | 151 | 44 | 70.9% | local/diagnostic scenario |
| `context show` | 330 | 151 | 54.2% | local/diagnostic scenario |
| `context unset` | 154 | 47 | 69.5% | local/diagnostic scenario |
| `context update` | 154 | 47 | 69.5% | local/diagnostic scenario |
| `context use` | 151 | 44 | 70.9% | local/diagnostic scenario |
| `control-key` | — | — | — | delegated: Alias; use the corresponding canonical operation row |
| `develop agent activate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent archive` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent bindings` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent candidate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent checkout` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent create` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent current` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent delete` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent deployment` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent diff` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent draft` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent evaluation` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent git-attest` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent git-proof` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent heads` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent history` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent lease` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent publication` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent publish` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent pull` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent push` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent rebase` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent receipt` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent reconcile` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent revision` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent rollback` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent stage` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent status` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent test` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop agent validate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network activate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network bindings` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network candidate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network checkout` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network create` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network current` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network deployment` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network diff` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network draft` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network evaluation` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network git-attest` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network git-proof` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network heads` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network history` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network lease` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network publication` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network publish` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network pull` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network push` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network rebase` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network receipt` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network reconcile` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network revision` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network rollback` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network stage` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network status` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network test` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop network validate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop surface create` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop surface diff` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop surface pull` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop surface push` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop surface status` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `develop surface validate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `doctor` | 56735 | 224 | 99.6% | local/diagnostic scenario |
| `export` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `help` | 1431110 | 40577 | 97.2% | local/diagnostic scenario |
| `init` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `instance bootstrap` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `instance status` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `knowledge` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `manifest apply` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `manifest capture` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `manifest compile` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `manifest diff` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `manifest export` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `manifest kinds` | 2005 | 1898 | 5.3% | local/diagnostic scenario |
| `manifest plan` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `manifest preflight` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `manifest reconcile` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `manifest status` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `manifest validate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `model` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `network` | — | — | — | delegated: Alias; use the corresponding canonical operation row |
| `package bindings` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `package cancel` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `package doctor` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `package edit` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `package export agent` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `package export network` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `package import` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `package plan` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `package resume` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `package seal` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `package status` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `package validate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `permission check` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `permission effective` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `permission explain` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `permission list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project access grant` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project access revoke` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent contract create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent contract get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent contract list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project agent contract update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent create` | 969 | 230 | 76.3% | HTTP presentation fixture |
| `project agent delete` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent environment list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project agent environment update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent export` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `project agent get` | 969 | 230 | 76.3% | HTTP presentation fixture |
| `project agent git-attestation create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent git-attestation get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent knowledge bind` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent knowledge list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project agent knowledge unbind` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent knowledge version-create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent knowledge version-list` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent list` | 1722 | 212 | 87.7% | HTTP presentation fixture |
| `project agent model-config create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent model-config get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent model-config list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project agent prompt create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent prompt get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent prompt list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project agent release activations` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release delete` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release list` | 452 | 111 | 75.4% | HTTP presentation fixture |
| `project agent release promote` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release rollback` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release run-test` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release test` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent release tests` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent signed-receipt get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project agent tool list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project agent update` | 969 | 230 | 76.3% | HTTP presentation fixture |
| `project agent usage daily` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project api-key create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project api-key list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project api-key revoke` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project api-key rotate` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project api-key update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project catalog context-assemblers` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project catalog execution-strategies` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project catalog knowledge-strategies` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project catalog rag-strategies` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project env list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project env set` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project env unset` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge collection create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge collection get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge collection list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project knowledge collection overview` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge collection update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge collection vector-preview` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge document create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge document delete` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge document get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge document list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project knowledge document upload` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `project knowledge search` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge snapshot create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge snapshot get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project knowledge snapshot list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project lifecycle operation` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project lifecycle show` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project lifecycle update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project member grant` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project member list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project member revoke` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network activation create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network activation list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project network create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network draft update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network environment list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project network environment update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network execution cancel` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network execution diagnostics` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network execution events` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network execution snapshot` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network git-attestation create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network git-attestation get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network list` | 452 | 97 | 78.5% | HTTP presentation fixture |
| `project network management external-context` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network management versions` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network promotion create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network promotion preview` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network rollback` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network session create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network session list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project network session messages` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project network session reset-context` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network signed-receipt get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project network version list` | 452 | 93 | 79.4% | HTTP presentation fixture |
| `project overview` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-credential create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-credential list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project provider-credential revoke` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-credential rotate` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-credential update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-credential usage` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-model create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-model get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-model list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project provider-model update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project provider-model usage` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project run list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project runtime-key create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project skill create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project skill list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project skill version create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project skill version get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project skill version list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project surface access-key create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface access-key list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project surface access-key revoke` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface access-key rotate` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface activate` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface activity` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface archive` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface disable` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project surface release` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface sessions` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project surface test-sessions` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project surface update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool delete` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool execute` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project tool mcp bulk` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp discover` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp oauth complete` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp oauth device-poll` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp oauth device-start` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp oauth disconnect` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp oauth start` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp oauth status` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp refresh` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool mcp set` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool status` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool test` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project tool usage-impact` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project trace get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project trace list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `project update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project usage daily` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `project usage summary` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `provider` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `receipt verify` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `request` | 450 | 175 | 61.1% | local/diagnostic scenario |
| `request-pages` | 737 | 368 | 50.1% | local/diagnostic scenario |
| `resources alias` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources bind` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources clone` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources create` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources diff` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources list` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources move` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources prune` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources push` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources register` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources unregister` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources used-by` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `resources validate` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `runtime agent sessions` | 692 | 400 | 42.2% | HTTP presentation fixture |
| `runtime run cancel` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `runtime run get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `runtime run invocations` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `runtime run list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `runtime run rerun` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `runtime session create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `runtime session messages` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `runtime target active` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `runtime target cancel` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `runtime target observe` | — | — | — | preserved stream: JSONL event protocol; compact is intentionally unsupported |
| `runtime target run` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `runtime target stream` | — | — | — | preserved stream: JSONL event protocol; compact is intentionally unsupported |
| `schema` | 6968 | 6907 | 0.9% | local/diagnostic scenario |
| `server-schema` | 5903 | 5842 | 1.0% | local/diagnostic scenario |
| `skill` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `skills agents` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `skills install` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `skills status` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `skills uninstall` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `surface` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `tool` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `trust pin` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `trust refresh` | — | — | — | not measured: Requires a dedicated valid input/state scenario; no invented reduction |
| `validate-input` | 549 | 370 | 32.6% | local/diagnostic scenario |
| `version` | 261 | 133 | 49.0% | local/diagnostic scenario |
| `workspace authority audit` | 692 | 400 | 42.2% | HTTP presentation fixture |
| `workspace authority category archive` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace authority category clone` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace authority category create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace authority category delete` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace authority category diff` | — | — | — | not measured: Requires a dedicated operation/recovery/SDK scenario; no invented reduction |
| `workspace authority category get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace authority category history` | 694 | 402 | 42.1% | HTTP presentation fixture |
| `workspace authority category list` | 692 | 400 | 42.2% | HTTP presentation fixture |
| `workspace authority category update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace control-key create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace control-key list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `workspace control-key revoke` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace control-key rotate` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace control-key update` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace get` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace invite cancel` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace invite create` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace invite list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `workspace list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `workspace member list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `workspace member remove` | 450 | 175 | 61.1% | HTTP presentation fixture |
| `workspace project-access list` | 452 | 177 | 60.8% | HTTP presentation fixture |
| `workspace update` | 450 | 175 | 61.1% | HTTP presentation fixture |
