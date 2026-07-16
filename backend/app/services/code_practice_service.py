"""Single-file code practice runner used by the Code Execution Agent.

This is intentionally narrower than a general terminal: it accepts only one source
file, rejects process/filesystem/network primitives, compiles in a per-submission
directory and runs only the generated test cases with short time limits.
"""
from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable

from app.services.sandbox_service import SANDBOX_ROOT
from app.services.sandbox_runtime import sandbox_runtime

_LANGUAGES = {"python", "c", "cpp", "java"}
_FORBIDDEN = re.compile(
    r"(?:\b(?:system\s*\(|popen\s*\(|fork\s*\(|exec(?:ve|vp|v)?\s*\(|CreateProcess\s*\(|Runtime\.getRuntime|ProcessBuilder|"
    r"subprocess|os\.system|socket|requests|urllib|open\s*\(|fopen|freopen|ofstream|ifstream)\b)", re.I
)
_JAVA_CLASS = re.compile(r"\bclass\s+Solution\b")
_WSL_DISTRO: str | None = None
_WSL_CHECKED = False


def _wsl_distro() -> str | None:
    """Use Ubuntu's compiler when the local MSYS linker is unavailable."""
    global _WSL_CHECKED, _WSL_DISTRO
    if _WSL_CHECKED:
        return _WSL_DISTRO
    _WSL_CHECKED = True
    try:
        listed = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, shell=False)
        names = [name.replace("\x00", "").strip() for name in listed.stdout.splitlines()]
        _WSL_DISTRO = next((name for name in names if name.lower().startswith("ubuntu")), None)
    except Exception:
        _WSL_DISTRO = None
    return _WSL_DISTRO


def _wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    return f"/mnt/{drive}/" + resolved.as_posix().split(":/", 1)[1]


def _wsl_command(workdir: Path, command: str) -> list[str]:
    distro = _wsl_distro()
    if not distro:
        raise ValueError("C/C++ 运行环境未就绪")
    return ["wsl.exe", "-d", distro, "--", "bash", "-lc", f"cd {shlex.quote(_wsl_path(workdir))} && {command}"]


def available_runtimes() -> dict[str, bool]:
    distro = _wsl_distro()
    gcc = sandbox_runtime("gcc")
    gxx = sandbox_runtime("g++")
    return {
        "python": bool(sandbox_runtime("python", "backend-python")),
        "c": bool(gcc or distro),
        "cpp": bool(gxx or distro),
        "java": bool(sandbox_runtime("javac", "javac") and sandbox_runtime("java", "java")),
    }


def _validate(code: str, language: str) -> str | None:
    if language not in _LANGUAGES:
        return "不支持该语言。"
    if not (code or '').strip() or len(code) > 24000 or code.count("\n") > 600:
        return "代码为空或超过单文件练习限制。"
    if _FORBIDDEN.search(code):
        return "练习代码不能访问文件、网络、系统命令或创建子进程。"
    return None


def _command_for_acm(workdir: Path, language: str, code: str) -> tuple[list[str], list[str]]:
    if language == "python":
        path = workdir / "main.py"; path.write_text(code, encoding="utf-8")
        return [sandbox_runtime("python", "backend-python"), str(path.name)], []
    if language == "c":
        source = workdir / "main.c"; source.write_text(code, encoding="utf-8")
        compiler = sandbox_runtime("gcc")
        if compiler:
            return [str(workdir / "main.exe")], [compiler, "main.c", "-O2", "-std=c11", "-o", "main.exe"]
        return _wsl_command(workdir, "./main"), _wsl_command(workdir, "gcc main.c -O2 -std=c11 -o main")
    if language == "cpp":
        source = workdir / "main.cpp"; source.write_text(code, encoding="utf-8")
        compiler = sandbox_runtime("g++")
        if compiler:
            return [str(workdir / "main.exe")], [compiler, "main.cpp", "-O2", "-std=c++17", "-o", "main.exe"]
        return _wsl_command(workdir, "./main"), _wsl_command(workdir, "g++ main.cpp -O2 -std=c++17 -o main")
    source = workdir / "Main.java"; source.write_text(code, encoding="utf-8")
    if "public class Main" not in code:
        raise ValueError("Java ACM 模式需要 `public class Main`。")
    return [sandbox_runtime("java", "java"), "-cp", ".", "Main"], [sandbox_runtime("javac", "javac"), source.name]


def _command_for_leetcode(workdir: Path, language: str, code: str) -> tuple[list[str], list[str]]:
    if language == "python":
        source = code + "\n\nimport sys\nfor line in sys.stdin:\n    a, b = map(int, line.split())\n    print(Solution().solve(a, b))\n"
        path = workdir / "main.py"; path.write_text(source, encoding="utf-8")
        return [sandbox_runtime("python", "backend-python"), path.name], []
    if language == "c":
        source = "#include <stdio.h>\n" + code + "\nint main(void){long long a,b; while(scanf(\"%lld %lld\",&a,&b)==2) printf(\"%lld\\n\",solve(a,b)); return 0;}\n"
        path = workdir / "main.c"; path.write_text(source, encoding="utf-8")
        compiler = sandbox_runtime("gcc")
        if compiler:
            return [str(workdir / "main.exe")], [compiler, "main.c", "-O2", "-std=c11", "-o", "main.exe"]
        return _wsl_command(workdir, "./main"), _wsl_command(workdir, "gcc main.c -O2 -std=c11 -o main")
    if language == "cpp":
        source = "#include <iostream>\nusing namespace std;\n" + code + "\nint main(){long long a,b; Solution s; while(cin>>a>>b) cout<<s.solve(a,b)<<'\\n';}\n"
        path = workdir / "main.cpp"; path.write_text(source, encoding="utf-8")
        compiler = sandbox_runtime("g++")
        if compiler:
            return [str(workdir / "main.exe")], [compiler, "main.cpp", "-O2", "-std=c++17", "-o", "main.exe"]
        return _wsl_command(workdir, "./main"), _wsl_command(workdir, "g++ main.cpp -O2 -std=c++17 -o main")
    if not _JAVA_CLASS.search(code):
        raise ValueError("Java 核心代码模式需要 `class Solution`。")
    source = "import java.util.*;\n" + code + "\npublic class Main { public static void main(String[] a) { Scanner s=new Scanner(System.in); Solution x=new Solution(); while(s.hasNextLong()) System.out.println(x.solve(s.nextLong(),s.nextLong())); }}\n"
    path = workdir / "Main.java"; path.write_text(source, encoding="utf-8")
    return [sandbox_runtime("java", "java"), "-cp", ".", "Main"], [sandbox_runtime("javac", "javac"), path.name]


def run_practice_code(
    *, user_id: bytes, assessment_id: str, language: str, mode: str,
    code: str, test_cases: list[dict[str, str]],
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Compile and run learner code. The original source is never mutated."""
    trace: list[dict[str, Any]] = []

    def emit(stage: str, status: str, detail: str) -> None:
        event = {"stage": stage, "status": status, "detail": detail}
        trace.append(event)
        if progress:
            progress(event)

    language = (language or "").lower()
    emit("代码检查", "running", "正在检查语言、代码长度和安全限制。")
    error = _validate(code, language)
    if error:
        emit("代码检查", "failed", error)
        return {"verdict": "rejected", "score": 0, "passed": False, "feedback": error, "cases": [], "trace": trace}
    emit("代码检查", "passed", "代码符合单文件实训规则。")
    if not available_runtimes().get(language):
        detail = f"服务器尚未配置 {language} 运行环境。"
        emit("运行环境", "failed", detail)
        return {"verdict": "runtime_unavailable", "score": 0, "passed": False, "feedback": detail, "cases": [], "trace": trace}
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", assessment_id)[:40]
    workdir = SANDBOX_ROOT / "users" / user_id.hex() / "practice" / safe_id
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        if mode == "acm":
            command, compile_command = _command_for_acm(workdir, language, code)
        else:
            command, compile_command = _command_for_leetcode(workdir, language, code)
        if compile_command:
            emit("编译代码", "running", f"正在编译 {language.upper()} 单文件代码。")
            compiled = subprocess.run(compile_command, cwd=workdir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12, shell=False)
            if compiled.returncode != 0:
                detail = (compiled.stderr or compiled.stdout or "编译失败")[:3000]
                emit("编译代码", "failed", "编译失败，请根据编译信息修改代码。")
                return {"verdict": "compile_error", "score": 0, "passed": False, "feedback": detail, "cases": [], "trace": trace}
            emit("编译代码", "passed", "编译成功。")
        else:
            emit("加载代码", "passed", "解释器已成功加载代码。")
        results = []
        for index, case in enumerate(test_cases):
            emit("运行测试", "running", f"正在执行第 {index + 1}/{len(test_cases)} 组测试。")
            run = subprocess.run(command, cwd=workdir, input=case["input"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3, shell=False)
            actual = (run.stdout or "").strip()
            expected = str(case["expected"]).strip()
            ok = run.returncode == 0 and actual == expected
            case_result = {"index": index + 1, "passed": ok, "expected": expected, "actual": actual[:500], "stderr": (run.stderr or "")[:500], "exit_code": run.returncode}
            results.append(case_result)
            if run.returncode != 0:
                detail = (run.stderr or f"程序异常退出，退出码 {run.returncode}")[:1200]
                emit("运行测试", "failed", f"第 {index + 1} 组测试运行错误。")
                return {"verdict": "runtime_error", "score": 0, "passed": False, "feedback": detail, "cases": results, "trace": trace}
            emit("运行测试", "passed" if ok else "failed", f"第 {index + 1} 组测试{'通过' if ok else '输出不符合预期'}。")
        passed_count = sum(item["passed"] for item in results)
        score = round(passed_count * 100 / len(results), 1) if results else 0
        passed = passed_count == len(results)
        feedback = "全部测试通过。" if passed else f"通过 {passed_count}/{len(results)} 个测试。请根据失败用例检查边界与输入输出。"
        if not passed and mode == "leetcode" and re.search(r"\b(?:print\s*\(|printf\s*\(|cout\s*<<|System\.out\.print)", code):
            feedback = "核心代码模式需要通过 return 返回结果，不要自行打印；评测器会调用 solve 并输出返回值。"
        emit("生成评分", "passed" if passed else "failed", f"评测完成：{score} 分。")
        return {"verdict": "accepted" if passed else "wrong_answer", "score": score, "passed": passed, "feedback": feedback, "cases": results, "trace": trace}
    except subprocess.TimeoutExpired:
        detail = "代码运行超时，请检查是否存在死循环或过高复杂度。"
        emit("运行测试", "failed", detail)
        return {"verdict": "time_limit", "score": 0, "passed": False, "feedback": detail, "cases": [], "trace": trace}
    except ValueError as exc:
        emit("准备评测", "failed", str(exc))
        return {"verdict": "invalid_submission", "score": 0, "passed": False, "feedback": str(exc), "cases": [], "trace": trace}
    except Exception:
        detail = "评测环境暂时无法完成本次运行，请保留代码后重试。"
        emit("评测环境", "failed", detail)
        return {"verdict": "runner_error", "score": 0, "passed": False, "feedback": detail, "cases": [], "trace": trace}
