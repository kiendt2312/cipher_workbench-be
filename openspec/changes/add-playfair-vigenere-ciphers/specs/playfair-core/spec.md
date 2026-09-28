## Purpose

Định nghĩa biến thể Playfair canonical 5×5 duy nhất của dự án, từ chuẩn hóa keyword/input và chuẩn bị digraph đến các phép encrypt/decrypt cùng giới hạn round-trip có chủ ý.

## ADDED Requirements

### Requirement: Chuẩn hóa keyword Playfair theo thứ tự xác định

Hệ thống SHALL chuẩn hóa keyword đúng thứ tự: (1) chuyển các ký tự ASCII `a-z` sang uppercase `A-Z`; (2) giữ lại duy nhất ASCII letter `A-Z`; (3) ánh xạ `J` thành `I`; (4) loại ký tự trùng, giữ lần xuất hiện đầu tiên. Bước uppercase SHALL là ánh xạ ASCII, MUST NOT transliterate hoặc dùng Unicode case expansion để biến ký tự non-ASCII thành một hay nhiều ASCII letter. Khoảng trắng, chữ số, dấu câu, chữ có dấu và Unicode ngoài ASCII SHALL bị loại chứ không gây lỗi nếu sau bước chuẩn hóa vẫn còn ít nhất một chữ cái. Keyword có kết quả rỗng sau chuẩn hóa MUST bị từ chối. (Truy vết: scope mới BE-PLAY-01, BE-PLAY-04, BE-PLAY-05; quyết định chủ sở hữu cho change này)

#### Scenario: Chuẩn hóa keyword PLAYFAIR EXAMPLE
- **WHEN** keyword là `PLAYFAIR EXAMPLE`
- **THEN** keyword chuẩn hóa và loại trùng là `PLAYFIREXM`

#### Scenario: J được nhập chung vào I trước khi loại trùng
- **WHEN** keyword là `JIG`
- **THEN** kết quả chuẩn hóa là `IG`

#### Scenario: Keyword Unicode-only trở thành rỗng
- **WHEN** keyword là `đỏ`, `ß` hoặc `123 !`
- **THEN** kết quả chuẩn hóa không có chữ cái hợp lệ
- **AND** keyword bị coi là không hợp lệ

### Requirement: Dựng ma trận Playfair 5×5 row-major

Hệ thống SHALL dựng ma trận 5×5 bằng cách điền keyword đã chuẩn hóa theo thứ tự row-major từ trái sang phải, trên xuống dưới, sau đó điền các chữ cái chưa xuất hiện của alphabet `A-Z` theo thứ tự bảng chữ cái và bỏ `J`. Mỗi chữ cái trong tập `A B C D E F G H I K L M N O P Q R S T U V W X Y Z` MUST xuất hiện đúng một lần. (Truy vết: scope mới BE-PLAY-01; quyết định chủ sở hữu cho change này)

#### Scenario: Ma trận chuẩn PLAYFAIR EXAMPLE
- **WHEN** keyword là `PLAYFAIR EXAMPLE`
- **THEN** ma trận được dựng chính xác là:

```text
P L A Y F
I R E X M
B C D G H
K N O Q S
T U V W Z
```

### Requirement: Chuẩn hóa plaintext Playfair

Trước khi tạo digraph để encrypt, hệ thống SHALL chuyển ASCII `a-z` sang `A-Z`, giữ lại duy nhất ASCII letter, rồi ánh xạ `J` thành `I`. Hệ thống MUST NOT transliterate hoặc dùng Unicode case expansion để biến ký tự non-ASCII thành dữ liệu Playfair. Mọi whitespace, newline, chữ số, dấu câu, chữ có dấu, emoji và Unicode ngoài ASCII SHALL bị loại. Plaintext không còn chữ cái hợp lệ sau chuẩn hóa MUST bị từ chối. (Truy vết: scope mới BE-PLAY-01, BE-PLAY-03, BE-PLAY-04; quyết định chủ sở hữu cho change này)

#### Scenario: Loại format và ánh xạ J
- **WHEN** plaintext là `Jolly, café! 123`
- **THEN** chuỗi trước bước tạo digraph là `IOLLYCAF`

#### Scenario: Plaintext không có ASCII letter
- **WHEN** plaintext là `123 — ộ 🙂`
- **THEN** chuỗi sau chuẩn hóa là rỗng
- **AND** input bị coi là không hợp lệ

### Requirement: Chuẩn bị digraph với filler X và fallback Q

Hệ thống SHALL duyệt chuỗi plaintext đã chuẩn hóa từ trái sang phải. Với ký tự hiện tại `a`: nếu không còn ký tự kế tiếp, hệ thống SHALL ghép `a` với `X`, trừ khi `a` là `X` thì SHALL dùng `Q`; nếu ký tự kế tiếp bằng `a`, hệ thống SHALL ghép `a` với `X`, trừ khi `a` là `X` thì SHALL dùng `Q`, và chỉ tiêu thụ ký tự `a` đầu tiên để ký tự lặp được xét lại ở vòng sau; nếu hai ký tự khác nhau, hệ thống SHALL ghép chúng và tiêu thụ cả hai. Kết quả MUST có độ dài chẵn và không có digraph chứa hai ký tự giống nhau. (Truy vết: scope mới BE-PLAY-01, BE-PLAY-05; quyết định chủ sở hữu cho change này)

#### Scenario: Chèn X giữa chữ cái lặp
- **WHEN** plaintext chuẩn hóa là `BALLOON`
- **THEN** chuỗi digraph đã chuẩn bị là `BA LX LO ON`
- **AND** biểu diễn liền là `BALXLOON`

#### Scenario: Fallback Q cho repeated XX
- **WHEN** plaintext chuẩn hóa là `XX`
- **THEN** ký tự `X` đầu được ghép với fallback `Q` và chỉ ký tự đầu được tiêu thụ
- **AND** ký tự `X` còn lại cũng được ghép với `Q` vì nằm cuối
- **AND** chuỗi digraph đã chuẩn bị là `XQ XQ`

#### Scenario: Fallback Q cho odd trailing X
- **WHEN** plaintext chuẩn hóa là `ABX`
- **THEN** chuỗi digraph đã chuẩn bị là `AB XQ`

#### Scenario: Odd trailing letter khác X dùng filler X
- **WHEN** plaintext chuẩn hóa là `ABC`
- **THEN** chuỗi digraph đã chuẩn bị là `AB CX`

### Requirement: Quy tắc biến đổi từng digraph

Với mỗi digraph gồm hai ô khác nhau trong ma trận: encrypt cùng hàng SHALL dịch mỗi chữ sang ô bên phải một vị trí; decrypt cùng hàng SHALL dịch sang trái; encrypt cùng cột SHALL dịch xuống một vị trí; decrypt cùng cột SHALL dịch lên; mọi phép dịch SHALL wrap ở biên. Với hai ô tạo hình chữ nhật, cả encrypt và decrypt SHALL giữ nguyên hàng của từng chữ và thay cột bằng cột của chữ còn lại. (Truy vết: scope mới BE-PLAY-01; quyết định chủ sở hữu cho change này)

#### Scenario: Encrypt cùng hàng có wraparound
- **WHEN** dùng ma trận `PLAYFAIR EXAMPLE` để encrypt digraph `FP`
- **THEN** kết quả là `PL`

#### Scenario: Decrypt cùng cột có wraparound
- **WHEN** dùng ma trận `PLAYFAIR EXAMPLE` để decrypt digraph `PB`
- **THEN** kết quả là `TI`

#### Scenario: Quy tắc hình chữ nhật
- **WHEN** dùng ma trận `PLAYFAIR EXAMPLE` để encrypt digraph `HI`
- **THEN** kết quả là `BM`

### Requirement: Vector Playfair canonical hoàn chỉnh

Hệ thống SHALL tạo đúng các vector bên dưới với keyword `PLAYFAIR EXAMPLE`; các vector này cố định đồng thời matrix, normalization, digraph preparation và hướng dịch. (Truy vết: scope mới BE-PLAY-01, BE-PLAY-02; quyết định chủ sở hữu cho change này)

#### Scenario: Encrypt vector canonical đầy đủ
- **WHEN** encrypt `HIDE THE GOLD IN THE TREE STUMP` với keyword `PLAYFAIR EXAMPLE`
- **THEN** plaintext prepared là `HIDETHEGOLDINTHETREXESTUMP`
- **AND** ciphertext là `BMODZBXDNABEKUDMUIXMMOUVIF`

#### Scenario: Decrypt vector canonical đầy đủ
- **WHEN** decrypt `BMODZBXDNABEKUDMUIXMMOUVIF` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả là `HIDETHEGOLDINTHETREXESTUMP`

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
- **THEN** kết quả là `XQX`
- **AND** chỉ filler `Q` cuối bị bỏ

### Requirement: Chuẩn hóa và kiểm tra ciphertext trước khi decrypt

Ciphertext Playfair SHALL được chuẩn hóa bằng uppercase, giữ lại ASCII `A-Z` và ánh xạ `J` thành `I`, giống bước chuẩn hóa ký tự nhưng không chèn filler. Hệ thống MUST từ chối ciphertext nếu không còn ký tự hợp lệ, nếu số ký tự sau chuẩn hóa là lẻ, hoặc nếu bất kỳ digraph nào gồm hai ký tự giống nhau; hệ thống SHALL không tự thêm filler để sửa ciphertext decrypt. (Truy vết: scope mới BE-PLAY-04, BE-PLAY-05; quyết định chủ sở hữu cho change này)

#### Scenario: Ciphertext lẻ bị từ chối
- **WHEN** ciphertext sau chuẩn hóa là `ABC`
- **THEN** input bị coi là không hợp lệ vì không thể chia hoàn toàn thành digraph

#### Scenario: Ciphertext có cặp trùng bị từ chối
- **WHEN** ciphertext sau chuẩn hóa là `AABC`
- **THEN** input bị coi là không hợp lệ vì digraph đầu là `AA`

#### Scenario: Decrypt không tự pad ciphertext
- **WHEN** ciphertext sau chuẩn hóa là `X`
- **THEN** hệ thống không ghép thêm `Q` hoặc `X`
- **AND** input bị coi là không hợp lệ

### Requirement: Decrypt bỏ filler cuối và không hứa round-trip lossless

Kết quả decrypt SHALL là chuỗi uppercase đã được biến đổi từ các digraph ciphertext, sau đó bỏ đúng một filler cuối chuỗi: nếu kết quả kết thúc bằng `XQ` thì bỏ `Q`, ngược lại nếu kết thúc bằng `X` thì bỏ `X`. Hệ thống MUST giữ nguyên mọi `X`/`Q` khác, không phục hồi whitespace/case/dấu câu/Unicode đã bị loại và không đổi `I` trở lại `J`. Vì ciphertext không phân biệt filler với chữ thật, plaintext có số chữ chẵn kết thúc bằng `X` SHALL mất `X` cuối. (Truy vết: quyết định chủ sở hữu 2026-09-28, thay thế quy tắc giữ mọi filler) Response thành công MUST chỉ chứa `result`; MUST NOT thêm `normalizedInput`. (Truy vết: scope mới BE-PLAY-02, BE-PLAY-06; quyết định chủ sở hữu cho change này)

#### Scenario: Filler giữa chữ lặp được giữ lại
- **WHEN** encrypt rồi decrypt plaintext `BALLOON` với cùng keyword hợp lệ
- **THEN** kết quả decrypt là `BALXLOON`
- **AND** hệ thống không tự loại `X` giữa chuỗi

#### Scenario: Filler cuối bị bỏ
- **WHEN** encrypt rồi decrypt plaintext `ABX` hoặc `ABC` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả decrypt lần lượt là `ABX` và `ABC`

#### Scenario: Plaintext chẵn kết thúc bằng X mất X cuối
- **WHEN** encrypt rồi decrypt plaintext `AX` với keyword `PLAYFAIR EXAMPLE`
- **THEN** kết quả decrypt là `A`

#### Scenario: Chuỗi gốc không thể được phục hồi lossless
- **WHEN** encrypt rồi decrypt plaintext `Jig saw!` với cùng keyword hợp lệ
- **THEN** kết quả chỉ phản ánh chuỗi normalized/prepared dùng bởi Playfair
- **AND** hệ thống không khôi phục chữ `J`, lowercase, khoảng trắng hoặc dấu `!`

### Requirement: Cùng core cho text và nội dung file

Với cùng chuỗi Unicode đã đọc từ request JSON hoặc file UTF-8, cùng keyword và operation, hệ thống SHALL tạo cùng kết quả Playfair. Lõi Playfair SHALL không phụ thuộc filename, transport, response mode hoặc trạng thái BOM. (Truy vết: scope mới BE-PLAY-01, BE-PLAY-03; baseline Caesar Week 1 `caesar-core`)

#### Scenario: Text và file dùng cùng normalization
- **WHEN** chuỗi `HIDE THE GOLD` từ JSON và cùng chuỗi đọc từ file được encrypt với keyword `PLAYFAIR EXAMPLE`
- **THEN** cả hai luồng chuẩn bị plaintext thành `HIDETHEGOLDX`
- **AND** cùng tạo ciphertext `BMODZBXDNAGE`
