class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None, extra: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}
        self.extra = extra or {}


class DuplicateError(Exception):
    def __init__(self, existing_id: str | None = None):
        super().__init__("duplicate")
        self.existing_id = existing_id
