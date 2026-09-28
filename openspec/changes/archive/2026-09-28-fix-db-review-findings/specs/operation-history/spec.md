## MODIFIED Requirements

### Requirement: Không bao giờ lưu nội dung hay dữ liệu định danh

Hệ thống MUST NOT lưu plaintext, ciphertext, key (kể cả `a`, `b`), tên file, nội dung file, header request, IP, user agent hay message lỗi. Độ dài SHALL là số Unicode code point cho nguồn text và số byte cho nguồn file. Với nguồn file, cả `input_length` lẫn `output_length` SHALL tính UTF-8 BOM nếu file đầu vào có BOM, ở cả hai `response_mode`. (Truy vết: quyết định chủ sở hữu 2026-09-28; ràng buộc stateless trong `openspec/config.yaml`)

#### Scenario: Không lưu nội dung
- **WHEN** client encrypt `"Attack at dawn!"` với key `"LEMON"` qua `POST /api/vigenere/encrypt`
- **THEN** bản ghi mới có `cipher = "vigenere"`, `operation = "encrypt"`, `source = "text"`, `input_length = 15`, `output_length = 15`, `http_status = 200`, `succeeded = true`
- **AND** không cột nào trong DB chứa `Attack`, `LEMON` hay `Lxfopv`

#### Scenario: File có BOM
- **WHEN** client gửi file `.txt` gồm BOM và `"é"` tới `POST /api/caesar/file` với `action = encrypt`
- **THEN** bản ghi mới có `input_length = 5` và `output_length = 5`
