"""Framework-independent application exceptions."""

from . import messages


class AppError(Exception):
    """Base error carrying the HTTP status and safe user-facing message."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class HillError(AppError):
    """A Hill-specific business error with the extended public envelope."""

    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, object] | None = None
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(status_code, message)


class DesError(AppError):
    """A DES error with an already formatted message, using the two-field envelope."""


class EmptyTextError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.TEXT_EMPTY)


class MissingKeyError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_KEY)


class InvalidKeyError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_KEY)


class MissingAffineMultiplierError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_AFFINE_MULTIPLIER)


class InvalidAffineMultiplierError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_AFFINE_MULTIPLIER)


class NonInvertibleAffineMultiplierError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.NON_INVERTIBLE_AFFINE_MULTIPLIER)


class MissingAffineShiftError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_AFFINE_SHIFT)


class InvalidAffineShiftError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_AFFINE_SHIFT)


class InvalidStringKeyError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_STRING_KEY)


class InvalidVigenereKeyError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_VIGENERE_KEY)


class InvalidPlayfairKeyError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_PLAYFAIR_KEY)


class InvalidColumnarKeyError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_COLUMNAR_KEY)


class EmptyPlayfairTextError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.PLAYFAIR_TEXT_EMPTY)


class OddPlayfairCiphertextError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.PLAYFAIR_CIPHERTEXT_ODD)


class DuplicatePlayfairDigraphError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.PLAYFAIR_DUPLICATE_DIGRAPH)


class MissingFileError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_FILE)


class EmptyFileError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.EMPTY_FILE)


class UnsupportedFileTypeError(AppError):
    def __init__(self) -> None:
        super().__init__(415, messages.UNSUPPORTED_FILE_TYPE)


class FileTooLargeError(AppError):
    def __init__(self) -> None:
        super().__init__(413, messages.FILE_TOO_LARGE)


class UnsupportedEncodingError(AppError):
    def __init__(self) -> None:
        super().__init__(415, messages.UNSUPPORTED_ENCODING)


class InvalidActionError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_ACTION)


class InvalidResponseModeError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_RESPONSE_MODE)


class FileReadError(AppError):
    def __init__(self) -> None:
        super().__init__(500, messages.FILE_READ_FAILURE)


class UnexpectedError(AppError):
    def __init__(self) -> None:
        super().__init__(500, messages.UNEXPECTED_FAILURE)


class InvalidRequestBodyError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_REQUEST_BODY)


class InvalidHistoryLimitError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_HISTORY_LIMIT)


class InvalidHistoryCursorError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_HISTORY_CURSOR)


class InvalidHistoryFilterError(AppError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_HISTORY_FILTER)


class HistoryUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(503, messages.HISTORY_UNAVAILABLE)


class HistoryDisabledError(AppError):
    def __init__(self) -> None:
        super().__init__(404, messages.HISTORY_DISABLED)
