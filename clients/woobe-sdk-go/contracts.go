package woobe

import (
	"mime"
	"strings"
	"unicode/utf8"
)

// ContentPart is the additive Runtime Protocol content shape. Text and exact
// Artifact revision references remain distinct so the server can reauthorize
// every revision when it accepts the Run.
type ContentPart struct {
	Type          string             `json:"type"`
	Text          string             `json:"text,omitempty"`
	Ref           *ArtifactReference `json:"ref,omitempty"`
	MediaTypeHint string             `json:"media_type_hint,omitempty"`
}

type ArtifactRef = ArtifactReference
type SourceRef = ArtifactSource

func TextPart(text string) ContentPart { return ContentPart{Type: "text", Text: text} }

// ValidateContentParts checks the bounded Runtime Protocol representation
// before a request is sent. It is exposed so adapters can validate dry-runs
// with the same rules as Run and Chat.
func ValidateContentParts(parts []ContentPart) error { return validateContentParts(parts) }

func ArtifactPart(reference ArtifactReference, mediaTypeHint string) ContentPart {
	return ContentPart{Type: "artifact", Ref: &reference, MediaTypeHint: mediaTypeHint}
}

func validateContentParts(parts []ContentPart) error {
	if len(parts) == 0 || len(parts) > 32 {
		return &ProtocolError{Message: "content_parts must contain 1–32 parts"}
	}
	textCharacters, artifactCount := 0, 0
	hasContent := false
	for _, part := range parts {
		switch part.Type {
		case "text":
			if part.Ref != nil || part.MediaTypeHint != "" || part.Text == "" {
				return &ProtocolError{Message: "text content parts require only non-empty text"}
			}
			characters := utf8.RuneCountInString(part.Text)
			if characters > 32768 {
				return &ProtocolError{Message: "a text content part exceeds 32768 characters"}
			}
			textCharacters += characters
			hasContent = hasContent || strings.TrimSpace(part.Text) != ""
		case "artifact":
			if part.Text != "" || part.Ref == nil {
				return &ProtocolError{Message: "Artifact content parts require exactly one revision reference"}
			}
			if err := requiredArtifactID("artifactID", part.Ref.ArtifactID); err != nil {
				return err
			}
			if err := requiredArtifactID("revisionID", part.Ref.RevisionID); err != nil {
				return err
			}
			if len(part.MediaTypeHint) > 255 {
				return &ProtocolError{Message: "Artifact media type hint exceeds 255 characters"}
			}
			if part.MediaTypeHint != "" {
				if !isASCII(part.MediaTypeHint) || strings.ContainsAny(part.MediaTypeHint, "\r\n\x00") {
					return &ProtocolError{Message: "invalid Artifact media type hint"}
				}
				if _, _, err := mime.ParseMediaType(part.MediaTypeHint); err != nil {
					return &ProtocolError{Message: "invalid Artifact media type hint", Cause: err}
				}
			}
			artifactCount++
			hasContent = true
		default:
			return &ProtocolError{Message: "unsupported runtime content part type"}
		}
	}
	if textCharacters > 32768 {
		return &ProtocolError{Message: "combined message text exceeds 32768 characters"}
	}
	if artifactCount > 16 {
		return &ProtocolError{Message: "a message can reference at most 16 Artifacts"}
	}
	if !hasContent {
		return &ProtocolError{Message: "content_parts must contain text or an Artifact reference"}
	}
	return nil
}

func cloneContentParts(parts []ContentPart) []ContentPart {
	if parts == nil {
		return nil
	}
	cloned := append([]ContentPart(nil), parts...)
	for index := range cloned {
		if cloned[index].Ref != nil {
			copy := *cloned[index].Ref
			cloned[index].Ref = &copy
		}
	}
	return cloned
}

func isASCII(value string) bool {
	for index := 0; index < len(value); index++ {
		if value[index] >= utf8.RuneSelf {
			return false
		}
	}
	return true
}

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
