package controlplane

// Only exact, fixed owner messages are classified. Never copy arbitrary server
// messages, input snapshots, Provider failures or protected values to output.
func packageExportIncompleteMessage(code, message string) string {
	switch code {
	case "ASAC_ORIGIN_MISMATCH":
		return "Local source belongs to another target; preserve local edits and history, then explicitly pull the intended Agent/Network to establish its own capture before a new deploy"
	case "ASAC_SOURCE_CHANGED":
		return "Native Draft changed since capture; preserve local edits and history, inspect the current Draft and explicitly recapture/reconcile before a new deploy"
	case "ASAC_HISTORY_INCOMPLETE":
		return "Revision ancestors are not accepted by this target; reconcile prior operations and checkpoint exact parents in order in matching isolated Drafts; local history verify does not prove remote acceptance"

	case "ASAC_CANDIDATE_BINDING_UNAVAILABLE":
		return "Stage blocked: the reported component has no accepted native identity in this registry; inspect bindings recover --dry-run, establish the closure with a managed push, then update/checkpoint the isolated Draft before staging"
	case "PACKAGE_EXPORT_NETWORK_BINDING":
		return "Network export blocked: an Agent or pinned snapshot is unavailable; inspect the reported node binding"
	case "PACKAGE_EXPORT_NETWORK_CONSTITUENT":
		return "Network export blocked: a constituent has no complete exact Agent snapshot; inspect the reported node and its selected Model/dependencies"
	case "PACKAGE_EXPORT_NETWORK_INTEGRITY":
		return "Network export blocked: saved snapshot integrity differs; preserve the request ID and investigate the original version"
	case "PACKAGE_EXPORT_NETWORK_DEFINITION":
		return "Network export blocked: saved definition is incompatible with the portable graph contract; inspect its topology and bindings"
	case "PACKAGE_EXPORT_NETWORK_CONFLICT":
		return "Network export blocked: saved snapshot or dependencies conflict; preserve the request ID for diagnosis"
	}
	if code != "PACKAGE_EXPORT_INCOMPLETE" {
		return ""
	}
	switch message {
	case "Snapshot has no complete ModelSpec":
		return "Package export blocked: selected snapshot has no complete ModelSpec; inspect the Agent Model configuration in the selected environment"
	case "Snapshot credential intent is unavailable":
		return "Package export blocked: selected snapshot has no Provider credential binding; inspect its Model and Provider configuration"
	case "Snapshot credential provider differs":
		return "Package export blocked: snapshot Model and credential use different Providers; inspect their bindings"
	case "Project Environment requirement is unavailable":
		return "Package export blocked: a required Project Environment field is unavailable; inspect the reported requirement path"
	}
	return ""
}
