package woobe

type RuntimeContractIssue struct {
	Code     string `json:"code"`
	Field    string `json:"field"`
	Expected any    `json:"expected,omitempty"`
	Received any    `json:"received,omitempty"`
}

type RuntimeContractValidation struct {
	Valid        bool                   `json:"valid"`
	Expected     map[string]any         `json:"expected"`
	Received     map[string]any         `json:"received"`
	ExpectedHash string                 `json:"expected_hash"`
	ReceivedHash string                 `json:"received_hash"`
	Issues       []RuntimeContractIssue `json:"issues"`
}

type RuntimeContractsValidation struct {
	Valid           bool                      `json:"valid"`
	TargetType      string                    `json:"target_type"`
	TargetID        string                    `json:"target_id"`
	Environment     string                    `json:"environment"`
	ReleaseID       string                    `json:"release_id"`
	ReleaseVersion  string                    `json:"release_version"`
	OutputContract  RuntimeContractValidation `json:"output_contract"`
	ExternalContext RuntimeContractValidation `json:"external_context"`
}

type ContractValidationRequest struct {
	OutputContract  map[string]any `json:"output_contract"`
	ExternalContext map[string]any `json:"external_context"`
}
