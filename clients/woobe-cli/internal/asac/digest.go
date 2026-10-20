// Package asac implements the versioned, portable authorship record contract.
// It does not own remote lifecycle or authority.
package asac

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"sort"
	"strconv"
	"strings"
)

const Version = "1.0"

// Digest uses a type-tagged ASCII canonical tree. Strings are UTF-8 hex and
// numbers are exact reduced fractions, avoiding Go/Python float and escaping
// differences. Missing keys, nulls and list order retain distinct meanings.
func Digest(scope string, value any) (string, error) {
	data, err := json.Marshal(value)
	if err != nil {
		return "", err
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.UseNumber()
	var v any
	if err = d.Decode(&v); err != nil {
		return "", err
	}
	tree, err := canonical(v, 0)
	if err != nil {
		return "", err
	}
	data, err = json.Marshal(tree)
	if err != nil {
		return "", err
	}
	hash := sha256.Sum256(append([]byte("woobe-asac@1.0/"+scope+"\n"), data...))
	return "sha256:" + hex.EncodeToString(hash[:]), nil
}

func canonical(v any, depth int) (any, error) {
	if depth > 128 {
		return nil, fmt.Errorf("ASaC nesting exceeds 128")
	}
	switch v := v.(type) {
	case nil:
		return []any{"null"}, nil
	case bool:
		return []any{"bool", v}, nil
	case string:
		return []any{"string", hex.EncodeToString([]byte(v))}, nil
	case json.Number:
		text := v.String()
		if len(text) > 4096 {
			return nil, fmt.Errorf("ASaC number exceeds canonical bounds")
		}
		if i := strings.IndexAny(text, "eE"); i >= 0 {
			exponent, err := strconv.Atoi(text[i+1:])
			if err != nil || exponent < -4096 || exponent > 4096 {
				return nil, fmt.Errorf("ASaC number exceeds canonical bounds")
			}
		}
		n, ok := new(big.Rat).SetString(text)
		if !ok {
			return nil, fmt.Errorf("invalid ASaC number")
		}
		return []any{"number", n.Num().String(), n.Denom().String()}, nil
	case []any:
		items := make([]any, 0, len(v))
		for _, item := range v {
			n, err := canonical(item, depth+1)
			if err != nil {
				return nil, err
			}
			items = append(items, n)
		}
		return []any{"array", items}, nil
	case map[string]any:
		keys := make([]string, 0, len(v))
		for k := range v {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		items := make([]any, 0, len(v))
		for _, k := range keys {
			n, err := canonical(v[k], depth+1)
			if err != nil {
				return nil, err
			}
			items = append(items, []any{hex.EncodeToString([]byte(k)), n})
		}
		return []any{"object", items}, nil
	default:
		return nil, fmt.Errorf("unsupported ASaC value")
	}
}
