"""
TOOL REGISTRY & SAFE TOOL CONTRACTS
Role 2: Tool & Spec Engineer

Đề tài 10: Trợ lý tìm và đặt lịch xem nhà trọ/căn hộ.

Checkpoint 3 bổ sung lớp xử lý lỗi an toàn:
- Mọi Tool luôn trả về ``str`` để dùng làm Observation.
- Lỗi nghiệp vụ có mã lỗi rõ ràng và không làm chương trình crash.
- ``book_viewing`` tự chặn khi chưa có xác nhận từ application layer.
- Tool đặt lịch chống slot sai, thời gian quá khứ và booking trùng.
"""

from datetime import datetime
from functools import wraps
from typing import Callable


# ---------------------------------------------------------------------------
# MOCK DATA — dữ liệu demo trong bộ nhớ, không phải dữ liệu production.
# ---------------------------------------------------------------------------
MOCK_RENTALS = [
    {
        "listing_id": "CG101",
        "title": "Studio có ban công tại Cầu Giấy",
        "district": "Cầu Giấy",
        "price": 5_200_000,
        "room_type": "studio",
        "amenities": ["điều hòa", "ban công"],
        "status": "available",
    },
    {
        "listing_id": "CG102",
        "title": "Căn 1 phòng ngủ gần đường Trần Thái Tông",
        "district": "Cầu Giấy",
        "price": 6_500_000,
        "room_type": "1-bedroom",
        "amenities": ["điều hòa", "máy giặt"],
        "status": "available",
    },
    {
        "listing_id": "NTL201",
        "title": "Studio tại Mỹ Đình",
        "district": "Nam Từ Liêm",
        "price": 4_800_000,
        "room_type": "studio",
        "amenities": ["điều hòa"],
        "status": "available",
    },
    {
        "listing_id": "HD301",
        "title": "Phòng trọ gần ga Hà Đông",
        "district": "Hà Đông",
        "price": 4_000_000,
        "room_type": "room",
        "amenities": [],
        "status": "unavailable",
    },
]

MOCK_VIEWING_SLOTS = {
    "CG101": ["2026-07-30 18:00", "2026-07-30 19:00"],
    "CG102": ["2026-07-31 09:00"],
    "NTL201": [],
}

MOCK_BOOKINGS = []


# ---------------------------------------------------------------------------
# SAFE HELPERS
# ---------------------------------------------------------------------------
def _error(error_code: str, message: str) -> str:
    """Tạo chuỗi lỗi nhất quán để Agent dùng làm Observation."""
    return f"LỖI [{error_code}]: {message}"


def _safe_tool(function: Callable) -> Callable:
    """
    Chặn exception ngoài dự kiến ở ranh giới Tool.

    Lỗi nghiệp vụ vẫn được xử lý trong từng hàm. Decorator này là lớp bảo vệ
    cuối để dữ liệu mock hỏng hoặc lỗi lập trình không làm ReAct Loop crash.
    """

    @wraps(function)
    def wrapper(*args, **kwargs) -> str:
        try:
            result = function(*args, **kwargs)
            if not isinstance(result, str):
                return _error(
                    "INVALID_TOOL_OUTPUT",
                    f"Tool {function.__name__} trả về dữ liệu không phải chuỗi.",
                )
            return result
        except Exception as exc:
            return _error(
                "TOOL_FAILURE",
                f"{function.__name__} gặp lỗi ngoài dự kiến: {exc}",
            )

    return wrapper


def _normalize_text(value: str) -> str:
    """Chuẩn hóa khoảng trắng và chữ hoa/thường để so sánh."""
    return " ".join(value.strip().casefold().split())


def _parse_max_price(max_price) -> tuple:
    """Đổi giá đầu vào về số nguyên dương hoặc trả chuỗi lỗi."""
    if isinstance(max_price, bool):
        return None, _error(
            "INVALID_ARGUMENT",
            "max_price phải là số nguyên dương, tính bằng VNĐ.",
        )

    if isinstance(max_price, int):
        parsed_price = max_price
    elif isinstance(max_price, str):
        cleaned_price = (
            max_price.strip()
            .casefold()
            .replace("vnđ", "")
            .replace("vnd", "")
            .replace(".", "")
            .replace(",", "")
            .replace("_", "")
            .replace(" ", "")
        )
        if not cleaned_price.isdigit():
            return None, _error(
                "INVALID_ARGUMENT",
                "max_price phải là số nguyên dương, tính bằng VNĐ.",
            )
        parsed_price = int(cleaned_price)
    else:
        return None, _error(
            "INVALID_ARGUMENT",
            "max_price phải là số nguyên dương, tính bằng VNĐ.",
        )

    if parsed_price <= 0:
        return None, _error(
            "INVALID_ARGUMENT",
            "max_price phải lớn hơn 0.",
        )

    return parsed_price, None


def _find_rental(listing_id: str):
    """Tìm listing theo mã đã chuẩn hóa."""
    normalized_id = listing_id.strip().upper()
    return next(
        (
            rental
            for rental in MOCK_RENTALS
            if rental["listing_id"] == normalized_id
        ),
        None,
    )


def _booked_slot_keys() -> set:
    """Lấy tập các cặp listing/slot đã được đặt."""
    return {
        (booking["listing_id"], booking["slot"])
        for booking in MOCK_BOOKINGS
    }


# ---------------------------------------------------------------------------
# TOOL 1: SEARCH RENTALS
# ---------------------------------------------------------------------------
@_safe_tool
def search_rentals(district: str, max_price: int) -> str:
    """
    Tìm căn nhà trọ/căn hộ mock theo khu vực và ngân sách.

    Use when:
        Người dùng cần dữ liệu căn đang có và đã cung cấp khu vực cùng ngân
        sách tối đa.

    Do not use when:
        Người dùng chỉ hỏi kiến thức chung như kinh nghiệm xem phòng hoặc
        phân biệt tiền cọc với tiền thuê tháng đầu.

    Args:
        district: Tên quận/khu vực, ví dụ ``"Cầu Giấy"``.
        max_price: Giá thuê tối đa mỗi tháng, tính bằng VNĐ.

    Returns:
        Chuỗi Observation chứa các listing phù hợp. Nếu input sai hoặc không
        có kết quả, trả chuỗi ``LỖI [MÃ_LỖI]: ...`` và không crash.

    Side effects:
        Không. Tool chỉ đọc ``MOCK_RENTALS``.
    """
    if not isinstance(district, str) or not district.strip():
        return _error(
            "INVALID_ARGUMENT",
            "district phải là chuỗi không rỗng.",
        )

    parsed_price, price_error = _parse_max_price(max_price)
    if price_error:
        return price_error

    normalized_district = _normalize_text(district)
    matches = [
        rental
        for rental in MOCK_RENTALS
        if _normalize_text(rental["district"]) == normalized_district
        and rental["price"] <= parsed_price
        and rental["status"] == "available"
    ]
    matches.sort(key=lambda rental: (rental["price"], rental["listing_id"]))

    if not matches:
        return _error(
            "NO_MATCH",
            f"Không tìm thấy căn đang trống tại {district.strip()} trong "
            f"ngân sách {parsed_price:,} VNĐ/tháng.",
        )

    lines = [
        "KẾT QUẢ search_rentals:",
        f"district={district.strip()} | max_price={parsed_price} | "
        f"count={len(matches)}",
    ]
    for rental in matches:
        amenities = ", ".join(rental["amenities"]) or "không có dữ liệu"
        lines.append(
            f"- listing_id={rental['listing_id']} | "
            f"title={rental['title']} | price={rental['price']} | "
            f"room_type={rental['room_type']} | amenities={amenities}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TOOL 2: CHECK VIEWING SLOTS
# ---------------------------------------------------------------------------
@_safe_tool
def check_viewing_slots(listing_id: str) -> str:
    """
    Kiểm tra các khung giờ xem còn trống của một listing.

    Use when:
        Agent đã lấy được ``listing_id`` hợp lệ từ Observation của
        ``search_rentals`` và người dùng muốn xem lịch.

    Do not use when:
        Mã căn chưa xuất hiện trong dữ liệu Tool hoặc người dùng chỉ muốn tìm
        danh sách căn.

    Args:
        listing_id: Mã căn, ví dụ ``"CG101"``.

    Returns:
        Chuỗi Observation chứa các slot còn trống. Mã căn không tồn tại, căn
        ngừng hoạt động hoặc hết lịch đều trả chuỗi lỗi an toàn.

    Side effects:
        Không. Tool chỉ đọc dữ liệu mock và booking trong bộ nhớ.
    """
    if not isinstance(listing_id, str) or not listing_id.strip():
        return _error(
            "INVALID_ARGUMENT",
            "listing_id phải là chuỗi không rỗng.",
        )

    normalized_id = listing_id.strip().upper()
    rental = _find_rental(normalized_id)

    if rental is None:
        return _error(
            "LISTING_NOT_FOUND",
            f"Không tìm thấy căn có mã {normalized_id}.",
        )

    if rental["status"] != "available":
        return _error(
            "LISTING_UNAVAILABLE",
            f"Căn {normalized_id} hiện không còn nhận lịch xem.",
        )

    booked_slots = _booked_slot_keys()
    available_slots = [
        slot
        for slot in MOCK_VIEWING_SLOTS.get(normalized_id, [])
        if (normalized_id, slot) not in booked_slots
    ]

    if not available_slots:
        return _error(
            "NO_AVAILABLE_SLOT",
            f"Căn {normalized_id} hiện không còn lịch xem trống.",
        )

    return (
        "KẾT QUẢ check_viewing_slots:\n"
        f"listing_id={normalized_id} | "
        f"available_slots={available_slots}"
    )


# ---------------------------------------------------------------------------
# TOOL 3: BOOK VIEWING — SENSITIVE / SIDE EFFECT
# ---------------------------------------------------------------------------
@_safe_tool
def book_viewing(
    listing_id: str,
    slot: str,
    confirmed: bool = False,
) -> str:
    """
    Mô phỏng đặt một lịch xem đã được người dùng xác nhận.

    Use when:
        Người dùng đã chọn một ``listing_id`` có thật, chọn đúng một ``slot``
        từ Observation của ``check_viewing_slots`` và xác nhận rõ thao tác.

    Do not use when:
        Chưa xác nhận, mã căn/slot do Agent tự bịa, thời gian trong quá khứ,
        hoặc người dùng yêu cầu bỏ qua Guardrail.

    Args:
        listing_id: Mã căn cần xem, ví dụ ``"CG101"``.
        slot: Khung giờ khớp chính xác dữ liệu Tool, định dạng
            ``"YYYY-MM-DD HH:MM"``.
        confirmed: Chỉ application layer được truyền ``True`` sau khi kiểm
            tra xác nhận của người dùng. Mặc định ``False`` để fail-safe.

    Returns:
        Chuỗi xác nhận booking mock khi thành công. Mọi lỗi đều trả chuỗi
        ``LỖI [MÃ_LỖI]: ...`` và không làm chương trình crash.

    Side effects:
        Khi thành công, thêm một booking vào ``MOCK_BOOKINGS`` trong bộ nhớ.
    """
    if confirmed is not True:
        return _error(
            "CONFIRMATION_REQUIRED",
            "Chưa có xác nhận hợp lệ của người dùng; không tạo lịch xem.",
        )

    if not isinstance(listing_id, str) or not listing_id.strip():
        return _error(
            "INVALID_ARGUMENT",
            "listing_id phải là chuỗi không rỗng.",
        )

    if not isinstance(slot, str) or not slot.strip():
        return _error(
            "INVALID_ARGUMENT",
            "slot phải là chuỗi không rỗng.",
        )

    normalized_id = listing_id.strip().upper()
    normalized_slot = slot.strip()
    rental = _find_rental(normalized_id)

    if rental is None:
        return _error(
            "LISTING_NOT_FOUND",
            f"Không tìm thấy căn có mã {normalized_id}.",
        )

    if rental["status"] != "available":
        return _error(
            "LISTING_UNAVAILABLE",
            f"Căn {normalized_id} hiện không nhận lịch xem.",
        )

    try:
        slot_datetime = datetime.strptime(
            normalized_slot,
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        return _error(
            "INVALID_SLOT_FORMAT",
            "slot phải có định dạng YYYY-MM-DD HH:MM.",
        )

    if slot_datetime <= datetime.now():
        return _error(
            "PAST_SLOT",
            "Không thể đặt lịch xem trong quá khứ.",
        )

    if normalized_slot not in MOCK_VIEWING_SLOTS.get(normalized_id, []):
        return _error(
            "SLOT_NOT_FOUND",
            f"Slot '{normalized_slot}' không thuộc căn {normalized_id}.",
        )

    if (normalized_id, normalized_slot) in _booked_slot_keys():
        return _error(
            "DUPLICATE_BOOKING",
            f"Slot '{normalized_slot}' của căn {normalized_id} đã được đặt.",
        )

    booking = {
        "booking_id": f"BK{len(MOCK_BOOKINGS) + 1:03d}",
        "listing_id": normalized_id,
        "slot": normalized_slot,
        "status": "confirmed",
    }
    MOCK_BOOKINGS.append(booking)

    return (
        "KẾT QUẢ book_viewing: "
        f"booking_id={booking['booking_id']} | "
        f"listing_id={booking['listing_id']} | "
        f"slot={booking['slot']} | status=confirmed"
    )


# Registry chính thức của đề tài. Role 4 chỉ thực thi Tool trong registry này.
AVAILABLE_TOOLS = {
    "search_rentals": search_rentals,
    "check_viewing_slots": check_viewing_slots,
    "book_viewing": book_viewing,
}


# ---------------------------------------------------------------------------
# LEGACY COMPATIBILITY
# Chỉ giữ để app.py cũ không lỗi import trong lúc Role 4 đang tích hợp Mốc 3.
# Hai hàm này không nằm trong AVAILABLE_TOOLS và Agent không được phép gọi.
# ---------------------------------------------------------------------------
def get_weather(location: str) -> str:
    """Legacy stub của đề cũ, không phải Tool hợp lệ của đề 10."""
    return _error(
        "UNKNOWN_TOOL",
        f"get_weather không thuộc đề tài tìm nhà (location={location!r}).",
    )


def search_flights(origin: str, destination: str) -> str:
    """Legacy stub của đề cũ, không phải Tool hợp lệ của đề 10."""
    return _error(
        "UNKNOWN_TOOL",
        "search_flights không thuộc đề tài tìm nhà "
        f"(origin={origin!r}, destination={destination!r}).",
    )


if __name__ == "__main__":
    print("=== CHECKPOINT 3: SAFE TOOL SMOKE TEST ===")
    print(search_rentals("Cầu Giấy", 6_000_000))
    print(check_viewing_slots("CG101"))
    print(book_viewing("CG101", "2026-07-30 18:00"))
    print(book_viewing("CG999", "2026-07-27 02:00", confirmed=True))