package config

import (
	"bytes"
	"encoding/json"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
)

type Context struct {
	APIURL            string `json:"api_url"`
	AuthAPIURL        string `json:"auth_api_url,omitempty"`
	Workspace         string `json:"workspace_id,omitempty"`
	Project           string `json:"project_id,omitempty"`
	Credential        string `json:"credential,omitempty"`
	RuntimeCredential string `json:"runtime_credential,omitempty"`
}
type Config struct {
	Version  int                `json:"version"`
	Current  string             `json:"current,omitempty"`
	Contexts map[string]Context `json:"contexts"`
}

func DefaultPath() string {
	if s := os.Getenv("WOOBE_CONFIG"); s != "" {
		return s
	}
	d, err := os.UserConfigDir()
	if err != nil {
		d = "."
	}
	return filepath.Join(d, "woobe", "config.json")
}
func Load(path string) (Config, error) {
	c := Config{Version: 1, Contexts: map[string]Context{}}
	f, err := os.Open(path)
	if os.IsNotExist(err) {
		return c, nil
	}
	if err != nil {
		return c, err
	}
	defer f.Close()
	b, err := io.ReadAll(io.LimitReader(f, 1<<20+1))
	if err != nil {
		return c, err
	}
	if len(b) > 1<<20 {
		return c, fmt.Errorf("config exceeds 1 MiB")
	}
	if err = jsoninput.Validate(b); err != nil {
		return c, fmt.Errorf("invalid config JSON: %w", err)
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.DisallowUnknownFields()
	if err = d.Decode(&c); err != nil {
		return c, err
	}
	if err = Validate(c); err != nil {
		return c, err
	}
	if c.Contexts == nil {
		c.Contexts = map[string]Context{}
	}
	return c, nil
}
func Save(path string, c Config) error {
	if e := Validate(c); e != nil {
		return e
	}
	b, e := json.MarshalIndent(c, "", "  ")
	if e != nil {
		return e
	}
	return AtomicWrite(path, b, 0600)
}
func AtomicWrite(path string, b []byte, mode os.FileMode) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	f, err := os.CreateTemp(dir, ".woobe-*")
	if err != nil {
		return err
	}
	name := f.Name()
	defer os.Remove(name)
	if err = f.Chmod(mode); err == nil {
		_, err = f.Write(b)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Rename(name, path)
}

func Validate(c Config) error {
	if c.Version != 1 {
		return fmt.Errorf("unsupported config version %d", c.Version)
	}
	if c.Current != "" {
		if _, ok := c.Contexts[c.Current]; !ok {
			return fmt.Errorf("active context does not exist")
		}
	}
	for name := range c.Contexts {
		if !regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$`).MatchString(name) {
			return fmt.Errorf("invalid context name")
		}
	}
	for _, v := range c.Contexts {
		u, e := url.Parse(v.APIURL)
		if e != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
			return fmt.Errorf("invalid context API URL")
		}
	}
	return nil
}
