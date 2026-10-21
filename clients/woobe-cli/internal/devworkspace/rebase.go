package devworkspace

import (
	"encoding/json"
	"fmt"
	"gopkg.in/yaml.v3"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

// ancestors rejects incomplete histories rather than guessing a merge base.
func (c *Config) ancestors(resource Resource, id string) (map[string]bool, error) {
	state := map[string]uint8{}
	type frame struct {
		id   string
		exit bool
	}
	stack := []frame{{id: id}}
	for len(stack) > 0 {
		current := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		if current.exit {
			state[current.id] = 2
			continue
		}
		if state[current.id] == 2 {
			continue
		}
		if state[current.id] == 1 {
			return nil, fmt.Errorf("ASAC_HISTORY_CYCLE")
		}
		if len(state) >= 10000 {
			return nil, fmt.Errorf("ASAC_HISTORY_LIMIT")
		}
		record, err := c.ReadRevision(resource, current.id)
		if err != nil {
			return nil, err
		}
		state[current.id] = 1
		stack = append(stack, frame{id: current.id, exit: true})
		for _, parent := range record.Parents {
			stack = append(stack, frame{id: parent})
		}
	}
	result := map[string]bool{}
	for id := range state {
		result[id] = true
	}
	return result, nil
}

func (c *Config) commonBase(resource Resource, left, right, explicit string) (string, error) {
	l, err := c.ancestors(resource, left)
	if err != nil {
		return "", err
	}
	r, err := c.ancestors(resource, right)
	if err != nil {
		return "", err
	}
	if explicit != "" {
		if !l[explicit] || !r[explicit] {
			return "", fmt.Errorf("explicit base is not an ancestor of both revisions")
		}
		return explicit, nil
	}
	candidates := map[string]bool{}
	for id := range l {
		if r[id] {
			candidates[id] = true
		}
	}
	// The common ancestor set is closed under parent links. Mark direct parents
	// once instead of walking the full DAG for every common revision.
	lower := map[string]bool{}
	for id := range candidates {
		record, err := c.ReadRevision(resource, id)
		if err != nil {
			return "", err
		}
		for _, parent := range record.Parents {
			if candidates[parent] {
				lower[parent] = true
			}
		}
	}
	bases := []string{}
	for id := range candidates {
		if !lower[id] {
			bases = append(bases, id)
		}
	}
	if len(bases) != 1 {
		return "", fmt.Errorf("rebase requires one known common ancestor; fetch missing history or choose --base explicitly")
	}
	return bases[0], nil
}

// Comments are separate author edits. Compare their positions by mapping keys,
// not textual field order, so formatting-only changes do not invent conflicts.
func authorComments(raw string) (string, error) {
	var root yaml.Node
	if err := yaml.Unmarshal([]byte(raw), &root); err != nil {
		return "", err
	}
	notes := map[string]string{}
	var visit func(*yaml.Node, []string)
	visit = func(node *yaml.Node, path []string) {
		for kind, text := range map[string]string{"head": node.HeadComment, "line": node.LineComment, "foot": node.FootComment} {
			if text != "" {
				key, _ := json.Marshal(append(append([]string{}, path...), kind))
				notes[string(key)] = text
			}
		}
		if node.Kind == yaml.MappingNode {
			for i := 0; i+1 < len(node.Content); i += 2 {
				visit(node.Content[i], append(append([]string{}, path...), node.Content[i].Value, "key"))
				visit(node.Content[i+1], append(append([]string{}, path...), node.Content[i].Value, "value"))
			}
		} else {
			for i, child := range node.Content {
				visit(child, append(append([]string{}, path...), fmt.Sprint(i)))
			}
		}
	}
	visit(&root, nil)
	encoded, err := json.Marshal(notes)
	return string(encoded), err
}

func mergeAuthorObjects(base, local, remote *AuthorObject) (*AuthorObject, []Conflict, error) {
	recipe := previousCompilerRecipe
	if local.CompilerRecipe == CurrentCompilerRecipe || remote.CompilerRecipe == CurrentCompilerRecipe {
		recipe = CurrentCompilerRecipe
	}
	result := &AuthorObject{CompilerRecipe: recipe, Format: "woobe-author-object", Version: "1.0", UID: local.UID, Components: map[string]AuthorComponent{}}
	conflicts := []Conflict{}
	uids := map[string]bool{}
	for _, object := range []*AuthorObject{base, local, remote} {
		if object.UID != local.UID {
			return nil, nil, fmt.Errorf("author roots differ")
		}
		for uid := range object.Components {
			uids[uid] = true
		}
	}
	ordered := []string{}
	for uid := range uids {
		ordered = append(ordered, uid)
	}
	sort.Strings(ordered)
	for _, uid := range ordered {
		b, bok := base.Components[uid]
		l, lok := local.Components[uid]
		r, rok := remote.Components[uid]
		carrier := l
		if !lok {
			carrier = r
		}
		if lok && rok {
			bs, err := authorComments(b.Raw)
			if err != nil {
				return nil, nil, err
			}
			ls, err := authorComments(l.Raw)
			if err != nil {
				return nil, nil, err
			}
			rs, err := authorComments(r.Raw)
			if err != nil {
				return nil, nil, err
			}
			if ls != bs && rs != bs && ls != rs {
				conflicts = append(conflicts, Conflict{Path: "/components/" + uid + "/author_comments"})
				continue
			}
			if ls == bs && rs != bs {
				carrier = r
			}
		} else if bok && ((lok && l.Raw != b.Raw) || (rok && r.Raw != b.Raw)) {
			conflicts = append(conflicts, Conflict{Path: "/components/" + uid + "/author_source"})
			continue
		}
		withComments := func(item AuthorComponent) (AuthorComponent, error) {
			if reflect.DeepEqual(item.Document, carrier.Document) {
				item.Raw = carrier.Raw
				return item, nil
			}
			encoded, err := EncodeWithComments(item.Document, descriptor(item.Resource), carrier.Raw)
			item.Raw = string(encoded)
			return item, err
		}
		// Compare payload, not paths/aliases: identity follows UID and current registry.
		equal := func(a AuthorComponent, aok bool, b AuthorComponent, bok bool) bool {
			return aok == bok && (!aok || reflect.DeepEqual(a.Document, b.Document) && reflect.DeepEqual(a.Supports, b.Supports))
		}
		if equal(l, lok, r, rok) || equal(r, rok, b, bok) {
			if lok {
				item, err := withComments(l)
				if err != nil {
					return nil, nil, err
				}
				result.Components[uid] = item
			}
			continue
		}
		if equal(l, lok, b, bok) {
			if rok {
				if lok {
					r.Resource = l.Resource
				}
				item, err := withComments(r)
				if err != nil {
					return nil, nil, err
				}
				result.Components[uid] = item
			}
			continue
		}

		if !lok || !rok || !bok || l.Resource.Kind != r.Resource.Kind || l.Resource.Key != r.Resource.Key {
			conflicts = append(conflicts, Conflict{Path: "/components/" + uid})
			continue
		}
		merged, issues := Merge(b.Document, l.Document, r.Document)
		for _, issue := range issues {
			conflicts = append(conflicts, Conflict{Path: "/components/" + uid + issue.Path})
		}
		// Support bytes are atomic values; concurrent changes to one file conflict.
		supports := func(item AuthorComponent) map[string]any {
			values := map[string]any{}
			for name, data := range item.Supports {
				values[name] = data
			}
			return values
		}
		files, fileIssues := Merge(supports(b), supports(l), supports(r))
		for _, issue := range fileIssues {
			conflicts = append(conflicts, Conflict{Path: "/components/" + uid + "/files" + issue.Path})
		}
		raw := carrier.Raw
		if !reflect.DeepEqual(merged, carrier.Document) {
			encoded, err := EncodeWithComments(merged, descriptor(l.Resource), carrier.Raw)
			if err != nil {
				return nil, nil, err
			}
			raw = string(encoded)
		}

		item := AuthorComponent{Resource: l.Resource, Document: merged, Raw: raw, Supports: map[string]string{}}
		for name, data := range files {
			item.Supports[name] = data.(string)
		}
		result.Components[uid] = item
	}
	return result, conflicts, nil
}

// RebaseRevision writes a new sealed revision, never rewrites shared history.
// Conflicts return only paths and leave all working files and history unchanged.
func (g *Graph) RebaseRevision(resource Resource, onto, base, message string) (map[string]any, error) {
	tracking, err := g.Config.ReadTracking(resource)
	if err != nil {
		return nil, err
	}
	if tracking.Working == "" || onto == tracking.Working {
		return nil, fmt.Errorf("select a distinct sealed revision and checkpoint current work before rebase")
	}
	current, err := g.Config.ReadRevision(resource, tracking.Working)
	if err != nil {
		return nil, err
	}
	target, err := g.Config.ReadRevision(resource, onto)
	if err != nil {
		return nil, err
	}
	base, err = g.Config.commonBase(resource, current.ID, target.ID, base)
	if err != nil {
		return nil, err
	}
	ancestor, err := g.Config.ReadRevision(resource, base)
	if err != nil {
		return nil, err
	}
	objects := []*AuthorObject{}
	for _, record := range []*Revision{ancestor, current, target} {
		object, err := g.Config.ReadAuthorObject(resource, record)
		if err != nil {
			return nil, err
		}
		if err = g.validateAuthorExecution(resource, record, object, tracking); err != nil {
			return nil, err
		}
		objects = append(objects, object)
	}
	merged, conflicts, err := mergeAuthorObjects(objects[0], objects[1], objects[2])
	if err != nil {
		return nil, err
	}
	if len(conflicts) > 0 {
		return map[string]any{"resource_uid": resource.UID, "conflicts": conflicts, "base_revision": base, "working_revision": current.ID, "onto_revision": onto, "complete": false, "remote_changed": false}, fmt.Errorf("ASAC_REBASE_CONFLICT: resolve concurrent paths explicitly before creating a merge checkpoint")
	}
	writes, tracking, err := g.prepareAuthorRestore(resource, merged)
	if err != nil {
		return nil, err
	}
	// Build and seal the merged graph in scratch space first. A bad merged
	// dependency graph cannot leave half-written YAML in the working directory.
	dir, err := os.MkdirTemp("", "woobe-rebase-")
	if err != nil {
		return nil, err
	}
	defer os.RemoveAll(dir)
	staged := *g.Config
	staged.File = filepath.Join(dir, Filename)
	staged.Root = ".woobe"
	staged.Resources = nil
	for _, uid := range sortedAuthorUIDs(merged) {
		staged.Resources = append(staged.Resources, merged.Components[uid].Resource)
	}
	sourceWrites, err := staged.sourceWrites(merged)
	if err != nil {
		return nil, err
	}
	for file, data := range sourceWrites {
		if err = os.MkdirAll(filepath.Dir(file), 0700); err != nil {
			return nil, err
		}
		if err = os.WriteFile(file, data, 0600); err != nil {
			return nil, err
		}
	}
	recordDir, err := staged.historyDirectory(resource)
	if err != nil {
		return nil, err
	}
	parentBytes, err := json.Marshal(target)
	if err != nil {
		return nil, err
	}
	if err = staged.immutableWrite(filepath.Join(recordDir, "revisions", target.ID+".yaml"), parentBytes); err != nil {
		return nil, err
	}
	stagedTracking := *tracking
	stagedTracking.Working = ""
	if err = staged.WriteTracking(resource, stagedTracking); err != nil {
		return nil, err
	}
	graph, err := LoadGraph(&staged)
	if err != nil {
		return nil, err
	}
	if message == "" {
		message = "Rebase " + current.ID + " onto " + onto
	}
	revision, err := graph.CreateRevision(resource, &State{Requirements: tracking.Requirements}, message, []string{onto})
	if err != nil {
		return nil, err
	}
	for _, item := range []struct{ directory, digest, suffix string }{{"sha256", revision.ArtifactDigest, ".tar.gz"}, {"author", revision.AuthorDigest, ".json"}} {
		relative := filepath.Join("objects", item.directory, strings.TrimPrefix(item.digest, "sha256:")+item.suffix)
		bytes, err := staged.ReadOperationalFile(filepath.Join(staged.RootPath(), relative), packagebundle.MaxArchiveBytes)
		if err != nil {
			return nil, err
		}
		if err = g.Config.immutableWrite(filepath.Join(g.Config.RootPath(), relative), bytes); err != nil {
			return nil, err
		}
	}
	actualDir, err := g.Config.historyDirectory(resource)
	if err != nil {
		return nil, err
	}
	revisionBytes, err := json.Marshal(revision)
	if err != nil {
		return nil, err
	}
	if err = g.Config.immutableWrite(filepath.Join(actualDir, "revisions", revision.ID+".yaml"), revisionBytes); err != nil {
		return nil, err
	}
	tracking.Working = revision.ID
	lock, err := g.Config.TrackingPath(resource)
	if err != nil {
		return nil, err
	}
	raw, err := json.Marshal(tracking)
	if err != nil {
		return nil, err
	}
	writes[lock] = raw
	if err = g.Config.Commit(writes); err != nil {
		return nil, err
	}
	loaded, err := Load(g.Config.File)
	if err != nil {
		return nil, err
	}
	*g.Config = *loaded
	return map[string]any{"resource_uid": resource.UID, "revision": revision, "base_revision": base, "rebased_from": current.ID, "onto_revision": onto, "origin_preserved": true, "scope": "local", "remote_changed": false}, nil
}
