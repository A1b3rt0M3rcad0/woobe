package cli

import (
	"crypto/sha256"
	"encoding/hex"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"os"
)

func (a *App) credentialFingerprint(v config.Context) (string, error) {
	key := os.Getenv("WOOBE_CONTROL_KEY")
	if v.Credential != "" {
		var e error
		key, e = a.store().Get(v.Credential)
		if e != nil {
			return "", e
		}
	}
	if key == "" {
		return "", nil
	}
	sum := sha256.Sum256([]byte(key))
	return hex.EncodeToString(sum[:]), nil
}
