## Purpose

Định nghĩa hợp đồng chung của object `padding` mà response decrypt Playfair và Hill trả kèm bản giải mã thô, để FE có toggle lọc ký tự đệm bật/tắt tức thì mà không phải gọi lại API.

## ADDED Requirements

### Requirement: Object padding trên response decrypt

Mọi response thành công của `POST /api/playfair/decrypt`, của `POST /api/playfair/file` khi `action=decrypt` và `response_mode=content`, và của `POST /api/hill/decrypt` SHALL có trường top-level `padding`. Đây là object có đúng ba trường: `count` (số nguyên ≥ 0), `positions` (mảng số nguyên ≥ 0, tăng dần nghiêm ngặt) và `filtered` (chuỗi). Khi không nhận diện được ký tự đệm, `padding` vẫn có mặt với `count=0`, `positions=[]` và `filtered` bằng `result`. Response encrypt của Playfair và Hill, response lỗi và response của mọi cipher khác MUST NOT có `padding`. (Truy vết: yêu cầu chủ sở hữu ngày 2026-10-01; quyết định chủ sở hữu (a) cho change này)

#### Scenario: Decrypt Hill có hai ký tự đệm
- **WHEN** decrypt `HQKRJYDPDONU` với khóa `[[6,1,3],[17,5,7],[3,2,3]]` và options mặc định
- **THEN** `result` là `THUDOHANOIXX`
- **AND** `padding` là `{"count":2,"positions":[10,11],"filtered":"THUDOHANOI"}`

#### Scenario: Decrypt không có ký tự đệm vẫn có padding
- **WHEN** decrypt Playfair `DKQNOIIAXE` với keyword `PLAYFAIR EXAMPLE`
- **THEN** `result` là `BOOKKEEPER`
- **AND** `padding` là `{"count":0,"positions":[],"filtered":"BOOKKEEPER"}`

#### Scenario: Encrypt không có padding
- **WHEN** encrypt Hill `HELLO` với K `[[3,3],[2,5]]` hoặc encrypt Playfair `BALLOON` với keyword hợp lệ
- **THEN** response thành công không có key `padding`

### Requirement: Bất biến giữa result, positions và filtered

`result` SHALL là bản giải mã thô toán học và MUST NOT bị bộ lọc thay đổi. `positions` SHALL là chỉ số 0-based trong dãy chữ cái tham gia biến đổi, theo thứ tự xử lý. Với Playfair, dãy này trùng với `result`. Với Hill, dãy này trùng với dãy `output` nối liền của `blocks`: vị trí `p` nằm ở khối `⌊p/m⌋`, ô `p mod m`. `count` SHALL bằng số phần tử của `positions`. `filtered` SHALL bằng `result` sau khi bỏ đúng các chữ cái tại `positions`, giữ nguyên mọi ký tự khác cùng thứ tự và case. Bộ lọc MUST NOT tạo, đổi case hoặc di chuyển ký tự. Quy tắc nhận diện riêng của từng hệ mã thuộc `playfair-core` và `hill-core`. (Truy vết: quyết định chủ sở hữu (a) cho change này)

#### Scenario: Hill giữ dấu câu khi lọc
- **WHEN** decrypt Hill `DPDKK!B` với K `[[3,3],[2,5]]`
- **THEN** `result` là `HELLO!X`, `padding.positions` là `[5]` và `padding.filtered` là `HELLO!`

#### Scenario: Playfair bỏ filler giữa chuỗi trong bản lọc
- **WHEN** decrypt Playfair `DPYRANQO` với keyword `PLAYFAIR EXAMPLE`
- **THEN** `result` là `BALXLOON`
- **AND** `padding` là `{"count":1,"positions":[3],"filtered":"BALLOON"}`

### Requirement: Toggle lọc ký tự đệm phía FE

Hướng dẫn FE SHALL mô tả một toggle dùng chung cho Playfair và Hill có nhãn `Tự động lọc ký tự đệm (Playfair/Hill padding)`. Toggle bật thì FE hiển thị, sao chép và tải `padding.filtered`; tắt thì dùng `result`. Với kết quả text, đổi trạng thái toggle MUST NOT cần gọi lại API. Hướng dẫn SHALL chỉ cách dùng `positions` để đánh dấu ký tự đệm trong bản thô. Hướng dẫn SHALL nêu rõ giới hạn: chữ thật trùng mẫu ký tự đệm có thể bị lọc nhầm, nên bản thô phải luôn xem được. Với file Playfair tải bằng attachment, FE SHALL gửi `strip_padding` khớp trạng thái toggle. Mặc định của toggle do FE quyết định. (Truy vết: yêu cầu chủ sở hữu ngày 2026-10-01)

#### Scenario: Tắt toggle trả về bản thô ngay
- **WHEN** người dùng đã decrypt Hill `HQKRJYDPDONU` với toggle bật rồi tắt toggle
- **THEN** FE chuyển hiển thị từ `THUDOHANOI` sang `THUDOHANOIXX`
- **AND** FE không gửi request mới
