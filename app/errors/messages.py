"""Canonical user-facing error messages.

This module is the single source of truth for the error strings shared by the
application's exception classes and HTTP adapters.
"""

TEXT_EMPTY = "Văn bản không được để trống."
MISSING_KEY = "Thiếu khóa."
INVALID_KEY = "Khóa phải là số nguyên."
MISSING_AFFINE_MULTIPLIER = "Thiếu khóa a."
INVALID_AFFINE_MULTIPLIER = "Khóa a phải là số nguyên."
NON_INVERTIBLE_AFFINE_MULTIPLIER = "Khóa a phải nguyên tố cùng nhau với 26."
MISSING_AFFINE_SHIFT = "Thiếu khóa b."
INVALID_AFFINE_SHIFT = "Khóa b phải là số nguyên."
INVALID_STRING_KEY = "Khóa phải là chuỗi."
INVALID_VIGENERE_KEY = "Khóa Vigenère chỉ được chứa chữ cái A-Z hoặc a-z."
INVALID_PLAYFAIR_KEY = "Khóa Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z."
INVALID_COLUMNAR_KEY = "Khóa Columnar phải là hoán vị 1..m hoặc từ khóa gồm 2 đến 256 chữ cái A-Z."
PLAYFAIR_TEXT_EMPTY = "Văn bản Playfair phải chứa ít nhất một chữ cái A-Z hoặc a-z."
PLAYFAIR_CIPHERTEXT_ODD = "Bản mã Playfair phải chứa số lượng chữ cái chẵn."
PLAYFAIR_DUPLICATE_DIGRAPH = "Bản mã Playfair không được chứa cặp hai chữ cái giống nhau."
MISSING_FILE = "Thiếu file."
EMPTY_FILE = "File không được để trống."
UNSUPPORTED_FILE_TYPE = "Chỉ chấp nhận file .txt."
FILE_TOO_LARGE = "File vượt quá dung lượng tối đa 5 MB."
UNSUPPORTED_ENCODING = "File phải sử dụng UTF-8."
INVALID_ACTION = "Action phải là encrypt hoặc decrypt."
INVALID_RESPONSE_MODE = "Response mode phải là content hoặc file."
FILE_READ_FAILURE = "Không thể đọc file."
UNEXPECTED_FAILURE = "Đã xảy ra lỗi hệ thống."
INVALID_REQUEST_BODY = "Dữ liệu gửi lên không hợp lệ."
INVALID_HISTORY_LIMIT = "Giới hạn phải là số nguyên từ 1 đến 100."
INVALID_HISTORY_CURSOR = "Con trỏ phân trang không hợp lệ."
INVALID_HISTORY_FILTER = "Bộ lọc lịch sử không hợp lệ."
HISTORY_UNAVAILABLE = "Lịch sử tạm thời không khả dụng."

# Owner-approved infrastructure exception; not a canonical DOCX §5 business message.
REQUEST_TOO_LARGE = "Yêu cầu vượt quá dung lượng cho phép."

# OpenAPI descriptions are user-visible through /docs and remain Vietnamese here.
FILE_API_SUCCESS_DESCRIPTION = "Kết quả JSON xem trước hoặc file văn bản UTF-8 đính kèm."
FILE_API_UNSUPPORTED_DESCRIPTION = "Loại file hoặc bảng mã không được hỗ trợ."
FILE_API_INVALID_MULTIPART_DESCRIPTION = "Dữ liệu multipart không hợp lệ."
FILE_API_UPLOAD_DESCRIPTION = "File .txt sử dụng UTF-8."

CANONICAL_MESSAGES = (
    TEXT_EMPTY,
    MISSING_KEY,
    INVALID_KEY,
    MISSING_AFFINE_MULTIPLIER,
    INVALID_AFFINE_MULTIPLIER,
    NON_INVERTIBLE_AFFINE_MULTIPLIER,
    MISSING_AFFINE_SHIFT,
    INVALID_AFFINE_SHIFT,
    INVALID_STRING_KEY,
    INVALID_VIGENERE_KEY,
    INVALID_PLAYFAIR_KEY,
    INVALID_COLUMNAR_KEY,
    PLAYFAIR_TEXT_EMPTY,
    PLAYFAIR_CIPHERTEXT_ODD,
    PLAYFAIR_DUPLICATE_DIGRAPH,
    MISSING_FILE,
    EMPTY_FILE,
    UNSUPPORTED_FILE_TYPE,
    FILE_TOO_LARGE,
    UNSUPPORTED_ENCODING,
    INVALID_ACTION,
    INVALID_RESPONSE_MODE,
    FILE_READ_FAILURE,
    UNEXPECTED_FAILURE,
    INVALID_REQUEST_BODY,
    INVALID_HISTORY_LIMIT,
    INVALID_HISTORY_CURSOR,
    INVALID_HISTORY_FILTER,
    HISTORY_UNAVAILABLE,
)
