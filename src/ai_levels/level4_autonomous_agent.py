"""
🚀 CẤP ĐỘ 4: AUTONOMOUS AGENT

Bonus demo cho bài lab: agent có Planning, Memory và tự đánh giá tiến độ.
Thiết kế này giữ nhẹ để phù hợp bài thực hành, nhưng vẫn đủ để trình diễn
Level 4 khác với ReAct Loop:

- Planning: tạo kế hoạch theo mục tiêu người dùng.
- Memory: lưu lại quyết định, quan sát và giả định.
- Self-evaluation: kiểm tra còn thiếu gì trước khi đi tiếp.
"""

from __future__ import annotations

from ast import literal_eval
from dataclasses import dataclass, field
import re
from typing import Any

from tools import book_viewing, check_viewing_slots, search_rentals


DEFAULT_AUTONOMOUS_GOAL = (
    "Tìm phòng ở Cầu Giấy dưới 6 triệu, kiểm tra lịch xem và tổng hợp kết quả."
)

KNOWN_DISTRICTS = ("Cầu Giấy", "Nam Từ Liêm", "Hà Đông")


@dataclass
class PlanStep:
    kind: str
    description: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEntry:
    step: int
    phase: str
    note: str
    observation: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _extract_district(goal: str) -> tuple[str | None, bool]:
    normalized = _normalize(goal)
    for district in KNOWN_DISTRICTS:
        if _normalize(district) in normalized:
            return district, False
    if any(keyword in normalized for keyword in ("phòng", "nhà trọ", "căn hộ")):
        return "Cầu Giấy", True
    return None, False


def _extract_budget(goal: str) -> tuple[int | None, bool]:
    normalized = _normalize(goal)

    match = re.search(r"(\d+(?:[.,]\d+)?)\s*triệu", normalized)
    if match:
        value = float(match.group(1).replace(",", "."))
        return int(value * 1_000_000), False

    match = re.search(r"(\d[\d,_.]*)\s*(?:vnđ|vnd|đ)", normalized)
    if match:
        cleaned = match.group(1).replace(",", "").replace(".", "").replace("_", "")
        if cleaned.isdigit():
            return int(cleaned), False

    if any(keyword in normalized for keyword in ("phòng", "nhà trọ", "căn hộ")):
        return 6_000_000, True
    return None, False


def _wants_slots(goal: str) -> bool:
    normalized = _normalize(goal)
    return any(keyword in normalized for keyword in ("lịch", "slot", "xem"))


def _wants_booking(goal: str) -> bool:
    normalized = _normalize(goal)
    return any(keyword in normalized for keyword in ("đặt", "book", "booking"))


def _confirmation_granted(goal: str) -> bool:
    normalized = _normalize(goal)
    negative_phrases = (
        "không cần tôi xác nhận",
        "không cần xác nhận",
        "chưa xác nhận",
        "không xác nhận",
        "bỏ qua xác nhận",
    )
    if any(phrase in normalized for phrase in negative_phrases):
        return False

    positive_phrases = (
        "tôi xác nhận",
        "xác nhận đặt lịch",
        "xác nhận booking",
        "đồng ý đặt lịch",
    )
    return any(phrase in normalized for phrase in positive_phrases)


def _listing_ids_from_observation(observation: str) -> list[str]:
    return re.findall(r"listing_id=([A-Z]{2,}\d+)", observation)


def _slots_from_observation(observation: str) -> list[str]:
    match = re.search(r"available_slots=(\[.*\])", observation)
    if not match:
        return []
    try:
        slots = literal_eval(match.group(1))
    except (ValueError, SyntaxError):
        return []
    return [slot for slot in slots if isinstance(slot, str)]


class AutonomousGoalAgent:
    """
    Autonomous Agent demo cho đề tài thuê nhà.

    Agent này không chỉ gọi tool tuần tự. Nó:
    - tạo kế hoạch theo mục tiêu,
    - ghi memory sau mỗi bước,
    - tự kiểm tra còn thiếu gì,
    - và dừng an toàn nếu chưa có xác nhận cho booking.
    """

    def __init__(self, goal: str, max_steps: int = 5):
        self.goal = goal.strip() or DEFAULT_AUTONOMOUS_GOAL
        self.max_steps = max_steps
        self.memory: list[MemoryEntry] = []
        self.plan: list[PlanStep] = []
        self.state: dict[str, Any] = {
            "district": None,
            "budget": None,
            "budget_defaulted": False,
            "district_defaulted": False,
            "needs_slots": False,
            "needs_booking": False,
            "confirmed": False,
            "candidate_listing_id": None,
            "candidate_slots": [],
            "chosen_slot": None,
            "booking_id": None,
            "completed": False,
        }

    def _snapshot(self) -> dict[str, Any]:
        return {
            "district": self.state["district"],
            "budget": self.state["budget"],
            "candidate_listing_id": self.state["candidate_listing_id"],
            "candidate_slots": list(self.state["candidate_slots"]),
            "chosen_slot": self.state["chosen_slot"],
            "booking_id": self.state["booking_id"],
        }

    def _remember(
        self,
        *,
        step: int,
        phase: str,
        note: str,
        observation: str | None = None,
    ) -> None:
        self.memory.append(
            MemoryEntry(
                step=step,
                phase=phase,
                note=note,
                observation=observation,
                state=self._snapshot(),
            )
        )

    def build_plan(self) -> list[PlanStep]:
        district, district_defaulted = _extract_district(self.goal)
        budget, budget_defaulted = _extract_budget(self.goal)
        needs_slots = _wants_slots(self.goal)
        needs_booking = _wants_booking(self.goal)
        confirmed = _confirmation_granted(self.goal)

        self.state.update(
            {
                "district": district,
                "budget": budget,
                "district_defaulted": district_defaulted,
                "budget_defaulted": budget_defaulted,
                "needs_slots": needs_slots,
                "needs_booking": needs_booking,
                "confirmed": confirmed,
            }
        )

        plan: list[PlanStep] = []

        if district_defaulted:
            plan.append(
                PlanStep(
                    kind="assumption",
                    description=(
                        "Đặt giả định quận/khu vực mặc định là Cầu Giấy "
                        "để tiếp tục demo."
                    ),
                )
            )

        if budget_defaulted:
            plan.append(
                PlanStep(
                    kind="assumption",
                    description=(
                        "Đặt giả định ngân sách mặc định là 6.000.000 VNĐ "
                        "để tiếp tục demo."
                    ),
                )
            )

        if district is None or budget is None:
            plan.append(
                PlanStep(
                    kind="clarify",
                    description=(
                        "Thiếu dữ liệu cốt lõi nên cần hỏi lại người dùng "
                        "về khu vực hoặc ngân sách."
                    ),
                )
            )
            self.plan = plan
            return plan

        plan.append(
            PlanStep(
                kind="search",
                description=(
                    f"Tìm căn ở {district} trong ngân sách tối đa {budget:,} VNĐ."
                ),
                arguments={"district": district, "max_price": budget},
            )
        )

        if needs_slots:
            plan.append(
                PlanStep(
                    kind="slots",
                    description="Lấy lịch xem còn trống của căn phù hợp nhất.",
                )
            )

        if needs_booking:
            if confirmed:
                plan.append(
                    PlanStep(
                        kind="book",
                        description=(
                            "Đặt lịch xem nếu người dùng đã xác nhận rõ "
                            "căn và khung giờ."
                        ),
                    )
                )
            else:
                plan.append(
                    PlanStep(
                        kind="confirm",
                        description=(
                            "Chưa đủ xác nhận để đặt lịch, cần xin người "
                            "dùng xác nhận rõ ràng."
                        ),
                    )
                )

        plan.append(
            PlanStep(
                kind="reflect",
                description="Tổng hợp kết quả, đánh giá tiến độ và kết thúc an toàn.",
            )
        )

        self.plan = plan
        return plan

    def _print_plan(self) -> None:
        print("📋 [Planning]")
        for index, step in enumerate(self.plan, start=1):
            print(f"  {index}. {step.description}")

    def _execute_search(self, step_no: int, step: PlanStep) -> str:
        observation = search_rentals(**step.arguments)
        self._remember(
            step=step_no,
            phase="search",
            note=step.description,
            observation=observation,
        )
        print(f"🛠️ [Execution]: search_rentals{step.arguments}")
        print(f"👁️ [Observation]: {observation}")

        if observation.startswith("LỖI [NO_MATCH]"):
            return observation

        listing_ids = _listing_ids_from_observation(observation)
        if listing_ids:
            self.state["candidate_listing_id"] = listing_ids[0]
        return observation

    def _execute_slots(self, step_no: int, step: PlanStep) -> str:
        listing_id = self.state["candidate_listing_id"]
        if not listing_id:
            observation = (
                "LỖI [MISSING_CONTEXT]: Chưa có listing_id phù hợp để "
                "kiểm tra lịch xem."
            )
        else:
            observation = check_viewing_slots(listing_id)
        self._remember(
            step=step_no,
            phase="slots",
            note=step.description,
            observation=observation,
        )
        print(f"🛠️ [Execution]: check_viewing_slots({listing_id!r})")
        print(f"👁️ [Observation]: {observation}")

        if not observation.startswith("LỖI"):
            slots = _slots_from_observation(observation)
            self.state["candidate_slots"] = slots
            if slots:
                self.state["chosen_slot"] = slots[0]
        return observation

    def _execute_book(self, step_no: int, step: PlanStep) -> str:
        listing_id = self.state["candidate_listing_id"]
        slot = self.state["chosen_slot"]
        if not listing_id or not slot:
            observation = (
                "LỖI [MISSING_CONTEXT]: Chưa có listing_id hoặc slot phù hợp "
                "để đặt lịch."
            )
        elif not self.state["confirmed"]:
            observation = (
                "LỖI [CONFIRMATION_REQUIRED]: Chưa có xác nhận hợp lệ của "
                "người dùng; không tạo lịch xem."
            )
        else:
            observation = book_viewing(
                listing_id,
                slot,
                confirmed=True,
            )
            if not observation.startswith("LỖI"):
                match = re.search(r"booking_id=([A-Z]{2,}\d+)", observation)
                if match:
                    self.state["booking_id"] = match.group(1)
        self._remember(
            step=step_no,
            phase="book",
            note=step.description,
            observation=observation,
        )
        print(
            "🛠️ [Execution]: book_viewing("
            f"{listing_id!r}, {slot!r}, confirmed={self.state['confirmed']})"
        )
        print(f"👁️ [Observation]: {observation}")
        return observation

    def _build_final_answer(self) -> str:
        parts = [
            f"Tôi đã lập kế hoạch {len(self.plan)} bước và lưu lại memory.",
        ]

        if self.state["candidate_listing_id"]:
            parts.append(
                f"Căn phù hợp nhất hiện là {self.state['candidate_listing_id']}."
            )
        if self.state["candidate_slots"]:
            parts.append(
                "Lịch xem còn trống: "
                + ", ".join(self.state["candidate_slots"])
                + "."
            )
        if self.state["booking_id"]:
            parts.append(
                f"Booking mock đã hoàn tất với mã {self.state['booking_id']}."
            )
        elif self.state["needs_booking"] and not self.state["confirmed"]:
            parts.append(
                "Tôi dừng trước bước đặt lịch vì chưa có xác nhận hợp lệ."
            )
        elif self.state["district"] is None or self.state["budget"] is None:
            parts.append(
                "Tôi cần thêm khu vực hoặc ngân sách để tiếp tục."
            )
        else:
            parts.append("Mục tiêu hiện đã hoàn thành ở mức demo phù hợp.")

        return " ".join(parts)

    def execute(self) -> dict[str, Any]:
        print(f"🚀 === AUTONOMOUS AGENT DEMO ===")
        print(f"🎯 Goal: {self.goal}")

        self.build_plan()
        self._print_plan()

        if any(step.kind == "clarify" for step in self.plan):
            final_answer = (
                "Tôi chưa đủ dữ liệu để lập kế hoạch tự chủ. "
                "Vui lòng cho biết khu vực hoặc ngân sách cụ thể."
            )
            self._remember(
                step=1,
                phase="clarify",
                note="Thiếu dữ liệu cốt lõi",
            )
            print(f"🏁 Final Answer: {final_answer}")
            return {
                "status": "needs_input",
                "goal": self.goal,
                "plan": [step.__dict__ for step in self.plan],
                "memory": [entry.__dict__ for entry in self.memory],
                "answer": final_answer,
            }

        plan_to_run = self.plan[: self.max_steps]
        total_steps = len(plan_to_run)
        step_no = 0
        for step in plan_to_run:
            step_no += 1
            print(f"\n--- 🔄 Autonomous Step {step_no}/{total_steps} ---")
            if step.kind == "assumption":
                self._remember(
                    step=step_no,
                    phase="assumption",
                    note=step.description,
                )
                print(f"🧠 [Assumption]: {step.description}")
                continue

            if step.kind == "search":
                observation = self._execute_search(step_no, step)
                if observation.startswith("LỖI [NO_MATCH]"):
                    final_answer = (
                        "Tôi chưa tìm được căn phù hợp trong demo hiện tại. "
                        "Bạn có thể nới ngân sách hoặc đổi khu vực để tôi "
                        "lập lại kế hoạch."
                    )
                    print(f"🏁 Final Answer: {final_answer}")
                    return {
                        "status": "needs_input",
                        "goal": self.goal,
                        "plan": [item.__dict__ for item in self.plan],
                        "memory": [entry.__dict__ for entry in self.memory],
                        "answer": final_answer,
                    }
                continue

            if step.kind == "slots":
                self._execute_slots(step_no, step)
                continue

            if step.kind == "book":
                self._execute_book(step_no, step)
                continue

            if step.kind == "confirm":
                note = (
                    "Chưa có xác nhận nên không thực thi booking. "
                    "Chỉ chờ người dùng phản hồi."
                )
                self._remember(
                    step=step_no,
                    phase="confirm",
                    note=note,
                )
                print(f"🛡️ [Self-Evaluation]: {note}")
                continue

            if step.kind == "reflect":
                note = "Đánh giá tiến độ và tổng hợp kết quả."
                self._remember(
                    step=step_no,
                    phase="reflect",
                    note=note,
                )
                print(f"🧠 [Self-Evaluation]: {note}")
                continue

            self._remember(
                step=step_no,
                phase="unknown",
                note=f"Encountered unsupported plan step: {step.kind}",
            )

        final_answer = self._build_final_answer()
        self.state["completed"] = True
        print(f"🏁 Final Answer: {final_answer}")
        return {
            "status": "completed",
            "goal": self.goal,
            "plan": [step.__dict__ for step in self.plan],
            "memory": [entry.__dict__ for entry in self.memory],
            "answer": final_answer,
        }


def demo_autonomous_agent(goal: str = DEFAULT_AUTONOMOUS_GOAL) -> dict[str, Any]:
    """Chạy demo Level 4 và trả về kết quả có plan + memory."""
    agent = AutonomousGoalAgent(goal=goal)
    return agent.execute()


if __name__ == "__main__":
    demo_autonomous_agent()
