"""Explicit, provider-neutral selection for the optional live acceptance check."""
from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class LiveModelSettings:
    provider: str
    model: str
    destination: str
    credential: str = field(repr=False)


def live_model_settings():
    if os.environ.get('WOOBE_ARTIFACT_RUN_LIVE_MODEL') != '1':
        return None
    names = ('WOOBE_ARTIFACT_MODEL_PROVIDER', 'WOOBE_ARTIFACT_MODEL_NAME',
             'WOOBE_ARTIFACT_MODEL_BASE_URL', 'WOOBE_ARTIFACT_MODEL_API_KEY')
    values = [os.environ.get(name) for name in names]
    if not all(values):
        raise ValueError('Explicit provider, model, approved HTTPS endpoint and its secure credential are required for this opt-in live test')
    return LiveModelSettings(*values)
