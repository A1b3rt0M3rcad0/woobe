package schemacheck

// Required readOnly properties belong to responses, even through references or
// allOf. Other compositions retain their required rules; no branch is guessed.
func requestReadOnly(raw, doc any, p string, depth int, budget *int) (bool, error) {
	*budget--
	if *budget < 0 || depth > 64 {
		return false, unsupported(p, "request direction evaluation budget exceeded")
	}
	s, ok := raw.(map[string]any)
	if !ok {
		return false, nil
	}
	if s["readOnly"] == true {
		return true, nil
	}
	if ref, ok := s["$ref"].(string); ok {
		target, e := Resolve(doc, ref)
		if e != nil {
			return false, e
		}
		ro, e := requestReadOnly(target, doc, p, depth+1, budget)
		if e != nil || ro {
			return ro, e
		}
	}
	if branches, ok := s["allOf"].([]any); ok {
		for _, sub := range branches {
			ro, e := requestReadOnly(sub, doc, p, depth+1, budget)
			if e != nil || ro {
				return ro, e
			}
		}
	}
	return false, nil
}
