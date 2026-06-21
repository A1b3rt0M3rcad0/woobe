class _UnavailableUseCase:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def execute(self, *args, **kwargs):
        raise NotImplementedError


class CreatePromptUseCase(_UnavailableUseCase):
    pass


class ListPromptsUseCase(_UnavailableUseCase):
    pass


class GetPromptUseCase(_UnavailableUseCase):
    pass
