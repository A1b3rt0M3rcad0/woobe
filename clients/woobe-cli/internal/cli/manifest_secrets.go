package cli

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func stepSecretNames(s manifest.Step) []string {
	var value any
	d := json.NewDecoder(bytes.NewReader(s.Body))
	d.UseNumber()
	if d.Decode(&value) != nil {
		return nil
	}
	return manifest.SecretReferences(value)
}

func secretConfigurationCommand(command string) bool {
	switch command {
	case "project tool create", "project tool update", "project provider-credential create", "project provider-credential update", "project provider-credential rotate":
		return true
	}
	return false
}

func (a *App) manifestSecretSnapshot(d manifest.Document) (map[string]string, map[string]string, error) {
	values, hashes := map[string]string{}, map[string]string{}
	for _, s := range d.Steps {
		for _, name := range stepSecretNames(s) {
			if _, ok := values[name]; ok {
				continue
			}
			value, e := a.store().Get(name)
			if e != nil {
				return nil, nil, output.New(output.Normalize(e).Code, "protected manifest credential unavailable")
			}
			values[name] = value
			sum := sha256.Sum256([]byte(value))
			hashes[name] = hex.EncodeToString(sum[:])
		}
	}
	return values, hashes, nil
}

func sameSecretSnapshot(a, b map[string]string) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if b[k] != v {
			return false
		}
	}
	return true
}

func resolveStepSecrets(s manifest.Step, values map[string]string) (manifest.Step, error) {
	if len(stepSecretNames(s)) == 0 {
		return s, nil
	}
	var body any
	d := json.NewDecoder(bytes.NewReader(s.Body))
	d.UseNumber()
	if e := d.Decode(&body); e != nil {
		return s, output.New(2, "invalid manifest body")
	}
	body, e := manifest.ResolveSecrets(body, values)
	if e != nil {
		return s, output.New(3, "protected manifest credential unavailable")
	}
	s.Body, e = json.Marshal(body)
	return s, e
}
