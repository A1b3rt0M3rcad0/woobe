package jsoninput

import (
	"encoding/json"
	"math"
	"strings"
	"testing"
)

func TestComparatorPreservesJSONMeaning(t *testing.T) {
	for _, tc := range []struct {
		a, b  any
		equal bool
	}{
		{json.Number("1"), json.Number("1.0"), true},
		{json.Number("1e0"), json.Number("1.00"), true},
		{json.Number("-0"), json.Number("0.0"), true},
		{json.Number("9007199254740992"), json.Number("9007199254740993"), false},
		{json.Number("0.10000000000000000001"), json.Number("0.1"), false},
		{float64(1), json.Number("1.0"), true},
		{"1", json.Number("1"), false},
		{nil, map[string]any{}, false},
		{map[string]any{}, map[string]any{"x": nil}, false},
		{[]any{json.Number("1"), "x"}, []any{json.Number("1e0"), "x"}, true},
		{[]any{"x", "y"}, []any{"y", "x"}, false},
		{map[string]any{"x": []any{json.Number("1")}}, map[string]any{"x": []any{json.Number("1.0")}}, true},
	} {
		got, err := (&Comparator{}).Equal(tc.a, tc.b)
		if err != nil || got != tc.equal {
			t.Fatalf("%v / %v: %v, %v", tc.a, tc.b, got, err)
		}
	}
}
func TestComparatorRejectsUnsupportedValuesEvenOnMismatch(t *testing.T) {
	deep := any(nil)
	for i := 0; i < 130; i++ {
		deep = []any{deep}
	}
	for _, v := range []any{json.Number("1e4097"), json.Number("1e-4097"), json.Number(strings.Repeat("1", 4097)), json.Number("01"), json.Number(" 1"), json.Number("null"), math.Inf(1), math.NaN(), 1, deep, []any{"different", json.Number("1e9999")}} {
		if _, err := (&Comparator{}).Equal(nil, v); err == nil {
			t.Fatalf("accepted %T", v)
		}
	}
}
func TestComparatorSharesResourceWorkBudget(t *testing.T) {
	c := &Comparator{}
	for i := 0; i < 50000; i++ {
		if _, err := c.Equal(nil, nil); err != nil {
			t.Fatal(i, err)
		}
	}
	if _, err := c.Equal(nil, nil); err == nil {
		t.Fatal("budget was reset")
	}
}
