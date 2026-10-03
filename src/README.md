# Mã bài làm Lab 17

Các file Python đã hoàn thiện từ scaffold nguồn. Chạy benchmark từ thư mục gốc bằng `python src/benchmark.py`; chạy bốn test bắt buộc bằng `pytest src/test_agents.py -v`.

Baseline giữ hội thoại theo thread. Advanced thêm User.md bền vững và nén lịch sử. Cả hai dùng cùng hàm trả lời offline để phép so sánh chỉ thay đổi bộ nhớ được cung cấp.

`test_edge_cases.py` bổ sung kiểm thử về sửa fact, câu hỏi, nội dung trích dẫn, cách ly người dùng và checkpoint LangGraph. Kết quả và phân tích nằm ở `artifacts/` và `STEP8.md`.
