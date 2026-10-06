from fastapi import FastAPI
from woobe_api.http.agent.skill_routes import router

def test_skill_cli_contracts_preserve_import_and_paging_bounds():
    app=FastAPI();app.include_router(router);paths=app.openapi()["paths"]
    base="/ai/projects/{project_id}/skills"
    for path in [base,base+"/{skill_id}/versions"]:
        operation=paths[path]["post"]
        schema=operation["requestBody"]["content"]["application/json"]["schema"]
        assert schema["required"]==["version","skill_md"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["skill_md"]["maxLength"]==200_000
        params=paths[path]["get"]["parameters"]
        assert len(params)==len({(p["name"],p["in"]) for p in params})
        limit=next(p for p in params if p["name"]=="limit")
        assert limit["schema"]["minimum"]==1 and limit["schema"]["maximum"]==100
    assert "query" not in {p["name"] for p in paths[base+"/{skill_id}/versions"]["get"]["parameters"]}
