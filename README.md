# K4-DAY17-NguyenVanDuy-2A202602729

Bài làm cá nhân Lab 17: so sánh bộ nhớ của hai AI agent trên cùng dữ liệu tiếng Việt.

- **Người thực hiện:** Nguyễn Văn Duy.
- **MSSV:** 2A202602729.
- **Nguồn scaffold:** https://github.com/VinUni-AI20k/day17-cohort4-MemorySystems4Agent
- **Commit nguồn:** dc0e2dab1c9d2043472bf4e17cf0dcc8c7c76c6d.
- **Dữ liệu:** giữ nguyên hai file do lớp cung cấp.
- **Chế độ mặc định:** offline, chạy mô phỏng tất định, không cần khóa API.

## Chạy bài

Python 3.11 trở lên. Mở terminal tại thư mục này:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/benchmark.py
.\.venv\Scripts\python.exe -m pytest src/test_agents.py -v
.\.venv\Scripts\python.exe -m pytest src -v
```

Khi đã kích hoạt môi trường, hai lệnh theo đề là:

```text
python src/benchmark.py
pytest src/test_agents.py -v
```

Hai bảng có sáu chỉ số, cùng câu hỏi được hỏi ở thread mới. Benchmark tạo thư mục tạm sạch cho từng bộ dữ liệu và tự giải phóng sau khi chạy, nên không phụ thuộc hồ sơ còn sót trong `state/`.

## Phân biệt bộ nhớ

| Lớp | Baseline | Advanced |
|---|---|---|
| Bộ nhớ trong phiên | Toàn bộ tin nhắn theo thread | Tin nhắn gần nhất theo thread |
| Bộ nhớ bền vững | Không có | Fact theo khóa trong User.md |
| Nén hội thoại | Không có | Tóm tắt tích lũy và giữ 4 tin nhắn gần nhất |

Baseline và Advanced dùng cùng bộ trích fact, cùng hàm trả lời mô phỏng và cùng cách ước lượng token. Chỉ bộ nhớ được cung cấp khác nhau. Hai agent không nhận `expected_contains` hoặc đáp án chuẩn; các chuỗi này chỉ xuất hiện ở bước chấm điểm.

## File cần xem

| File | Nội dung |
|---|---|
| src/config.py | Đường dẫn, cấu hình model chính/model judge, ngưỡng nén |
| src/model_provider.py | Sáu provider; đồ thị LangGraph có checkpoint trong RAM |
| src/memory_store.py | User.md, trích fact, sửa mâu thuẫn, tóm tắt |
| src/agent_baseline.py | Nhớ trong thread; không đọc hồ sơ trên đĩa |
| src/agent_advanced.py | Đọc/ghi hồ sơ và dùng ngữ cảnh nén |
| src/benchmark.py | Hai benchmark và phép đo Advanced khi tắt nén |
| src/test_agents.py | Bốn test bắt buộc |
| src/test_edge_cases.py | Câu hỏi, correction, nhiễu, cách ly người dùng và checkpoint |
| STEP8.md | Trả lời bốn câu hỏi phân tích của Guide |
| artifacts/benchmark_results.json | Số liệu, câu trả lời thật, điểm và mã băm dữ liệu |
| artifacts/benchmark_output.txt | Hai bảng in ra từ lệnh chạy |
| artifacts/verification.json | Biên nhận kiểm thử và kiểm tra tái lập |

## Kết quả và giới hạn

Kết quả mới nhất được lưu trong `artifacts/` và phân tích ở `STEP8.md`.

Điểm recall đo số fact tìm được qua phiên mới. Response quality trong bài là **chỉ số thay thế dựa trên độ bao phủ fact**, không phải đánh giá độc lập bằng một model judge. Token là ước lượng ký tự, không phải token tính tiền của nhà cung cấp. Không diễn giải điểm 100% của mô phỏng thành chất lượng LLM ngoài thực tế.

## Cấu hình

`.env.example` liệt kê tên biến được dùng. Mặc định:

```dotenv
LLM_MODE=offline
COMPACT_THRESHOLD_TOKENS=1200
COMPACT_KEEP_MESSAGES=4
```

`LLM_MODE=live` bật model thật. Provider hỗ trợ: openai, custom, gemini, anthropic, ollama, openrouter. Khóa chỉ đặt ở biến môi trường hoặc `.env`; không đưa vào repo.

Model judge có cấu hình riêng `JUDGE_PROVIDER` và `JUDGE_MODEL`, nhưng benchmark bắt buộc hiện dùng phép chấm tất định. Đường live có đồ thị gọi model và checkpoint theo thread; test bằng model giả xác nhận lịch sử đã nén không bị checkpoint nối lại. Bài chưa có phép đo trên API thật, chưa có tool quản lý memory cho model tự gọi, và không tuyên bố đây là dịch vụ production.

## Bonus đã triển khai

- Trích xuất fact theo trường, từ phát biểu ngôi thứ nhất.
- Fact đơn trị như nơi ở và nghề được thay bằng giá trị mới.
- Bỏ qua câu hỏi, nội dung trong dấu ngoặc kép, tình huống giả định và câu đùa.
- Giữ nhiều sở thích khác nhau trong danh sách giới hạn sáu mục.
- Số bullet mới thay số cũ.
- Đường dẫn hồ sơ có mã băm để tránh va chạm ID và thoát thư mục.
- Người dùng khác không được dùng lại thread đã có chủ sở hữu.

Không có confidence model hoặc memory decay tự động; hai phần này là hướng mở rộng, chưa được ghi là tính năng hoàn thành.

## Bảo vệ dữ liệu bài làm

`.env`, `state/`, `.venv/`, cache và log được bỏ qua trong Git. `data/` được giữ nguyên và kiểm tra với commit nguồn. Nội dung đầy đủ của khóa học chỉ lưu local; repo nộp chứa code, dữ liệu benchmark gốc và phần phân tích bài làm.
