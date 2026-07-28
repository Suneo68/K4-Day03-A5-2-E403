"""
🛠️ TOOL REGISTRY & SCHEMAS (Dành cho Role 2: Tool & Spec Engineer)
Đề 10: Trợ lý tìm và đặt lịch xem nhà trọ/căn hộ.

Danh sách Tool của bài demo:
1. search_rentals(district, max_price): Tìm căn theo khu vực và ngân sách.
2. check_viewing_slots(listing_id): Kiểm tra lịch xem còn trống.
3. book_viewing(listing_id, slot): Mô phỏng đặt một lịch xem đã được xác nhận.

Toàn bộ dữ liệu bên dưới là mock, chỉ tồn tại trong bộ nhớ của tiến trình Python.
"""


# ---------------------------------------------------------------------------
# MOCK DATA — đủ nhỏ để demo trong bài lab, không phải dữ liệu production.
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


def _normalize_text(value: str) -> str:
    """Chuẩn hóa chuỗi đơn giản để so sánh dữ liệu mock."""
    return " ".join(value.strip().casefold().split())


def _error(error_code: str, message: str) -> dict:
    """Tạo output lỗi nhất quán để Agent đọc như một Observation."""
    return {
        "ok": False,
        "error_code": error_code,
        "message": message,
    }


def search_rentals(district: str, max_price: int) -> dict:
    """
    Tìm các căn nhà trọ/căn hộ mock theo khu vực và giá thuê tối đa.

    Use when:
        Người dùng cần dữ liệu căn đang có, giá thuê hoặc danh sách căn phù hợp.

    Do not use when:
        Người dùng chỉ hỏi kiến thức chung như kinh nghiệm xem phòng hoặc tiền cọc.

    Args:
        district: Tên quận/khu vực, ví dụ ``"Cầu Giấy"``.
        max_price: Giá thuê tối đa mỗi tháng, tính bằng VNĐ và phải lớn hơn 0.

    Returns:
        Dict có ``ok=True``, số lượng và danh sách căn phù hợp khi thành công.
        Nếu input sai hoặc không có căn phù hợp, trả ``ok=False`` cùng
        ``error_code``; hàm không quăng lỗi nghiệp vụ ra ngoài.

    Side effects:
        Không. Tool chỉ đọc ``MOCK_RENTALS``.

    Example:
        ``search_rentals("Cầu Giấy", 6_000_000)`` trả căn ``CG101``.
    """
    if not isinstance(district, str) or not district.strip():
        return _error(
            "INVALID_ARGUMENT",
            "district phải là chuỗi không rỗng.",
        )

    if (
        not isinstance(max_price, int)
        or isinstance(max_price, bool)
        or max_price <= 0
    ):
        return _error(
            "INVALID_ARGUMENT",
            "max_price phải là số nguyên dương, tính bằng VNĐ.",
        )

    normalized_district = _normalize_text(district)
    matches = [
        dict(rental)
        for rental in MOCK_RENTALS
        if _normalize_text(rental["district"]) == normalized_district
        and rental["price"] <= max_price
        and rental["status"] == "available"
    ]
    matches.sort(key=lambda rental: (rental["price"], rental["listing_id"]))

    if not matches:
        return _error(
            "NO_MATCH",
            f"Không tìm thấy căn đang trống tại {district} trong ngân sách "
            f"{max_price:,} VNĐ/tháng.",
        )

    return {
        "ok": True,
        "district": district.strip(),
        "max_price": max_price,
        "count": len(matches),
        "matches": matches,
    }


def check_viewing_slots(listing_id: str) -> dict:
    """
    Kiểm tra các lịch xem mock còn trống của một listing.

    Use when:
        Agent đã nhận được ``listing_id`` từ Observation của Tool tìm kiếm và
        người dùng muốn biết thời gian có thể đến xem.

    Do not use when:
        Chưa có ``listing_id`` hợp lệ hoặc người dùng chỉ cần tìm danh sách căn.

    Args:
        listing_id: Mã căn, ví dụ ``"CG101"``.

    Returns:
        Dict có ``ok=True`` và ``available_slots`` nếu còn lịch.
        Nếu mã căn không tồn tại hoặc hết lịch, trả error Observation an toàn.

    Side effects:
        Không. Tool chỉ đọc mock data và bỏ qua các slot đã được booking.

    Example:
        ``check_viewing_slots("CG101")`` trả hai slot demo nếu chưa đặt.
    """
    if not isinstance(listing_id, str) or not listing_id.strip():
        return _error(
            "INVALID_ARGUMENT",
            "listing_id phải là chuỗi không rỗng.",
        )

    normalized_id = listing_id.strip().upper()
    rental = next(
        (
            item
            for item in MOCK_RENTALS
            if item["listing_id"] == normalized_id
        ),
        None,
    )
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

    booked_slots = {
        (booking["listing_id"], booking["slot"])
        for booking in MOCK_BOOKINGS
    }
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

    return {
        "ok": True,
        "listing_id": normalized_id,
        "available_slots": available_slots,
    }


def book_viewing(listing_id: str, slot: str) -> dict:
    """
    Mô phỏng đặt một lịch xem căn hộ vào bộ nhớ của tiến trình Python.

    Use when:
        Người dùng đã chọn rõ ``listing_id``, chọn một ``slot`` có trong
        Observation và đã xác nhận hành động ở application layer.

    Do not use when:
        Chưa có xác nhận của người dùng. Việc kiểm tra xác nhận là Guardrail
        của ``src/app.py``; LLM không được tự cấp quyền gọi Tool này.

    Args:
        listing_id: Mã căn cần xem, ví dụ ``"CG101"``.
        slot: Thời gian phải khớp chính xác với một slot mock còn trống,
            ví dụ ``"2026-07-30 18:00"``.

    Returns:
        Dict có ``ok=True`` và ``booking_id`` khi đặt thành công.
        Nếu mã căn/slot sai hoặc booking bị lặp, trả ``ok=False`` cùng
        ``error_code`` và không làm chương trình crash.

    Side effects:
        Có. Append một booking vào ``MOCK_BOOKINGS`` trong bộ nhớ. Dữ liệu
        biến mất khi chương trình kết thúc; đây không phải booking thực tế.

    Example:
        ``book_viewing("CG101", "2026-07-30 18:00")`` tạo ``BK001``.
    """
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
    rental = next(
        (
            item
            for item in MOCK_RENTALS
            if item["listing_id"] == normalized_id
        ),
        None,
    )
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
    if normalized_slot not in MOCK_VIEWING_SLOTS.get(normalized_id, []):
        return _error(
            "SLOT_NOT_FOUND",
            f"Slot '{normalized_slot}' không thuộc căn {normalized_id}.",
        )

    duplicate = next(
        (
            booking
            for booking in MOCK_BOOKINGS
            if booking["listing_id"] == normalized_id
            and booking["slot"] == normalized_slot
        ),
        None,
    )
    if duplicate is not None:
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

    return {
        "ok": True,
        **booking,
        "message": "Đặt lịch xem mock thành công.",
    }


# Mốc 1 — danh sách Tool chính thức của đề 10.
AVAILABLE_TOOLS = {
    "search_rentals": search_rentals,
    "check_viewing_slots": check_viewing_slots,
    "book_viewing": book_viewing,
}


# ---------------------------------------------------------------------------
# LEGACY COMPATIBILITY
# Hai hàm dưới đây chỉ được giữ tạm để src/app.py cũ chưa lỗi import trước khi
# Role 4 chuyển hoàn toàn sang AVAILABLE_TOOLS. Chúng KHÔNG nằm trong registry.
# ---------------------------------------------------------------------------
def get_weather(location: str) -> str:
    """Legacy Tool của đề cũ; Role 4 sẽ xóa sau khi tích hợp đề 10."""
    return f"[LEGACY] Không còn dùng Tool thời tiết cho địa điểm '{location}'."


def search_flights(origin: str, destination: str) -> str:
    """Legacy Tool của đề cũ; Role 4 sẽ xóa sau khi tích hợp đề 10."""
    return (
        f"[LEGACY] Không còn dùng Tool chuyến bay {origin} -> {destination} "
        "trong đề 10."
    )


if __name__ == "__main__":
    import sys

    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=== SMOKE TEST MOCK RENTAL TOOLS ===")
    print(search_rentals("Cầu Giấy", 6_000_000))
    print(check_viewing_slots("CG101"))
    print(book_viewing("CG101", "2026-07-30 18:00"))
    print(book_viewing("CG101", "2026-07-30 18:00"))
