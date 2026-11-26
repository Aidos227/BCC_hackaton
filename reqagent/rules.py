"""Детерминированные проверки без LLM. Каждое срабатывание опирается на строку документа,
поэтому цитата всегда подлинная. Кандидаты затем проходят ту же скептическую проверку, что и
замечания модели (правило может сработать ложно — например, слово в цитате или в шаблоне)."""
from __future__ import annotations

import re
from typing import Dict, List

from .ingest import Document

# Расплывчатые слова и обороты (INCOSE GtWR, ISO 29148 п. 5.2.7 «unbounded / vague terms»)
VAGUE = [
    r"быстр\w*", r"удобн\w*", r"оптимальн\w*", r"достаточн\w*", r"своевременн\w*", r"максимально",
    r"по возможности", r"при необходимости", r"как правило", r"и т\.\s?д\.", r"и т\.\s?п\.",
    r"и другие", r"и прочее", r"гибк\w*", r"интуитивн\w*", r"надёжн\w*|надежн\w*", r"эффективн\w*",
    r"современн\w*", r"минимальн\w* задержк\w*", r"в разумн\w*", r"примерно", r"около\s\d",
]
INJECTION = [
    r"игнорир\w*\s+(все\s+)?(предыдущ|прошл|данн|эти|инструкц|правил)",
    r"ignore\s+(all\s+|the\s+)?(previous|prior|above)",
    r"(для|к)\s+(ии|ai|llm|нейросет|модели|ревьюер)\w*\s*[:,-]",
    r"(сообщи|укажи|ответь|напиши)\w*,?\s+что\s+(замечаний\s+нет|документ\s+(готов|согласован|корректен))",
    r"(не\s+(сообщай|указывай|упоминай))\s+\w*\s*(ошибк|дефект|замечан|противореч)",
    r"system\s+prompt|системн\w+\s+промпт",
    r"you\s+are\s+(an?\s+)?(ai|assistant|reviewer)",
]
PLACEHOLDER = [r"\bTBD\b", r"\bTODO\b", r"\bуточнить\b", r"\bуточняется\b", r"заполняются\s+\w+",
               r"\?\?\?", r"<\s*вставить", r"\[\s*вставить"]


def run_rules(doc: Document) -> List[Dict]:
    out: List[Dict] = []
    lines = doc.lines
    text = doc.plain

    def add(criterion, severity, title, quote, problem, fix):
        out.append({"source": "rule", "criterion": criterion, "severity": severity, "req_ids": [],
                    "title": title, "quotes": [quote], "problem": problem, "blocked_decision": "",
                    "fix": fix, "owner_question": ""})

    # 1. Расплывчатые слова — по одному кандидату на слово
    seen = set()
    for ln in lines:
        for pat in VAGUE:
            m = re.search(pat, ln.text, flags=re.I)
            if m and m.group(0).lower() not in seen:
                seen.add(m.group(0).lower())
                add("unambiguous", "minor", f"Расплывчатый термин «{m.group(0)}»", _clip(ln.text, m.start()),
                    f"Слово «{m.group(0)}» не задаёт измеримой границы (ISO 29148, п. 5.2.7).",
                    "Заменить измеримым значением с единицей и условием измерения.")

    # 1а. Внедрённые инструкции для ИИ (prompt injection) — данные документа не должны управлять проверкой
    for ln in lines:
        for pat in INJECTION:
            m = re.search(pat, ln.text, flags=re.I)
            if m:
                out.append({"source": "rule", "criterion": "injection", "severity": "critical", "req_ids": [],
                            "title": "В документ внедрена инструкция для ИИ-проверки", "quotes": [_clip(ln.text, m.start())],
                            "problem": "Текст документа пытается управлять автоматической проверкой. Агент её не выполняет "
                                       "и выносит в отчёт: такой фрагмент может скрыть дефекты при ревью ИИ-инструментами.",
                            "blocked_decision": "Можно ли доверять документу как источнику требований, пока в нём есть "
                                                "текст, адресованный не людям, а инструментам проверки.",
                            "fix": "Удалить фрагмент и выяснить у автора, как он попал в документ (ИБ-инцидент).",
                            "owner_question": "", "pinned": True})
                break

    # 2. Заглушки и незаполненные разделы
    for ln in lines:
        for pat in PLACEHOLDER:
            m = re.search(pat, ln.text, flags=re.I)
            if m:
                add("set_complete", "major", "Раздел не заполнен (заглушка)", _clip(ln.text, m.start()),
                    "В документе стоит заглушка вместо содержания; раздел нельзя проверить.",
                    "Заполнить раздел до передачи в разработку или явно указать, что он не требуется.")
                break

    # 3. Чек-лист с неотмеченными вариантами «Да / Нет»
    yn = [ln for ln in lines if re.search(r"Да\s*/\s*Нет", ln.text)]
    if len(yn) >= 3:
        add("modifiable", "major", "Чек-лист ревью не заполнен", _clip(yn[0].text, 0),
            f"В {len(yn)} строках оставлены варианты «Да / Нет» без выбора: ревью по шаблону банка не проведено.",
            "Провести ревью и проставить отметки (агент предлагает заполнение в разделе «Чек-лист банка»).")

    # 4. Версия и дата документа
    has_version = re.search(r"верси[яи]\s*[:№]?\s*\d", text, flags=re.I) or re.search(r"\bv\d+\.\d+", text)
    if not has_version:
        vline = next((ln for ln in lines if re.search(r"верси", ln.text, flags=re.I)), None)
        quote = _clip(vline.text, 0) if vline else _clip(lines[0].text, 0)
        add("modifiable", "major", "Не указаны версия и дата документа", quote,
            "Номер версии и дата не зафиксированы: нельзя сослаться на согласованную редакцию и отследить изменения.",
            "Добавить версию, дату и историю изменений.")

    # 5. Пустая таблица согласования (строка из одних разделителей в MD или заголовок без строк в PDF)
    for i, ln in enumerate(lines):
        if re.search(r"блок\s+согласующ|лист\s+согласовани", ln.text, flags=re.I):
            tail = [l.text for l in lines[i + 1:i + 8]]
            empty_md = any(re.fullmatch(r"\|(\s*\|)+", t.strip()) for t in tail)
            hdr = next((t for t in tail if re.search(r"ФИО|Подпись", t)), None)
            if empty_md or hdr:
                add("traceable", "major", "Блок согласования пуст", _clip(ln.text, 0),
                    "Нет ни одного согласующего: неизвестно, кто подтвердил требования и изменения смежных систем.",
                    "Заполнить подразделения, ответственных и отметки о согласовании.")
            break
    return out


def _clip(s: str, pos: int, width: int = 160) -> str:
    s = s.strip().strip("|").strip()
    s = re.sub(r"\s*\|\s*", " | ", s)
    if len(s) <= width:
        return s
    a = max(0, pos - width // 3)
    return s[a:a + width].strip()
