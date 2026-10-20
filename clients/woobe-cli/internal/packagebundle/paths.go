package packagebundle

import (
	"path"
	"regexp"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

var reservedName = regexp.MustCompile(`(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)`)

type pathIdentity struct {
	path      string
	directory bool
}
type pathRegistry map[string]pathIdentity

func (r pathRegistry) register(path string, directory bool) error {
	parts := strings.Split(path, "/")
	for i := 1; i <= len(parts); i++ {
		prefix := strings.Join(parts[:i], "/")
		identity := pathIdentity{prefix, i < len(parts) || directory}
		if previous, exists := r[fold(prefix)]; exists && previous != identity {
			return failure("PACKAGE_PATH_INVALID", "Path case collision or file/directory conflict", path)
		}
		r[fold(prefix)] = identity
	}
	return nil
}

func PortablePath(value, descriptor string) (string, error) {
	fail := func() (string, error) {
		return "", &packagefmt.Diagnostic{Code: "PACKAGE_PATH_INVALID", Message: "Path must be confined, relative and portable"}
	}
	if value == "" || strings.HasPrefix(value, "/") || strings.ContainsAny(value, `\<>:"|?*`) {
		return fail()
	}
	for _, char := range value {
		if char < 32 || char == 127 {
			return fail()
		}
	}
	joined := path.Clean(path.Join(path.Dir(descriptor), value))
	if joined == "." || joined == ".." || strings.HasPrefix(joined, "../") {
		return fail()
	}
	for _, part := range strings.Split(joined, "/") {
		if strings.HasSuffix(part, ".") || strings.HasSuffix(part, " ") || reservedName.MatchString(part) || strings.EqualFold(part, ".git") {
			return fail()
		}
	}
	return joined, nil
}

func SupportPaths(document map[string]any, descriptor string) ([]string, error) {
	spec := packagefmt.Object(document["spec"])
	values := []string{}
	switch document["kind"] {
	case "Skill":
		files := packagefmt.Object(spec["package"])
		values = append(values, packagefmt.Text(files["manifest"]))
		for _, value := range packagefmt.List(files["resources"]) {
			values = append(values, packagefmt.Text(value))
		}
	case "Knowledge":
		for _, value := range packagefmt.List(spec["documents"]) {
			values = append(values, packagefmt.Text(packagefmt.Object(value)["path"]))
		}
	}
	result := []string{}
	for _, value := range values {
		normalized, err := PortablePath(value, descriptor)
		if err != nil {
			return nil, err
		}
		result = append(result, normalized)
	}
	return result, nil
}
