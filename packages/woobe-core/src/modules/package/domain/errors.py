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
    ):
        super().__init__(message)
        self.code, self.file, self.path = code, file, path
        self.line, self.column = line, column

    def as_dict(self):
        return {
            "code": self.code,
            "message": str(self),
            "file": self.file,
            "path": self.path,
            "line": self.line,
            "column": self.column,
        }
