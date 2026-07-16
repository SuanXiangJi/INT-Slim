"""Question-set generation and validation for the chapter learning flow.

The generator asks the existing LLM service for strict JSON but always validates the
result before it reaches the database. A deterministic fallback keeps the learning
flow usable when an upstream model is unavailable.
"""
from __future__ import annotations

import json
import re
from typing import Any


def _extract_json(text: str) -> Any:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    start, end = raw.find("["), raw.rfind("]")
    if start >= 0 and end > start:
        return json.loads(raw[start:end + 1])
    return json.loads(raw)


def _clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*_>#]", "", value or "")).strip()


def _source_lines(content: str) -> list[str]:
    lines = [_clean_line(line) for line in (content or "").splitlines()]
    lines = [line for line in lines if 18 <= len(line) <= 180 and not line.startswith(("http://", "https://"))]
    return lines[:80]


def _fallback_questions(title: str, content: str, count: int) -> list[dict[str, Any]]:
    """Conservative fallback: it only claims facts visible in chapter text."""
    lines = _source_lines(content) or [f"本节《{title}》的核心概念与使用场景。"]
    questions: list[dict[str, Any]] = []
    for index in range(count):
        evidence = lines[index % len(lines)]
        fragment = evidence[:72].rstrip("，。；;：:")
        correct = f"应回到本节材料核对：{fragment}"
        questions.append({
            "question": f"关于《{title}》，以下哪项最符合本节材料中的表述？",
            "options": [correct, "只需记住结论，不必理解适用条件", "遇到任何场景都可以直接套用", "与本节主题无关"],
            "answer": "0",
            "explanation": f"依据本节材料：{evidence}",
            "evidence": evidence,
        })
    return questions


def _validate_questions(payload: Any, count: int) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or len(payload) != count:
        raise ValueError("题目数量不符合要求")
    validated = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("题目格式无效")
        question = _clean_line(str(item.get("question", "")))
        options = [_clean_line(str(option)) for option in (item.get("options") or [])]
        answer = str(item.get("answer", ""))
        explanation = _clean_line(str(item.get("explanation", "")))
        if len(question) < 8 or len(options) != 4 or any(len(option) < 1 for option in options):
            raise ValueError("选择题内容不完整")
        if answer not in {"0", "1", "2", "3"} or len(explanation) < 8:
            raise ValueError("答案或解析无效")
        validated.append({"question": question, "options": options, "answer": answer, "explanation": explanation})
    return validated


def generate_choice_questions(title: str, content: str, count: int, *, course_title: str = "") -> tuple[list[dict[str, Any]], str]:
    """Return validated questions and the generation mode (agent or fallback)."""
    context = (content or "")[:12000]
    if context:
        try:
            from app.services.llm_service import llm_service
            response = llm_service.call_model([
                {"role": "system", "content": (
                    "你是 Agents 伴学中的出题 Agent。仅根据给出的章节资料生成选择题。"
                    "输出严格 JSON 数组，不要 Markdown。每题含 question、options（恰好 4 个字符串）、"
                    "answer（正确选项的 0-3 字符串）、explanation。不得编造资料中没有的事实，"
                    "错误选项要合理但明确错误。"
                )},
                {"role": "user", "content": (
                    f"课程：{course_title or title}\n章节：{title}\n需要 {count} 道单选题。\n\n章节资料：\n{context}"
                )},
            ], temperature=0.25)
            return _validate_questions(_extract_json(response), count), "agent"
        except Exception:
            # The persisted fallback must be reusable just like an Agent-generated set.
            pass
    return _fallback_questions(title, content, count), "fallback"


def build_code_task(title: str, language: str, mode: str) -> dict[str, Any]:
    """Stable starter task with hidden cases; the evaluator never edits learner code."""
    language = language.lower()
    if language not in {"python", "c", "cpp", "java"}:
        raise ValueError("Unsupported practice language")
    if mode not in {"acm", "leetcode"}:
        raise ValueError("Unsupported practice mode")
    base = {
        "title": f"{title} · 两数求和练习",
        "description": "实现两个整数的求和。重点检查输入输出、函数边界和语言基础语法。",
        "constraints": "输入整数范围为 -10^9 到 10^9。不得读取文件、联网或启动其他进程。",
        "test_cases": [
            {"input": "2 3\n", "expected": "5"},
            {"input": "-4 9\n", "expected": "5"},
            {"input": "100 200\n", "expected": "300"},
        ],
    }
    if mode == "acm":
        base["prompt"] = "从标准输入读取两个整数，向标准输出打印它们的和。请提交完整、可运行的单文件程序。"
        base["starter_code"] = {
            "python": "a, b = map(int, input().split())\n# 在这里输出答案\n",
            "c": "#include <stdio.h>\nint main(void) {\n    long long a, b;\n    if (scanf(\"%lld %lld\", &a, &b) != 2) return 0;\n    // 在这里输出答案\n    return 0;\n}\n",
            "cpp": "#include <iostream>\nusing namespace std;\nint main() {\n    long long a, b;\n    if (!(cin >> a >> b)) return 0;\n    // 在这里输出答案\n    return 0;\n}\n",
            "java": "import java.util.*;\npublic class Main {\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in);\n        long a = scanner.nextLong(), b = scanner.nextLong();\n        // 在这里输出答案\n    }\n}\n",
        }[language]
    else:
        base["prompt"] = "实现 solve(a, b) 并返回两个整数的和。只提交核心函数/类，不要自行读取标准输入。"
        base["starter_code"] = {
            "python": "class Solution:\n    def solve(self, a: int, b: int) -> int:\n        # 在这里实现\n        pass\n",
            "c": "long long solve(long long a, long long b) {\n    // 在这里实现\n    return 0;\n}\n",
            "cpp": "class Solution {\npublic:\n    long long solve(long long a, long long b) {\n        // 在这里实现\n        return 0;\n    }\n};\n",
            "java": "class Solution {\n    long solve(long a, long b) {\n        // 在这里实现\n        return 0;\n    }\n}\n",
        }[language]
    return base
