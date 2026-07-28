"""
🚀 CORE AGENT APP (Dành cho Role 4: Core Agent Developer)
Mốc 2: Ghép Test Cases + Baseline Prompt + Multi-Provider.


Ở mốc này Baseline chỉ được gọi LLM đúng một lần cho mỗi câu hỏi và tuyệt đối
không gọi Tool. ReAct Agent sẽ được tích hợp ở Mốc 3.
"""


import json
import os
import sys
from dotenv import load_dotenv


# Đảm bảo import các module cùng thư mục src/ hoạt động mượt mà
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# Mốc 2 chỉ import Baseline Prompt và Provider; không import Tool.
from prompts import CHATBOT_BASELINE_PROMPT
from providers import get_llm_provider


load_dotenv()


def load_test_cases() -> list[dict]:
    """Đọc và kiểm tra sơ bộ bộ test cases của Role 1."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")


    # Fallback kiểm tra nếu file ở thư mục hiện tại
    if not os.path.exists(config_path):
        config_path = "test_cases.json"


    with open(config_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)


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
    """
    Chạy Chatbot Baseline bằng đúng một LLM call và không gọi Tool.


    Args:
        user_query: Câu hỏi của người dùng.
        provider: LLM Provider đã được khởi tạo qua ``get_llm_provider``.
        case_id: Mã test case để hiển thị và lưu kết quả.


    Returns:
        Dict kết quả gồm answer, status, llm_calls và tool_calls. Mốc 2 bắt
        buộc ``llm_calls == 1`` và ``tool_calls == 0`` cho mọi test case.
    """
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("user_query phải là chuỗi không rỗng.")


    label = f"Test Case #{case_id}" if case_id is not None else "User Query"
    print(f"\n{'-' * 70}")
    print(f"💬 {label}: {user_query}")


    # Baseline protocol: system prompt + user query -> đúng một provider call.
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
    """
    Chạy Baseline trên toàn bộ test cases và in tổng kết để Role 5 ghi report.
    """
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
    print("ℹ️ Các câu cần dữ liệu căn/slot cho thấy giới hạn của Baseline.")


    return results




def run_react_agent(*_args, **_kwargs):
    """
    Placeholder cho Mốc 3.


    ReAct không được hard-code để giả vờ đã gọi Tool. Role 4 sẽ tích hợp parser,
    executor, Observation feedback và Guardrails sau khi Mốc 2 được nghiệm thu.
    """
    return {
        "status": "not_implemented",
        "message": "ReAct Agent sẽ được triển khai ở Mốc 3.",
    }




if __name__ == "__main__":
    print("==================================================")
    print("🏫 BÀI LAB 3 - MỐC 2: CHATBOT BASELINE")
    print("==================================================")


    # Khởi tạo Multi-Provider LLM Adapter (Đọc từ biến môi trường LLM_PROVIDER)
    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(f"🔌 LLM Provider đang hoạt động: {provider.__class__.__name__} (Model: {model_name})")


    tests = load_test_cases()
    print(f"✅ Đã tải {len(tests)} Test Cases từ config/test_cases.json")
    print("\n⚙️ Baseline System Prompt:")
    print(CHATBOT_BASELINE_PROMPT.strip())


    baseline_results = run_all_baseline_tests(tests, provider)


    # Checkpoint cứng của Mốc 2.
    assert len(baseline_results) == len(tests)
    assert all(result["llm_calls"] == 1 for result in baseline_results)
    assert all(result["tool_calls"] == 0 for result in baseline_results)



