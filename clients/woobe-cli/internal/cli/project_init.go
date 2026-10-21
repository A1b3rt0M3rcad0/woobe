package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/projectinit"
	assistantskill "github.com/A1b3rt0M3rcad0/woobe-cli/packages/woobe-cli-skill"
	"github.com/spf13/cobra"
)

func (a *App) projectInitCommand() *cobra.Command {
	var root string
	var agents []string
	cmd := &cobra.Command{Use: "init", Short: "Prepare local YAML development and optional coding assistants", Args: cobra.NoArgs,
		Long:    "Create or reuse .woobe-config, protect private .state and .woobe-lab files from Git, and optionally install project-local assistant skills and managed project instructions. Repeating init preserves registry identity, resources and custom text. No backend calls or login. Existing connections can be selected with --context. Use --dry-run to preview without writing files.",
		Example: "woobe init --agents codex\nwoobe init --agents codex-legacy\nwoobe init --agents claude\nwoobe init --agents codex,claude --root .woobe --context local\nwoobe init --agents codex --dry-run", RunE: func(cmd *cobra.Command, _ []string) error {
			if a.ProjectConfig != "" || a.NoProjectConfig {
				return output.New(2, "init uses .woobe-config in the current directory; run it from the project root")
			}
			if cmd.Flags().Changed("agents") && len(agents) == 0 {
				return output.New(2, "--agents requires at least one assistant preset")
			}
			if err := a.initializeProject(cmd, root, agents); err != nil {
				return output.New(2, err.Error())
			}
			return nil
		}}
	cmd.Flags().StringVar(&root, "root", ".woobe", "Artifact root; reuse the existing root unless explicitly specified")
	cmd.Flags().StringSliceVar(&agents, "agents", nil, "Install project skills and instructions for assistant presets, comma-separated or repeatable")
	return cmd
}

func (a *App) initializeProject(cmd *cobra.Command, root string, agents []string) error {
	cwd, err := os.Getwd()
	if err != nil {
		return err
	}
	cwd, err = filepath.EvalSymlinks(cwd)
	if err != nil {
		return err
	}
	selected := map[string]bool{}
	for _, agent := range agents {
		if _, ok := assistantskill.Presets[agent]; !ok {
			return fmt.Errorf("unknown agent %q; see woobe skill agents", agent)
		}
		selected[agent] = true
	}
	lock := filepath.Join(cwd, ".woobe-init.lock")
	if !a.DryRun {
		f, e := os.OpenFile(lock, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if e != nil {
			return fmt.Errorf("cannot acquire %s; another init may be running; remove a stale lock only after confirming it has stopped", lock)
		}
		defer os.Remove(lock)
		if e = f.Close(); e != nil {
			return e
		}
	}
	file := filepath.Join(cwd, devworkspace.Filename)
	if discovered, e := devworkspace.Discover(cwd, "", false); e != nil {
		return e
	} else if discovered != "" && discovered != file {
		return fmt.Errorf("existing registry found at %s; run init from its project directory", discovered)
	}
	existing := false
	var c *devworkspace.Config
	if _, e := os.Lstat(file); e == nil {
		existing = true
		c, err = devworkspace.Load(file)
		if err != nil {
			return err
		}
	} else if !os.IsNotExist(e) {
		return e
	}
	if strings.ContainsAny(root, "\r\n\x00") {
		return fmt.Errorf("artifact root contains a control character")
	}
	if existing {
		if cmd.Flags().Changed("root") {
			requested := root
			if !filepath.IsAbs(requested) {
				requested = filepath.Join(cwd, requested)
			}
			if filepath.Clean(requested) != c.RootPath() {
				return fmt.Errorf("existing registry uses root %s; init does not migrate resources", c.Root)
			}
		}
		if cmd.Flags().Changed("context") && a.ContextName != c.Context {
			return fmt.Errorf("existing registry uses context %q; init preserves its connection binding", c.Context)
		}
	} else {
		user, e := config.Load(a.ConfigPath)
		if e != nil {
			return fmt.Errorf("cannot load private connection config")
		}
		connection := a.ContextName
		if connection == "" {
			connection = os.Getenv("WOOBE_CONTEXT")
		}
		if connection == "" {
			connection = user.Current
		}
		if connection != "" {
			if _, ok := user.Contexts[connection]; !ok {
				return fmt.Errorf("unknown connection; create it with context create or initialize without a context")
			}
		}
		c = &devworkspace.Config{File: file, Root: root, Context: connection}
	}
	if strings.TrimSpace(c.Root) == "" {
		return fmt.Errorf("artifact root cannot be empty")
	}
	if strings.ContainsAny(c.Root, "\r\n\x00") {
		return fmt.Errorf("artifact root contains a control character")
	}
	lab := filepath.Join(cwd, ".woobe-lab")
	for _, reserved := range []string{".git", ".woobe-lab", "AGENTS.md", "CLAUDE.md", ".woobe-config", ".woobe-init.lock", ".gitignore", ".github/copilot-instructions.md"} {
		if within(filepath.Join(cwd, filepath.FromSlash(reserved)), c.RootPath()) {
			return fmt.Errorf("artifact root overlaps reserved project path %s", reserved)
		}
	}
	for _, directory := range []string{c.RootPath(), filepath.Join(c.RootPath(), ".state"), lab} {
		if err := projectinit.SafeDirectory(directory); err != nil {
			return err
		}
	}
	skillOptions := assistantskill.Options{Agents: agents, Scope: "project", ProjectDir: cwd, Version: Version, Commit: Commit, DryRun: true}
	var skills assistantskill.Result
	files := []projectinit.File{}
	ignoreRules := map[string][]string{filepath.Join(cwd, ".gitignore"): {"/.woobe-lab/", "/.woobe-init.lock"}}
	artifactIgnore := filepath.Join(c.RootPath(), ".gitignore")
	ignoreRules[artifactIgnore] = append(ignoreRules[artifactIgnore], "/.state/")
	if relative, e := filepath.Rel(cwd, c.RootPath()); e == nil && relative != "." && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		path := filepath.Join(cwd, ".gitignore")
		ignoreRules[path] = append(ignoreRules[path], projectinit.EscapeIgnore(filepath.Join(relative, ".state")))
	}
	for path, rules := range ignoreRules {
		f, e := projectinit.Read(path)
		if e != nil {
			return e
		}
		f, e = projectinit.Manage(f, strings.Join(rules, "\n"), "#", nil, true)
		if e != nil {
			return e
		}
		files = append(files, f)
	}
	if len(agents) > 0 {
		f, e := projectinit.Read(filepath.Join(cwd, "AGENTS.md"))
		if e != nil {
			return e
		}
		previous, e := projectinit.Agents(f)
		if e != nil {
			return e
		}
		for _, name := range previous {
			if _, ok := assistantskill.Presets[name]; !ok {
				return fmt.Errorf("unknown preset in existing managed instructions: %s", name)
			}
			selected[name] = true
		}
		names := []string{}
		for name := range selected {
			names = append(names, name)
		}
		sort.Strings(names)
		f, e = projectinit.Manage(f, initInstructions(names), "<!--", names, false)
		if e != nil {
			return e
		}
		files = append(files, f)
		wrappers := map[string]string{}
		if selected["claude"] {
			wrappers[filepath.Join(cwd, "CLAUDE.md")] = "For Woobe operations, follow the Woobe CLI section in [AGENTS.md](AGENTS.md) and the local skill [.claude/skills/woobe-cli/SKILL.md](.claude/skills/woobe-cli/SKILL.md). Read only the reference needed for the current task."
		}
		if selected["copilot"] {
			wrappers[filepath.Join(cwd, ".github", "copilot-instructions.md")] = "For Woobe operations, follow the Woobe CLI section in [AGENTS.md](../AGENTS.md) and the local skill [skills/woobe-cli/SKILL.md](skills/woobe-cli/SKILL.md). Read only the reference needed for the current task."
		}
		for path, body := range wrappers {
			f, e := projectinit.Read(path)
			if e != nil {
				return e
			}
			f, e = projectinit.Manage(f, body, "<!--", nil, false)
			if e != nil {
				return e
			}
			files = append(files, f)
		}
		agents = names
		skillOptions.Agents = names
		skills, err = assistantskill.Run("install", skillOptions)
		if err != nil {
			return err
		}
		for _, row := range skills.Installations {
			if within(row.Target, c.RootPath()) {
				return fmt.Errorf("artifact root overlaps an assistant skill: %s", row.Target)
			}
		}
	}
	sort.Slice(files, func(i, j int) bool { return files[i].Path < files[j].Path })
	actions := []map[string]string{}
	instructions := []string{}
	for _, f := range files {
		action := "unchanged"
		if f.Changed() {
			action = "updated"
			if !f.Exists {
				action = "created"
			}
		}
		actions = append(actions, map[string]string{"path": f.Path, "action": action})
		if filepath.Base(f.Path) != ".gitignore" {
			relative, _ := filepath.Rel(cwd, f.Path)
			instructions = append(instructions, filepath.ToSlash(relative))
		}
	}
	if !a.DryRun {
		for _, f := range files {
			if filepath.Base(f.Path) == ".gitignore" {
				if e := f.Apply(); e != nil {
					return e
				}
			}
		}
		if !existing {
			c, err = devworkspace.Create(cwd, c.Root, c.Context)
			if err != nil {
				return err
			}
		}
		for _, directory := range []string{filepath.Join(c.RootPath(), ".state"), lab} {
			if err = packagecheckpoint.EnsurePrivateDirectory(directory); err != nil {
				return err
			}
		}
		if len(skillOptions.Agents) > 0 {
			skillOptions.DryRun = false
			skills, err = assistantskill.Run("install", skillOptions)
			if err != nil {
				return err
			}
		}
		for _, f := range files {
			if filepath.Base(f.Path) != ".gitignore" {
				if e := f.Apply(); e != nil {
					return e
				}
			}
		}
	}
	return a.emit(map[string]any{"initialized": !a.DryRun, "executed": !a.DryRun, "config": c.File, "root": c.RootPath(), "context": c.Context, "registry_id": c.RegistryID, "reused": existing, "agents": agents, "instructions": instructions, "lab": lab, "skills": skills.Installations, "files": actions})
}

func initInstructions(agents []string) string {
	lines := []string{"## Woobe CLI", "", "Use the installed `woobe-cli` skill for Woobe Agent/Network operations. Read its router and only the reference needed for the task:"}
	seen := map[string]bool{}
	for _, agent := range agents {
		path := assistantskill.Presets[agent].Project + "/woobe-cli/SKILL.md"
		if !seen[path] {
			lines = append(lines, "- ["+agent+"]("+path+")")
			seen[path] = true
		}
	}
	lines = append(lines, "", "Use `woobe version` and `woobe context show --output compact` to confirm the connection. For local work, read `.woobe-config` and use `woobe config check` / `woobe resources list`. Prefer UUID for the first pull, then registered `@alias` or path: pull → edit YAML → validate/diff → push Draft. Reuse registered dependencies; never create a duplicate to edit an existing resource.", "", "Use compact output and selected fields. Consult exact command help when needed. Keep credentials out of author YAML and Git. Keep `.woobe-lab/` scratch files and the configured root's `.state/` private; preserve pending receipts and reconcile uncertain writes before retrying. Version `.woobe-config`, author files and reviewed assistant instructions. Follow the user's authorization for publication, deployment and rollback; these instructions grant no extra permissions.")
	return strings.Join(lines, "\n")
}

func within(parent, child string) bool {
	relative, err := filepath.Rel(parent, child)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator))
}
