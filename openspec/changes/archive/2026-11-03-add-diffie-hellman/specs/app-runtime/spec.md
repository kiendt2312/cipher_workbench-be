# Spec Delta

## MODIFIED Requirements

### Requirement: Trần hạ tầng 64 MiB bảo vệ mọi request

Theo ngoại lệ hạ tầng được chủ sở hữu phê duyệt, ứng dụng SHALL từ chối ở tầng 0 mọi request có `Content-Length` lớn hơn 64 MiB trước khi đọc hoặc phân tích thân yêu cầu. Đây là trần chống lạm dụng, không đổi giới hạn file 5 MiB. Route cũ giữ exact envelope hiện hữu; sáu route `/api/dh/*` SHALL dùng `{success:false,code:"REQUEST_TOO_LARGE",message:"Yêu cầu vượt quá dung lượng cho phép.",field:null}`. (Truy vết: main `app-runtime`; Scope DH BE-07; quyết định chủ sở hữu DH Q6)

#### Scenario: Request text vượt trần hạ tầng
- **WHEN** client gửi request tới API văn bản với `Content-Length` lớn hơn 64 MiB
- **THEN** ứng dụng từ chối trước khi phân tích body với HTTP 413
- **AND** thân phản hồi là `{"success": false, "message": "Yêu cầu vượt quá dung lượng cho phép."}`
- **AND** thông báo không nêu con số 64 MiB

#### Scenario: Request file vượt trần hạ tầng
- **WHEN** client gửi request tới API file với `Content-Length` lớn hơn 64 MiB
- **THEN** ứng dụng từ chối trước khi phân tích multipart với HTTP 413
- **AND** thân phản hồi là `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

#### Scenario: Request không vượt trần tiếp tục được validate
- **WHEN** request có `Content-Length` bằng hoặc nhỏ hơn 64 MiB, hoặc không có/không đọc được header này
- **THEN** tầng 0 không từ chối request vì trần hạ tầng
- **AND** request tiếp tục tới bước phân tích body và validation nghiệp vụ tương ứng

#### Scenario: Trần hạ tầng giống nhau giữa local và container
- **WHEN** gửi cùng một request vượt 64 MiB tới ứng dụng chạy local và ứng dụng chạy trong container
- **THEN** hai môi trường trả cùng HTTP status, cùng error envelope và cùng thông báo theo tuyến

#### Scenario: DH request vượt trần dùng four-field envelope
- **WHEN** bất kỳ route `/api/dh/*` nhận `Content-Length` lớn hơn 64 MiB
- **THEN** HTTP 413 được trả trước khi đọc body
- **AND** body đúng bằng `{"success":false,"code":"REQUEST_TOO_LARGE","message":"Yêu cầu vượt quá dung lượng cho phép.","field":null}`
- **AND** không thay đổi envelope của route không phải DH
