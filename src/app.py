"""
CORE AGENT APP — Role 4: Core Developer / Integrator.

Modes:
    python src/app.py baseline
    python src/app.py react
    python src/app.py all
    python src/app.py react 4

Mặc định chạy cả Baseline và ReAct để so sánh ở Mốc 3. Có thể truyền mode
``baseline`` hoặc ``react`` khi chỉ muốn chạy một nhánh.
"""

import ast
import json
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv


# Cho phép import các module trong src/ khi chạy "python src/app.py".
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from prompts import (  # noqa: E402
    ALLOWED_TOOL_NAMES,
    CHATBOT_BASELINE_PROMPT,
    MAX_ITERATIONS,
    MAX_RETRIES_PER_ACTION,
    REACT_SYSTEM_PROMPT,
    SAFE_FALLBACK_MESSAGE,
)
from providers import get_llm_provider  # noqa: E402
from ai_levels.level4_autonomous_agent import (  # noqa: E402
    DEFAULT_AUTONOMOUS_GOAL,
    demo_autonomous_agent,
)
from tools import AVAILABLE_TOOLS  # noqa: E402


load_dotenv()


def load_test_cases() -> list[dict]:
    """Đọc và validate sơ bộ bộ test cases của Role 1."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")

    if not os.path.exists(config_path):
        config_path = "test_cases.json"

    with open(config_path, "r", encoding="utf-8") as file:
        test_cases = json.load(file)

    if not isinstance(test_cases, list) or not test_cases:
        raise ValueError("config/test_cases.json phải là một list không rỗng.")

    for index, case in enumerate(test_cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Test case #{index} phải là một JSON object.")
        if "id" not in case or not case.get("question"):
            raise ValueError(
                f"Test case #{index} phải có trường 'id' và 'question'."
            )

    return test_cases


def run_baseline_chatbot(
    user_query: str,
    provider,
    *,
    case_id: int | str | None = None,
) -> dict:
    """Chạy Baseline bằng đúng một LLM call và không gọi Tool."""
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("user_query phải là chuỗi không rỗng.")

    label = f"Test Case #{case_id}" if case_id is not None else "User Query"
    print(f"\n{'-' * 70}")
    print(f"💬 {label}: {user_query}")

    answer = provider.generate(
        user_query,
        system_prompt=CHATBOT_BASELINE_PROMPT,
    )
    if not isinstance(answer, str):
        answer = str(answer)

    result = {
        "case_id": case_id,
        "question": user_query,
        "answer": answer,
        "status": "completed",
        "llm_calls": 1,
        "tool_calls": 0,
    }

    print(f"🤖 Baseline Answer:\n{answer}")
    print("📈 Metrics: LLM calls = 1 | Tool calls = 0")
    return result


def run_all_baseline_tests(test_cases: list[dict], provider) -> list[dict]:
    """Chạy Baseline trên toàn bộ test cases."""
    results = [
        run_baseline_chatbot(
            case["question"],
            provider,
            case_id=case["id"],
        )
        for case in test_cases
    ]

    total_llm_calls = sum(result["llm_calls"] for result in results)
    total_tool_calls = sum(result["tool_calls"] for result in results)

    print(f"\n{'=' * 70}")
    print("📊 TỔNG KẾT CHATBOT BASELINE — MỐC 2")
    print(f"✅ Test cases đã chạy : {len(results)}")
    print(f"🧠 Tổng LLM calls     : {total_llm_calls}")
    print(f"🛠️ Tổng Tool calls    : {total_tool_calls}")
    return results


def _provider_failed(response: str) -> bool:
    """Nhận diện lỗi adapter để không parse lỗi thành Action giả."""
    prefixes = (
        "[Gemini Error]",
        "[Gemini Exception]",
        "[OpenAI Error]",
        "[OpenAI Exception]",
        "[Anthropic Error]",
        "[Anthropic Exception]",
        "[OpenRouter Error]",
        "[OpenRouter API Error",
        "[OpenRouter Exception]",
    )
    return response.lstrip().startswith(prefixes)


def parse_model_response(response: str) -> dict[str, Any]:
    """
    Parse đúng một Final Answer hoặc một Action JSON.

    Protocol:
        Action: {"tool":"...", "arguments":{...}}
        Final Answer: ...
    """
    if not isinstance(response, str) or not response.strip():
        return {
            "kind": "malformed",
            "error_code": "MALFORMED_ACTION",
            "message": "LLM trả về response rỗng.",
        }

    action_lines = [
        line.strip()
        for line in response.splitlines()
        if line.strip().startswith("Action:")
    ]
    has_final = "Final Answer:" in response

    if has_final and action_lines:
        return {
            "kind": "malformed",
            "error_code": "PROTOCOL_VIOLATION",
            "message": "Một response không được chứa cả Action và Final Answer.",
        }

    if has_final:
        answer = response.split("Final Answer:", 1)[1].strip()
        if not answer:
            return {
                "kind": "malformed",
                "error_code": "MALFORMED_FINAL",
                "message": "Final Answer không được rỗng.",
            }
        return {"kind": "final", "answer": answer}

    if len(action_lines) != 1:
        return {
            "kind": "malformed",
            "error_code": "MALFORMED_ACTION",
            "message": "Cần đúng một dòng Action JSON hoặc một Final Answer.",
        }

    payload = action_lines[0].split("Action:", 1)[1].strip()
    try:
        action = json.loads(payload)
    except json.JSONDecodeError:
        return {
            "kind": "malformed",
            "error_code": "MALFORMED_ACTION",
            "message": "Action không phải JSON hợp lệ.",
        }

    if not isinstance(action, dict):
        return {
            "kind": "malformed",
            "error_code": "MALFORMED_ACTION",
            "message": "Action phải là JSON object.",
        }

    tool_name = action.get("tool")
    arguments = action.get("arguments", {})
    if not isinstance(tool_name, str) or not tool_name.strip():
        return {
            "kind": "malformed",
            "error_code": "MALFORMED_ACTION",
            "message": "Action thiếu trường tool.",
        }
    if not isinstance(arguments, dict):
        return {
            "kind": "malformed",
            "error_code": "MALFORMED_ACTION",
            "message": "Action.arguments phải là JSON object.",
        }

    return {
        "kind": "action",
        "tool": tool_name.strip(),
        "arguments": arguments,
    }


def _canonical_action(tool_name: str, arguments: dict) -> str:
    """Tạo fingerprint ổn định để phát hiện cùng Action lặp lại."""
    return json.dumps(
        {"tool": tool_name, "arguments": arguments},
        sort_keys=True,
        ensure_ascii=False,
    )


def _user_confirmed_booking(user_query: str) -> bool:
    """
    Rule confirmation demo ở application layer.

    Cụm phủ định được xét trước để câu “không cần xác nhận” không bị hiểu
    nhầm là người dùng đã xác nhận.
    """
    normalized = " ".join(user_query.casefold().split())
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


def _listing_ids_from_observation(observation: str) -> set[str]:
    """Lấy listing_id đã được Tool chứng minh trong Observation."""
    return set(re.findall(r"listing_id=([A-Z]{2,}\d+)", observation))


def _slots_from_observation(observation: str) -> list[str]:
    """Parse danh sách slot từ output check_viewing_slots dạng Python list."""
    match = re.search(r"available_slots=(\[.*\])", observation)
    if not match:
        return []
    try:
        slots = ast.literal_eval(match.group(1))
    except (ValueError, SyntaxError):
        return []
    return [slot for slot in slots if isinstance(slot, str)]


def _validate_action(
    tool_name: str,
    arguments: dict,
    *,
    observed_listing_ids: set[str],
    observed_slots: dict[str, set[str]],
    confirmation_granted: bool,
) -> tuple[bool, str | None, dict]:
    """
    Validate policy trước khi gọi Tool.

    Trả về (allowed, error_observation, executor_arguments).
    """
    if tool_name not in ALLOWED_TOOL_NAMES or tool_name not in AVAILABLE_TOOLS:
        available = ", ".join(sorted(AVAILABLE_TOOLS))
        return (
            False,
            f"LỖI [UNKNOWN_TOOL]: Tool không hợp lệ. Tool hợp lệ: {available}.",
            arguments,
        )

    if not isinstance(arguments, dict):
        return (
            False,
            "LỖI [INVALID_ARGUMENTS]: arguments phải là object.",
            arguments,
        )

    executor_arguments = dict(arguments)

    if tool_name in {"check_viewing_slots", "book_viewing"}:
        listing_id = executor_arguments.get("listing_id")
        if not isinstance(listing_id, str):
            return (
                False,
                "LỖI [INVALID_ARGUMENTS]: thiếu listing_id hợp lệ.",
                executor_arguments,
            )
        listing_id = listing_id.strip().upper()
        executor_arguments["listing_id"] = listing_id
        if listing_id not in observed_listing_ids:
            return (
                False,
                "LỖI [CONFIRMATION_REQUIRED_OR_INVALID_LISTING]: "
                "listing_id chưa xuất hiện trong Observation hợp lệ.",
                executor_arguments,
            )

    if tool_name == "book_viewing":
        slot = executor_arguments.get("slot")
        listing_id = executor_arguments.get("listing_id")
        if not isinstance(slot, str) or not slot.strip():
            return (
                False,
                "LỖI [INVALID_ARGUMENTS]: thiếu slot hợp lệ.",
                executor_arguments,
            )
        executor_arguments["slot"] = slot.strip()

        if not confirmation_granted:
            return (
                False,
                "LỖI [CONFIRMATION_REQUIRED_OR_INVALID_LISTING]: "
                "chưa có xác nhận đặt lịch hợp lệ.",
                executor_arguments,
            )

        if executor_arguments["slot"] not in observed_slots.get(
            listing_id,
            set(),
        ):
            return (
                False,
                "LỖI [CONFIRMATION_REQUIRED_OR_INVALID_LISTING]: "
                "slot chưa xuất hiện trong Observation.",
                executor_arguments,
            )

        # Không tin confirmed do LLM truyền; app tự cấp quyền sau policy check.
        executor_arguments["confirmed"] = True

    return True, None, executor_arguments


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Dispatch Tool qua registry và chuyển mọi lỗi thành Observation string."""
    if tool_name not in AVAILABLE_TOOLS:
        available = ", ".join(sorted(AVAILABLE_TOOLS))
        return (
            f"LỖI [UNKNOWN_TOOL]: Tool không hợp lệ. "
            f"Tool hợp lệ: {available}."
        )

    try:
        result = AVAILABLE_TOOLS[tool_name](**arguments)
    except TypeError:
        return (
            "LỖI [INVALID_ARGUMENTS]: Tham số Action không khớp "
            "với contract của Tool."
        )
    except Exception:
        return "LỖI [TOOL_EXCEPTION]: Tool gặp lỗi ngoài dự kiến."

    if not isinstance(result, str):
        return "LỖI [INVALID_TOOL_OUTPUT]: Tool phải trả về chuỗi."
    return result


def _final_answer_is_grounded(
    answer: str,
    *,
    observed_listing_ids: set[str],
    trace: list[dict],
) -> tuple[bool, str | None]:
    """Chặn claim booking không có Observation confirmed."""
    lowered = answer.casefold()
    booking_claim = (
        "đã đặt" in lowered
        or "đặt lịch thành công" in lowered
        or "booking_id" in lowered
    )
    has_confirmed_booking = any(
        event.get("tool") == "book_viewing"
        and "status=confirmed" in event.get("observation", "")
        for event in trace
    )
    if booking_claim and not has_confirmed_booking:
        return (
            False,
            "LỖI [UNGROUNDED_FINAL]: Không được khẳng định booking "
            "khi chưa có Observation confirmed.",
        )

    mentioned_ids = {
        identifier
        for identifier in re.findall(r"\b[A-Z]{2,}\d+\b", answer)
        if not identifier.startswith("BK")
    }
    unsupported_ids = mentioned_ids - observed_listing_ids
    # Cho phép câu từ chối nhắc lại mã do người dùng cung cấp, nhưng chặn mọi
    # mã chưa có Observation nếu câu trả lời không thể hiện rõ sự từ chối.
    refusal_markers = (
        "không thể",
        "không tìm thấy",
        "không có dữ liệu",
        "không tồn tại",
        "chưa thể",
        "chưa được xác nhận",
    )
    is_refusal = any(marker in lowered for marker in refusal_markers)
    if unsupported_ids and not is_refusal:
        return (
            False,
            "LỖI [UNGROUNDED_FINAL]: Final Answer chứa listing chưa có "
            "trong Observation.",
        )

    return True, None


def _safe_fallback(
    *,
    case_id: int | str | None,
    question: str,
    trace: list[dict],
    model_turns: int,
    tool_calls: int,
    reason: str,
) -> dict:
    """Kết thúc an toàn với kết quả có thể dùng cho Role 5."""
    print(f"🛡️ SAFE FALLBACK [{reason}]: {SAFE_FALLBACK_MESSAGE}")
    return {
        "case_id": case_id,
        "question": question,
        "status": "safe_fallback",
        "answer": SAFE_FALLBACK_MESSAGE,
        "reason": reason,
        "model_turns": model_turns,
        "tool_calls": tool_calls,
        "trace": trace,
    }


def run_react_agent(
    user_query: str,
    provider,
    *,
    case_id: int | str | None = None,
) -> dict:
    """
    Chạy ReAct loop thật:
        LLM -> parse Action -> policy -> Tool -> Observation -> LLM.
    """
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("user_query phải là chuỗi không rỗng.")

    confirmation_granted = _user_confirmed_booking(user_query)
    transcript = f"Question: {user_query}"
    trace: list[dict] = []
    action_counts: dict[str, int] = {}
    observed_listing_ids: set[str] = set()
    observed_slots: dict[str, set[str]] = {}
    model_turns = 0
    tool_calls = 0

    label = f"Test Case #{case_id}" if case_id is not None else "User Query"
    print(f"\n{'=' * 70}")
    print(f"🤖 [REACT AGENT] {label}: {user_query}")
    print(
        f"🔐 Confirmation context: "
        f"{'granted' if confirmation_granted else 'not granted'}"
    )

    for step in range(1, MAX_ITERATIONS + 1):
        model_turns += 1
        print(f"\n--- 🔄 ReAct Step {step}/{MAX_ITERATIONS} ---")

        response = provider.generate(
            transcript,
            system_prompt=REACT_SYSTEM_PROMPT,
        )
        if not isinstance(response, str):
            response = str(response)

        print(f"🧠 LLM output:\n{response}")

        if _provider_failed(response):
            trace.append(
                {
                    "step": step,
                    "event": "provider_error",
                    "model_output": response,
                }
            )
            return _safe_fallback(
                case_id=case_id,
                question=user_query,
                trace=trace,
                model_turns=model_turns,
                tool_calls=tool_calls,
                reason="PROVIDER_ERROR",
            )

        parsed = parse_model_response(response)

        if parsed["kind"] == "final":
            grounded, grounding_error = _final_answer_is_grounded(
                parsed["answer"],
                observed_listing_ids=observed_listing_ids,
                trace=trace,
            )
            if grounded:
                print(f"🏁 Final Answer:\n{parsed['answer']}")
                return {
                    "case_id": case_id,
                    "question": user_query,
                    "status": "completed",
                    "answer": parsed["answer"],
                    "model_turns": model_turns,
                    "tool_calls": tool_calls,
                    "trace": trace,
                }

            observation = grounding_error or (
                "LỖI [UNGROUNDED_FINAL]: Final Answer chưa đủ evidence."
            )
            print(f"👁️ Observation: {observation}")
            trace.append(
                {
                    "step": step,
                    "event": "guardrail",
                    "model_output": response,
                    "observation": observation,
                }
            )
            transcript += f"\n{response}\nObservation: {observation}"
            continue

        if parsed["kind"] == "malformed":
            observation = (
                f"LỖI [{parsed['error_code']}]: {parsed['message']}"
            )
            print(f"👁️ Observation: {observation}")
            trace.append(
                {
                    "step": step,
                    "event": "guardrail",
                    "model_output": response,
                    "observation": observation,
                }
            )
            transcript += f"\n{response}\nObservation: {observation}"
            continue

        tool_name = parsed["tool"]
        arguments = parsed["arguments"]
        fingerprint = _canonical_action(tool_name, arguments)
        action_counts[fingerprint] = action_counts.get(fingerprint, 0) + 1

        if action_counts[fingerprint] > MAX_RETRIES_PER_ACTION:
            return _safe_fallback(
                case_id=case_id,
                question=user_query,
                trace=trace,
                model_turns=model_turns,
                tool_calls=tool_calls,
                reason="REPEATED_ACTION",
            )

        allowed, policy_error, executor_arguments = _validate_action(
            tool_name,
            arguments,
            observed_listing_ids=observed_listing_ids,
            observed_slots=observed_slots,
            confirmation_granted=confirmation_granted,
        )

        if not allowed:
            observation = policy_error or (
                "LỖI [GUARDRAIL]: Action bị từ chối."
            )
        else:
            print(
                f"🛠️ Execute Tool: {tool_name}"
                f"{json.dumps(executor_arguments, ensure_ascii=False)}"
            )
            tool_calls += 1
            observation = execute_tool(tool_name, executor_arguments)

            if not observation.startswith("LỖI"):
                ids = _listing_ids_from_observation(observation)
                observed_listing_ids.update(ids)
                if tool_name == "check_viewing_slots":
                    listing_id = executor_arguments.get("listing_id")
                    slots = _slots_from_observation(observation)
                    observed_slots.setdefault(listing_id, set()).update(slots)

        print(f"👁️ Observation: {observation}")
        trace.append(
            {
                "step": step,
                "event": "tool_or_guardrail",
                "tool": tool_name,
                "arguments": executor_arguments,
                "model_output": response,
                "observation": observation,
            }
        )
        transcript += f"\n{response}\nObservation: {observation}"

    return _safe_fallback(
        case_id=case_id,
        question=user_query,
        trace=trace,
        model_turns=model_turns,
        tool_calls=tool_calls,
        reason="MAX_ITERATIONS_REACHED",
    )


def run_all_react_tests(test_cases: list[dict], provider) -> list[dict]:
    """Chạy ReAct trên toàn bộ test cases và in summary."""
    results = [
        run_react_agent(
            case["question"],
            provider,
            case_id=case["id"],
        )
        for case in test_cases
    ]

    completed = sum(result["status"] == "completed" for result in results)
    fallbacks = sum(result["status"] == "safe_fallback" for result in results)
    total_tool_calls = sum(result["tool_calls"] for result in results)

    print(f"\n{'=' * 70}")
    print("📊 TỔNG KẾT REACT AGENT — MỐC 3")
    print(f"✅ Test cases đã chạy : {len(results)}")
    print(f"🏁 Completed           : {completed}")
    print(f"🛡️ Safe fallback       : {fallbacks}")
    print(f"🛠️ Tổng Tool calls     : {total_tool_calls}")
    return results


def run_autonomous_demo(goal: str) -> dict:
    """Chạy demo Autonomous Agent Level 4."""
    print("\n--- DEMO: AUTONOMOUS AGENT ---")
    result = demo_autonomous_agent(goal)
    print("\n📊 TỔNG KẾT AUTONOMOUS AGENT — BONUS")
    print(f"🎯 Goal            : {result['goal']}")
    print(f"🏁 Status          : {result['status']}")
    print(f"💬 Final Answer    : {result['answer']}")
    print(f"📋 Plan steps      : {len(result['plan'])}")
    print(f"💾 Memory entries  : {len(result['memory'])}")
    return result


def main() -> None:
    """CLI entry point cho baseline, react, autonomous hoặc all."""
    mode = sys.argv[1].casefold() if len(sys.argv) > 1 else "all"
    if mode not in {"baseline", "react", "autonomous", "bonus", "all"}:
        print(
            "Cách dùng: python src/app.py [baseline|react|autonomous|all] "
            "[test_case_id|autonomous_goal]"
        )
        raise SystemExit(2)

    print("==================================================")
    print("🏫 BÀI LAB 3: CHATBOT VS REACT AGENT")
    print("==================================================")

    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(
        "🔌 LLM Provider đang hoạt động: "
        f"{provider.__class__.__name__} (Model: {model_name})"
    )

    tests = load_test_cases()
    print(f"✅ Đã tải {len(tests)} Test Cases từ config/test_cases.json")

    selected_tests = tests
    autonomous_goal = DEFAULT_AUTONOMOUS_GOAL

    if mode in {"baseline", "react", "all"} and len(sys.argv) > 2:
        requested_case_id = sys.argv[2]
        selected_tests = [
            case
            for case in tests
            if str(case["id"]) == requested_case_id
        ]
        if not selected_tests:
            print(f"Không tìm thấy Test Case #{requested_case_id}.")
            raise SystemExit(2)
        print(f"🎯 Chỉ chạy Test Case #{requested_case_id}")
    elif mode in {"autonomous", "bonus"} and len(sys.argv) > 2:
        autonomous_goal = " ".join(sys.argv[2:]).strip() or DEFAULT_AUTONOMOUS_GOAL

    if mode in {"baseline", "all"}:
        print("\n--- DEMO: CHATBOT BASELINE ---")
        run_all_baseline_tests(selected_tests, provider)

    if mode in {"react", "all"}:
        print("\n--- DEMO: REACT AGENT ---")
        run_all_react_tests(selected_tests, provider)

    if mode in {"autonomous", "bonus"}:
        run_autonomous_demo(autonomous_goal)


if __name__ == "__main__":
    main()
