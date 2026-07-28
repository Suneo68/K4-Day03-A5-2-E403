# 📊 BÁO CÁO GIÁM SÁT & ĐÁNH GIÁ (OBSERVABILITY TRACE LOGS)



## Role 2 - Proposed Tools

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