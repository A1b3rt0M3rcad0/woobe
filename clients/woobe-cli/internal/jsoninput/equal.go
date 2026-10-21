package jsoninput

import (
	"encoding/json"
	"fmt"
	"math"
	"math/big"
	"reflect"
	"strconv"
	"strings"
)

// Comparator compares decoded JSON values with exact decimal number semantics.
// Its zero value shares a 100,000-node budget across comparisons. Reuse one
// comparator for all fields in a resource comparison.
type Comparator struct{ work int }
type decimal struct{ value string }

func (c *Comparator) Equal(a, b any) (bool, error) {
	x, err := c.normalize(a, 0)
	if err != nil {
		return false, err
	}
	y, err := c.normalize(b, 0)
	if err != nil {
		return false, err
	}
	return reflect.DeepEqual(x, y), nil
}

func (c *Comparator) normalize(v any, depth int) (any, error) {
	c.work++
	if c.work > 100000 || depth > 128 {
		return nil, fmt.Errorf("state comparison exceeds work or depth limit")
	}
	switch x := v.(type) {
	case nil, bool, string:
		return x, nil
	case json.Number:
		return exactDecimal(x.String())
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return nil, fmt.Errorf("state comparison requires finite JSON numbers")
		}
		return exactDecimal(strconv.FormatFloat(x, 'g', -1, 64))
	case []any:
		if len(x) > 100000-c.work {
			return nil, fmt.Errorf("state comparison exceeds work limit")
		}
		out := make([]any, len(x))
		for i, child := range x {
			n, err := c.normalize(child, depth+1)
			if err != nil {
				return nil, err
			}
			out[i] = n
		}
		return out, nil
	case map[string]any:
		if len(x) > 100000-c.work {
			return nil, fmt.Errorf("state comparison exceeds work limit")
		}
		out := make(map[string]any, len(x))
		for key, child := range x {
			n, err := c.normalize(child, depth+1)
			if err != nil {
				return nil, err
			}
			out[key] = n
		}
		return out, nil
	default:
		return nil, fmt.Errorf("state comparison requires decoded JSON values")
	}
}

func exactDecimal(text string) (decimal, error) {
	if len(text) == 0 || len(text) > 4096 || strings.TrimSpace(text) != text || !json.Valid([]byte(text)) || (text[0] != '-' && (text[0] < '0' || text[0] > '9')) {
		return decimal{}, fmt.Errorf("state comparison number is invalid or exceeds 4096 characters")
	}
	if i := strings.IndexAny(text, "eE"); i >= 0 {
		exp, err := strconv.Atoi(text[i+1:])
		if err != nil || exp > 4096 || exp < -4096 {
			return decimal{}, fmt.Errorf("state comparison number exponent exceeds 4096")
		}
	}
	r, ok := new(big.Rat).SetString(text)
	if !ok {
		return decimal{}, fmt.Errorf("state comparison number is unsupported")
	}
	return decimal{r.RatString()}, nil
}
