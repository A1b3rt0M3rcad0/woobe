"""Real PostgreSQL tests use disposable databases, never the application DB."""

import os
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg2
from psycopg2 import sql
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
import botocore.session
from botocore.config import Config as S3Config


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def s3_backend():
    filename = os.environ.get('WOOBE_ARTIFACT_TEST_S3_CONFIG_FILE')
    if not filename:
        pytest.skip('Explicit local S3-compatible test configuration required')
    configuration = json.loads(Path(filename).read_text())
    session = botocore.session.Session()
    # Explicit test credentials must not use an unrelated ambient AWS profile.
    session.get_component('config_store').set_config_variable('profile', None)
    session.set_credentials(configuration['access_key'], configuration['secret_key'])
    client = session.create_client('s3', endpoint_url=configuration['endpoint'],
        region_name='us-east-1', config=S3Config(signature_version='s3v4',
            s3={'addressing_style': 'path'}, connect_timeout=5, read_timeout=10,
            retries={'mode': 'standard', 'max_attempts': 1}))
    bucket = 'woobe-artifacts-tests-' + uuid4().hex
    created = False
    try:
        client.create_bucket(Bucket=bucket)
        created = True
        yield client, bucket
    finally:
        if created:
            for upload in client.list_multipart_uploads(Bucket=bucket).get('Uploads', []):
                client.abort_multipart_upload(Bucket=bucket, Key=upload['Key'], UploadId=upload['UploadId'])
            while True:
                page = client.list_objects_v2(Bucket=bucket)
                objects = page.get('Contents', [])
                if not objects:
                    break
                for obj in objects:
                    client.delete_object(Bucket=bucket, Key=obj['Key'])
            client.delete_bucket(Bucket=bucket)
        client.close()


@pytest.fixture
async def engine(artifacts_database):
    engine = create_async_engine(artifacts_database['url'])
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope='module', params=['fresh', 'populated'])
def artifacts_database(request):
    supplied = os.environ.get('WOOBE_ARTIFACT_TEST_POSTGRES_URL')
    if not supplied and os.environ.get('WOOBE_ENVIRONMENT') == 'test':
        supplied = os.environ.get('WOOBE_POSTGRES_URL')
    if not supplied:
        pytest.skip('Explicit disposable PostgreSQL test configuration required')
    base = make_url(supplied).set(drivername='postgresql')
    database = f'woobe_artifacts_test_{uuid4().hex}'
    admin = psycopg2.connect(base.set(database='postgres').render_as_string(hide_password=False))
    admin.autocommit = True
    cursor = admin.cursor()
    cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
    url = base.set(database=database)
    migration_env = os.environ | {'WOOBE_POSTGRES_URL': url.render_as_string(hide_password=False)}

    def migrate(target):
        result = subprocess.run(
            [sys.executable, '-m', 'alembic', '-c', 'packages/woobe-core/alembic.ini', 'upgrade', target],
            cwd=ROOT, env=migration_env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    project = uuid4()
    try:
        migrate('0106' if request.param == 'populated' else 'head')
        with psycopg2.connect(url.render_as_string(hide_password=False)) as connection:
            with connection.cursor() as seed:
                seed.execute("INSERT INTO core.projects (id,workspace_id,name,slug,status,data) VALUES (%s,%s,'Baseline retained','artifact-baseline','active','{}')", (str(project), str(uuid4())))
        migrate('head')
        migrate('head')
        yield {'url': url.set(drivername='postgresql+asyncpg').render_as_string(hide_password=False),
               'sync_url': url.render_as_string(hide_password=False), 'project_id': str(project),
               'current_head': ScriptDirectory.from_config(Config(str(ROOT / 'packages/woobe-core/alembic.ini'))).get_current_head()}
    finally:
        cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
        cursor.close()
        admin.close()
