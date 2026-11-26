"""Независимая проверка: агент против одного сильного запроса к той же модели.

Запуск:  python eval/run_eval.py --reps 2
Результат: eval/RESULTS.md и сырые ответы в eval/runs/<время>/
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
from score import score  # noqa: E402

CASES = [
    ("official", ROOT / "docs" / "requirements.pdf", "выданный документ (PDF)"),
    ("official_paraphrased", ROOT / "eval" / "fixtures" / "official_paraphrased.md", "перефразировка выданного"),
    ("official_fixed", ROOT / "eval" / "fixtures" / "official_fixed.md", "выданный с устранёнными причинами"),
    ("autopay", ROOT / "eval" / "fixtures" / "autopay.md", "незнакомый документ"),
]


def run_one(system: str, doc: Path, out_dir: Path, rep: int, extra):
    stem = out_dir / f"{doc.stem}.{system}.{rep}"
    if system == "agent":
        target = Path(str(stem) + ".md")
        cmd = [sys.executable, "-m", "lsj", str(doc), str(target)] + extra
        produced = Path(str(stem) + ".json")
    else:
        produced = Path(str(stem) + ".json")
        cmd = [sys.executable, "-m", "lsj", str(doc), str(produced), "--baseline"] + extra
    if produced.exists():
        return produced
    print(f"\n>>> {system} #{rep}: {doc.name}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0 or not produced.exists():
        print(f"!!! прогон не удался (код {r.returncode}): {system} #{rep} {doc.name}", flush=True)
        return None
    return produced


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--out", help="папка прогонов (по умолчанию новая)")
    ap.add_argument("--only", nargs="*", help="подмножество кейсов")
    ap.add_argument("--provider")
    ap.add_argument("--model")
    a = ap.parse_args()
    extra = (["--provider", a.provider] if a.provider else []) + (["--model", a.model] if a.model else [])
    out_dir = (ROOT / a.out).resolve() if a.out else ROOT / "eval" / "runs" / dt.datetime.now().strftime("%Y%m%d-%H%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    table = {}
    models = set()
    failed = []
    for name, doc, label in CASES:
        if a.only and name not in a.only:
            continue
        key = json.loads((ROOT / "eval" / "keys" / f"{name}.key.json").read_text(encoding="utf-8"))
        for system in ("agent", "baseline"):
            for rep in range(1, a.reps + 1):
                p = run_one(system, doc, out_dir, rep, extra)
                if p is None:
                    failed.append(f"{name}/{system}#{rep}")
                    continue
                res = json.loads(p.read_text(encoding="utf-8"))
                models.add((res.get("passport") or {}).get("Модель") or (res.get("_meta") or {}).get("model"))
                table.setdefault((name, label), {}).setdefault(system, []).append(score(res, key))
    write_results(table, out_dir, models, a.reps, failed)


def pct(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def write_results(table, out_dir, models, reps, failed=()):
    L = ["# Результаты независимой проверки\n",
         f"Дата: {dt.datetime.now():%d.%m.%Y %H:%M}. Модель: {', '.join(sorted(m for m in models if m))}. "
         f"Повторов на систему: {reps}. Сырые ответы: `{out_dir.relative_to(ROOT).as_posix()}`.\n",
         "Системы: **агент** — полный конвейер LSJ; **один запрос** — тот же документ и та же модель, "
         "один сильный промпт с критериями ISO 29148 и требованием цитат (`--baseline`).\n",
         "Метрики считает `eval/score.py` без LLM: дефект найден, если у замечания есть подлинная "
         "(найденная в документе) цитата из каждого места дефекта. Разметка дефектов — авторская "
         "(`eval/keys/*.json`), составлена до прогонов; это ограничение метода.\n",
         "| Документ | Система | Полнота по размеченным дефектам | Критичные противоречия распознаны как критичные | "
         "Подлинность цитат | Замечаний (среднее) | Ложные замечания по устранённым причинам |",
         "|---|---|---|---|---|---|---|"]
    detail = []
    for (name, label), systems in table.items():
        for system, runs in systems.items():
            sysname = "агент" if system == "agent" else "один запрос"
            viol = [len(r["absent_violations"]) for r in runs]
            absent_total = runs[0]["absent_total"]
            L.append(f"| {label} | {sysname} | {pct(avg([r['recall'] for r in runs]))} "
                     f"({' / '.join(pct(r['recall']) for r in runs)}) | {pct(avg([r['critical_recall'] for r in runs]))} | "
                     f"{pct(avg([r['quote_validity'] for r in runs]))} | {avg([r['findings'] for r in runs]):.0f} | "
                     + (f"{avg(viol):.1f} из {absent_total}" if absent_total else "—") + " |")
            ids = list(runs[0]["found"].keys())
            detail.append(f"\n**{label} — {sysname}:** " + ", ".join(
                f"{i} {sum(r['found'][i]['hit'] for r in runs)}/{len(runs)}" for i in ids)
                + ("; нарушения «должно исчезнуть»: " + "; ".join(",".join(r["absent_violations"]) or "нет" for r in runs)
                   if absent_total else ""))
    if failed:
        L.append(f"\nНе завершились (не вошли в средние): {', '.join(failed)}.")
    L.append("\nСтабильность: в скобках — полнота каждого повтора. Ниже — сколько раз из N найден каждый дефект.")
    L += detail
    (ROOT / "eval" / "RESULTS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
