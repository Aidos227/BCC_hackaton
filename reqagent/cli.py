"""Точка входа: python -m reqagent <документ> <отчёт.md>"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .ingest import load
from .llm import LLM, LLMError, load_dotenv
from .pipeline import run, run_baseline
from .report import delta_md, render

ROOT = Path(__file__).resolve().parent.parent


def _git_head() -> str:
    """Хеш коммита без вызова git (git может быть не установлен на машине защиты)."""
    g = ROOT / ".git"
    try:
        head = (g / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            p = g / ref
            if p.exists():
                return p.read_text(encoding="utf-8").strip()[:7]
            packed = g / "packed-refs"
            if packed.exists():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        return line.split()[0][:7]
            return ""
        return head[:7]
    except OSError:
        return ""


def agent_version() -> str:
    sha, dirty = "", ""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", "reqagent"],
                               cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        pass
    sha = sha or _git_head()
    if sha:
        return f"{__version__} (коммит {sha}{', код агента изменён после коммита' if dirty else ''})"
    return f"{__version__} (вне git)"


def _jsonable(o):
    if hasattr(o, "__dataclass_fields__"):
        return o.__dict__
    return str(o)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="reqagent", description="Агент статической проверки требований")
    ap.add_argument("input", help="путь к документу требований (.pdf, .md, .txt, .docx)")
    ap.add_argument("output", help="путь к файлу отчёта (.md)")
    ap.add_argument("--provider", choices=["gemini", "anthropic", "openai"], help="провайдер LLM (по умолчанию — по ключу в .env)")
    ap.add_argument("--model", help="имя модели (по умолчанию — из .env или встроенное)")
    ap.add_argument("--no-model", action="store_true", help="не строить исполняемую модель требований")
    ap.add_argument("--baseline", action="store_true", help="сравнительный режим: один запрос, без этапов агента (JSON)")
    ap.add_argument("--compare", help="JSON прошлого прогона (<отчёт>.json): показать закрытые и новые замечания")
    ap.add_argument("--cache", help="папка кэша ответов модели (для отладки; в финальном прогоне не использовать)")
    ap.add_argument("--env", default=str(ROOT / ".env"), help="путь к .env")
    a = ap.parse_args(argv)

    load_dotenv(a.env)
    load_dotenv(".env")
    t0 = time.time()
    try:
        doc = load(a.input)
        llm = LLM(a.provider, a.model, cache_dir=a.cache)
    except (FileNotFoundError, ValueError, LLMError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 2
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Документ: {doc.path.name} ({doc.kind}, страниц: {doc.pages}, строк: {len(doc.lines)})", file=sys.stderr)
    print(f"Модель: {llm.provider}/{llm.model}", file=sys.stderr)

    try:
        if a.baseline:
            res = run_baseline(llm, doc)
            res["_meta"] = {"model": ", ".join(llm.models_used) or llm.resolved_model, "usage": llm.usage.__dict__}
            out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=_jsonable), encoding="utf-8")
            print(f"Baseline записан: {out}", file=sys.stderr)
            return 0
        res = run(llm, doc, use_model=not a.no_model)
    except LLMError as e:
        print(f"Ошибка модели: {e}", file=sys.stderr)
        return 3

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5)))
    passport = {
        "Документ": doc.title,
        "Файл": f"{doc.path.name} ({doc.kind.upper()}, страниц: {doc.pages}, SHA-256: "
                f"{hashlib.sha256(doc.path.read_bytes()).hexdigest()[:16]}…)",
        "Дата прогона": now.strftime("%d.%m.%Y %H:%M (UTC+5, Алматы)"),
        "Модель": f"{llm.provider} / {', '.join(llm.models_used) or llm.resolved_model}, temperature={llm.temperature}",
        "Версия агента": agent_version(),
        "Этапы": "нарезка → проверка требований → проверка набора → исполняемая модель → правила → "
                  "привязка цитат → скептическая перепроверка → чек-лист",
        "Обращений к модели": f"{llm.usage.calls} (токены: вход {llm.usage.input_tokens}, выход {llm.usage.output_tokens})",
        "Длительность": f"{time.time() - t0:.0f} с",
    }
    delta = ""
    if a.compare:
        prev = json.loads(Path(a.compare).read_text(encoding="utf-8"))
        delta = delta_md(prev, res["confirmed"], Path(a.compare).name, doc)
    out.write_text(render(doc, res, passport, llm.usage.log, delta), encoding="utf-8")
    stem = out.with_suffix("")
    m = res.get("model") or {}
    if m.get("code"):
        Path(str(stem) + ".model.py").write_text(model_file(m), encoding="utf-8")
    Path(str(stem) + ".json").write_text(json.dumps({"passport": passport, **{k: v for k, v in res.items()}},
                                                    ensure_ascii=False, indent=1, default=_jsonable), encoding="utf-8")
    c = [f for f in res["confirmed"] if f["severity"] == "critical"]
    print(f"\nГотово. Отчёт: {out}", file=sys.stderr)
    print(f"Требований: {len(res['requirements'])}; нарушений: {len(res['confirmed'])} "
          f"(критичных {len(c)}); вопросов владельцу: {len(res['questions'])}", file=sys.stderr)
    return 0


def model_file(m) -> str:
    """Самодостаточный файл модели: можно запустить `python report.model.py` и увидеть прогон."""
    sc = json.dumps(m.get("scenarios") or [], ensure_ascii=False, indent=1)
    it = json.dumps(m.get("interpretations") or [], ensure_ascii=False, indent=1)
    return f'''# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
{m["code"]}
# ---- конец кода модели ----

SCENARIOS = json.loads(r"""{sc}""")
INTERPRETATIONS = json.loads(r"""{it}""")

if __name__ == "__main__":
    ids = [i["id"] for i in INTERPRETATIONS][:4]
    combos = [dict(zip(ids, v)) for v in itertools.product("ab", repeat=len(ids))] or [{{}}]
    for s in SCENARIOS:
        print(f"\\n{{s['id']}} [{{s.get('source')}}] {{s.get('title')}}")
        if s.get("expected"):
            print("  ожидается по документу:", s["expected"])
        for c in combos:
            try:
                r = run(s.get("input") or {{}}, dict(c))
                print(" ", c or "", "→", r)
            except Undefined as u:
                print(" ", c or "", "→ НЕ ОПРЕДЕЛЕНО:", u.question)
'''


if __name__ == "__main__":
    sys.exit(main())
