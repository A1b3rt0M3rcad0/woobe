from uuid import uuid4

import pytest
from pydantic import ValidationError
from modules.agent.application.dtos.runtime_dtos import ListMessagesInput

@pytest.mark.parametrize("values", [{"offset":-1},{"offset":1_000_001},{"limit":0},{"limit":1001}])
def test_message_paging_is_bounded(values):
    with pytest.raises(ValidationError):ListMessagesInput(session_id=uuid4(),**values)

def test_message_paging_defaults_and_boundaries():
    assert ListMessagesInput(session_id=uuid4()).limit==100
    assert ListMessagesInput(session_id=uuid4(),offset=1_000_000,limit=1000).limit==1000
