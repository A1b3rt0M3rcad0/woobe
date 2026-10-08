class ImportedDependencyPending(Exception):
    """A native asynchronous dependency is not ready; carries no provider message."""

    def __init__(self, dependencies):
        super().__init__("Imported dependency is pending")
        self.dependencies = dependencies
