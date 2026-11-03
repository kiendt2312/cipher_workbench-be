## MODIFIED Requirements

### Requirement: Vector Playfair canonical hoàn chỉnh

Hệ thống SHALL tạo đúng các vector bên dưới với keyword `PLAYFAIR EXAMPLE`; các vector này cố định đồng thời matrix, normalization, digraph preparation, hướng dịch và bộ nhận diện filler. (Truy vết: scope mới BE-PLAY-01, BE-PLAY-02; quyết định chủ sở hữu cho change Playfair/Vigenère; yêu cầu chủ sở hữu ngày 2026-10-01 cho bản thô và bản lọc)

#### Scenario: Encrypt vector canonical đầy đủ
- **WHEN** encrypt `HIDE THE GOLD IN THE TREE STUMP` với keyword `PLAYFAIR EXAMPLE`
- **THEN** plaintext prepared là `HIDETHEGOLDINTHETREXESTUMP`
- **AND** ciphertext là `BMODZBXDNABEKUDMUIXMMOUVIF`

#### Scenario: Decrypt vector canonical đầy đủ
- **WHEN** decrypt `BMODZBXDNABEKUDMUIXMMOUVIF` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả thô là `HIDETHEGOLDINTHETREXESTUMP`
- **AND** filler được nhận diện ở vị trí `19` và bản lọc là `HIDETHEGOLDINTHETREESTUMP`

#### Scenario: Encrypt vector repeated XX
- **WHEN** encrypt `XX` với keyword `PLAYFAIR EXAMPLE`
- **THEN** plaintext prepared là `XQXQ`
- **AND** ciphertext là `GWGW`

#### Scenario: Encrypt vector odd trailing X
- **WHEN** encrypt `ABX` với keyword `PLAYFAIR EXAMPLE`
- **THEN** plaintext prepared là `ABXQ`
- **AND** ciphertext là `PDGW`

#### Scenario: Decrypt vector fallback Q
- **WHEN** decrypt `GWGW` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả thô là `XQXQ`
- **AND** filler `Q` được nhận diện ở vị trí `1` và `3`, bản lọc là `XX`

## REMOVED Requirements

### Requirement: Decrypt bỏ filler cuối và không hứa round-trip lossless

**Reason**: Yêu cầu chủ sở hữu ngày 2026-10-01 đồng bộ Playfair với Hill: `result` decrypt luôn là bản thô toán học, còn việc lọc ký tự đệm chuyển sang `padding.filtered` để FE bật/tắt bằng toggle. Quy tắc bỏ đúng một filler cuối ngày 2026-09-28 bị thay thế.

**Migration**: Dùng requirement "Decrypt trả bản thô và nhận diện filler". Client cần chuỗi đã bỏ filler thì đọc `padding.filtered` thay vì `result`; với attachment file, gửi `strip_padding=true`.

## ADDED Requirements

### Requirement: Decrypt trả bản thô và nhận diện filler

Kết quả decrypt SHALL là chuỗi uppercase biến đổi từ các digraph ciphertext và giữ nguyên mọi ký tự, kể cả filler. Trên chuỗi thô `r` có độ dài chẵn `n`, hệ thống SHALL xét từng chỉ số lẻ `i` (chữ thứ hai của một digraph). Gọi `f` là `Q` nếu `r[i-1]` là `X`, ngược lại `f` là `X`. `r[i]` được nhận diện là filler khi `r[i] = f` và thỏa một trong hai điều kiện: `i + 1 < n` và `r[i+1] = r[i-1]` (filler giữa cặp chữ lặp), hoặc `i = n - 1` (filler cuối). Các chữ ở chỉ số chẵn MUST NOT bị nhận diện là filler. Bản lọc là `r` bỏ đúng các filler đã nhận diện. Hệ thống MUST NOT phục hồi whitespace, case, dấu câu hay Unicode đã bị loại, và không đổi `I` trở lại `J`. Ciphertext không phân biệt được filler với chữ thật, nên bản lọc SHALL mất chữ thật trùng mẫu filler (plaintext có số chữ chẵn kết thúc bằng `X`, hoặc chuỗi thật dạng `aXa` bắt đầu ở ranh giới digraph); kết quả thô luôn giữ các chữ đó. Response thành công MUST NOT thêm `normalizedInput`. (Truy vết: scope mới BE-PLAY-02, BE-PLAY-06; yêu cầu chủ sở hữu ngày 2026-10-01 và quyết định (b) cho change này, thay thế quy tắc bỏ một filler cuối ngày 2026-09-28)

#### Scenario: Filler giữa chữ lặp được nhận diện
- **WHEN** encrypt rồi decrypt plaintext `BALLOON` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả thô là `BALXLOON`
- **AND** filler ở vị trí `3` và bản lọc là `BALLOON`

#### Scenario: X thật giữa hai chữ khác nhau được giữ
- **WHEN** encrypt rồi decrypt plaintext `TAXICAB` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả thô là `TAXICABX`
- **AND** chỉ filler cuối ở vị trí `7` được nhận diện, bản lọc là `TAXICAB`

#### Scenario: Filler cuối được nhận diện
- **WHEN** encrypt rồi decrypt plaintext `ABX` hoặc `ABC` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả thô lần lượt là `ABXQ` và `ABCX`
- **AND** bản lọc lần lượt là `ABX` và `ABC`

#### Scenario: Plaintext chẵn kết thúc bằng X mất X cuối trong bản lọc
- **WHEN** encrypt rồi decrypt plaintext `AX` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả thô là `AX`
- **AND** bản lọc là `A`

#### Scenario: Chuỗi gốc không thể được phục hồi lossless
- **WHEN** encrypt rồi decrypt plaintext `Jig saw!` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả thô là `IXIGSAWX`, filler ở vị trí `1` và `7`, bản lọc là `IIGSAW`
- **AND** hệ thống không khôi phục chữ `J`, lowercase, khoảng trắng hoặc dấu `!`
