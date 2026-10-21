//go:build !windows

package credentials

const nativeStore = false

func (s Store) nativeGet(string) (string, error) { panic("Windows only") }
func (s Store) nativePut(string, string) error   { panic("Windows only") }
func (s Store) nativeRemove(string) error        { panic("Windows only") }
func (s Store) nativeList() ([]string, error)    { panic("Windows only") }
