"""Цикл уточнения: вопросы владельцу → ответы → учёт ответов.

1. После прогона рядом с отчётом пишется <отчёт>.questions.json — бланк ответов.
2. Владелец заполняет поле "answer" (буква варианта или свой текст) — вручную или через `--ask` в консоли.
3. Ответы применяются двумя способами:
   - сразу: замечания, на которые ответил владелец, переносятся в раздел «Решения владельца» и больше
     не блокируют вердикт (сопоставление — по цитатам, кодом);
   - при повторном прогоне с `--answers`: ответы передаются всем этапам как уточнения к документу,
     чтобы агент перепроверил документ с учётом решений.
Ответ привязан к цитатам: если процитированный текст исчез из документа, ответ помечается как устаревший.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .ingest import Document, normalize


def questions_file(doc: Document, res: Dict, agent_version: str) -> Dict:
    qs = []
    for q in res.get("clarifications") or []:
        qs.append({"id": q["qid"], "question": q["question"], "why": q.get("why", ""),
                   "finding_ids": q["finding_ids"],
                   "findings": [{"fid": f.get("fid"), "title": f.get("title"), "criterion": f.get("criterion"),
                                 "quotes": [a["text"] for a in f.get("anchored") or []]}
                                for f in res["confirmed"] + res["questions"] if f.get("fid") in q["finding_ids"]],
                   "quotes": [a["text"] for a in q["anchored"]],
                   "options": q.get("options") or [], "check_after": q.get("check_after", ""),
                   "answer": None})
    return {"document": doc.path.name, "sha256": hashlib.sha256(doc.path.read_bytes()).hexdigest(),
            "agent_version": agent_version,
            "how_to_answer": "Впишите в поле answer букву варианта (a, b, c) или свой ответ текстом. "
                             "Пустые ответы считаются отложенными.",
            "questions": qs}


def load(path: str | Path) -> Dict:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ValueError("файл ответов должен содержать список questions")
    return data


def answer_text(q: Dict) -> Optional[str]:
    a = q.get("answer")
    if a is None or not str(a).strip():
        return None
    a = str(a).strip()
    for o in q.get("options") or []:
        if a.lower() == str(o.get("key", "")).lower():
            return f"{o['key']}) {o['text']}"
    return a


def owner_block(answers: Dict) -> str:
    """Текст для моделей при повторном прогоне: решения владельца как уточнения к документу."""
    lines = []
    for q in answers.get("questions", []):
        t = answer_text(q)
        if t:
            lines.append(f"- Вопрос: {q['question']}\n  Решение владельца: {t}")
    if not lines:
        return ""
    return ("=== Решения владельца продукта (НЕ часть документа; учитывай их как уточнения: замечание, "
            "которое снято решением, не повторяй, но проверь, не создаёт ли решение новых противоречий) ===\n"
            + "\n".join(lines))


def apply(res: Dict, answers: Dict, doc: Document) -> Dict:
    """Переносит замечания, закрытые ответами, в res['resolved']. Возвращает сводку применения."""
    applied, stale, pending = [], [], []
    resolved = res.setdefault("resolved", [])
    for q in answers.get("questions", []):
        t = answer_text(q)
        if not t:
            pending.append(q.get("id"))
            continue
        quotes = [normalize(x) for x in q.get("quotes") or [] if x]
        if quotes and not any(doc.locate(x).found for x in q.get("quotes") or []):
            stale.append(q.get("id"))          # текст, к которому относился ответ, в документе изменился
            continue
        from .report import _match
        linked = [{"criterion": x.get("criterion"),
                   "anchored": [{"text": t, "anchor": {"found": True}} for t in x.get("quotes") or []]}
                  for x in q.get("findings") or []]
        hit = []
        for f in list(res["confirmed"]) + list(res["questions"]):
            if res.get("_same_run"):
                ok = f.get("fid") in (q.get("finding_ids") or [])
            else:
                ok = any(_match(f, old) for old in linked)
            if ok:
                hit.append(f)
        for f in hit:
            for lst in (res["confirmed"], res["questions"]):
                if f in lst:
                    lst.remove(f)
            f["owner_decision"] = t
            f["owner_qid"] = q.get("id")
            f["owner_question_text"] = q.get("question")
            resolved.append(f)
        applied.append({"id": q.get("id"), "question": q.get("question"), "answer": t,
                        "closed": [f.get("fid") for f in hit], "check_after": q.get("check_after", "")})
    summary = {"applied": applied, "stale": stale, "pending": pending}
    res["owner_answers"] = summary
    return summary


def ask(questions: Dict) -> Dict:
    """Интерактивный опрос в консоли (режим --ask)."""
    qs = questions.get("questions", [])
    if not qs:
        print("Уточняющих вопросов нет.", file=sys.stderr)
        return questions
    print(f"\nАгент задаёт {len(qs)} уточняющих вопросов. Введите букву варианта, свой ответ или Enter, "
          "чтобы отложить.\n", file=sys.stderr)
    for q in qs:
        print(f"[{q['id']}] {q['question']}", file=sys.stderr)
        if q.get("why"):
            print(f"    зачем: {q['why']}", file=sys.stderr)
        for o in q.get("options") or []:
            print(f"    {o['key']}) {o['text']}", file=sys.stderr)
        try:
            a = input("    ваш ответ > ").strip()
        except EOFError:
            a = ""
        q["answer"] = a or None
        print("", file=sys.stderr)
    return questions
