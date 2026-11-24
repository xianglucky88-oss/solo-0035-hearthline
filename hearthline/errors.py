class Problem(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.status = status
        self.details = details or {}
