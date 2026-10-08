# Diffie–Hellman engineering evidence

Ngày đo: 2026-10-08. Runtime: Python 3.12 trong môi trường khóa của repository.
Đây là số đo kỹ thuật cục bộ, không phải cam kết latency hay worst-case guarantee.

## Primality và factorization

- `q ≤ 10^12` ở `/params` dùng trial division.
- Giá trị downstream đến 128 bit dùng small-prime screening và 32 vòng
  Miller–Rabin với witness lấy từ CSPRNG. Kết quả là **probable prime**, không phải
  chứng minh nguyên tố xác định. Core RSA deterministic dưới 64 bit không được tái
  sử dụng để tuyên bố deterministic ở miền DH 128 bit.
- Factorization `q-1` dùng small-prime division rồi Pollard–Brent/Rho có giới hạn
  retry/iteration. Công việc CPU chạy ngoài event loop qua threadpool ở HTTP adapter.

Lệnh benchmark dùng `time.perf_counter()` và kiểm tra tích các factor bằng đúng input.
Một lượt sinh safe prime và factor `q-1`:

| Bits | Sinh group | Factor `q-1` |
|---:|---:|---:|
| 16 | 0.000177 s | 0.000014 s |
| 32 | 0.017631 s | 0.000829 s |
| 64 | 0.042832 s | 0.000377 s |
| 128 | 0.117161 s | 0.000970 s |

Counterexample tài nguyên: semiprime cân bằng 96 bit
`281474976710597 × 281474976710591` chạm giới hạn factorization sau 4.084130 s và
trả domain failure. Điều này xác nhận không thể hứa latency worst-case cho tham số
tùy ý. Safe-prime do endpoint sinh có cấu trúc `q-1 = 2p`, nên đường downstream
thông thường nhanh hơn đáng kể. Resource policy hiện tại giới hạn bốn DH jobs đồng
thời, tối đa 100.000 lần đánh giá đa thức mỗi Pollard attempt và tối đa 10.000 candidate khi tìm
primitive root. CPU work chạy trong threadpool nên không thực thi trực tiếp trên event
loop. Các bound có thể trả domain failure cho tham số tùy ý khó phân tích; đây là giới
hạn tài nguyên có chủ đích trong phạm vi giáo dục, không phải bảo đảm worst-case latency.

## Migration SQLite

Targeted migration/continuity suite kiểm tra tuyến tính `sqlite_0001 → sqlite_0002`,
giữ 11 cột, hai index, row, `sqlite_sequence`, cho phép `rsa` và `dh`, và downgrade
fail trước mutation khi còn row `cipher='dh'`. PostgreSQL revision không được chạy
trên SQLite.

## Ma trận test nguồn TC-01–TC-13

| TC | Requirement/scenario | Automated evidence |
|---|---|---|
| TC-01 | params q/alpha hợp lệ | `test_params_missing_alpha_is_suggestion_only`, `test_parameter_validation_checks_all_distinct_factors_and_suggests_alpha` |
| TC-02 | keypair/exchange q=23 | `test_keypair_resamples_weak_random_private_key_and_rejects_manual_weak_key`, `test_exchange_returns_grouped_traces_and_educational_warning` |
| TC-03 | hai phía cùng K | `test_keypair_and_shared_secret_vectors`, `test_exchange_exposes_educational_private_keys` |
| TC-04 | trace trái sang phải | `test_left_to_right_mod_pow_has_the_exact_dh_trace`, `test_keypair_and_left_to_right_trace` |
| TC-05 | q composite | `test_exact_domain_errors` (`q=21`) |
| TC-06 | alpha không nguyên căn | `test_parameter_validation_checks_all_distinct_factors_and_suggests_alpha`, `test_exact_domain_errors` |
| TC-07 | alpha ngoài miền | `test_exact_domain_errors` (`alpha=25`) |
| TC-08 | random bit sizes | `test_safe_prime_generation_all_supported_sizes`, `test_random_params_all_bit_sizes_are_composable` |
| TC-09 | private-key boundary | `test_keypair_resamples_weak_random_private_key_and_rejects_manual_weak_key`, `test_exact_domain_errors` |
| TC-10 | peer public boundary | `test_keypair_and_shared_secret_vectors`, `test_exact_domain_errors` |
| TC-11 | DH Caesar encrypt/decrypt và Unicode | `test_caesar_json_tc11_and_shift_zero`, `test_caesar_json_decrypt_round_trip_preserves_non_ascii` |
| TC-12 | shift zero warning | `test_caesar_json_tc11_and_shift_zero` |
| TC-13 | cap q manual | `test_parameter_validation_distinguishes_manual_cap_and_composite_q`, `test_exact_domain_errors` |

Các deviation D1–D8 được khóa trong `openspec/changes/add-diffie-hellman/design.md`
và được phủ chéo bởi `test_dh_endpoints.py`, `test_dh_resources.py`,
`test_history_recording.py`, `test_sqlite_history.py` và `test_sqlite_continuity.py`.
