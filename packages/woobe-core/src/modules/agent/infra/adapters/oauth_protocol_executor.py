"""Keep OAuth protocol material inside its owner flow, outside Tool results."""
from dataclasses import replace
import json

from modules.agent.application.interfaces.oauth_protocol import private_oauth_protocol_response, current_oauth_operation_authorizer
from modules.agent.application.interfaces.project_configuration import current_tool_configuration

OAUTH_ERROR_CODES = frozenset({'authorization_pending', 'slow_down', 'expired_token', 'access_denied',
    'invalid_grant', 'invalid_client', 'invalid_request', 'unauthorized_client', 'unsupported_grant_type',
    'invalid_scope', 'server_error', 'temporarily_unavailable'})


class OAuthProtocolExecutor:
    def __init__(self, executor):
        self.executor = executor

    async def execute(self, *args, **kwargs):
        authorize = current_oauth_operation_authorizer.get()
        if authorize is not None:
            await authorize()
        private = private_oauth_protocol_response.set(True)
        parent = current_tool_configuration.set(None)
        try:
            result = await self.executor.execute(*args, **kwargs)
            if result.success:
                return result
            # Providers can echo credentials in error descriptions or arbitrary
            # error codes. The device state machine needs only closed protocol
            # codes; discovery additionally needs the original challenge header.
            output = result.output if isinstance(result.output, dict) else {}
            body = output.get('body')
            code = body.get('error') if isinstance(body, dict) else None
            safe_body = {'error': code if isinstance(code, str) and code in OAUTH_ERROR_CODES else 'oauth_protocol_error'}
            return replace(result, error='OAuth protocol request failed', body=json.dumps(safe_body),
                output={'status_code': result.status_code, 'headers': output.get('headers') or {}, 'body': safe_body})
        finally:
            current_tool_configuration.reset(parent)
            private_oauth_protocol_response.reset(private)
