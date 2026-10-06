from fastapi import FastAPI
from woobe_api.http.agent.mcp_tools_routes import router

def test_mcp_oauth_contracts_are_inputs_without_advertising_connection_success():
    app=FastAPI();app.include_router(router);paths=app.openapi()["paths"]
    for route in ["start","complete","device/start","device/poll","status","disconnect"]:
        schema=paths["/tools/mcp/oauth/"+route]["post"]["requestBody"]["content"]["application/json"]["schema"]
        assert "tool_id" in schema["required"]
        assert "connected" not in schema["properties"]
        if route in {"start","complete","device/start","device/poll"}:assert schema["properties"]["timeout_ms"]["minimum"]==1
    complete=paths["/tools/mcp/oauth/complete"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert {"code","state"} <= set(complete["required"])
