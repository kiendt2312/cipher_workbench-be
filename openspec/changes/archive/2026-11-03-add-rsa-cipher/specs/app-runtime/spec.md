# Spec Delta

## MODIFIED Requirements

### Requirement: Trần hạ tầng 64 MiB bảo vệ mọi request

Theo ngoại lệ hạ tầng được chủ sở hữu phê duyệt, ứng dụng SHALL từ chối ở tầng 0 mọi request có `Content-Length` lớn hơn 64 MiB trước khi đọc hoặc phân tích thân yêu cầu. Đây là trần chống lạm dụng của hạ tầng OpenSpec, MUST NOT thay đổi giới hạn nghiệp vụ file 5 MiB trong docx, giới hạn RSA file 1.000.000 byte, hoặc được coi là thông báo nghiệp vụ bổ sung của các scope đó. Việc chọn thông báo và envelope SHALL dựa trên tuyến: request tới API file hiện hữu SHALL dùng thông báo file hiện có `File vượt quá dung lượng tối đa 5 MB.`; request tới route hiện hữu khác SHALL dùng `Yêu cầu vượt quá dung lượng cho phép.`; cả hai giữ exact error envelope hai trường `success` và `message`, không machine code. Riêng bốn route bắt đầu `/api/rsa/` SHALL trả HTTP 413 với exact RSA envelope `{"success":false,"code":"REQUEST_TOO_LARGE","message":"Yêu cầu vượt quá dung lượng cho phép.","field":null}`, kể cả multipart `/api/rsa/encrypt`. Thông báo công khai generic MUST NOT nêu con số 64 MiB. Request có `Content-Length` bằng hoặc nhỏ hơn 64 MiB, hoặc không có/không đọc được header này, SHALL đi tiếp tới bước phân tích và validation tương ứng. Hành vi này MUST giống nhau khi chạy local và trong container. Mọi route không phải RSA MUST giữ nguyên behavior baseline. (Truy vết: ngoại lệ hạ tầng OpenSpec đã được chấp thuận; main spec hiện tại; quyết định chủ sở hữu RSA Q2, Q5, Q8, Q15)

#### Scenario: Request text vượt trần hạ tầng

- **WHEN** client gửi request tới API văn bản không phải RSA với `Content-Length` lớn hơn 64 MiB
- **THEN** ứng dụng từ chối trước khi phân tích body với HTTP 413
- **AND** thân phản hồi là `{"success": false, "message": "Yêu cầu vượt quá dung lượng cho phép."}`
- **AND** thông báo không nêu con số 64 MiB

#### Scenario: Request file vượt trần hạ tầng

- **WHEN** client gửi request tới API file không phải RSA với `Content-Length` lớn hơn 64 MiB
- **THEN** ứng dụng từ chối trước khi phân tích multipart với HTTP 413
- **AND** thân phản hồi là `{"success": false, "message": "File vượt quá dung lượng tối đa 5 MB."}`

#### Scenario: Request RSA vượt trần hạ tầng

- **WHEN** client gửi JSON hoặc multipart tới một trong bốn RSA route với `Content-Length` lớn hơn 64 MiB
- **THEN** ứng dụng từ chối trước khi đọc/phân tích body với HTTP 413
- **AND** thân phản hồi là `{"success":false,"code":"REQUEST_TOO_LARGE","message":"Yêu cầu vượt quá dung lượng cho phép.","field":null}`

#### Scenario: Request không vượt trần tiếp tục được validate

- **WHEN** request có `Content-Length` bằng hoặc nhỏ hơn 64 MiB, hoặc không có/không đọc được header này
- **THEN** tầng 0 không từ chối request vì trần hạ tầng
- **AND** request tiếp tục tới bước phân tích body và validation nghiệp vụ tương ứng

#### Scenario: Trần hạ tầng giống nhau giữa local và container

- **WHEN** gửi cùng một request vượt 64 MiB tới ứng dụng chạy local và ứng dụng chạy trong container
- **THEN** hai môi trường trả cùng HTTP status, cùng error envelope và cùng thông báo theo tuyến
