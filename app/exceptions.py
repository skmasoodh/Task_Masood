"""Domain-specific exceptions mapped to HTTP errors in the routers."""


class AttendanceError(Exception):
    """Base class for attendance business-rule violations."""


class AlreadyPunchedInError(AttendanceError):
    """Raised when an employee tries to punch in with a session already open."""


class NotPunchedInError(AttendanceError):
    """Raised when an employee tries to punch out without an open session."""


class RecordNotFoundError(AttendanceError):
    """Raised when an attendance record cannot be found."""


class InvalidCorrectionError(AttendanceError):
    """Raised when a manual correction request is invalid."""
