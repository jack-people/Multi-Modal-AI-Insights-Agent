class ApiError(Exception):
    def __init__(self, http_status: int, error_code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code
        self.message = message
        self.detail = detail or {}
