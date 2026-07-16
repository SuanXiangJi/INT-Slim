from app.services.learning_assessment_service import _validate_questions, build_code_task
from app.api.v1.learning import _practice_language_policy


def test_choice_question_validator_rejects_missing_answer():
    payload = [{"question": "Python 函数的作用是什么？", "options": ["封装逻辑", "跳过输入", "关闭解释器", "删除文件"], "answer": "9", "explanation": "函数用于组织可复用逻辑。"}]
    try:
        _validate_questions(payload, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid answer index must be rejected")


def test_code_task_has_language_specific_starter_and_hidden_cases():
    task = build_code_task("Python3 基础语法", "python", "leetcode")
    assert "class Solution" in task["starter_code"]
    assert len(task["test_cases"]) >= 3


def test_practice_language_policy_fixes_framework_languages():
    assert _practice_language_policy("python3")["allowed_languages"] == ["python"]
    assert _practice_language_policy("pytorch")["allowed_languages"] == ["python"]
    assert _practice_language_policy("java")["allowed_languages"] == ["java"]
    assert _practice_language_policy("cprogramming")["allowed_languages"] == ["c"]
    assert _practice_language_policy("cplusplus")["allowed_languages"] == ["cpp"]


def test_practice_language_policy_keeps_algorithms_flexible():
    policy = _practice_language_policy("data-structures")
    assert policy["policy"] == "flexible"
    assert policy["allowed_languages"] == ["python", "c", "cpp", "java"]
