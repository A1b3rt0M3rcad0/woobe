package manifest

import "testing"

func TestSkillVersionTypedDependency(t *testing.T) {
	b := `{"schema_version":"2","project_id":"p","resources":[{"key":"skill","kind":"Skill","action":"create","spec":{"name":"S"}},{"key":"version","kind":"SkillVersion","action":"create","parents":{"skill":"${resources.skill.id}"},"depends_on":["skill"],"spec":{"content":"Teach"}}]}`
	d, e := Parse([]byte(b))
	if e != nil || d.Steps[1].Command != "project skill version create" {
		t.Fatal(e, d)
	}
	if _, e := Parse([]byte(`{"schema_version":"2","project_id":"p","resources":[{"key":"p","kind":"Project","action":"update","resource_id":"other","spec":{}}]}`)); e == nil {
		t.Fatal("project crossed scope")
	}
}
