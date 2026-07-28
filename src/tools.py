"""
TOOL REGISTRY & SCHEMAS
Dành cho Role 2: Tool & Spec Engineer.

Đề tài: Trợ lý tìm và đặt lịch xem nhà.
"""

import re
import unicodedata
from datetime import date, datetime
from typing import Any, Callable


# =====================================================================
# 1. DỮ LIỆU NHÀ TRỌ/CĂN HỘ MÔ PHỎNG
# =====================================================================

RENTAL_PROPERTIES = [
    {
        "property_id": "P001",
        "title": "Phòng trọ Dịch Vọng",
        "location": "Cầu Giấy",
        "address": "Dịch Vọng, Cầu Giấy, Hà Nội",
        "price": 3500000,
        "room_type": "phòng trọ",
        "area_m2": 25,
    },
    {
        "property_id": "P002",
        "title": "Căn hộ mini Mỹ Đình",
        "location": "Mỹ Đình",
        "address": "Mỹ Đình 2, Nam Từ Liêm, Hà Nội",
        "price": 5200000,
        "room_type": "căn hộ mini",
        "area_m2": 32,
    },
    {
        "property_id": "P003",
        "title": "Phòng trọ Mai Dịch",
        "location": "Cầu Giấy",
        "address": "Mai Dịch, Cầu Giấy, Hà Nội",
        "price": 4200000,
        "room_type": "phòng trọ",
        "area_m2": 28,
    },
    {
        "property_id": "P004",
        "title": "Chung cư mini Hoàng Mai",
        "location": "Hoàng Mai",
        "address": "Định Công, Hoàng Mai, Hà Nội",
        "price": 5800000,
        "room_type": "chung cư mini",
        "area_m2": 35,
    },
]


# Khung giờ xem nhà mô phỏng của từng phòng
PROPERTY_VIEWING_TIMES = {
    "P001": ["09:00", "10:30", "14:00", "16:00"],
    "P002": ["09:30", "11:00", "14:30", "16:30"],
    "P003": ["08:30", "10:00", "15:00", "17:00"],
    "P004": ["09:00", "11:30", "14:00", "17:30"],
}


# Lưu dữ liệu đặt lịch trong thời gian chương trình đang chạy
BOOKED_VIEWING_SLOTS = set()
BOOKING_RECORDS = []


# =====================================================================
# 2. CÁC HÀM HỖ TRỢ
# =====================================================================

def _normalize_text(value: Any) -> str:
    """Chuẩn hóa chữ thường và loại bỏ dấu tiếng Việt."""
    text = str(value).strip().casefold().replace("đ", "d")

    return "".join(
        character
        for character in unicodedata.normalize("NFD", text)
        if unicodedata.category(character) != "Mn"
    )


def _format_price(price: int) -> str:
    """Định dạng giá tiền theo kiểu Việt Nam."""
    return f"{price:,}".replace(",", ".")


def _find_property(property_id: str):
    """Tìm phòng theo mã phòng."""
    normalized_id = str(property_id).strip().upper()

    for property_item in RENTAL_PROPERTIES:
        if property_item["property_id"] == normalized_id:
            return property_item

    return None


def _parse_viewing_date(viewing_date: str):
    """Kiểm tra và chuyển ngày từ chuỗi YYYY-MM-DD."""
    try:
        parsed_date = datetime.strptime(
            str(viewing_date).strip(),
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        return None, "LỖI: Ngày xem phải có định dạng YYYY-MM-DD."

    if parsed_date < date.today():
        return None, "LỖI: Ngày xem nhà không được là ngày trong quá khứ."

    return parsed_date, None


def _is_confirmed(value: Any) -> bool:
    """Kiểm tra giá trị xác nhận từ người dùng."""
    if value is True:
        return True

    return str(value).strip().casefold() == "true"


# =====================================================================
# 3. TOOL 1: TÌM PHÒNG
# =====================================================================

def search_properties(
    location: str,
    max_price: int,
    room_type: str,
) -> str:
    """
    Tìm phòng theo khu vực, ngân sách và loại phòng.

    Failure modes:
    - Thiếu khu vực hoặc loại phòng.
    - Ngân sách không phải số nguyên dương.
    - Không tìm thấy phòng phù hợp.
    """
    if not str(location).strip():
        return "LỖI: Khu vực tìm kiếm không được để trống."

    if not str(room_type).strip():
        return "LỖI: Loại phòng không được để trống."

    if isinstance(max_price, bool):
        return "LỖI: Giá thuê tối đa phải là một số nguyên."

    try:
        parsed_max_price = int(
            str(max_price)
            .replace(".", "")
            .replace(",", "")
            .strip()
        )
    except (TypeError, ValueError):
        return "LỖI: Giá thuê tối đa phải là một số nguyên."

    if parsed_max_price <= 0:
        return "LỖI: Giá thuê tối đa phải lớn hơn 0."

    normalized_location = _normalize_text(location)
    normalized_room_type = _normalize_text(room_type)

    matched_properties = []

    for property_item in RENTAL_PROPERTIES:
        searchable_location = _normalize_text(
            f"{property_item['location']} {property_item['address']}"
        )
        searchable_room_type = _normalize_text(
            property_item["room_type"]
        )

        location_matches = normalized_location in searchable_location
        room_type_matches = normalized_room_type in searchable_room_type
        price_matches = property_item["price"] <= parsed_max_price

        if location_matches and room_type_matches and price_matches:
            matched_properties.append(property_item)

    if not matched_properties:
        return (
            "KẾT QUẢ: Không tìm thấy phòng phù hợp với khu vực, "
            "ngân sách và loại phòng đã cung cấp."
        )

    result_lines = [
        f"Tìm thấy {len(matched_properties)} phòng phù hợp:"
    ]

    for property_item in matched_properties:
        result_lines.append(
            f"- {property_item['property_id']}: "
            f"{property_item['title']} | "
            f"{_format_price(property_item['price'])} VNĐ/tháng | "
            f"{property_item['area_m2']} m² | "
            f"{property_item['address']}"
        )

    return "\n".join(result_lines)


# =====================================================================
# 4. TOOL 2: XEM CHI TIẾT PHÒNG
# =====================================================================

def get_property_details(property_id: str) -> str:
    """
    Tra cứu thông tin chi tiết một phòng theo mã.

    Failure modes:
    - Thiếu mã phòng.
    - Mã phòng không tồn tại.
    """
    if not str(property_id).strip():
        return "LỖI: Mã phòng không được để trống."

    property_item = _find_property(property_id)

    if property_item is None:
        return f"LỖI: Không tìm thấy phòng có mã '{property_id}'."

    return (
        "CHI TIẾT PHÒNG:\n"
        f"- Mã phòng: {property_item['property_id']}\n"
        f"- Tên phòng: {property_item['title']}\n"
        f"- Loại phòng: {property_item['room_type']}\n"
        f"- Khu vực: {property_item['location']}\n"
        f"- Địa chỉ: {property_item['address']}\n"
        f"- Diện tích: {property_item['area_m2']} m²\n"
        f"- Giá thuê: {_format_price(property_item['price'])} VNĐ/tháng"
    )


# =====================================================================
# 5. TOOL 3: KIỂM TRA LỊCH XEM NHÀ
# =====================================================================

def check_viewing_slots(
    property_id: str,
    viewing_date: str,
) -> str:
    """
    Kiểm tra các khung giờ xem nhà còn trống.

    Failure modes:
    - Mã phòng không tồn tại.
    - Ngày không đúng định dạng YYYY-MM-DD.
    - Ngày đã qua hoặc không còn khung giờ trống.
    """
    property_item = _find_property(property_id)

    if property_item is None:
        return f"LỖI: Không tìm thấy phòng có mã '{property_id}'."

    _, date_error = _parse_viewing_date(viewing_date)

    if date_error:
        return date_error

    normalized_id = property_item["property_id"]
    normalized_date = str(viewing_date).strip()

    available_slots = [
        viewing_time
        for viewing_time in PROPERTY_VIEWING_TIMES[normalized_id]
        if (
            normalized_id,
            normalized_date,
            viewing_time,
        ) not in BOOKED_VIEWING_SLOTS
    ]

    if not available_slots:
        return (
            f"KẾT QUẢ: Phòng {normalized_id} không còn lịch xem trống "
            f"trong ngày {normalized_date}."
        )

    return (
        f"Lịch xem còn trống của phòng {normalized_id} "
        f"ngày {normalized_date}: "
        + ", ".join(available_slots)
        + "."
    )


# =====================================================================
# 6. TOOL 4: ĐẶT LỊCH XEM NHÀ
# =====================================================================

def book_viewing(
    property_id: str,
    viewing_date: str,
    viewing_time: str,
    customer_name: str,
    confirmed: bool = False,
) -> str:
    """
    Đặt lịch xem nhà sau khi người dùng xác nhận đầy đủ thông tin.

    confirmed chỉ được là true khi người dùng đã xác nhận rõ:
    mã phòng, ngày xem và giờ xem.

    Failure modes:
    - Thiếu thông tin bắt buộc.
    - Chưa có xác nhận của người dùng.
    - Phòng, ngày hoặc giờ không hợp lệ.
    - Khung giờ đã được đặt.
    """
    property_item = _find_property(property_id)

    if property_item is None:
        return f"LỖI: Không tìm thấy phòng có mã '{property_id}'."

    if not str(customer_name).strip():
        return "LỖI: Tên người đặt lịch không được để trống."

    if not _is_confirmed(confirmed):
        return (
            "YÊU CẦU XÁC NHẬN: Chưa thể đặt lịch. "
            "Người dùng phải xác nhận rõ mã phòng, ngày và giờ xem nhà."
        )

    _, date_error = _parse_viewing_date(viewing_date)

    if date_error:
        return date_error

    normalized_id = property_item["property_id"]
    normalized_date = str(viewing_date).strip()
    normalized_time = str(viewing_time).strip()

    if not re.fullmatch(r"\d{2}:\d{2}", normalized_time):
        return "LỖI: Giờ xem phải có định dạng HH:MM."

    valid_times = PROPERTY_VIEWING_TIMES[normalized_id]

    if normalized_time not in valid_times:
        return (
            f"LỖI: Khung giờ {normalized_time} không được mở "
            f"cho phòng {normalized_id}."
        )

    booking_key = (
        normalized_id,
        normalized_date,
        normalized_time,
    )

    if booking_key in BOOKED_VIEWING_SLOTS:
        return (
            f"LỖI: Khung giờ {normalized_time} ngày {normalized_date} "
            f"của phòng {normalized_id} đã được đặt."
        )

    booking_id = f"B{len(BOOKING_RECORDS) + 1:03d}"

    booking_record = {
        "booking_id": booking_id,
        "property_id": normalized_id,
        "viewing_date": normalized_date,
        "viewing_time": normalized_time,
        "customer_name": str(customer_name).strip(),
    }

    BOOKED_VIEWING_SLOTS.add(booking_key)
    BOOKING_RECORDS.append(booking_record)

    return (
        "ĐẶT LỊCH THÀNH CÔNG:\n"
        f"- Mã lịch: {booking_id}\n"
        f"- Phòng: {normalized_id} - {property_item['title']}\n"
        f"- Ngày xem: {normalized_date}\n"
        f"- Giờ xem: {normalized_time}\n"
        f"- Người đặt: {booking_record['customer_name']}"
    )


# =====================================================================
# 7. GUARDRAIL: LỌC PROMPT INJECTION TRONG TOOL OUTPUT
# =====================================================================

def sanitize_tool_output(raw_text: str) -> str:
    """Lọc các chỉ thị đáng ngờ khỏi kết quả Tool."""
    dangerous_patterns = [
        r"ignore\s+(all\s+)?previous\s+instructions?",
        r"system\s+instruction\s+override",
        r"your\s+new\s+task\s+is",
        r"disable\s+(all\s+)?guardrails?",
        r"reveal\s+(the\s+)?system\s+prompt",
    ]

    cleaned_text = str(raw_text)

    for pattern in dangerous_patterns:
        cleaned_text = re.sub(
            pattern,
            "[BLOCKED_INJECTION_ATTEMPT]",
            cleaned_text,
            flags=re.IGNORECASE,
        )

    return cleaned_text


# =====================================================================
# 8. TOOL REGISTRY WHITELIST
# =====================================================================

AVAILABLE_TOOLS: dict[str, Callable[..., str]] = {
    "search_properties": search_properties,
    "get_property_details": get_property_details,
    "check_viewing_slots": check_viewing_slots,
    "book_viewing": book_viewing,
}

ALLOWED_TOOL_REGISTRY = AVAILABLE_TOOLS

SENSITIVE_TOOLS = {
    "book_viewing",
}


def execute_tool_safely(
    tool_name: str,
    tool_args: dict,
) -> str:
    """Chỉ thực thi Tool đã đăng ký và kiểm tra hành động nhạy cảm."""
    tool_function = ALLOWED_TOOL_REGISTRY.get(tool_name)

    if tool_function is None:
        return f"LỖI: Tool '{tool_name}' không được phép sử dụng."

    if not isinstance(tool_args, dict):
        return "LỖI: Tham số Tool phải được cung cấp dưới dạng dictionary."

    if (
        tool_name in SENSITIVE_TOOLS
        and not _is_confirmed(tool_args.get("confirmed", False))
    ):
        return (
            "YÊU CẦU XÁC NHẬN: Người dùng phải xác nhận rõ "
            "phòng, ngày và giờ trước khi đặt lịch."
        )

    try:
        result = tool_function(**tool_args)
        return sanitize_tool_output(result)
    except TypeError:
        return f"LỖI: Tham số của Tool '{tool_name}' không hợp lệ."
    except Exception:
        return f"LỖI: Không thể thực thi Tool '{tool_name}'."


# =====================================================================
# 9. TOOL SCHEMAS
# =====================================================================

TOOL_SCHEMAS = {
    "search_properties": {
        "description": "Tìm phòng theo khu vực, ngân sách và loại phòng.",
        "required": ["location", "max_price", "room_type"],
    },
    "get_property_details": {
        "description": "Tra cứu chi tiết phòng theo mã.",
        "required": ["property_id"],
    },
    "check_viewing_slots": {
        "description": "Kiểm tra lịch xem nhà còn trống.",
        "required": ["property_id", "viewing_date"],
    },
    "book_viewing": {
        "description": "Đặt lịch xem nhà sau khi người dùng xác nhận.",
        "required": [
            "property_id",
            "viewing_date",
            "viewing_time",
            "customer_name",
            "confirmed",
        ],
    },
}