package packagefmt

import (
	"bytes"
	"embed"
	"encoding/json"
	"fmt"
	"sync"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

//go:embed schemas/v1/catalog.json schemas/v1/catalog.sha256 schemas/v2/catalog.json schemas/v2/catalog.sha256
var schemaFiles embed.FS

type offlineLoader struct{}

func (offlineLoader) Load(string) (any, error) {
	return nil, fmt.Errorf("remote schema loading is forbidden")
}

var schemaOnce sync.Once
var compiled map[string]*jsonschema.Schema
var compilationError error

func CatalogBytes() []byte  { return VersionCatalogBytes("1.0") }
func CatalogDigest() string { return VersionCatalogDigest("1.0") }
func catalogPath(version string) string {
	switch version {
	case "1.0":
		return "schemas/v1/"
	case "2.0":
		return "schemas/v2/"
	}
	return ""
}
func VersionCatalogBytes(version string) []byte {
	prefix := catalogPath(version)
	if prefix == "" {
		return nil
	}
	data, _ := schemaFiles.ReadFile(prefix + "catalog.json")
	return data
}
func VersionCatalogDigest(version string) string {
	prefix := catalogPath(version)
	if prefix == "" {
		return ""
	}
	data, _ := schemaFiles.ReadFile(prefix + "catalog.sha256")
	return string(bytes.TrimSpace(data))
}
func loadSchemas() {
	compiled = map[string]*jsonschema.Schema{}
	for _, version := range []string{"1.0", "2.0"} {
		var catalog map[string]any
		decoder := json.NewDecoder(bytes.NewReader(VersionCatalogBytes(version)))
		decoder.UseNumber()
		if err := decoder.Decode(&catalog); err != nil {
			compilationError = err
			return
		}
		for kind, document := range catalog {
			compiler := jsonschema.NewCompiler()
			compiler.UseLoader(offlineLoader{})
			uri := "urn:woobe-package:" + version + ":" + kind
			if err := compiler.AddResource(uri, document); err != nil {
				compilationError = err
				return
			}
			schema, err := compiler.Compile(uri)
			if err != nil {
				compilationError = err
				return
			}
			compiled[version+":"+kind] = schema
		}
	}
}

func Validate(document *Document) error {
	failure := func(code, message, path string) error {
		location := document.Locations[path]
		return &Diagnostic{Code: code, Message: message, File: document.File, Path: path, Line: location.Line, Column: location.Column}
	}
	if document.Value["format"] != "woobe-package" || (document.Value["schema_version"] != "1.0" && document.Value["schema_version"] != "2.0") {
		return failure("PACKAGE_SCHEMA_UNSUPPORTED", "Expected woobe-package schema_version string 1.0 or 2.0", "")
	}
	kind, ok := document.Value["kind"].(string)
	if !ok {
		return failure("PACKAGE_SCHEMA_UNSUPPORTED", "Unknown component kind", "/kind")
	}
	schemaOnce.Do(loadSchemas)
	if compilationError != nil {
		return failure("PACKAGE_SCHEMA_UNSUPPORTED", "Embedded schema catalog is invalid", "")
	}
	schema, ok := compiled[document.Value["schema_version"].(string)+":"+kind]
	if !ok {
		return failure("PACKAGE_SCHEMA_UNSUPPORTED", "Unknown component kind", "/kind")
	}
	if err := schema.Validate(document.Value); err != nil {
		path := ""
		if validation, ok := err.(*jsonschema.ValidationError); ok {
			for len(validation.Causes) > 0 {
				validation = validation.Causes[0]
			}
			for _, part := range validation.InstanceLocation {
				path += "/" + part
			}
		}
		return failure("PACKAGE_SCHEMA_INVALID", "Document violates its component schema", path)
	}
	if document.Value["schema_version"] == "2.0" {
		spec := Object(document.Value["spec"])
		if kind == "Package" {
			for _, raw := range Object(spec["connections"]) {
				if !validateConfigurationAuthentication(Object(Object(raw)["authentication"]), true) {
					return failure("PACKAGE_SCHEMA_INVALID", "Invalid remote authentication fields", "/spec/connections")
				}
			}
		} else if kind == "Tool" {
			config := Object(spec["config"])
			if !validateConfigurationAuthentication(Object(config["authentication"]), false) {
				return failure("PACKAGE_SCHEMA_INVALID", "Invalid remote authentication fields", "/spec/config/authentication")
			}
			for _, raw := range List(config["routes"]) {
				if auth := Object(raw)["authentication"]; auth != nil && !validateConfigurationAuthentication(Object(auth), false) {
					return failure("PACKAGE_SCHEMA_INVALID", "Invalid remote route authentication fields", "/spec/config/routes")
				}
			}
		}
	}
	return nil
}
