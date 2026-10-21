package packagefmt

import (
	"io"
	"os"
	"regexp"
	"strings"
)

var bindingID = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

// LoadBindings resolves only public identities and protected references. It must
// never open a credential store or include material in the portable bundle.
func LoadBindings(path string, shortcuts []string, graph *Graph) (map[string]any, error) {
	version := Text(graph.Manifest["schema_version"])
	if version == "" {
		version = "1.0"
	}
	groups := []string{"credentials", "project_environment", "secrets", "knowledge"}
	if version == "2.0" {
		groups = []string{"credentials", "project_environment", "knowledge"}
	}
	document := map[string]any{"format": "woobe-package", "schema_version": version, "kind": "ImportBindings",
		"metadata": map[string]any{"name": "Destination"}, "spec": map[string]any{}}
	if path != "" {
		info, err := os.Lstat(path)
		if err != nil || !info.Mode().IsRegular() || info.Size() > 2<<20 {
			return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_INVALID", Message: "Bindings must be a bounded regular file"}
		}
		file, err := openBindingsRead(path)
		if err != nil {
			return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_INVALID", Message: "Bindings file is unavailable"}
		}
		opened, statErr := file.Stat()
		if statErr != nil || !os.SameFile(info, opened) || !opened.Mode().IsRegular() {
			_ = file.Close()
			return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_INVALID", Message: "Bindings file changed while opening"}
		}
		data, readErr := io.ReadAll(io.LimitReader(file, 2<<20+1))
		_ = file.Close()
		if readErr != nil || len(data) > 2<<20 {
			return nil, &Diagnostic{Code: "PACKAGE_LIMIT_EXCEEDED", Message: "Bindings file exceeds 2 MiB"}
		}
		parsed, err := Decode(data, path)
		if err != nil {
			return nil, err
		}
		if err = Validate(parsed); err != nil {
			return nil, err
		}
		if parsed.Value["kind"] != "ImportBindings" {
			return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_INVALID", Message: "Expected ImportBindings"}
		}
		document = parsed.Value
	}
	if document["schema_version"] != version {
		return nil, &Diagnostic{Code: "PACKAGE_SCHEMA_UNSUPPORTED", Message: "Bindings must match the package schema version"}
	}
	spec := Object(document["spec"])
	for _, shortcut := range shortcuts {
		name, value, ok := strings.Cut(shortcut, "=")
		group, alias, typed := strings.Cut(name, ".")
		if !ok || !typed || alias == "" || (group != "credential" && !(group == "configuration" && version == "2.0")) || (group == "credential" && !bindingID.MatchString(value)) {
			return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_INVALID", Message: "--bind requires credential.ALIAS=UUID or configuration.KEY=REMOTE_KEY (schema 2.0)"}
		}
		plural, field := "credentials", "credential_id"
		if group == "configuration" {
			plural, field = "project_environment", "existing_key"
		}
		credentials := Object(spec[plural])
		if credentials == nil {
			credentials = map[string]any{}
			spec[plural] = credentials
		}
		if _, exists := credentials[alias]; exists {
			return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_DUPLICATE", Message: "Binding alias is declared more than once"}
		}
		credentials[alias] = map[string]any{field: value}
	}
	requires := Requirements(graph.Manifest)
	if version == "2.0" && path == "" {
		for _, group := range []string{"credentials", "project_environment"} {
			supplied := Object(spec[group])
			if supplied == nil {
				supplied = map[string]any{}
				spec[group] = supplied
			}
			field := "ref"
			if group == "project_environment" {
				field = "key"
			}
			for _, raw := range List(requires[group]) {
				alias := Text(Object(raw)[field])
				if _, exists := supplied[alias]; !exists {
					supplied[alias] = map[string]any{"create": true}
				}
			}
		}
	}
	parsed := &Document{Value: document, File: path}
	if err := Validate(parsed); err != nil {
		return nil, err
	}
	for _, group := range groups {
		aliases := map[string]bool{}
		items, _ := requires[group].([]any)
		for _, item := range items {
			field := "ref"
			if group == "project_environment" {
				field = "key"
			}
			alias, _ := Object(item)[field].(string)
			if aliases[alias] {
				return nil, &Diagnostic{Code: "PACKAGE_REQUIREMENT_DUPLICATE", Message: "Destination requirement is duplicated"}
			}
			aliases[alias] = true
		}
		supplied := Object(spec[group])
		if len(supplied) != len(aliases) {
			return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_INCOMPLETE", Message: "Bindings must match declared destination requirements"}
		}
		for alias := range supplied {
			if !aliases[alias] {
				return nil, &Diagnostic{Code: "PACKAGE_BINDINGS_INCOMPLETE", Message: "Binding alias is not declared by the package"}
			}
		}
	}
	metadata := Object(document["metadata"])
	if _, exists := metadata["description"]; !exists {
		metadata["description"] = ""
	}
	for _, group := range groups {
		values := Object(spec[group])
		if values == nil {
			values = map[string]any{}
			spec[group] = values
		}
		for _, raw := range values {
			if version == "2.0" && group != "knowledge" {
				if _, exists := Object(raw)["create"]; !exists {
					Object(raw)["create"] = false
				}
			}
			for key, value := range Object(raw) {
				if value == nil {
					delete(Object(raw), key)
				}
			}
		}
	}
	return document, nil
}
