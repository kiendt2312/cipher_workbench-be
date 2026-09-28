## Purpose

Capability `web-ui` đặc tả giao diện web Caesar Cipher được phục vụ trực tiếp từ chính ứng dụng backend: chọn chế độ mã hóa/giải mã, nhập văn bản từ bàn phím hoặc tải file `.txt`, nhập khóa dịch chuyển, xem kết quả kèm tab phân tích và bảng dịch chuyển bảng chữ cái, rồi sao chép hoặc tải kết quả xuống. Spec này chỉ mô tả hành vi quan sát được của giao diện, không quy định cấu trúc DOM, tên phần tử hay cách hiện thực bên trong.

## ADDED Requirements

### Requirement: Phục vụ giao diện từ chính ứng dụng, cùng origin

Giao diện web SHALL được phục vụ từ chính ứng dụng backend tại đường dẫn gốc `/`, không tách thành một dự án frontend riêng. Mọi lời gọi API từ giao diện SHALL dùng đường dẫn tương đối cùng origin với trang đang mở, do đó ứng dụng MUST NOT phụ thuộc vào cấu hình CORS hay vào một host/cổng được ghi cứng trong giao diện. (Truy vết: docx §2.2, §8)

#### Scenario: Mở trang gốc của ứng dụng

- **WHEN** người dùng mở đường dẫn gốc `/` của ứng dụng
- **THEN** giao diện Caesar Cipher được trả về và hiển thị đầy đủ: bộ chọn chế độ, panel đầu vào, panel kết quả, bảng dịch chuyển và khu vực nhập khóa

#### Scenario: Gọi API bằng đường dẫn tương đối

- **WHEN** người dùng thực hiện một thao tác mã hóa hoặc giải mã trên giao diện
- **THEN** yêu cầu được gửi tới cùng origin đang phục vụ trang bằng đường dẫn tương đối dưới tiền tố `/api/caesar/`
- **AND** thao tác thành công mà không cần bất kỳ header CORS nào từ máy chủ

#### Scenario: Truy cập qua host hoặc cổng khác

- **WHEN** ứng dụng được truy cập qua một host hoặc cổng khác với môi trường phát triển mặc định
- **THEN** giao diện vẫn gọi API thành công vì địa chỉ máy chủ được suy ra từ origin của trang, không ghi cứng trong giao diện

### Requirement: Mọi phép biến đổi Caesar đều do máy chủ thực hiện

Giao diện SHALL lấy kết quả mã hóa/giải mã từ phản hồi của máy chủ. Giao diện MUST NOT tự tính kết quả Caesar ở phía trình duyệt rồi hiển thị như kết quả thật, để bảo đảm cả luồng văn bản và luồng file đều dùng chung một lõi thuật toán duy nhất. Các phần minh họa như tô màu ký tự hay bảng dịch chuyển chỉ mang tính trực quan và không được coi là kết quả. (Truy vết: docx §2.1, §6)

#### Scenario: Không có kết quả khi máy chủ không phản hồi

- **WHEN** người dùng nhấn nút hành động với đầu vào và khóa hợp lệ nhưng máy chủ không phản hồi
- **THEN** vùng kết quả không hiển thị bất kỳ bản mã hay bản rõ nào
- **AND** giao diện báo lỗi kết nối thay vì tự sinh kết quả

#### Scenario: Kết quả hiển thị đúng bằng nội dung máy chủ trả về

- **WHEN** máy chủ trả về phản hồi thành công cho một yêu cầu mã hóa
- **THEN** chuỗi quan sát được trong vùng kết quả đúng từng ký tự với `result` do máy chủ trả về, không bị giao diện thêm ký tự xuống dòng hay sửa đổi nội dung
- **AND** thao tác sao chép và tải kết quả dùng đúng chuỗi đó, không thêm ký tự nào

### Requirement: Chọn chế độ mã hóa hoặc giải mã

Giao diện SHALL cho phép người dùng chọn giữa hai chế độ "Mã hóa" và "Giải mã", với đúng một chế độ được chọn tại mỗi thời điểm và chế độ mặc định là mã hóa. Khi đổi chế độ, nhãn panel đầu vào và panel kết quả SHALL hoán đổi giữa "Bản rõ" và "Bản mã", nhãn nút hành động SHALL đổi giữa "Mã hóa" và "Giải mã", và câu hướng dẫn phía trên SHALL đổi theo chế độ. (Truy vết: docx §2.2, §3.1)

#### Scenario: Chế độ mặc định khi mở trang

- **WHEN** người dùng mở giao diện lần đầu
- **THEN** chế độ mã hóa đang được chọn
- **AND** panel đầu vào có nhãn "Bản rõ", panel kết quả có nhãn "Bản mã" và nút hành động ghi "Mã hóa"

#### Scenario: Chuyển sang chế độ giải mã

- **WHEN** người dùng chọn chế độ "Giải mã"
- **THEN** panel đầu vào đổi nhãn thành "Bản mã", panel kết quả đổi nhãn thành "Bản rõ"
- **AND** nút hành động đổi nhãn thành "Giải mã"
- **AND** câu hướng dẫn đổi sang nội dung dành cho giải mã

#### Scenario: Đổi chế độ không làm mất đầu vào đang nhập

- **WHEN** người dùng đã nhập văn bản và khóa rồi đổi chế độ
- **THEN** nội dung văn bản và khóa đang nhập được giữ nguyên
- **AND** thông báo đang hiển thị (nếu có) được ẩn đi

### Requirement: Chọn nguồn đầu vào văn bản hoặc file

Giao diện SHALL cho phép người dùng chọn nguồn đầu vào là "Văn bản" (nhập từ bàn phím) hoặc "File .txt", với nguồn mặc định là Văn bản. Khi đổi nguồn, panel đầu vào SHALL chuyển sang dạng tương ứng: ô nhập văn bản cho nguồn Văn bản, vùng chọn/kéo-thả file cho nguồn File. (Truy vết: docx §2.2, §3.1, §3.2)

#### Scenario: Nguồn mặc định là văn bản

- **WHEN** người dùng mở giao diện lần đầu
- **THEN** nguồn đầu vào đang chọn là Văn bản
- **AND** panel đầu vào hiển thị ô nhập văn bản

#### Scenario: Chuyển sang nguồn file

- **WHEN** người dùng chọn nguồn đầu vào là File .txt
- **THEN** panel đầu vào thay ô nhập văn bản bằng vùng chọn file kèm vùng kéo-thả
- **AND** trạng thái đầu vào chuyển về mức trung tính với thông điệp cho biết chưa chọn file

#### Scenario: Quay lại nguồn văn bản

- **WHEN** người dùng đang ở nguồn File và chọn lại nguồn Văn bản
- **THEN** panel đầu vào hiển thị lại ô nhập văn bản cùng nội dung đã nhập trước đó

### Requirement: Nhập và dán văn bản có tô màu phân loại ký tự

Ở nguồn Văn bản, giao diện SHALL cung cấp một vùng nhập nhiều dòng để người dùng gõ hoặc dán văn bản, giữ nguyên xuống dòng và mọi ký tự Unicode. Nội dung đang nhập SHALL được tô màu phân biệt ba nhóm ký tự: chữ hoa ASCII, chữ thường ASCII và các ký tự giữ nguyên (số, dấu câu, khoảng trắng, Unicode). Việc tô màu MUST NOT làm thay đổi nội dung văn bản được gửi đi. (Truy vết: docx §2.2, §2.3)

#### Scenario: Tô màu ba nhóm ký tự

- **WHEN** người dùng nhập chuỗi chứa cả chữ hoa, chữ thường, số và ký tự tiếng Việt
- **THEN** chữ hoa ASCII, chữ thường ASCII và nhóm ký tự còn lại được hiển thị bằng ba màu khác nhau

#### Scenario: Dán văn bản nhiều dòng

- **WHEN** người dùng dán một đoạn văn bản nhiều dòng vào vùng nhập
- **THEN** toàn bộ ngắt dòng được giữ nguyên khi hiển thị
- **AND** trạng thái đầu vào cập nhật ngay theo nội dung vừa dán

#### Scenario: Nội dung gửi đi không bị tô màu làm sai lệch

- **WHEN** người dùng thực hiện mã hóa trên văn bản đã được tô màu
- **THEN** văn bản gửi tới máy chủ đúng bằng nội dung người dùng đã nhập, không kèm bất kỳ ký tự trang trí nào

### Requirement: Sao chép và xóa nội dung panel đầu vào

Panel đầu vào SHALL có nút "Sao chép" để sao chép nội dung đầu vào hiện tại vào bộ nhớ tạm và nút "Xóa" để xóa đầu vào. Nút "Sao chép" SHALL bị vô hiệu khi đầu vào rỗng. Ở nguồn File, nút "Xóa" SHALL gỡ bỏ file đang chọn. Khi không sao chép được vào bộ nhớ tạm, giao diện SHALL hiển thị thông báo cảnh báo hướng dẫn người dùng sao chép thủ công thay vì im lặng. (Truy vết: docx §2.2, §2.3)

#### Scenario: Sao chép văn bản đầu vào

- **WHEN** người dùng nhấn "Sao chép" ở panel đầu vào trong khi đang có văn bản
- **THEN** nội dung đầu vào được đưa vào bộ nhớ tạm
- **AND** giao diện hiển thị thông báo thành công

#### Scenario: Nút Sao chép bị vô hiệu khi chưa có đầu vào

- **WHEN** panel đầu vào đang rỗng
- **THEN** nút "Sao chép" của panel đầu vào ở trạng thái vô hiệu

#### Scenario: Xóa văn bản đầu vào

- **WHEN** người dùng nhấn "Xóa" ở nguồn Văn bản
- **THEN** vùng nhập văn bản trở nên rỗng
- **AND** trạng thái đầu vào quay về mức trung tính và nút hành động bị vô hiệu

#### Scenario: Xóa file đang chọn

- **WHEN** người dùng nhấn "Xóa" ở nguồn File trong khi đang có file được chọn
- **THEN** file được gỡ bỏ và panel đầu vào trở lại vùng chọn/kéo-thả file

#### Scenario: Trình duyệt chặn bộ nhớ tạm

- **WHEN** thao tác sao chép bị trình duyệt từ chối
- **THEN** giao diện hiển thị thông báo cảnh báo cho biết không sao chép được và gợi ý sao chép thủ công

### Requirement: Tạo ví dụ mẫu

Giao diện SHALL có một nút mang nhãn "Tạo ví dụ"; khi được kích hoạt, giao diện SHALL chuyển về nguồn Văn bản, điền sẵn văn bản "Hello World" và khóa `3`, đồng thời cập nhật trạng thái để nút hành động sẵn sàng sử dụng. (Truy vết: docx §2.3, §7)

#### Scenario: Điền ví dụ mẫu

- **WHEN** người dùng nhấn nút "Tạo ví dụ"
- **THEN** nguồn đầu vào chuyển về Văn bản, vùng nhập chứa "Hello World" và ô khóa chứa `3`
- **AND** trạng thái đầu vào và trạng thái khóa đều ở mức hợp lệ, nút hành động được bật

#### Scenario: Mã hóa ví dụ mẫu

- **WHEN** người dùng nhấn nút hành động ngay sau khi tạo ví dụ mẫu ở chế độ mã hóa
- **THEN** vùng kết quả hiển thị "Khoor Zruog"

### Requirement: Chọn file bằng nút bấm hoặc kéo-thả

Ở nguồn File, giao diện SHALL cho phép chọn file `.txt` theo hai cách: nhấn nút chọn file để mở hộp thoại của hệ điều hành, hoặc kéo-thả file vào vùng thả. Vùng thả SHALL có phản hồi trực quan khi file được kéo qua và trở lại trạng thái bình thường khi con trỏ rời đi hoặc khi file đã được thả. (Truy vết: docx §2.4, §3.2)

#### Scenario: Chọn file qua hộp thoại

- **WHEN** người dùng nhấn nút chọn file và chọn một file `.txt`
- **THEN** giao diện ghi nhận file đó làm đầu vào hiện tại

#### Scenario: Kéo-thả file vào vùng thả

- **WHEN** người dùng kéo một file `.txt` và thả vào vùng thả
- **THEN** giao diện ghi nhận file đó làm đầu vào hiện tại, tương đương với việc chọn qua hộp thoại

#### Scenario: Phản hồi trực quan khi kéo file qua vùng thả

- **WHEN** người dùng kéo một file ngang qua vùng thả
- **THEN** vùng thả đổi trạng thái hiển thị để báo hiệu có thể thả file tại đây
- **AND** trạng thái hiển thị đó được gỡ bỏ khi con trỏ rời khỏi vùng thả hoặc sau khi file được thả

### Requirement: Hiển thị thông tin file đã chọn

Sau khi chọn file, giao diện SHALL hiển thị tên file, kích thước và bản xem trước nội dung file với cùng quy tắc tô màu như panel văn bản. Kích thước SHALL được hiển thị bằng đơn vị nhị phân với nhãn đúng là byte, KiB hoặc MiB (1 KiB = 1024 byte, 1 MiB = 1024 KiB); giao diện MUST NOT gắn nhãn MB cho giá trị quy đổi theo bội số 1024. Giao diện SHALL cung cấp nút "Đổi file" để chọn file khác và nút "Gỡ file" để gỡ file hiện tại. (Truy vết: docx §2.4, §3.2, §5)

#### Scenario: Hiển thị tên, kích thước và xem trước

- **WHEN** người dùng vừa chọn một file `.txt` hợp lệ
- **THEN** giao diện hiển thị tên file, kích thước kèm nhãn đơn vị nhị phân và bản xem trước nội dung file
- **AND** bản xem trước tô màu chữ hoa, chữ thường và ký tự giữ nguyên như panel văn bản

#### Scenario: Nhãn đơn vị dung lượng là MiB

- **WHEN** người dùng chọn một file `.txt` có kích thước 2 097 152 byte
- **THEN** giao diện hiển thị kích thước đó với nhãn đơn vị `MiB`, không dùng nhãn `MB`
- **AND** mọi chỗ khác hiển thị giới hạn dung lượng cũng dùng nhãn `MiB`

#### Scenario: Đổi sang file khác

- **WHEN** người dùng nhấn "Đổi file" và chọn một file khác
- **THEN** tên file, kích thước và bản xem trước được cập nhật theo file mới
- **AND** kết quả của lần xử lý trước không còn được coi là kết quả của file mới

#### Scenario: Gỡ file đang chọn

- **WHEN** người dùng nhấn "Gỡ file"
- **THEN** thông tin file và bản xem trước bị xóa, panel đầu vào trở lại vùng chọn/kéo-thả
- **AND** nút hành động bị vô hiệu

### Requirement: Kiểm tra sơ bộ file trên giao diện với giới hạn 5 MiB

Giao diện SHALL kiểm tra sơ bộ file được chọn và đặt trạng thái đầu vào ở mức lỗi kèm mô tả tiếng Việt khi file không có đuôi `.txt` (không phân biệt hoa thường), khi file có kích thước 0 byte, hoặc khi file vượt quá 5 MiB. Mọi chỗ hiển thị giới hạn dung lượng cho người dùng SHALL ghi 5 MiB. File đúng 5 MiB SHALL được chấp nhận. Việc kiểm tra sơ bộ này không thay thế kiểm tra phía máy chủ; kiểm tra encoding UTF-8 SHALL do máy chủ quyết định. (Truy vết: docx §2.4, §5, §7)

#### Scenario: Hiển thị giới hạn dung lượng

- **WHEN** người dùng chuyển sang nguồn File
- **THEN** vùng chọn file ghi rõ chỉ nhận file `.txt` và dung lượng tối đa 5 MiB

#### Scenario: File sai đuôi mở rộng

- **WHEN** người dùng chọn hoặc kéo-thả một file không có đuôi `.txt`
- **THEN** trạng thái đầu vào chuyển sang mức lỗi với mô tả cho biết chỉ chấp nhận file `.txt`
- **AND** nút hành động bị vô hiệu

#### Scenario: File có đuôi .txt viết hoa

- **WHEN** người dùng chọn một file có đuôi `.TXT`
- **THEN** file được chấp nhận và trạng thái đầu vào ở mức hợp lệ

#### Scenario: File 0 byte

- **WHEN** người dùng chọn một file `.txt` có kích thước 0 byte
- **THEN** trạng thái đầu vào chuyển sang mức lỗi với mô tả cho biết file rỗng
- **AND** nút hành động bị vô hiệu

#### Scenario: File đúng 5 MiB được chấp nhận

- **WHEN** người dùng chọn một file `.txt` có kích thước đúng 5 MiB
- **THEN** trạng thái đầu vào ở mức hợp lệ và nút hành động được bật khi khóa cũng hợp lệ

#### Scenario: File vượt quá 5 MiB

- **WHEN** người dùng chọn một file `.txt` lớn hơn 5 MiB
- **THEN** trạng thái đầu vào chuyển sang mức lỗi với mô tả cho biết file vượt quá giới hạn 5 MiB
- **AND** nút hành động bị vô hiệu

#### Scenario: File chỉ chứa khoảng trắng vẫn hợp lệ

- **WHEN** người dùng chọn một file `.txt` khác 0 byte nhưng chỉ chứa khoảng trắng hoặc xuống dòng
- **THEN** trạng thái đầu vào ở mức hợp lệ và người dùng có thể thực hiện xử lý

### Requirement: Nhập khóa và hiển thị giá trị sau chuẩn hóa

Giao diện SHALL có ô nhập khóa nhận số nguyên có dấu, bao gồm số âm và số lớn hơn 25. Ô khóa SHALL chấp nhận dấu `-` hoặc dấu `+` đứng đầu và SHALL bỏ qua khoảng trắng thừa ở hai đầu trước khi diễn giải giá trị. Khi ô khóa vắng giá trị hoặc chỉ chứa khoảng trắng, trạng thái khóa SHALL nêu "Thiếu khóa."; khi ô khóa có giá trị nhưng không phải số nguyên, trạng thái khóa SHALL nêu "Khóa phải là số nguyên.". Khi khóa nằm ngoài khoảng 0–25, giao diện SHALL hiển thị giá trị sau chuẩn hóa bên cạnh ô nhập; khi khóa đã nằm trong 0–25 thì không hiển thị thêm giá trị nào. Giao diện SHALL kèm ghi chú giải thích quy tắc chuẩn hóa. Giá trị gửi lên máy chủ SHALL là khóa người dùng nhập, không phải giá trị đã chuẩn hóa ở giao diện. (Truy vết: docx §2.1, §2.2)

#### Scenario: Khóa lớn hơn 25

- **WHEN** người dùng nhập khóa `29`
- **THEN** giao diện hiển thị giá trị sau chuẩn hóa là `3`
- **AND** trạng thái khóa ở mức hợp lệ

#### Scenario: Khóa âm

- **WHEN** người dùng nhập khóa `-3`
- **THEN** giao diện hiển thị giá trị sau chuẩn hóa là `23`
- **AND** trạng thái khóa ở mức hợp lệ

#### Scenario: Khóa đã nằm trong khoảng 0–25

- **WHEN** người dùng nhập khóa `3`
- **THEN** trạng thái khóa ở mức hợp lệ và giao diện không hiển thị thêm giá trị chuẩn hóa

#### Scenario: Khóa có dấu cộng đứng đầu

- **WHEN** người dùng nhập khóa `+3`
- **THEN** trạng thái khóa ở mức hợp lệ, giao diện diễn giải giá trị là số nguyên `3`
- **AND** giao diện không báo lỗi định dạng khóa

#### Scenario: Khóa có khoảng trắng thừa hai đầu

- **WHEN** người dùng nhập khóa gồm số nguyên `-3` kèm khoảng trắng thừa ở đầu và cuối
- **THEN** khoảng trắng thừa được bỏ qua, trạng thái khóa ở mức hợp lệ và giá trị sau chuẩn hóa hiển thị là `23`

#### Scenario: Ô khóa để trống

- **WHEN** ô khóa đang rỗng hoặc chỉ chứa khoảng trắng
- **THEN** trạng thái khóa chuyển sang mức nêu rõ thiếu khóa với nội dung "Thiếu khóa."
- **AND** nút hành động bị vô hiệu

#### Scenario: Khóa không phải số nguyên

- **WHEN** người dùng nhập một giá trị có nội dung nhưng không phải số nguyên vào ô khóa
- **THEN** trạng thái khóa chuyển sang mức lỗi với nội dung "Khóa phải là số nguyên."
- **AND** nút hành động bị vô hiệu

#### Scenario: Gửi đúng khóa người dùng nhập

- **WHEN** người dùng nhập khóa `29` và thực hiện mã hóa
- **THEN** yêu cầu gửi lên máy chủ mang khóa `29`

### Requirement: Sao chép và xóa khóa

Khu vực khóa SHALL có nút "Sao chép" để sao chép giá trị khóa hiện tại và nút "Xóa" để xóa ô khóa. Nút "Sao chép" SHALL bị vô hiệu khi ô khóa rỗng. Sau khi xóa, tiêu điểm SHALL quay lại ô khóa và trạng thái khóa trở về mức trung tính. (Truy vết: docx §2.2)

#### Scenario: Sao chép khóa

- **WHEN** người dùng nhấn "Sao chép" ở khu vực khóa trong khi ô khóa có giá trị
- **THEN** giá trị khóa được đưa vào bộ nhớ tạm và giao diện hiển thị thông báo thành công

#### Scenario: Xóa khóa

- **WHEN** người dùng nhấn "Xóa" ở khu vực khóa
- **THEN** ô khóa trở nên rỗng, trạng thái khóa về mức trung tính và nút hành động bị vô hiệu

#### Scenario: Nút Sao chép khóa bị vô hiệu khi chưa nhập

- **WHEN** ô khóa đang rỗng
- **THEN** nút "Sao chép" của khu vực khóa ở trạng thái vô hiệu

### Requirement: Thanh trạng thái cho đầu vào, khóa và kết quả

Giao diện SHALL có ba thanh trạng thái độc lập: một cho đầu vào, một cho khóa và một cho kết quả. Mỗi thanh SHALL thể hiện một trong ba mức: trung tính (chưa có dữ liệu hoặc chưa xử lý), hợp lệ và lỗi; mức được phân biệt bằng cả màu sắc lẫn nội dung chữ để không phụ thuộc riêng vào màu. Nội dung thanh trạng thái SHALL cập nhật ngay khi dữ liệu tương ứng thay đổi. Đầu vào chỉ chứa khoảng trắng hoặc xuống dòng SHALL được coi là hợp lệ; giao diện MUST NOT xem đầu vào như vậy là rỗng hay là lỗi. (Truy vết: docx §2.2, §8)

#### Scenario: Trạng thái trung tính khi mới mở trang

- **WHEN** người dùng mở giao diện và chưa nhập gì
- **THEN** thanh trạng thái đầu vào, thanh trạng thái khóa và thanh trạng thái kết quả đều ở mức trung tính với mô tả tương ứng

#### Scenario: Trạng thái hợp lệ của đầu vào văn bản

- **WHEN** người dùng nhập văn bản khác rỗng
- **THEN** thanh trạng thái đầu vào chuyển sang mức hợp lệ kèm số ký tự và số dòng của văn bản

#### Scenario: Văn bản chỉ chứa khoảng trắng vẫn hợp lệ

- **WHEN** người dùng chỉ nhập khoảng trắng hoặc xuống dòng vào vùng văn bản
- **THEN** thanh trạng thái đầu vào ở mức hợp lệ
- **AND** nút hành động được bật khi khóa cũng hợp lệ

#### Scenario: Trạng thái lỗi được phân biệt không chỉ bằng màu

- **WHEN** một thanh trạng thái chuyển sang mức lỗi
- **THEN** thanh đó vừa đổi màu vừa hiển thị chỉ báo và nội dung chữ mô tả lỗi

### Requirement: Nút hành động chỉ bật khi đầu vào và khóa cùng hợp lệ

Nút hành động SHALL chỉ ở trạng thái bật khi cả trạng thái đầu vào và trạng thái khóa đều ở mức hợp lệ. Trong mọi trường hợp còn lại, nút hành động SHALL bị vô hiệu. Giao diện SHALL hiển thị ghi chú giải thích điều kiện bật nút. (Truy vết: docx §2.2, §3.1, §3.2)

#### Scenario: Thiếu khóa

- **WHEN** người dùng đã nhập văn bản nhưng chưa nhập khóa
- **THEN** nút hành động bị vô hiệu

#### Scenario: Thiếu đầu vào

- **WHEN** người dùng đã nhập khóa hợp lệ nhưng chưa nhập văn bản và chưa chọn file
- **THEN** nút hành động bị vô hiệu

#### Scenario: Đủ điều kiện

- **WHEN** cả đầu vào lẫn khóa đều ở mức hợp lệ
- **THEN** nút hành động được bật và mang nhãn tương ứng chế độ đang chọn

#### Scenario: Đầu vào trở nên không hợp lệ sau khi đã đủ điều kiện

- **WHEN** người dùng xóa hết văn bản trong khi nút hành động đang bật
- **THEN** nút hành động lập tức bị vô hiệu trở lại

### Requirement: Khóa nút hành động và hiển thị trạng thái trong lúc xử lý

Trong lúc chờ phản hồi từ máy chủ, giao diện SHALL vô hiệu hóa nút hành động, hiển thị chỉ báo đang xử lý trên nút và đặt thanh trạng thái kết quả sang trạng thái đang gửi yêu cầu, sao cho người dùng không thể gửi trùng lặp yêu cầu. Trong cùng khoảng thời gian đó, giao diện SHALL khóa toàn bộ cụm nhập liệu gồm vùng nhập văn bản hoặc vùng chọn/kéo-thả file, ô khóa, bộ chọn chế độ và bộ chọn nguồn đầu vào, để trạng thái đang hiển thị không lệch với yêu cầu đang được xử lý. Khi có phản hồi hoặc khi gặp lỗi, giao diện SHALL mở khóa lại toàn bộ cụm nhập liệu và trả nút hành động về trạng thái bình thường. (Truy vết: docx §2.2)

#### Scenario: Khóa nút trong lúc gửi

- **WHEN** người dùng nhấn nút hành động và yêu cầu đang được gửi đi
- **THEN** nút hành động bị vô hiệu và hiển thị chỉ báo đang xử lý
- **AND** thanh trạng thái kết quả cho biết đang gửi yêu cầu

#### Scenario: Khóa cả cụm nhập liệu trong lúc gửi

- **WHEN** một yêu cầu đang được gửi đi và chưa có phản hồi
- **THEN** vùng nhập đầu vào, ô khóa, bộ chọn chế độ và bộ chọn nguồn đầu vào đều bị khóa, không nhận thay đổi từ người dùng
- **AND** người dùng không thể đổi chế độ hay đổi nguồn đầu vào khiến trạng thái lệch với yêu cầu đang xử lý

#### Scenario: Khóa phím tắt và mọi cách kích hoạt vùng thả trong lúc gửi

- **WHEN** một yêu cầu đang được gửi đi và chưa có phản hồi
- **THEN** các phím tắt của giao diện không thay đổi trạng thái và không gửi thêm request
- **AND** click, Enter hoặc Space trên vùng thả không mở hộp chọn file
- **AND** việc thả một file thực tế lên vùng thả không thay thế file hay đầu vào đang gắn với request

#### Scenario: Không gửi trùng lặp

- **WHEN** người dùng cố kích hoạt nút hành động lần nữa trong lúc yêu cầu trước chưa hoàn tất
- **THEN** không có yêu cầu thứ hai nào được gửi đi

#### Scenario: Mở khóa sau khi có phản hồi

- **WHEN** máy chủ trả về phản hồi, dù thành công hay lỗi
- **THEN** nút hành động hết trạng thái đang xử lý và trở về nhãn tương ứng chế độ đang chọn
- **AND** vùng nhập đầu vào, ô khóa, bộ chọn chế độ và bộ chọn nguồn đầu vào được mở khóa trở lại
- **AND** nút được bật trở lại nếu đầu vào và khóa vẫn hợp lệ

### Requirement: Thông báo thành công, lỗi và cảnh báo đóng được

Giao diện SHALL hiển thị thông báo cho người dùng ở ba loại: thành công, lỗi và cảnh báo, phân biệt bằng cả màu lẫn nội dung chữ. Mỗi thông báo SHALL có cách để người dùng đóng lại. Thông báo SHALL tự ẩn khi người dùng thay đổi đầu vào, khóa, chế độ hoặc nguồn đầu vào để không hiển thị thông tin lỗi thời. (Truy vết: docx §2.2)

#### Scenario: Thông báo thành công sau khi xử lý

- **WHEN** máy chủ trả về phản hồi thành công
- **THEN** giao diện hiển thị thông báo thành công nêu rõ thao tác vừa thực hiện

#### Scenario: Đóng thông báo

- **WHEN** người dùng kích hoạt nút đóng của thông báo đang hiển thị
- **THEN** thông báo biến mất và phần còn lại của giao diện giữ nguyên trạng thái

#### Scenario: Thông báo tự ẩn khi đầu vào thay đổi

- **WHEN** một thông báo đang hiển thị và người dùng sửa văn bản, sửa khóa, đổi chế độ hoặc đổi nguồn đầu vào
- **THEN** thông báo đó được ẩn đi

### Requirement: Hiển thị lỗi từ máy chủ mà không lộ chi tiết kỹ thuật

Khi máy chủ trả về phản hồi lỗi, giao diện SHALL hiển thị đúng chuỗi `message` do máy chủ trả về cho người dùng và đặt thanh trạng thái kết quả sang mức lỗi. Giao diện MUST NOT hiển thị stack trace, mã ngoại lệ, thân phản hồi thô hay bất kỳ chi tiết kỹ thuật nào khác. Khi phản hồi lỗi không có `message` dùng được, giao diện SHALL hiển thị một thông báo lỗi chung bằng tiếng Việt. (Truy vết: docx §1, §5)

#### Scenario: Hiển thị nguyên văn thông báo lỗi của máy chủ

- **WHEN** máy chủ trả về lỗi với `message` là "File vượt quá dung lượng tối đa 5 MB."
- **THEN** giao diện hiển thị đúng chuỗi "File vượt quá dung lượng tối đa 5 MB." trong thông báo lỗi
- **AND** thanh trạng thái kết quả chuyển sang mức lỗi

#### Scenario: Hiển thị nguyên văn lỗi trần hạ tầng generic

- **WHEN** máy chủ trả HTTP 413 với `message` là "Yêu cầu vượt quá dung lượng cho phép."
- **THEN** giao diện hiển thị đúng chuỗi "Yêu cầu vượt quá dung lượng cho phép."
- **AND** thanh trạng thái kết quả chuyển sang mức lỗi

#### Scenario: Không lộ chi tiết kỹ thuật khi máy chủ lỗi hệ thống

- **WHEN** máy chủ trả về lỗi hệ thống với `message` là "Đã xảy ra lỗi hệ thống."
- **THEN** giao diện chỉ hiển thị chuỗi đó
- **AND** không có stack trace, tên ngoại lệ hay mã trạng thái kỹ thuật nào xuất hiện trên giao diện

#### Scenario: Phản hồi lỗi không đọc được

- **WHEN** máy chủ trả về phản hồi lỗi không đúng khuôn dạng chuẩn hoặc không có `message`
- **THEN** giao diện hiển thị một thông báo lỗi chung bằng tiếng Việt thay vì hiển thị nội dung phản hồi thô

#### Scenario: Kết quả cũ không bị giữ lại khi gặp lỗi

- **WHEN** một yêu cầu thất bại và trước đó đã có kết quả hiển thị
- **THEN** giao diện không trình bày kết quả cũ như kết quả của yêu cầu vừa thất bại

#### Scenario: Tải file kết quả thất bại sau một lượt thành công

- **WHEN** giao diện đang có kết quả và phân tích của một lượt thành công, rồi request tải file kết quả thất bại
- **THEN** giao diện xóa kết quả và phân tích cũ, đồng thời vô hiệu các hành động cần kết quả
- **AND** vùng kết quả trở về nội dung gợi ý thay vì tiếp tục hiển thị thành công cũ
- **AND** thanh trạng thái kết quả chuyển sang mức lỗi và thông báo hiển thị `message` của máy chủ

### Requirement: Xử lý lỗi không gọi được máy chủ

Khi không gọi được máy chủ, ví dụ mất mạng hoặc máy chủ không phản hồi, giao diện SHALL hiển thị thông báo lỗi kết nối rõ ràng bằng tiếng Việt và đặt thanh trạng thái kết quả sang mức lỗi. Giao diện SHALL không bị treo: nút hành động được mở khóa để người dùng thử lại và mọi thao tác khác vẫn dùng được. (Truy vết: docx §1, §2.2)

#### Scenario: Máy chủ không phản hồi

- **WHEN** người dùng nhấn nút hành động nhưng không kết nối được tới máy chủ
- **THEN** giao diện hiển thị thông báo lỗi kết nối bằng tiếng Việt
- **AND** thanh trạng thái kết quả chuyển sang mức lỗi

#### Scenario: Giao diện không bị treo sau lỗi kết nối

- **WHEN** vừa xảy ra lỗi kết nối
- **THEN** nút hành động hết trạng thái đang xử lý và được bật lại vì đầu vào và khóa vẫn hợp lệ
- **AND** người dùng có thể sửa đầu vào, sửa khóa hoặc nhấn lại nút hành động để thử lại

### Requirement: Vùng kết quả chỉ đọc có tô màu

Vùng kết quả SHALL là chỉ đọc: người dùng không chỉnh sửa được nội dung kết quả. Nội dung kết quả SHALL được tô màu phân biệt chữ hoa, chữ thường và ký tự giữ nguyên theo cùng quy tắc với panel đầu vào, đồng thời giữ nguyên xuống dòng và khoảng trắng. Khi chưa có kết quả, vùng kết quả SHALL hiển thị nội dung gợi ý cho biết kết quả sẽ xuất hiện sau khi xử lý. (Truy vết: docx §2.2, §2.3)

#### Scenario: Không chỉnh sửa được kết quả

- **WHEN** người dùng cố gõ hoặc sửa nội dung trong vùng kết quả
- **THEN** nội dung kết quả không thay đổi

#### Scenario: Tô màu kết quả

- **WHEN** vùng kết quả đang hiển thị một kết quả có cả chữ hoa, chữ thường và ký tự khác
- **THEN** ba nhóm ký tự được tô ba màu khác nhau như ở panel đầu vào

#### Scenario: Trạng thái rỗng của vùng kết quả

- **WHEN** người dùng chưa thực hiện xử lý lần nào
- **THEN** vùng kết quả hiển thị nội dung gợi ý cho biết kết quả sẽ hiển thị sau khi xử lý

#### Scenario: Giữ nguyên định dạng dòng của kết quả

- **WHEN** kết quả trả về có nhiều dòng và khoảng trắng đầu dòng
- **THEN** vùng kết quả hiển thị đúng các ngắt dòng và khoảng trắng đó

### Requirement: Tab kết quả dạng văn bản và tab phân tích

Panel kết quả SHALL có hai tab: tab "Văn bản" hiển thị nội dung kết quả và tab "Phân tích" hiển thị thống kê của lần xử lý gần nhất. Tab "Phân tích" SHALL hiển thị: chế độ đang dùng, nguồn đầu vào (kèm tên file khi nguồn là file), khóa nhập kèm khóa sau chuẩn hóa, tổng số ký tự, số chữ hoa được dịch chuyển, số chữ thường được dịch chuyển và số ký tự giữ nguyên. Mọi giá trị hiển thị trong tab này SHALL bằng tiếng Việt: chế độ hiển thị là "Mã hóa" hoặc "Giải mã", nguồn đầu vào hiển thị là "Văn bản" hoặc "File · <tên file>"; giao diện MUST NOT hiển thị các giá trị kỹ thuật tiếng Anh như `encrypt`, `decrypt`, `text` hay `file`. Chuyển tab MUST NOT làm mất kết quả đang có. (Truy vết: docx §2.3, §7)

#### Scenario: Tab mặc định là Văn bản

- **WHEN** người dùng vừa nhận được kết quả
- **THEN** tab "Văn bản" đang được chọn và hiển thị nội dung kết quả

#### Scenario: Xem tab Phân tích cho nguồn văn bản

- **WHEN** người dùng mã hóa văn bản "Hello World" với khóa `29` rồi mở tab "Phân tích"
- **THEN** tab hiển thị chế độ "Mã hóa", nguồn đầu vào "Văn bản", khóa nhập `29` kèm khóa chuẩn hóa `3`, tổng ký tự `11`, số chữ hoa dịch chuyển `2`, số chữ thường dịch chuyển `8` và số ký tự giữ nguyên `1`

#### Scenario: Xem tab Phân tích cho nguồn file

- **WHEN** người dùng xử lý một file và mở tab "Phân tích"
- **THEN** dòng nguồn đầu vào hiển thị "File · <tên file>" với đúng tên file đã chọn
- **AND** dòng chế độ hiển thị "Mã hóa" hoặc "Giải mã" theo chế độ vừa dùng

#### Scenario: Chuyển qua lại giữa hai tab

- **WHEN** người dùng chuyển sang tab "Phân tích" rồi quay lại tab "Văn bản"
- **THEN** nội dung kết quả vẫn còn nguyên và được hiển thị lại

### Requirement: Sao chép và xóa kết quả

Panel kết quả SHALL có nút "Sao chép" để sao chép toàn bộ kết quả vào bộ nhớ tạm và nút "Xóa" để xóa kết quả. Cả hai nút SHALL bị vô hiệu khi chưa có kết quả. Sau khi xóa kết quả, vùng kết quả SHALL trở về trạng thái rỗng, phần phân tích bị xóa và thanh trạng thái kết quả trở về mức trung tính. (Truy vết: docx §2.2, §2.3, §3.1)

#### Scenario: Sao chép kết quả

- **WHEN** người dùng nhấn "Sao chép" ở panel kết quả trong khi đang có kết quả
- **THEN** toàn bộ chuỗi kết quả được đưa vào bộ nhớ tạm và giao diện hiển thị thông báo thành công

#### Scenario: Các nút kết quả bị vô hiệu khi chưa có kết quả

- **WHEN** chưa có kết quả nào được hiển thị
- **THEN** nút "Sao chép" và nút "Xóa" của panel kết quả đều ở trạng thái vô hiệu

#### Scenario: Xóa kết quả

- **WHEN** người dùng đang xem tab "Phân tích" rồi nhấn "Xóa" ở panel kết quả
- **THEN** trạng thái view được đặt lại về tab "Văn bản", vùng kết quả hiển thị nội dung gợi ý ban đầu và phần phân tích bị xóa/ẩn
- **AND** tab "Văn bản" có trạng thái ARIA được chọn, tab "Phân tích" có trạng thái ARIA không được chọn
- **AND** thanh trạng thái kết quả trở về mức trung tính và các nút của panel kết quả bị vô hiệu

### Requirement: Tải kết quả xuống dưới dạng file UTF-8

Panel kết quả SHALL có nút "Tải kết quả" để tải kết quả xuống dưới dạng file văn bản mã hóa UTF-8. Nút này SHALL hiện diện với cả hai nguồn đầu vào, văn bản nhập từ bàn phím lẫn file `.txt`; điều kiện khả dụng duy nhất SHALL là đang có kết quả, và nút SHALL bị vô hiệu khi chưa có kết quả. Khi nguồn đầu vào là file, tên file tải xuống SHALL theo quy ước `<ten-goc>.encrypted.txt` ở chế độ mã hóa và `<ten-goc>.decrypted.txt` ở chế độ giải mã, trong đó `<ten-goc>` là tên file đầu vào sau khi bỏ đuôi `.txt`. Khi nguồn đầu vào là văn bản nhập từ bàn phím và do đó không có tên file gốc, tên file tải xuống SHALL là `ket-qua.encrypted.txt` ở chế độ mã hóa và `ket-qua.decrypted.txt` ở chế độ giải mã. Nếu file đầu vào có UTF-8 BOM thì file tải xuống SHALL giữ BOM. (Truy vết: docx §2.3, §2.4, §3.1, §3.2)

#### Scenario: Tên file tải xuống ở chế độ mã hóa

- **WHEN** người dùng mã hóa file `note.txt` và nhấn "Tải kết quả"
- **THEN** file được tải xuống với tên `note.encrypted.txt`

#### Scenario: Tên file tải xuống ở chế độ giải mã

- **WHEN** người dùng giải mã file `note.txt` và nhấn "Tải kết quả"
- **THEN** file được tải xuống với tên `note.decrypted.txt`

#### Scenario: Nội dung tải xuống là UTF-8

- **WHEN** kết quả chứa tiếng Việt có dấu và ký tự Unicode khác và người dùng nhấn "Tải kết quả"
- **THEN** file tải xuống được mã hóa UTF-8 và mở lại hiển thị đúng toàn bộ ký tự

#### Scenario: Giữ UTF-8 BOM

- **WHEN** file đầu vào có UTF-8 BOM và người dùng tải kết quả xuống
- **THEN** file tải xuống cũng bắt đầu bằng UTF-8 BOM

#### Scenario: Tải kết quả của luồng nhập từ bàn phím

- **WHEN** người dùng mã hóa văn bản nhập từ bàn phím, nhận được kết quả rồi nhấn "Tải kết quả"
- **THEN** file được tải xuống với nội dung đúng bằng kết quả đang hiển thị và được mã hóa UTF-8
- **AND** tên file tải xuống là `ket-qua.encrypted.txt`

#### Scenario: Tên file mặc định khi giải mã văn bản nhập từ bàn phím

- **WHEN** người dùng giải mã văn bản nhập từ bàn phím và nhấn "Tải kết quả"
- **THEN** file được tải xuống với tên `ket-qua.decrypted.txt`

#### Scenario: Nút Tải kết quả hiện diện ở cả hai nguồn đầu vào

- **WHEN** người dùng đã có kết quả với nguồn đầu vào là văn bản, rồi lặp lại với nguồn đầu vào là file
- **THEN** ở cả hai lần, nút "Tải kết quả" đều hiển thị trên panel kết quả và ở trạng thái bật

#### Scenario: Nút Tải kết quả bị vô hiệu khi chưa có kết quả

- **WHEN** chưa có kết quả nào được hiển thị, bất kể nguồn đầu vào là văn bản hay file
- **THEN** nút "Tải kết quả" hiển thị nhưng ở trạng thái vô hiệu

### Requirement: Làm mới đặt lại toàn bộ giao diện về trạng thái ban đầu

Giao diện SHALL có một nút "Làm mới" ở phạm vi toàn trang, tách biệt với các nút "Xóa" của từng panel. Khi được kích hoạt, nút "Làm mới" SHALL đưa toàn bộ giao diện về trạng thái như khi vừa mở trang: xóa văn bản đầu vào, gỡ file đang chọn cùng thông tin và bản xem trước của file, xóa ô khóa, xóa kết quả và nội dung tab phân tích, ẩn mọi thông báo đang hiển thị, đưa cả ba thanh trạng thái về mức trung tính, đưa chế độ và nguồn đầu vào về mặc định, và vô hiệu hóa nút hành động cùng các nút "Sao chép"/"Xóa"/"Tải kết quả". Nút "Làm mới" SHALL không thay thế các nút "Xóa" theo từng panel: hai loại nút này cùng tồn tại, nút "Xóa" chỉ tác động lên panel của nó còn nút "Làm mới" tác động lên toàn trang. (Truy vết: docx §2.2)

#### Scenario: Làm mới sau một lượt xử lý hoàn chỉnh

- **WHEN** người dùng đã nhập văn bản, nhập khóa, nhận kết quả và đang thấy một thông báo, rồi nhấn "Làm mới"
- **THEN** vùng nhập văn bản, ô khóa và vùng kết quả đều trở về trạng thái rỗng với nội dung gợi ý ban đầu
- **AND** thông báo đang hiển thị được ẩn đi và cả ba thanh trạng thái trở về mức trung tính
- **AND** nút hành động bị vô hiệu

#### Scenario: Làm mới khi nguồn đầu vào là file

- **WHEN** người dùng đang ở nguồn File với một file đã chọn và nhấn "Làm mới"
- **THEN** file đang chọn bị gỡ bỏ cùng tên file, kích thước và bản xem trước
- **AND** chế độ trở về mã hóa và nguồn đầu vào trở về Văn bản như khi mới mở trang

#### Scenario: Nút Xóa từng panel vẫn tồn tại song song với Làm mới

- **WHEN** người dùng nhấn nút "Xóa" của panel kết quả trong khi đang có cả đầu vào lẫn khóa
- **THEN** chỉ kết quả và phần phân tích bị xóa
- **AND** văn bản đầu vào và giá trị khóa vẫn được giữ nguyên

### Requirement: Bảng dịch chuyển bảng chữ cái theo khóa hiện tại

Giao diện SHALL hiển thị bảng dịch chuyển gồm hai hàng 26 chữ cái: hàng nguồn là bảng chữ cái gốc và hàng đích là bảng chữ cái sau khi dịch theo khóa đã chuẩn hóa hiện tại. Tiêu đề bảng SHALL có dạng "Khóa `<k>` · A → `<chữ cái đích của A>`". Nhãn hai hàng và chiều ánh xạ SHALL đổi theo chế độ: ở chế độ mã hóa ánh xạ từ bản rõ sang bản mã, ở chế độ giải mã ánh xạ từ bản mã sang bản rõ. Bảng SHALL cập nhật ngay khi khóa hoặc chế độ thay đổi; khi khóa chưa hợp lệ, bảng SHALL hiển thị theo khóa `0`. (Truy vết: docx §2.1, §2.2)

#### Scenario: Bảng dịch chuyển với khóa 3 ở chế độ mã hóa

- **WHEN** chế độ đang là mã hóa và khóa hiện tại là `3`
- **THEN** tiêu đề bảng ghi "Khóa 3 · A → D"
- **AND** hàng nguồn có nhãn bản rõ, hàng đích có nhãn bản mã và chữ `A` ánh xạ sang `D`

#### Scenario: Đổi chiều ánh xạ ở chế độ giải mã

- **WHEN** người dùng chuyển sang chế độ giải mã với khóa `3`
- **THEN** hàng nguồn có nhãn bản mã, hàng đích có nhãn bản rõ
- **AND** chữ `A` ánh xạ sang `X`

#### Scenario: Bảng dùng khóa đã chuẩn hóa

- **WHEN** người dùng nhập khóa `29` ở chế độ mã hóa
- **THEN** bảng dịch chuyển hiển thị theo khóa chuẩn hóa `3` và tiêu đề ghi "Khóa 3 · A → D"

#### Scenario: Khóa chưa hợp lệ

- **WHEN** ô khóa đang rỗng hoặc chứa giá trị không phải số nguyên
- **THEN** bảng dịch chuyển hiển thị theo khóa `0`, tức mỗi chữ cái ánh xạ sang chính nó

### Requirement: Tô nổi bật các chữ cái xuất hiện trong đầu vào

Bảng dịch chuyển SHALL tô nổi bật những chữ cái thực sự xuất hiện trong đầu vào hiện tại, không phân biệt hoa thường, ở cả hàng nguồn lẫn hàng đích tương ứng. Phần tô nổi bật SHALL cập nhật ngay khi đầu vào thay đổi và SHALL có chú thích giải thích ý nghĩa. (Truy vết: docx §2.1, §2.2)

#### Scenario: Tô nổi bật theo văn bản đang nhập

- **WHEN** người dùng nhập "Hello World"
- **THEN** các chữ cái `H`, `E`, `L`, `O`, `W`, `R`, `D` được tô nổi bật ở hàng nguồn và ô đích tương ứng

#### Scenario: Cập nhật khi đầu vào thay đổi

- **WHEN** người dùng xóa bớt ký tự khiến một chữ cái không còn xuất hiện trong đầu vào
- **THEN** chữ cái đó không còn được tô nổi bật

#### Scenario: Tô nổi bật theo nội dung file

- **WHEN** nguồn đầu vào là file và file đã được chọn hợp lệ
- **THEN** các chữ cái xuất hiện trong nội dung file được tô nổi bật trên bảng dịch chuyển

### Requirement: Giao diện responsive trên màn hình hẹp

Giao diện SHALL sử dụng được trên màn hình hẹp: bố cục hai cột SHALL xếp chồng thành một cột, mọi nút và ô nhập vẫn thao tác được, không có nội dung bị cắt mất và không xuất hiện cuộn ngang toàn trang. Riêng bảng dịch chuyển được phép cuộn ngang trong phạm vi khối của nó. (Truy vết: docx §2.2)

#### Scenario: Bố cục trên màn hình hẹp

- **WHEN** giao diện được xem trên màn hình hẹp cỡ điện thoại
- **THEN** panel đầu vào, panel kết quả và khu vực khóa xếp chồng theo chiều dọc thành một cột
- **AND** không có cuộn ngang ở cấp toàn trang

#### Scenario: Bảng dịch chuyển trên màn hình hẹp

- **WHEN** bảng dịch chuyển rộng hơn màn hình
- **THEN** bảng cuộn ngang trong phạm vi khối của nó mà không làm cả trang cuộn ngang

### Requirement: Sử dụng được hoàn toàn bằng bàn phím

Toàn bộ chức năng SHALL thao tác được bằng bàn phím: chọn chế độ, chọn nguồn đầu vào, nhập văn bản, chọn file, nhập khóa, kích hoạt các nút "Sao chép", "Xóa", "Tải kết quả", "Tạo ví dụ" và "Làm mới", chuyển tab kết quả, kích hoạt nút hành động và đóng thông báo. Mọi phần tử tương tác SHALL có chỉ báo tiêu điểm nhìn thấy rõ. Thứ tự tiêu điểm SHALL theo trình tự đọc hợp lý của trang. (Truy vết: docx §2.2)

#### Scenario: Duyệt toàn bộ giao diện bằng bàn phím

- **WHEN** người dùng chỉ dùng phím Tab và Shift+Tab để di chuyển
- **THEN** mọi phần tử tương tác đều nhận được tiêu điểm theo thứ tự đọc hợp lý
- **AND** phần tử đang có tiêu điểm hiển thị chỉ báo tiêu điểm rõ ràng

#### Scenario: Hoàn tất một luồng mã hóa chỉ bằng bàn phím

- **WHEN** người dùng dùng bàn phím để chọn chế độ, nhập văn bản, nhập khóa và kích hoạt nút hành động
- **THEN** kết quả được hiển thị đúng như khi thao tác bằng chuột

#### Scenario: Không có bẫy tiêu điểm

- **WHEN** tiêu điểm đang ở trong vùng nhập văn bản hoặc vùng thả file
- **THEN** người dùng vẫn rời khỏi vùng đó được bằng bàn phím

### Requirement: Kết quả và trạng thái thông báo được cho trình đọc màn hình

Vùng kết quả SHALL được công bố cho trình đọc màn hình khi nội dung thay đổi, để người dùng biết đã có kết quả mới mà không cần tự dò tìm. Các thông báo thành công, lỗi và cảnh báo SHALL được công bố tương tự. Các nhóm điều khiển như bộ chọn chế độ, bộ chọn nguồn đầu vào và tab kết quả SHALL có nhãn mô tả và thể hiện được trạng thái đang chọn cho công nghệ trợ giúp. (Truy vết: docx §2.2)

#### Scenario: Công bố kết quả mới

- **WHEN** vùng kết quả được cập nhật bằng kết quả mới
- **THEN** trình đọc màn hình công bố nội dung kết quả mà không cần người dùng chuyển tiêu điểm

#### Scenario: Công bố thông báo lỗi

- **WHEN** một thông báo lỗi xuất hiện
- **THEN** trình đọc màn hình công bố nội dung thông báo đó

#### Scenario: Trạng thái đang chọn của các nhóm điều khiển

- **WHEN** người dùng dùng trình đọc màn hình duyệt bộ chọn chế độ, bộ chọn nguồn đầu vào và tab kết quả
- **THEN** mỗi nhóm có nhãn mô tả và lựa chọn đang hoạt động được công bố là đang được chọn

### Requirement: Toàn bộ văn bản giao diện bằng tiếng Việt

Mọi văn bản hướng tới người dùng cuối trên giao diện SHALL bằng tiếng Việt: tiêu đề, nhãn panel, nhãn nút, câu hướng dẫn, nội dung thanh trạng thái, nội dung thông báo và nội dung gợi ý khi rỗng. Giao diện MUST NOT hiển thị thông báo kỹ thuật bằng tiếng Anh cho người dùng cuối. Ngôn ngữ của trang SHALL được khai báo là tiếng Việt. (Truy vết: docx §1, §2.2, §5)

#### Scenario: Nhãn và hướng dẫn bằng tiếng Việt

- **WHEN** người dùng mở giao diện
- **THEN** tiêu đề, nhãn panel, câu hướng dẫn, nhãn nút hành động và nội dung các thanh trạng thái đều bằng tiếng Việt

#### Scenario: Thông báo lỗi bằng tiếng Việt

- **WHEN** xảy ra lỗi kết nối hoặc lỗi do máy chủ trả về
- **THEN** thông báo hiển thị cho người dùng bằng tiếng Việt, không dùng chuỗi kỹ thuật tiếng Anh

#### Scenario: Bộ nhãn nút bằng tiếng Việt

- **WHEN** người dùng xem các nút điều khiển trên giao diện
- **THEN** nút hành động mang nhãn "Mã hóa" hoặc "Giải mã" theo chế độ đang chọn
- **AND** các nút còn lại mang nhãn "Sao chép", "Xóa", "Đổi file", "Gỡ file", "Tải kết quả", "Tạo ví dụ" và "Làm mới"
- **AND** không có nhãn nút nào hiển thị bằng tiếng Anh như "Copy", "Clear", "Change", "Remove", "Download" hay "Generate example"

#### Scenario: Tiêu đề thông báo bằng tiếng Việt

- **WHEN** giao diện hiển thị một thông báo thành công, lỗi hoặc cảnh báo
- **THEN** cả tiêu đề lẫn nội dung thông báo đều bằng tiếng Việt
- **AND** không có tiêu đề nào hiển thị bằng tiếng Anh như "Network error" hay "Server error"

#### Scenario: Giá trị hiển thị trong tab Phân tích bằng tiếng Việt

- **WHEN** người dùng mở tab "Phân tích" sau một lượt xử lý
- **THEN** giá trị chế độ hiển thị là "Mã hóa" hoặc "Giải mã"
- **AND** giá trị nguồn đầu vào hiển thị là "Văn bản" hoặc "File · <tên file>"
- **AND** không có giá trị nào hiển thị bằng chuỗi kỹ thuật tiếng Anh như `encrypt`, `decrypt`, `text` hay `file`

#### Scenario: Khai báo ngôn ngữ trang

- **WHEN** công nghệ trợ giúp đọc trang
- **THEN** ngôn ngữ của trang được khai báo là tiếng Việt

### Requirement: Giao diện chỉ gồm thành phần thuộc phạm vi mã hóa/giải mã

Trang SHALL chỉ chứa những thành phần phục vụ trực tiếp luồng mã hóa/giải mã Caesar. Giao diện MUST NOT có thanh điều hướng hay liên kết dẫn tới trang chưa tồn tại, MUST NOT chứa liên kết chết hoặc liên kết không dẫn tới đâu, và MUST NOT hiển thị chú thích về backend giả lập, về chế độ dữ liệu giả hay về tham số cấu hình nội bộ của lời gọi API. (Truy vết: docx §8)

#### Scenario: Không có điều hướng ngoài phạm vi

- **WHEN** người dùng xem toàn bộ trang
- **THEN** trang không có mục điều hướng nào dẫn tới trang khác chưa tồn tại trong phạm vi Tuần 1
- **AND** mọi liên kết hiển thị trên trang đều dẫn tới một đích dùng được

#### Scenario: Không có chú thích về backend giả lập

- **WHEN** người dùng xem toàn bộ trang
- **THEN** không có biểu ngữ, chú thích hay ghi chú nào nói rằng backend đang được giả lập
- **AND** không có tên tham số cấu hình nội bộ nào của lời gọi API được hiển thị cho người dùng
