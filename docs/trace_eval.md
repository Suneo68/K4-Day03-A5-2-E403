# 📊 BÁO CÁO GIÁM SÁT & ĐÁNH GIÁ (OBSERVABILITY TRACE LOGS)



<<<<<<< HEAD
## Role 2 - Proposed Tools
=======
| Tiêu chí | Điểm (1-5) | Lý do đánh giá |
| :--- | :---: | :--- |
| 🧠 **Multi-step Reasoning** | `4/5` | Cần suy luận phân tích từ nhu cầu mua nhà đến việc chọn vị trí, lên lịch hẹn xem nhà |
| 🛠️ **Tool Interaction** | `5/5` | Cần tra cứu dữ liệu nhà trọ, kiểm tra lịch và có thể gửi email xác nhận |
| 🔀 **Dynamic Decision** | `4/5` | Kết quả bước trước quyết định hành động bước sau. |
| ⏳ **Long Horizon** | `3/5` | Quy trình gồm 3-4 bước xử lý. |
| **TỔNG ĐIỂM FIT** | **17/20** | **KẾT LUẬN: BÀI TOÁN RẤT NÊN DÙNG REACT AGENT!** |
>>>>>>> afea6b4ab6a6704cbabffb8e6e1b042201553de8

- `search_properties(location, max_price, room_type)`
- `get_property_details(property_id)`
- `check_viewing_slots(property_id, viewing_date)`
- `book_viewing(property_id, viewing_date, viewing_time, customer_name, confirmed)`

## Role 3 - Tool Failure Modes

| Tool | Failure Modes | Safe behavior |
|---|---|---|
| search_properties | Thiếu điều kiện, giá không hợp lệ, không có kết quả | Trả thông báo lỗi hoặc không tìm thấy, không bịa phòng |
| get_property_details | Mã phòng trống hoặc không tồn tại | Trả chuỗi lỗi, không crash |
| check_viewing_slots | Sai mã phòng, sai ngày, hết lịch | Trả lỗi rõ ràng, không tự tạo lịch trống |
| book_viewing | Thiếu thông tin, chưa xác nhận, lịch đã được đặt | Chặn thao tác và yêu cầu xác nhận lại |