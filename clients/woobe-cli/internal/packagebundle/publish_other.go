//go:build !linux && !darwin && !windows

package packagebundle

func renameNoReplace(source, destination string) error {
	return failure("PACKAGE_UNSUPPORTED", "Exclusive package publication is unavailable on this OS", "")
}
