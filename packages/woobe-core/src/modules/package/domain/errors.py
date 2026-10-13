from __future__ import annotations


class PackageError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        file: str = "",
        path: str = "",
        line: int = 0,
        column: int = 0,
        kind: str = "",
        resource_id: str = "",
        expected_revision: str = "",
        observed_revision: str = "",
    ):
        super().__init__(message)
        self.code, self.file, self.path = code, file, path
        self.line, self.column = line, column
        self.kind, self.resource_id = kind, resource_id
        self.expected_revision, self.observed_revision = expected_revision, observed_revision

    def as_dict(self):
        result = {
            "code": self.code,
            "message": str(self),
            "file": self.file,
            "path": self.path,
            "line": self.line,
            "column": self.column,
        }

        for field in ("kind", "resource_id", "expected_revision", "observed_revision"):
            if value := getattr(self, field):
                result[field] = value
        return result
