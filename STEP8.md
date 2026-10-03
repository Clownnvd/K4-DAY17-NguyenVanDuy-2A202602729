# Bước 8 - Phân tích kết quả Lab 17

Nguyễn Văn Duy - MSSV 2A202602729.

Các số liệu dưới đây được đo bằng mô phỏng offline trên hai file dữ liệu gốc. Agent không được đọc đáp án chuẩn. Ngưỡng nén là 1.200 token ước lượng; sau nén giữ bốn tin nhắn gần nhất.

## Số liệu

| Bộ dữ liệu | Agent | Token trả lời | Token ngữ cảnh xử lý | Recall xuyên phiên | Quality proxy | File memory tăng | Lần nén |
|---|---|---:|---:|---:|---:|---:|---:|
| Standard | Baseline | 2.049 | 18.808 | 0% | 0% | 0 byte | 0 |
| Standard | Advanced | 1.962 | 26.277 | 100% | 100% | 366 byte | 0 |
| Long-Context Stress | Baseline | 386 | 23.300 | 0% | 0% | 0 byte | 0 |
| Long-Context Stress | Advanced | 381 | 14.543 | 100% | 100% | 507 byte | 3 |

`Recall (độ nhớ fact qua phiên mới)`: phép chấm trả 1 khi có đủ chuỗi đáp án, 0,5 khi có một phần và 0 khi không có. Ví dụ câu cần tên và nghề, trả đúng tên nhưng chưa biết nghề được 0,5. Điểm chung là trung bình các câu, không phải tỷ lệ fact riêng lẻ.

`Quality proxy (chỉ số thay thế cho chất lượng)`: độ bao phủ các chuỗi fact, nhân hệ số phạt nếu câu dài hơn 600 ký tự. Ví dụ đúng 3/4 fact trong câu 300 ký tự thì điểm là 0,75. Chỉ số này không đo văn phong, độ đúng của tin tức hoặc chất lượng suy luận.

`Token (đơn vị độ dài văn bản ước lượng)`: bài dùng ceil(len(text.strip())/4). Ví dụ 40 ký tự là 10 token ước lượng. Bộ đếm ngữ cảnh cộng ở từng lượt, gồm system prompt, profile, summary và tin nhắn gần nhất. Token trả lời chỉ tính phần agent sinh ra. Hai cột đều bao gồm lượt hỏi recall.

## 1. Vì sao Advanced nhớ tốt hơn Baseline?

Advanced đạt 100% ở cả hai bộ; Baseline đạt 0%. Thông tin tên, nơi ở, nghề và sở thích được trích từ lời người dùng và ghi vào User.md theo khóa. Thread mới đọc lại file đó, kể cả khi tạo đối tượng Advanced mới. Baseline chỉ có danh sách tin nhắn của thread hiện tại nên không biết fact đã nói trong thread cũ.

Baseline trả lời chưa có thông tin trong trường hợp này là đúng thiết kế. Điểm 0% không có nghĩa model kém; đó là phép đo khả năng nhớ xuyên phiên. Các câu hỏi recall của bộ gốc chủ yếu hỏi profile, nên 100% không chứng minh agent nhớ được toàn bộ chi tiết hội thoại hoặc suy luận tốt trên câu hỏi khác.

## 2. Vì sao Advanced có thể tốn hơn ở hội thoại ngắn?

Trong Standard, Advanced xử lý 26.277 token ngữ cảnh, cao hơn Baseline 18.808 khoảng 39,7%. Không có lần nén nào; chi phí thêm đến từ việc đưa User.md vào mỗi lượt và khả năng trả lời các câu recall.

Token trả lời của Advanced là 1.962, thấp hơn 2.049 của Baseline. Hai cột đo hai thứ khác nhau, nên không cần ép Advanced phải cao hơn ở mọi cột để bảng trông đúng lý thuyết. Ghi file bằng code không sinh token model; chỉ khi dùng một model để trích fact hoặc tóm tắt thì mới có thêm token từ các lời gọi đó.

## 3. Vì sao nén có lợi ở hội thoại dài?

Trong stress, Advanced xử lý 14.543 token ngữ cảnh, giảm 8.757 token, tương đương 37,6% so với 23.300 của Baseline. Ba lần nén chuyển lịch sử cũ thành summary giới hạn và giữ lại bốn tin nhắn gần nhất.

Phép đo tắt nén giữ nguyên Advanced và profile nhưng đặt ngưỡng rất cao. Prompt load tăng từ 14.543 lên 25.030 token ước lượng, trong khi recall vẫn là 100%. Đây là bằng chứng tách tác dụng của nén khỏi tác dụng của User.md: nén giảm khoảng 41,9% so với cùng Advanced không nén.

Nén chủ yếu giảm ngữ cảnh đưa vào mỗi lượt. Token trả lời 381 và 386 gần nhau, nên kết luận hợp lý là tiết kiệm ngữ cảnh, không phải mọi loại token đều giảm. Summary dùng heuristic, không có chi phí gọi LLM. Trong hệ thống live dùng model tóm tắt, phải tính thêm chi phí tóm tắt và đo điểm hòa vốn.

## 4. File memory tăng trưởng thế nào và có rủi ro gì?

Standard tăng 366 byte; stress tăng 507 byte. Agent ghi các field ổn định, không nối toàn bộ hội thoại vào User.md. Correction thay giá trị nơi ở/nghề cũ, sở thích được giữ thành danh sách có giới hạn. Phần tin tức dài thuộc summary trong thread, không được biến thành fact profile chỉ vì có từ khóa.

Rủi ro vẫn còn: regex có thể bỏ sót cách diễn đạt mới, hiểu sai phạm vi lời nói hoặc không xử lý được phủ định sở thích phức tạp. Summary chỉ giữ đoạn rút gọn nên có thể mất chi tiết news hoặc quan hệ giữa các sự kiện. Một tin nhắn riêng dài hơn ngưỡng vẫn có thể khiến ngữ cảnh sau nén vượt ngưỡng; bài giữ nguyên tin nhắn gần nhất thay vì cắt mất lời người dùng.

## Bonus và đánh đổi

Bài có structured extraction (trích fact theo field), conflict handling (thay fact cũ khi có đính chính) và chặn ghi profile từ câu hỏi/quote/giả định. Test bổ sung tái hiện lỗi câu hỏi “Mình ở Huế?” bị ghi như fact, lỗi 3 bullet và 4 bullet cùng tồn tại, và lỗi sở thích mới làm mất Python/AI đã ghi. Sau sửa, các hành vi đó được kiểm tra hồi quy.

Đây là guardrail tất định, không phải confidence threshold bằng model. Cách làm có chi phí thấp và chạy lặp lại được nhưng độ bao phủ ngôn ngữ hạn chế. Sản phẩm thực tế cần cơ chế người dùng xác nhận fact, quyền xóa profile, quản lý thời hạn dữ liệu và đo recall trên câu hỏi chưa thấy.

## Tái lập

Chạy từ thư mục gốc:

```text
python src/benchmark.py
pytest src/test_agents.py -v
pytest src -v
```

Benchmark tự dùng thư mục tạm sạch, không tái sử dụng User.md có sẵn. Số liệu chi tiết và câu trả lời thật nằm ở artifacts/benchmark_results.json. Kết quả hai lần chạy và mã băm data được ghi trong artifacts/verification.json.
