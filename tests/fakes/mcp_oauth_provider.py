"""Disposable OAuth/MCP peer; fixed synthetic credentials, never customer access."""
import base64
import hashlib
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
ACCESS = 'native-oauth-access-canary'
REFRESH = 'native-oauth-refresh-canary'
CLIENT_SECRET = 'native-oauth-client-canary'
DEVICE = 'native-oauth-device-canary'
challenge = None
device_polls = 0
registrations = 0


@app.get('/health')
async def health():
    return {'ready': True}


@app.get('/resource-metadata')
async def resource(request: Request):
    origin = str(request.base_url).rstrip('/')
    return {'resource': origin + '/mcp', 'authorization_servers': [origin], 'scopes_supported': ['mcp:read']}


@app.get('/.well-known/oauth-authorization-server')
@app.get('/.well-known/openid-configuration')
async def authorization_metadata(request: Request):
    origin = str(request.base_url).rstrip('/')
    return {'issuer': origin, 'authorization_endpoint': origin + '/authorize', 'token_endpoint': origin + '/token',
        'registration_endpoint': origin + '/register', 'scopes_supported': ['mcp:read'],
        'device_authorization_endpoint': origin + '/device',
        'grant_types_supported': ['authorization_code', 'refresh_token', 'urn:ietf:params:oauth:grant-type:device_code'],
        'response_types_supported': ['code'], 'code_challenge_methods_supported': ['S256'],
        'token_endpoint_auth_methods_supported': ['client_secret_post']}


@app.post('/register')
async def register(request: Request):
    global registrations
    registrations += 1
    body = await request.json()
    assert body['client_name'] == 'Woobe'
    return {'client_id': 'native-client', 'client_secret': CLIENT_SECRET, 'token_endpoint_auth_method': 'client_secret_post'}


@app.get('/authorize')
async def authorize(request: Request):
    global challenge
    assert request.query_params['code_challenge_method'] == 'S256'
    challenge = request.query_params['code_challenge']
    return {'authorization': 'pending'}


@app.post('/device')
async def device(request: Request):
    global device_polls
    device_polls = 0
    body = {key: values[0] for key, values in parse_qs((await request.body()).decode()).items()}
    if body.get('client_id') != 'native-client':
        return JSONResponse({'error': 'invalid_client'}, status_code=401)
    return {'device_code': DEVICE, 'user_code': 'NATIVE-CODE', 'verification_uri': str(request.base_url) + 'verify',
        'expires_in': 600, 'interval': 1}


@app.post('/token')
async def token(request: Request):
    global device_polls
    body = {key: values[0] for key, values in parse_qs((await request.body()).decode()).items()}
    if body.get('client_id') != 'native-client' or body.get('client_secret') != CLIENT_SECRET:
        return JSONResponse({'error': 'invalid_client'}, status_code=401)
    if body.get('grant_type') == 'authorization_code':
        calculated = base64.urlsafe_b64encode(hashlib.sha256(body.get('code_verifier', '').encode()).digest()).decode().rstrip('=')
        if body.get('code') != 'native-code' or calculated != challenge:
            return JSONResponse({'error': 'invalid_grant'}, status_code=400)
    elif body.get('grant_type') == 'refresh_token':
        if body.get('refresh_token') != REFRESH:
            return JSONResponse({'error': 'invalid_grant'}, status_code=400)
    elif body.get('grant_type') == 'urn:ietf:params:oauth:grant-type:device_code':
        if body.get('device_code') != DEVICE:
            return JSONResponse({'error': 'invalid_grant'}, status_code=400)
        device_polls += 1
        if device_polls == 1:
            return JSONResponse({'error': 'authorization_pending',
                'error_description': CLIENT_SECRET + ' ' + DEVICE}, status_code=400)
    else:
        return JSONResponse({'error': 'unsupported_grant_type'}, status_code=400)
    return {'access_token': ACCESS, 'refresh_token': REFRESH, 'token_type': 'Bearer', 'expires_in': 3600}


@app.post('/mcp')
async def mcp(request: Request):
    if request.headers.get('authorization') != 'Bearer ' + ACCESS:
        origin = str(request.base_url).rstrip('/')
        return JSONResponse({'error': 'authentication_required'}, status_code=401,
            headers={'WWW-Authenticate': f'Bearer resource_metadata="{origin}/resource-metadata"'})
    body = await request.json()
    identifier = body.get('id')
    if body['method'] == 'initialize':
        result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'native-oauth', 'version': '1'}}
    elif body['method'] == 'tools/list':
        result = {'tools': [{'name': 'read_status', 'description': 'Synthetic status', 'inputSchema': {'type': 'object'}}]}
    elif body['method'] == 'notifications/initialized':
        return JSONResponse({}, status_code=202)
    else:
        result = {'content': [{'type': 'text', 'text': 'Synthetic status'}]}
    return {'jsonrpc': '2.0', 'id': identifier, 'result': result}
