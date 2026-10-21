import hashlib
import json
from uuid import UUID

from shared.contracts.project_configuration import ConfigurationError


class OperationModelBindings:
    def __init__(self, models, configuration):
        self._models, self._configuration = models, configuration

    async def freeze(self, *, project_id, environment, model_id, model_revision,
                     configuration_key_id, configuration_revision):
        if self._configuration is None:
            raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
        if environment not in {'draft', 'staging', 'production'}:
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        # Same project-before-owner/key order as central configuration writes.
        await self._configuration.lock_project(project_id)
        metadata = await self._models.metadata(project_id, model_id, lock=True)
        if metadata['definition']['model_revision'] != model_revision:
            raise ConfigurationError('CONFIG_REVISION_CONFLICT')
        evidence = await self._configuration.activation_evidence(project_id=project_id,
            environment=environment, dependencies=metadata['dependencies'])
        if (len(evidence['pins']) != 1 or evidence['pins'][0]['source'] != 'environment'
            or evidence['definitions'] != [{'key_id': str(configuration_key_id), 'revision': configuration_revision}]):
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        snapshot = {'schema_version': '1', 'definition': metadata['definition'], 'configuration': evidence}
        encoded = json.dumps(snapshot, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if len(encoded) > 65_536:
            raise ConfigurationError('CONFIG_DEFINITION_INVALID')
        return {**snapshot, 'fingerprint': hashlib.sha256(encoded).hexdigest()}

    async def verify(self, snapshot, *, project_id):
        if snapshot.get('schema_version') != '1' or snapshot.get('definition', {}).get('project_id') != str(project_id):
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        try:
            document = {name: snapshot[name] for name in ('schema_version', 'definition', 'configuration')}
            encoded = json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
            if len(encoded) > 65_536 or hashlib.sha256(encoded).hexdigest() != snapshot.get('fingerprint'):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ConfigurationError('CONFIG_REVISION_CONFLICT') from None
        expected = snapshot['definition']
        metadata = await self._models.metadata(project_id, UUID(expected['model_id']))
        if metadata['definition'] != expected:
            raise ConfigurationError('CONFIG_REVISION_CONFLICT')
        if self._configuration is None:
            raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
        await self._configuration.verify_operation_evidence(project_id=project_id,
            environment=snapshot['configuration']['environment'], dependencies=metadata['dependencies'],
            evidence=snapshot['configuration'])
        return metadata['definition']
