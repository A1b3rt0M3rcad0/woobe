"""SQL projection of route identities/references; literal header values stay out."""
from sqlalchemy import case, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH

from modules.agent.infra.database.models import AgentToolModel


def route_configuration_metadata():
    raw = AgentToolModel.config['routes']
    array = case((func.jsonb_typeof(raw) == 'array', raw), else_=cast([], JSONB))
    route = func.jsonb_array_elements(array).table_valued('value').alias('configuration_route')
    template_headers = func.jsonb_path_query_array(route.c.value,
        cast('$.headers[*] ? (@.value starts with "{{secret:")', JSONPATH))
    metadata = func.jsonb_build_object('id', route.c.value.op('->>')('id'),
        'path', route.c.value.op('->>')('path'), 'authentication', route.c.value.op('->')('authentication'),
        'headers', template_headers)
    return select(func.coalesce(func.jsonb_agg(metadata), cast([], JSONB))).select_from(route).correlate(
        AgentToolModel).scalar_subquery().label('routes')
