"""Безопасный прогон исполняемой модели требований.

Код модели пишет LLM, поэтому перед запуском он проходит статическую проверку (AST):
разрешены только безопасные модули стандартной библиотеки, запрещены файлы, сеть, eval/exec,
доступ к «dunder»-атрибутам. Запуск — в отдельном процессе `python -I` с таймаутом.
"""
from __future__ import annotations

import ast
import itertools
import json
import subprocess
import sys
from typing import Any, Dict, List, Tuple

ALLOWED_MODULES = {"datetime", "decimal", "math", "re", "collections", "itertools", "functools",
                   "dataclasses", "typing", "enum", "fractions", "calendar", "copy"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars",
                   "input", "breakpoint", "help", "memoryview", "getattr", "setattr", "delattr",
                   "exit", "quit"}


class UnsafeCode(ValueError):
    pass


def sanitize(code: str) -> str:
    """Убирает собственное определение Undefined, если модель его всё-таки написала."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    lines = code.splitlines()
    drop = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Undefined":
            drop.update(range(node.lineno - 1 - len(node.decorator_list), node.end_lineno))
    return "\n".join(l for i, l in enumerate(lines) if i not in drop) if drop else code


def check_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise UnsafeCode(f"Синтаксическая ошибка: {e}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_MODULES:
                    raise UnsafeCode(f"Запрещённый импорт: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_MODULES:
                raise UnsafeCode(f"Запрещённый импорт: {node.module}")
        elif isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id.startswith("__")):
            raise UnsafeCode(f"Запрещённое имя: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeCode(f"Запрещённый атрибут: {node.attr}")
        elif isinstance(node, ast.ClassDef) and node.name == "Undefined":
            raise UnsafeCode("Класс Undefined переопределять нельзя")


HARNESS = r'''
import json, sys, traceback
class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question = str(question)
        self.req_ids = list(req_ids or [])
_job = json.loads(sys.stdin.buffer.read().decode("utf-8"))
_ns = {"Undefined": Undefined, "__name__": "reqmodel"}
exec(compile(_job["code"], "reqmodel.py", "exec"), _ns)
_out = []
for _sc in _job["scenarios"]:
    for _key, _interp in _job["combos"]:
        _rec = {"scenario": _sc["id"], "combo": _key}
        try:
            _r = _ns["run"](_sc.get("input") or {}, dict(_interp))
            _rec["status"] = "ok"
            _rec["result"] = json.loads(json.dumps(_r, default=str, ensure_ascii=False))
        except Undefined as _u:
            _rec["status"] = "undefined"
            _rec["question"] = _u.question
            _rec["req_ids"] = _u.req_ids
        except Exception as _e:
            _rec["status"] = "error"
            _rec["error"] = f"{type(_e).__name__}: {_e}"
        _out.append(_rec)
print(json.dumps(_out, ensure_ascii=True))
'''


def combos(interpretations: List[Dict[str, Any]], cap: int = 16) -> List[Tuple[str, Dict[str, str]]]:
    ids = [i["id"] for i in interpretations][:4]          # не больше 16 комбинаций
    if not ids:
        return [("—", {})]
    out = []
    for vals in itertools.product("ab", repeat=len(ids)):
        d = dict(zip(ids, vals))
        out.append((",".join(f"{k}={v}" for k, v in d.items()), d))
    return out[:cap]


def run_model(code: str, scenarios: List[Dict[str, Any]], interpretations: List[Dict[str, Any]],
              timeout: int = 30) -> List[Dict[str, Any]]:
    code = sanitize(code)
    check_code(code)
    job = {"code": code, "scenarios": scenarios, "combos": combos(interpretations)}
    try:
        proc = subprocess.run([sys.executable, "-I", "-c", HARNESS],
                              input=json.dumps(job, ensure_ascii=False).encode("utf-8"),
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Модель не уложилась в {timeout} с (возможен бесконечный цикл)")
    stdout = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0 or not stdout.strip():
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-6:]
        raise RuntimeError("Модель не загрузилась: " + " | ".join(tail))
    return json.loads(stdout.strip().splitlines()[-1])


def clean(d: Any) -> Any:
    """Результат без служебного _trace — для сравнения."""
    if isinstance(d, dict):
        return {k: v for k, v in d.items() if not str(k).startswith("_")}
    return d


def _kind(v: Any) -> str:
    n = _norm(v)
    if v is None:
        return "none"
    if isinstance(n, bool):
        return "bool"
    if isinstance(n, (int, float)):
        return "num"
    return type(n).__name__


def comparable(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    """Сравнивать можно, только если модель вычисляет те же величины того же вида
    (число с числом, строку со строкой); фраза «счётчик вырос на 4 000» с числом 4000 не сравнивается."""
    if not expected or not all(k in (actual or {}) for k in expected):
        return False
    return all(_kind(expected[k]) == _kind(actual[k]) or expected[k] is None for k in expected)


def same(expected: Dict[str, Any], actual: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Сравнение ожидаемого результата документа с вычисленным: только по ключам expected."""
    diffs = []
    for k, ev in (expected or {}).items():
        if k not in (actual or {}) or ev is None:
            continue   # модель не вычисляет эту величину или критерий её не задаёт — сравнивать не с чем
        av = actual[k]
        if _norm(ev) != _norm(av):
            diffs.append(f"{k}: ожидается {ev!r}, по правилам {av!r}")
    return (not diffs), diffs


def _norm(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    if isinstance(v, str):
        s = v.strip().lower().replace(" ", "").replace(" ", "")
        try:
            return round(float(s.replace(",", ".")), 6)
        except ValueError:
            return {"true": True, "false": False, "да": True, "нет": False}.get(s, s)
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    return v
