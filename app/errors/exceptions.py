"""Framework-independent application exceptions."""

from . import messages


class CaesarError(Exception):
    """Base error carrying the HTTP status and safe user-facing message."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class EmptyTextError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.TEXT_EMPTY)


class MissingKeyError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_KEY)


class InvalidKeyError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_KEY)


class MissingAffineMultiplierError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_AFFINE_MULTIPLIER)


class InvalidAffineMultiplierError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_AFFINE_MULTIPLIER)


class NonInvertibleAffineMultiplierError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.NON_INVERTIBLE_AFFINE_MULTIPLIER)


class MissingAffineShiftError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_AFFINE_SHIFT)


class InvalidAffineShiftError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_AFFINE_SHIFT)


class InvalidStringKeyError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_STRING_KEY)


class InvalidVigenereKeyError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_VIGENERE_KEY)


class InvalidPlayfairKeyError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_PLAYFAIR_KEY)


class InvalidColumnarKeyError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_COLUMNAR_KEY)


class EmptyPlayfairTextError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.PLAYFAIR_TEXT_EMPTY)


class OddPlayfairCiphertextError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.PLAYFAIR_CIPHERTEXT_ODD)


class DuplicatePlayfairDigraphError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.PLAYFAIR_DUPLICATE_DIGRAPH)


class MissingFileError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.MISSING_FILE)


class EmptyFileError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.EMPTY_FILE)


class UnsupportedFileTypeError(CaesarError):
    def __init__(self) -> None:
        super().__init__(415, messages.UNSUPPORTED_FILE_TYPE)


class FileTooLargeError(CaesarError):
    def __init__(self) -> None:
        super().__init__(413, messages.FILE_TOO_LARGE)


class UnsupportedEncodingError(CaesarError):
    def __init__(self) -> None:
        super().__init__(415, messages.UNSUPPORTED_ENCODING)


class InvalidActionError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_ACTION)


class InvalidResponseModeError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_RESPONSE_MODE)


class FileReadError(CaesarError):
    def __init__(self) -> None:
        super().__init__(500, messages.FILE_READ_FAILURE)


class UnexpectedError(CaesarError):
    def __init__(self) -> None:
        super().__init__(500, messages.UNEXPECTED_FAILURE)


class InvalidRequestBodyError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_REQUEST_BODY)


class InvalidHistoryLimitError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_HISTORY_LIMIT)


class InvalidHistoryCursorError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_HISTORY_CURSOR)


class InvalidHistoryFilterError(CaesarError):
    def __init__(self) -> None:
        super().__init__(422, messages.INVALID_HISTORY_FILTER)


class HistoryUnavailableError(CaesarError):
    def __init__(self) -> None:
        super().__init__(503, messages.HISTORY_UNAVAILABLE)
