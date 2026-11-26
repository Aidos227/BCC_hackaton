"""Сборка отчёта. Отчёт собирает код из результатов этапов — модель не пишет отчёт «целиком»,
поэтому в нём нет общих фраз без привязки: каждая строка замечания ссылается на цитату и место."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .prompts import CRIT_NAMES, CRITERIA_REQ, CRITERIA_SET

SEV_RU = {"critical": "КРИТИЧНО", "major": "СУЩЕСТВЕННО", "minor": "НЕЗНАЧИТЕЛЬНО"}
SRC_RU = {"oracle": "трассировка сценария", "model": "исполняемая модель", "set": "проверка набора", "review": "проверка требования",
          "rule": "правило", "baseline": "один запрос"}
MARK = {"ok": "✔", "issue": "✖", "n/a": "—"}


def esc(s: Any) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def where(a, kind) -> str:
    return a.label(kind)


def render(doc, res: Dict[str, Any], passport: Dict[str, str], log: List[Dict] = (), delta: str = "") -> str:
    kind = doc.kind
    reqs: List[Dict] = res["requirements"]
    conf: List[Dict] = res["confirmed"]
    ques: List[Dict] = res["questions"]
    crit = [f for f in conf if f["severity"] == "critical"]
    major = [f for f in conf if f["severity"] == "major"]
    minor = [f for f in conf if f["severity"] == "minor"]
    by_req: Dict[str, List[Dict]] = {}
    for f in conf + ques:
        for rid in f.get("req_ids") or []:
            by_req.setdefault(rid, []).append(f)
    o: List[str] = []
    w = o.append

    w(f"# Отчёт о проверке требований: «{esc(doc.title)}»\n")
    intake = getattr(doc, "intake", None)
    partial = bool(intake and intake.status == "partial")
    if res.get("no_requirements"):
        verdict_line = ("**Итог: проверка невозможна — в документе не найдено ни одного требования.** "
                        "Похоже, передан не тот документ; разработку по нему начинать нельзя.")
    elif crit:
        verdict_line = ("**Итог: начинать разработку и тестирование по документу нельзя** — "
                        f"критичных дефектов: {len(crit)}; каждый блокирует конкретное решение (см. раздел 7).")
    elif partial:
        verdict_line = ("**Итог: вывод ограничен — документ прочитан не полностью** (см. «Входной контроль»). "
                        "Критичных дефектов в прочитанной части нет, но готовность документа подтвердить нельзя.")
    elif major:
        verdict_line = ("**Итог: разработку можно начинать с оговорками** — критичных дефектов нет, "
                        f"но {len(major)} существенных нужно закрыть до приёмки.")
    else:
        verdict_line = "**Итог: документ готов к разработке и тестированию.**"
    if partial and crit:
        verdict_line += " Документ прочитан не полностью — см. «Входной контроль»."
    w(verdict_line + "\n")
    if crit:
        w("**Главное (критичные дефекты):**\n")
        for f in crit:
            locs = "; ".join(dict.fromkeys(where(a["anchor"], kind) for a in f["anchored"]))
            w(f"- **{f['fid']}** — {esc(f.get('title'))} ({locs}). Нельзя решить: {esc(f.get('blocked_decision'))}")
        w("")
    if delta:
        w(delta)

    # ------------------------------------------------------------ 1. паспорт
    w("## 1. Паспорт прогона\n")
    w("| Поле | Значение |\n|---|---|")
    for k, v in passport.items():
        w(f"| {esc(k)} | {esc(v)} |")
    w("")
    if intake is not None:
        w(intake_md(intake, kind))
    w("Как читать отчёт: каждое замечание содержит дословные цитаты; место (страница, строка) "
      "вычислено кодом поиском цитаты в исходном файле, а не указано моделью. Замечания, у которых "
      "не нашлось ни одной подлинной цитаты, в отчёт не попадают (см. приложение А).\n")

    # ------------------------------------------------------------ 2. нарезка
    w("## 2. Как агент нарезал требования\n")
    w("| ID в отчёте | ID в документе | Тип | Краткая формулировка | Цитата из документа | Место |")
    w("|---|---|---|---|---|---|")
    for r in reqs:
        did = r.get("doc_id") or f"нет (присвоен {r['id']})"
        w(f"| {r['id']} | {esc(did)} | {esc(r.get('type'))} | {esc(r.get('summary'))} | «{esc(r.get('quote'))}» | "
          f"{where(r['anchor'], kind)} |")
    unanch = [r["id"] for r in reqs if not r["anchor"].found]
    w(f"\nВыделено требований: **{len(reqs)}**. Цитаты найдены в источнике у {len(reqs) - len(unanch)} из {len(reqs)}"
      + (f"; не найдены у: {', '.join(unanch)}." if unanch else ".") + "\n")

    # ------------------------------------------------------------ 3. каждое требование
    w("## 3. Проверка каждого требования\n")
    w("Критерии ISO/IEC/IEEE 29148:2018 п. 5.2.5 (соответствуют свойствам IEEE 830 п. 4.3). "
      "✔ — выполнено, ✖ — есть замечание, — — неприменимо. Итог по требованию учитывает только замечания, "
      "подтверждённые перепроверкой.\n")
    short = {"necessary": "Необх.", "appropriate": "Уместн.", "unambiguous": "Однозн.", "complete": "Полн.",
             "singular": "Единичн.", "feasible": "Осущ.", "verifiable": "Провер.", "correct": "Корр.",
             "conforming": "Шаблон"}
    w("| Треб. | " + " | ".join(short[k] for k, _ in CRITERIA_REQ) + " | Замечания | Итог |")
    w("|---|" + "---|" * len(CRITERIA_REQ) + "---|---|")
    for r in reqs:
        rv = res["reviews"].get(r["id"], {})
        cr = rv.get("criteria") or {}
        fs = by_req.get(r["id"], [])
        bad_crit = {f.get("criterion") for f in fs if f["fid"].startswith("F")}
        cells = []
        for k, _ in CRITERIA_REQ:
            m = cr.get(k, "n/a")
            if k in bad_crit:
                m = "issue"
            elif m == "issue":
                m = "ok*"
            cells.append(MARK.get(m, "✔*" if m == "ok*" else "—"))
        sev = min((f["severity"] for f in fs if f["fid"].startswith("F")),
                  key=lambda s: {"critical": 0, "major": 1, "minor": 2}[s], default=None)
        verdict = {"critical": "блокер", "major": "доработать", "minor": "уточнить", None: "годно"}[sev]
        w(f"| {r['id']} | " + " | ".join(cells) + f" | {', '.join(sorted({f['fid'] for f in fs})) or '—'} | {verdict} |")
    w("\n✔* — первичная проверка видела проблему, но перепроверка её не подтвердила (см. приложение А).\n")
    w("### Замечания по отдельным требованиям\n")
    any_req = False
    for f in conf:
        if f["source"] in ("review", "rule") and f.get("criterion") in short:
            w(finding_md(f, kind))
            any_req = True
    if not any_req:
        w("Нет подтверждённых замечаний уровня отдельного требования.\n")

    # ------------------------------------------------------------ 4. набор
    w("## 4. Проверка всего набора требований\n")
    w("Критерии ISO/IEC/IEEE 29148:2018 п. 5.2.6 и IEEE 830 п. 4.3.\n")
    set_crit = (res.get("set") or {}).get("set_criteria") or {}
    set_f = [f for f in conf if f.get("criterion") not in short or f["source"] in ("set", "model", "oracle")]
    w("| Критерий | Оценка | Комментарий | Замечания |\n|---|---|---|---|")
    for k, name in CRITERIA_SET:
        sc = set_crit.get(k) or {}
        refs = sorted({f["fid"] for f in set_f if f.get("criterion") == k})
        v = "✖" if refs else ("✔" if sc.get("verdict") == "ok" else ("✖" if sc.get("verdict") == "issue" else "—"))
        w(f"| {name} | {v} | {esc(sc.get('comment'))} | {', '.join(refs) or '—'} |")
    w("")
    w("### Исполняемая модель требований\n")
    w(model_md(res.get("model") or {}, conf, kind))
    w("### Замечания по набору\n")
    shown = False
    for f in conf:
        if f in set_f:
            w(finding_md(f, kind))
            shown = True
    if not shown:
        w("Нет подтверждённых замечаний уровня набора.\n")

    # ------------------------------------------------------------ 5. чек-лист банка
    chk = res.get("checklist") or {}
    if chk.get("present"):
        w("## 5. Чек-лист «Ревью требований» из документа — заполнен агентом\n")
        w("Отметки предложены агентом на основании подтверждённых замечаний; финальное решение — за ревьюером.\n")
        w("| Пункт чек-листа | Создано / доступно | Проверено | Основание | Комментарий |\n|---|---|---|---|---|")
        for it in chk.get("items", []):
            w(f"| {esc(it.get('item'))} | {esc(it.get('available'))} | {esc(it.get('passed'))} | "
              f"{', '.join(it.get('refs') or []) or '—'} | {esc(it.get('comment'))} |")
        w("")
    else:
        w("## 5. Чек-лист ревью\n\nВ документе нет встроенного чек-листа ревью — раздел не заполняется.\n")

    # ------------------------------------------------------------ 6. сводка
    w("## 6. Сводка\n")
    w("| Показатель | Значение |\n|---|---|")
    w(f"| Требований выделено | {len(reqs)} |")
    w(f"| Требований с подтверждёнными нарушениями | {sum(1 for r in reqs if any(f['fid'].startswith('F') for f in by_req.get(r['id'], [])))} |")
    w(f"| Нарушений подтверждено | {len(conf)} (критичных {len(crit)}, существенных {len(major)}, незначительных {len(minor)}) |")
    w(f"| Вопросов владельцу продукта | {len(ques)} |")
    w(f"| Кандидатов в замечания до проверок | {res.get('candidates_total')} |")
    w(f"| Отброшено: цитата не найдена в документе | {len(res.get('no_evidence') or [])} |")
    w(f"| Отклонено скептической перепроверкой | {len(res.get('rejected') or [])} |")
    w(f"| Объединено дублей | {len(res.get('duplicates') or [])} |")
    w("")
    w("**Критичные дефекты:**\n")
    if crit:
        for f in crit:
            locs = "; ".join(dict.fromkeys(where(a["anchor"], kind) for a in f["anchored"]))
            w(f"- **{f['fid']}** ({CRIT_NAMES.get(f.get('criterion'), f.get('criterion'))}) — {esc(f.get('title'))}. "
              f"Место: {locs}.")
    else:
        w("- нет")
    w("")

    # ------------------------------------------------------------ 7. итог
    w("## 7. Итог\n")
    w(verdict_line + "\n")
    if crit:
        w("Что невозможно решить по документу сейчас:\n")
        for f in crit:
            w(f"- {f['fid']}: {esc(f.get('blocked_decision'))}")
        w("")
    order = crit + major
    if order:
        w("**Что исправить в первую очередь:**\n")
        for n, f in enumerate(order[:10], start=1):
            fix = f.get("fix") or (f"Принять решение владельцем: {f['owner_question']}" if f.get("owner_question") else "")
            w(f"{n}. **{f['fid']}** — {esc(f.get('title'))}. {esc(fix)}")
        w("")

    # ------------------------------------------------------------ 8. вопросы
    w("## 8. Вопросы владельцу продукта\n")
    w("Это не дефекты формулировок, а решения, которые текст не принимает и которые агент не вправе принять сам.\n")
    qs = ques + [f for f in conf if f.get("owner_question")]
    if qs:
        for f in qs:
            locs = "; ".join(f"«{esc(a['text'])}» ({where(a['anchor'], kind)})" for a in f["anchored"][:2])
            w(f"- **{f['fid']}** {esc(f.get('owner_question') or f.get('title'))} — основание: {locs}")
    else:
        w("- нет")
    w("")

    # ------------------------------------------------------------ приложения
    w("## Приложение А. Что агент отбросил и почему\n")
    w("Прозрачность фильтрации: эти кандидаты НЕ вошли в выводы отчёта.\n")
    rows = []
    for f in res.get("no_evidence") or []:
        rows.append((f["cid"], SRC_RU.get(f["source"], f["source"]), f.get("title"), "цитата не найдена в документе"))
    for f in res.get("rejected") or []:
        rows.append((f["cid"], SRC_RU.get(f["source"], f["source"]), f.get("title"), "перепроверка: " + (f.get("verify_reason") or "")))
    for f in res.get("duplicates") or []:
        rows.append((f["cid"], SRC_RU.get(f["source"], f["source"]), f.get("title"), f"дубль {f.get('dup_fid') or ''}"))
    if rows:
        w("| Кандидат | Источник | Суть | Причина |\n|---|---|---|---|")
        for r in rows:
            w("| " + " | ".join(esc(x) for x in r) + " |")
    else:
        w("Ничего не отброшено.")
    w("")
    w("## Приложение Б. Журнал обращений к модели\n")
    w("| Этап | Модель | Токены вход | Токены выход | Секунды |\n|---|---|---|---|---|")
    for e in log:
        w(f"| {esc(e['stage'])} | {esc(e.get('model'))} | {e['in']} | {e['out']} | {e['sec']} |")
    return "\n".join(o) + "\n"


INTAKE_RU = {"ok": "годен", "partial": "прочитан частично", "unreadable": "не прочитан"}


def intake_md(i, kind: str = "") -> str:
    o = ["### Входной контроль\n", "| Проверка | Результат |\n|---|---|",
         f"| Статус | **{INTAKE_RU.get(i.status, i.status)}** |",
         f"| Тип по содержимому | {esc(i.detected)} |",
         f"| Размер | {i.size} байт |"]
    if i.encoding:
        o.append(f"| Кодировка | {esc(i.encoding)} |")
    if i.pages_declared is not None:
        o.append(f"| Страниц в файле / с текстом | {i.pages_declared} / {i.pages_with_text} |")
    o.append(f"| Извлечено символов | {i.chars}" + (f" (читаемых {round(100 * i.readable_ratio)}%)" if i.chars else "") + " |")
    if i.problems:
        o.append(f"| Замечания к файлу | {esc('; '.join(i.problems))} |")
    if i.advice:
        o.append(f"| Что сделать | {esc(' '.join(i.advice))} |")
    return "\n".join(o) + "\n"


def render_unreadable(path, intake, passport: Dict[str, str]) -> str:
    """Отчёт-диагноз, когда документ нельзя проверить: файл отчёта создаётся всегда."""
    o = [f"# Отчёт о проверке требований: файл «{esc(path.name)}» не прочитан\n",
         "**Итог: проверка невозможна — документ не удалось прочитать.** Начинать разработку и тестирование по "
         "этому файлу нельзя: агент не может подтвердить ни одного требования. Модель не вызывалась.\n",
         "## 1. Паспорт прогона\n", "| Поле | Значение |\n|---|---|"]
    o += [f"| {esc(k)} | {esc(v)} |" for k, v in passport.items()]
    o.append("")
    o.append(intake_md(intake))
    o.append("## Что сделать\n")
    for a in intake.advice or ["Прислать документ в формате PDF с текстовым слоем, DOCX или Markdown (UTF-8)."]:
        o.append(f"- {esc(a)}")
    return "\n".join(o) + "\n"


def finding_md(f: Dict, kind: str) -> str:
    crit_name = CRIT_NAMES.get(f.get("criterion"), f.get("criterion") or "")
    head = (f"**{f['fid']} · {SEV_RU[f['severity']]} · {crit_name}** — {esc(f.get('title'))}"
            f"  \nТребования: {', '.join(f.get('req_ids') or []) or 'документ в целом'}; "
            f"найдено: {SRC_RU.get(f['source'], f['source'])}"
            + (f" (также: {', '.join(sorted(set(SRC_RU.get(s, s) for s in f['also'])))})" if f.get("also") else ""))
    lines = [head]
    for a in f["anchored"]:
        lines.append(f"- Цитата ({where(a['anchor'], kind)}): «{esc(a['text'])}»")
    lines.append(f"- Проблема: {esc(f.get('problem'))}")
    if f["severity"] == "critical" and f.get("blocked_decision"):
        lines.append(f"- Какое решение нельзя принять: {esc(f.get('blocked_decision'))}")
    if f.get("evidence"):
        lines.append(f"- Доказательство ({f.get('methods', 'прогон сценария')}):\n\n```text\n" + f["evidence"] + "\n```")
    if f.get("fix"):
        lines.append(f"- Как исправить: {esc(f.get('fix'))}")
    if f.get("owner_question"):
        lines.append(f"- Вопрос владельцу: {esc(f.get('owner_question'))}")
    if f.get("notes"):
        lines.append(f"- Примечание агента: {esc('; '.join(f['notes']))}")
    return "\n".join(lines) + "\n"


def model_md(m: Dict, conf: List[Dict], kind: str) -> str:
    if m.get("skipped"):
        return "Этап отключён флагом --no-model.\n"
    if not m.get("applicable"):
        if m.get("error"):
            return f"Этап не выполнен: {esc(m['error'])}.\n"
        return "В документе не найдено вычислимой бизнес-логики — этап не применялся.\n"
    o = [f"Предмет моделирования: {esc(m.get('summary'))}. Агент составил сценарии из каждой строки критериев "
         "приёмки и граничных ситуаций и проверил их двумя независимыми способами: (1) трассировкой — какие правила "
         "документа применимы и что каждое предписывает; (2) вычислением — исполняемой моделью правил на Python, "
         "которая писалась БЕЗ доступа к ожидаемым результатам критериев приёмки (они скрыты от этого запроса). "
         "Код модели сохранён рядом с отчётом (`*.model.py`) и запускается без LLM.\n"]
    if m.get("error"):
        o.append(f"Вычисление: {esc(m['error'])}\n")
    if m.get("interpretations"):
        o.append("Спорные формулировки, заложенные в модель как развилки:\n")
        o.append("| Развилка | Формулировка | Прочтение a | Прочтение b |\n|---|---|---|---|")
        for i in m["interpretations"]:
            o.append(f"| {esc(i.get('id'))} | «{esc(i.get('quote'))}» | {esc(i.get('a'))} | {esc(i.get('b'))} |")
        o.append("")
    runs = m.get("runs") or []
    fid_by_sc = {}
    for f in conf:
        if f.get("scenario"):
            fid_by_sc.setdefault(f["scenario"], []).append(f["fid"])
    traces = m.get("traces") or {}
    o.append("| Сценарий | Источник | Описание | Трассировка по правилам | Вычисление модели | Замечание |\n|---|---|---|---|---|---|")
    from .sandbox import clean, comparable, same
    for sc in m.get("scenarios") or []:
        rs = [r for r in runs if r["scenario"] == sc["id"]]
        st = {r["status"] for r in rs}
        if not rs:
            res = "не запускалась"
        elif sc.get("lost_facts"):
            res = "не учитывается: сценарий потерял факты " + ", ".join(sc["lost_facts"])
        elif "undefined" in st:
            res = "не определено документом"
        elif "error" in st and "ok" not in st:
            res = "ошибка модели"
        elif sc.get("source") == "acceptance" and sc.get("expected") and not all(
                comparable(sc["expected"], clean(r["result"])) for r in rs if r["status"] == "ok"):
            res = "несопоставимо: модель не вычисляет величины критерия"
        elif sc.get("source") == "acceptance" and sc.get("expected"):
            oks = [same(sc["expected"], clean(r["result"]))[0] for r in rs if r["status"] == "ok"]
            res = "выполняется" if oks and all(oks) else ("зависит от прочтения" if any(oks) else "НЕ выполняется")
        else:
            outs = {json.dumps(clean(r.get("result")), sort_keys=True, ensure_ascii=False) for r in rs if r["status"] == "ok"}
            res = "однозначно" if len(outs) <= 1 else "зависит от прочтения"
        t = traces.get(sc["id"]) or {}
        tr = ("правила противоречат друг другу" if t.get("conflict") else
              {"match": "выполняется", "mismatch": "НЕ выполняется", "undetermined": "не определено"}.get(t.get("acceptance"))
              or ("не определено" if (t.get("undetermined") or "").strip() else ("однозначно" if t else "—")))
        src = "критерий приёмки" if sc.get("source") == "acceptance" else "граничный"
        o.append(f"| {sc['id']} | {src} | {esc(sc.get('title'))} | {tr} | {res} | {', '.join(fid_by_sc.get(sc['id'], [])) or '—'} |")
    o.append("")
    return "\n".join(o)


# ---------------------------------------------------------------------- сравнение с прошлым прогоном
def _qset(f: Dict) -> List[str]:
    from .ingest import normalize
    out = []
    for a in f.get("anchored") or []:
        anc = a.get("anchor")
        found = anc.found if hasattr(anc, "found") else (anc or {}).get("found")
        if found:
            out.append(normalize(a["text"]))
    return out


def _tok(s: str) -> set:
    return {w for w in s.split() if len(w) > 2}


def _qeq(x: str, y: str) -> bool:
    if x in y or y in x:
        return True
    tx, ty = _tok(x), _tok(y)
    return bool(tx and ty and len(tx & ty) / len(tx | ty) >= 0.6)


def _match(a: Dict, b: Dict) -> bool:
    """Одно и то же замечание: тот же критерий и общая цитата, либо совпали все цитаты (не меньше двух)."""
    qa, qb = _qset(a), _qset(b)
    if not qa or not qb:
        return False
    small, big = (qa, qb) if len(qa) <= len(qb) else (qb, qa)
    covered = sum(1 for x in small if any(_qeq(x, y) for y in big))
    if a.get("criterion") == b.get("criterion") and covered:
        return True
    return len(small) >= 2 and covered == len(small)


def delta_md(prev: Dict, cur_confirmed: List[Dict], prev_name: str, doc=None) -> str:
    """Какие замечания прошлого прогона ушли, какие остались, какие новые (сопоставление по цитатам).
    Ушедшие делятся честно на две группы: процитированный текст изменён (причина устранена) и
    текст не менялся (замечание просто не воспроизвелось в этом прогоне)."""
    old = [f for f in prev.get("confirmed", []) if f.get("severity") in ("critical", "major")]
    new = [f for f in cur_confirmed if f.get("severity") in ("critical", "major")]
    gone = [o for o in old if not any(_match(o, n) for n in new)]
    added = [n for n in new if not any(_match(n, o) for o in old)]
    kept = len(new) - len(added)

    def text_changed(f: Dict) -> bool:
        if doc is None:
            return True
        return any(not doc.locate(a["text"]).found for a in f.get("anchored") or [])

    fixed = [f for f in gone if text_changed(f)]
    unstable = [f for f in gone if not text_changed(f)]
    o = [f"## 0. Изменения относительно прошлого прогона (`{esc(prev_name)}`)\n",
         "Сопоставление по цитатам (критичные и существенные замечания). «Закрыто» — только если процитированный "
         "в прошлом замечании текст в документе изменился.\n",
         f"| Закрыто (текст исправлен) | Не воспроизвелось (текст тот же) | Осталось | Новых |\n|---|---|---|---|\n"
         f"| {len(fixed)} | {len(unstable)} | {kept} | {len(added)} |\n"]
    for f in fixed:
        o.append(f"- ✔ закрыто: {f.get('fid')} — {esc(f.get('title'))} (было: {SEV_RU.get(f.get('severity'), '')})")
    for f in unstable:
        o.append(f"- ? не воспроизвелось, текст не менялся: {f.get('fid')} — {esc(f.get('title'))}")
    for f in added:
        o.append(f"- ✚ новое: {f.get('fid')} — {esc(f.get('title'))} ({SEV_RU.get(f.get('severity'), '')})")
    return "\n".join(o) + "\n"
