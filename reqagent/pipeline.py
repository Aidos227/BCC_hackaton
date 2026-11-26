"""Конвейер проверки: нарезка → проверка требований → проверка набора → исполняемая модель →
детерминированные правила → привязка цитат → скептическая перепроверка → чек-лист банка."""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from . import prompts as P
from .ingest import Document, normalize
from .llm import LLM
from .rules import run_rules
from .sandbox import UnsafeCode, clean, comparable, combos, run_model, same

SEV_ORDER = {"critical": 0, "major": 1, "minor": 2}
SRC_ORDER = {"oracle": 0, "model": 0, "set": 1, "review": 2, "rule": 3}


def say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------------- 1. нарезка
def segment(llm: LLM, doc: Document) -> List[Dict]:
    data = llm.json(P.SYSTEM, P.segment_prompt(doc.text), "1/7 нарезка требований")
    reqs = data.get("requirements", []) if isinstance(data, dict) else data
    out = []
    for i, r in enumerate(reqs, start=1):
        r = dict(r)
        r["id"] = f"R-{i:02d}"
        r["doc_id"] = r.get("doc_id") or None
        a = doc.locate(r.get("quote", ""))
        r["anchor"] = a
        out.append(r)
    bad = [r["id"] for r in out if not r["anchor"].found]
    say(f"    требований: {len(out)}, цитат не найдено: {len(bad)} {bad if bad else ''}")
    return out


def _reqs_for_prompt(reqs: List[Dict]) -> str:
    return _j([{k: r.get(k) for k in ("id", "doc_id", "section", "type", "summary", "quote")} for r in reqs])


# ---------------------------------------------------------------------------- 2. каждое требование
def review(llm: LLM, doc: Document, reqs: List[Dict], batch: int = 12) -> Dict[str, Dict]:
    result: Dict[str, Dict] = {}
    queue = [reqs[i:i + batch] for i in range(0, len(reqs), batch)]
    n = 0
    while queue:
        ch = queue.pop(0)
        n += 1
        try:
            data = llm.json(P.SYSTEM, P.review_prompt(doc.text, _reqs_for_prompt(ch)),
                            f"2/7 проверка требований ({ch[0]['id']}–{ch[-1]['id']})")
        except ValueError:
            if len(ch) > 3:
                half = len(ch) // 2
                say(f"    пакет {ch[0]['id']}–{ch[-1]['id']} не разобран, делю пополам")
                queue[:0] = [ch[:half], ch[half:]]
                continue
            say(f"    пакет {ch[0]['id']}–{ch[-1]['id']} пропущен: модель не вернула JSON")
            continue
        for rv in (data.get("reviews", []) if isinstance(data, dict) else data):
            if isinstance(rv, dict):
                result[rv.get("id")] = rv
    return result


# ---------------------------------------------------------------------------- 3. набор
def review_set(llm: LLM, doc: Document, reqs: List[Dict]) -> Dict:
    data = llm.json(P.SYSTEM, P.set_prompt(doc.text, _reqs_for_prompt(reqs)), "3/7 проверка набора")
    return data if isinstance(data, dict) else {"findings": data}


# ---------------------------------------------------------------------------- 4. исполняемая модель
def executable_model(llm: LLM, doc: Document, reqs: List[Dict]) -> Dict:
    """4а сценарии → 4б трассировка сценариев по правилам → 4в код модели и прогон в песочнице.
    Код пишется БЕЗ доступа к ожидаемым результатам критериев приёмки: они скрыты от этого запроса."""
    rj = _reqs_for_prompt(reqs)
    try:
        spec = llm.json(P.SYSTEM, P.scenarios_prompt(doc.text, rj), "4/7 сценарии")
    except ValueError:
        return {"applicable": False, "error": "модель не вернула JSON сценариев", "summary": ""}
    if not isinstance(spec, dict) or not spec.get("applicable"):
        return {"applicable": False, "summary": (spec or {}).get("summary", "") if isinstance(spec, dict) else ""}
    scenarios = [sc for sc in spec.get("scenarios") or [] if isinstance(sc, dict) and sc.get("id")]
    spec["scenarios"] = scenarios
    interps = (spec.get("interpretations") or [])[:4]
    spec["interpretations"] = interps
    for sc in scenarios:
        sc["lost_facts"] = lost_facts(sc)
    broken = [sc for sc in scenarios if sc["lost_facts"]]
    if broken:
        say(f"    сценарии потеряли факты строк критериев: {', '.join(sc['id'] for sc in broken)} — исправление")
        try:
            fx = llm.json(P.SYSTEM, P.scenario_fix_prompt(_j(broken)), "4/7 исправление сценариев")
            for new in (fx.get("scenarios", []) if isinstance(fx, dict) else []):
                old = next((sc for sc in scenarios if sc["id"] == new.get("id")), None)
                if old is not None and isinstance(new.get("input"), dict):
                    old["input"], old["expected"] = new["input"], new.get("expected") or old.get("expected")
                    old["lost_facts"] = lost_facts(old)
        except ValueError:
            pass
    # 4б «слепая» трассировка и сравнение с критериями приёмки
    spec["traces"] = oracle(llm, doc, rj, scenarios)
    compare(llm, scenarios, spec["traces"])
    # 4в код: сценарии без ожидаемых значений и без строк критериев
    blind = {"outputs": spec.get("outputs"), "interpretations": interps,
             "scenarios": [{k: v for k, v in sc.items() if k in ("id", "title", "situation", "input")} for sc in scenarios]}
    code, rules, runs, error = "", [], [], ""
    try:
        cg = llm.json(P.SYSTEM, P.code_prompt(doc.text, rj, _j(blind)), "4/7 код модели", max_tokens=48000)
        code = cg.get("code", "") if isinstance(cg, dict) else ""
        rules = cg.get("rules", []) if isinstance(cg, dict) else []
    except ValueError:
        error = "модель не вернула JSON с кодом"
    if code:
        for attempt in range(3):
            try:
                runs = run_model(code, scenarios, interps)
                errs = [r for r in runs if r["status"] == "error"]
                if not errs or attempt == 2:
                    break
                msg = "\n".join(f"{r['scenario']} [{r['combo']}]: {r['error']}" for r in errs[:12])
            except (UnsafeCode, RuntimeError) as e:
                msg = str(e)
                if attempt == 2:
                    error = msg
                    break
            say(f"    модель упала, исправление {attempt + 1}/2: {msg.splitlines()[0][:120]}")
            try:
                fixed = llm.json(P.SYSTEM, P.model_repair_prompt(code, msg), f"4/7 исправление модели {attempt + 1}")
                code = fixed.get("code", code) if isinstance(fixed, dict) else code
            except ValueError:
                pass
    spec.update({"code": code, "rules": rules, "runs": runs, "error": error})
    mf = model_findings(spec, reqs, doc) if runs else []
    of = oracle_findings(spec, reqs)
    spec["findings"] = merge_methods(mf, of)
    say(f"    сценариев: {len(scenarios)}, развилок: {len(interps)}, находок: модель {len(mf)}, "
        f"трассировка {len(of)}, после объединения {len(spec['findings'])}")
    return spec


def lost_facts(sc: Dict) -> List[str]:
    """Числа и время из строки критерия, которые не попали в структурированный сценарий."""
    import re as _re
    q = sc.get("quote") or ""
    if sc.get("source") != "acceptance" or not q:
        return []
    blob = json.dumps([sc.get("input"), sc.get("expected")], ensure_ascii=False).replace(" ", "").replace("\u00a0", "")
    facts = set(_re.findall(r"\d{1,2}:\d{2}", q))
    for n in _re.findall(r"\d[\d \u00a0]*\d|\d", _re.sub(r"\d{1,2}:\d{2}", " ", q)):
        facts.add(_re.sub(r"\s", "", n))
    lost = sorted(f for f in facts if f not in blob)
    # Месяц в виде прилагательного («Февральский счётчик») описывает ожидаемый результат —
    # он должен попасть именно в expected.
    months = ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
    exp_blob = json.dumps(sc.get("expected"), ensure_ascii=False).lower()
    for i, stem in enumerate(months, start=1):
        for m_ in _re.finditer(r"\b" + stem + r"\w*ск\w*", q.lower()):
            if not (stem in exp_blob or f"-{i:02d}" in exp_blob or f'"{i:02d}"' in exp_blob
                    or _re.search(r'"month[^"]*"\s*:\s*' + str(i) + r"\b", exp_blob)):
                lost.append(m_.group(0))
    return sorted(set(lost))


def oracle(llm: LLM, doc: Document, rj: str, scenarios: List[Dict], batch: int = 4) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    view = [{k: sc.get(k) for k in ("id", "title", "situation")} for sc in scenarios]   # без ожидаемых результатов
    queue = [view[i:i + batch] for i in range(0, len(view), batch)]
    while queue:
        part = queue.pop(0)
        try:
            data = llm.json(P.SYSTEM, P.oracle_prompt(doc.text, rj, _j(part)),
                            f"4/7 трассировка ({part[0]['id']}–{part[-1]['id']})")
        except ValueError:
            if len(part) > 1:
                queue[:0] = [part[:len(part) // 2], part[len(part) // 2:]]
            continue
        for t in (data.get("traces", []) if isinstance(data, dict) else data):
            if isinstance(t, dict) and t.get("id"):
                out[t["id"]] = t
    return out


def compare(llm: LLM, scenarios: List[Dict], traces: Dict[str, Dict]) -> None:
    pairs = []
    for sc in scenarios:
        t = traces.get(sc["id"])
        if sc.get("source") == "acceptance" and t:
            pairs.append({"id": sc["id"], "строка_критерия": sc.get("quote"), "ожидает_критерий": sc.get("expected"),
                          "по_правилам": t.get("derived"), "не_определено": t.get("undetermined")})
    if not pairs:
        return
    try:
        data = llm.json(P.SYSTEM, P.compare_prompt(_j(pairs)), "4/7 сравнение с критериями")
    except ValueError:
        return
    for v in (data.get("verdicts", []) if isinstance(data, dict) else data):
        if isinstance(v, dict) and v.get("id") in traces:
            traces[v["id"]]["acceptance"] = v.get("verdict")
            traces[v["id"]]["difference"] = v.get("difference", "")


def oracle_findings(spec: Dict, reqs: List[Dict]) -> List[Dict]:
    out = []
    traces = spec.get("traces") or {}
    for sc in spec.get("scenarios") or []:
        t = traces.get(sc["id"])
        if not t:
            continue
        ro = [r for r in t.get("rule_outcomes") or [] if isinstance(r, dict)]
        rq = [r.get("quote", "") for r in ro]
        ids = sorted({r.get("req_id") for r in ro if r.get("req_id")})
        is_acc = sc.get("source") == "acceptance"
        lines = [f"Сценарий {sc['id']}: {sc.get('title', '')}", f"Ситуация: {sc.get('situation', '')}"]
        lines += [f"{r.get('req_id')}: «{r.get('quote')}» → {r.get('outcome')}" for r in ro]
        lines.append(f"Вывод по правилам (без доступа к ожидаемому результату): {t.get('derived', '')}")
        if is_acc:
            lines.append(f"Ожидается критерием: {json.dumps(sc.get('expected'), ensure_ascii=False)}")
        ev = "\n".join(lines)
        blocked = t.get("blocked_decision") or ""
        if is_acc and t.get("acceptance") == "mismatch":
            out.append(_of(sc, "set_consistent", "critical",
                           f"Критерий приёмки противоречит правилам ({sc['id']})",
                           [sc.get("quote", "")] + rq, ids,
                           f"По правилам документа (вывод сделан без доступа к критерию): {t.get('derived', '').rstrip('.')}. "
                           f"Критерий приёмки: «{sc.get('quote', '')}». "
                           f"Расхождение: {t.get('difference', '').rstrip('.')}.",
                           blocked or "Какой ожидаемый результат закладывать в тест и в реализацию.", ev))
        if t.get("conflict") and t.get("acceptance") != "mismatch":
            out.append(_of(sc, "set_consistent", "critical",
                           f"Правила требуют разного: {sc.get('title', sc['id'])}",
                           ([sc.get("quote", "")] if is_acc and sc.get("quote") else []) + rq, ids,
                           t.get("conflict_explanation") or "Применимые правила предписывают несовместимые результаты.",
                           blocked or "Какое из правил реализовать в этой ситуации.", ev))
        if (t.get("undetermined") or "").strip() and t.get("acceptance") != "mismatch" and not t.get("conflict"):
            out.append(_of(sc, "complete", "critical" if is_acc else "major",
                           f"Документ не определяет исход: {sc.get('title', sc['id'])}",
                           ([sc.get("quote", "")] if sc.get("quote") else []) + rq, ids,
                           f"По правилам документа исход не определён: {t['undetermined']}",
                           blocked if is_acc else "", ev, owner_question=t["undetermined"]))
    return out


def _of(sc, criterion, severity, title, quotes, ids, problem, blocked, ev, owner_question=""):
    return {"source": "oracle", "criterion": criterion, "severity": severity, "req_ids": ids, "title": title,
            "quotes": [q for q in quotes if q], "problem": problem, "blocked_decision": blocked, "fix": "",
            "owner_question": owner_question, "scenario": sc["id"], "evidence": ev}


def merge_methods(mf: List[Dict], of: List[Dict]) -> List[Dict]:
    """Одна находка на сценарий и вид дефекта; совпадение двух методов отмечается явно."""
    out = list(of)
    for m in mf:
        twin = next((o for o in of if o["scenario"] == m["scenario"] and
                     (o["criterion"] == m["criterion"] or {o["criterion"], m["criterion"]} <= {"set_consistent", "unambiguous"})), None)
        if twin:
            twin["evidence"] = twin["evidence"] + "\n\nПрогон исполняемой модели:\n" + m["evidence"]
            twin["methods"] = "трассировка правил + вычисление модели"
            twin["quotes"] = twin["quotes"] + [q for q in m["quotes"] if q not in twin["quotes"]]
            twin["req_ids"] = sorted(set(twin["req_ids"]) | set(m["req_ids"]))
        else:
            out.append(m)
    for o in out:
        o.setdefault("methods", "вычисление модели" if o["source"] == "model" else "трассировка правил")
    return out


def model_findings(spec: Dict, reqs: List[Dict], doc: Document) -> List[Dict]:
    by_id = {r["id"]: r for r in reqs}
    interps = {i["id"]: i for i in spec.get("interpretations") or []}
    runs = spec.get("runs") or []
    out: List[Dict] = []

    def req_quotes(ids):
        return [by_id[i]["quote"] for i in ids if i in by_id and by_id[i].get("quote")]

    for sc in spec.get("scenarios") or []:
        rs = [r for r in runs if r["scenario"] == sc["id"]]
        if not rs or sc.get("lost_facts"):
            continue   # сценарий потерял факты строки критерия — вычислению по нему не доверяем
        ok = [r for r in rs if r["status"] == "ok"]
        und = [r for r in rs if r["status"] == "undefined"]
        exp = sc.get("expected")
        is_acc = sc.get("source") == "acceptance" and isinstance(exp, dict) and exp
        trace = sorted({t for r in ok for t in (r["result"].get("_trace") or []) if isinstance(t, str)})
        targets = [t for t in (sc.get("targets") or []) if t in by_id]
        ids = sorted(set(trace or targets))

        if is_acc and ok and not all(comparable(exp, clean(r["result"])) for r in ok):
            ok_cmp = []
        else:
            ok_cmp = ok
        if is_acc and ok_cmp:
            verdicts = [(r["combo"], *same(exp, clean(r["result"]))) for r in ok]
            passing = [v for v in verdicts if v[1]]
            failing = [v for v in verdicts if not v[1]]
            if failing and not passing and not und:
                diffs = "; ".join(failing[0][2])
                out.append(_mf(sc, "set_consistent", "critical",
                               f"Критерий приёмки не выполняется по правилам документа ({sc['id']})",
                               [sc.get("quote", "")] + req_quotes(ids), ids,
                               f"Прогон модели правил на сценарии «{sc.get('title', '')}»: {diffs}.",
                               "Какой ожидаемый результат закладывать в тест и в реализацию: из правила или "
                               "из критерия приёмки.",
                               evidence=_evidence(sc, rs)))
            elif failing and passing:
                ii = sorted({k.split("=")[0] for c, *_ in failing for k in c.split(",") if "=" in k})
                iq = [interps[i]["quote"] for i in ii if i in interps and interps[i].get("quote")]
                out.append(_mf(sc, "unambiguous", "critical",
                               f"Исход критерия приёмки зависит от прочтения формулировки ({sc['id']})",
                               [sc.get("quote", "")] + iq + req_quotes(ids), ids,
                               "Критерий выполняется при одном прочтении правила и не выполняется при другом: "
                               + "; ".join(f"[{c}] {('выполняется' if okv else '; '.join(d))}"
                                           for c, okv, d in verdicts) + ".",
                               "Какое прочтение правила реализовать, чтобы критерий приёмки был выполним.",
                               evidence=_evidence(sc, rs)))
        if und:
            q = und[0].get("question", "")
            uids = sorted(set(und[0].get("req_ids") or ids))
            out.append(_mf(sc, "complete", "critical" if is_acc else "major",
                           f"Документ не определяет исход: {sc.get('title', sc['id'])}",
                           ([sc.get("quote", "")] if sc.get("quote") else []) + req_quotes(uids), uids,
                           f"При прогоне сценария модель правил не может вычислить результат: {q}",
                           "Какой результат ожидать в тесте и реализовать для этого сценария." if is_acc else "",
                           owner_question=q, evidence=_evidence(sc, rs)))
        if not is_acc and len(ok) >= 2:
            outcomes = {}
            for r in ok:
                outcomes.setdefault(json.dumps(clean(r["result"]), sort_keys=True, ensure_ascii=False), []).append(r["combo"])
            if len(outcomes) >= 2:
                ii = sorted({k.split("=")[0] for c in [r["combo"] for r in ok] for k in c.split(",") if "=" in k})
                diverging = [i for i in ii if _matters(i, ok)]
                iq = [interps[i]["quote"] for i in diverging if i in interps and interps[i].get("quote")]
                qtext = "; ".join(interps[i]["question"] for i in diverging if i in interps)
                out.append(_mf(sc, "unambiguous", "major",
                               f"Разные прочтения дают разный результат: {sc.get('title', sc['id'])}",
                               iq + req_quotes(ids), sorted(set(ids) | {x for i in diverging for x in interps.get(i, {}).get("req_ids", [])}),
                               f"Неоднозначность ({qtext}) влияет на наблюдаемый результат: "
                               + "; ".join(f"[{', '.join(v)}] → {k}" for k, v in outcomes.items()) + ".",
                               "", owner_question=qtext, evidence=_evidence(sc, rs)))
    return out


def _matters(iid: str, ok_runs: List[Dict]) -> bool:
    """Влияет ли выбор интерпретации iid на результат при прочих равных."""
    groups: Dict[str, set] = {}
    for r in ok_runs:
        parts = dict(p.split("=") for p in r["combo"].split(",") if "=" in p)
        if iid not in parts:
            continue
        rest = ",".join(f"{k}={v}" for k, v in sorted(parts.items()) if k != iid)
        groups.setdefault(rest, set()).add(json.dumps(clean(r["result"]), sort_keys=True, ensure_ascii=False))
    return any(len(v) > 1 for v in groups.values())


def _mf(sc, criterion, severity, title, quotes, req_ids, problem, blocked, owner_question="", evidence=""):
    return {"source": "model", "criterion": criterion, "severity": severity, "req_ids": req_ids,
            "title": title, "quotes": [q for q in quotes if q], "problem": problem,
            "blocked_decision": blocked, "fix": "", "owner_question": owner_question,
            "scenario": sc["id"], "evidence": evidence}


def _evidence(sc: Dict, rs: List[Dict]) -> str:
    lines = [f"Сценарий {sc['id']}: {sc.get('title', '')}",
             f"Вход: {json.dumps(sc.get('input'), ensure_ascii=False)}"]
    if sc.get("expected"):
        lines.append(f"Ожидается по документу: {json.dumps(sc['expected'], ensure_ascii=False)}")
    for r in rs:
        if r["status"] == "ok":
            lines.append(f"[{r['combo']}] вычислено: {json.dumps(r['result'], ensure_ascii=False)}")
        elif r["status"] == "undefined":
            lines.append(f"[{r['combo']}] НЕ ОПРЕДЕЛЕНО: {r.get('question')}")
        else:
            lines.append(f"[{r['combo']}] ошибка модели: {r.get('error')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------- 5. сбор и привязка
def collect(reviews: Dict[str, Dict], set_rv: Dict, model: Dict, rule_f: List[Dict], doc: Document) -> List[Dict]:
    cand: List[Dict] = []
    for rid, rv in reviews.items():
        for f in rv.get("findings") or []:
            f = dict(f)
            f["source"] = "review"
            f["req_ids"] = sorted(set((f.get("req_ids") or []) + [rid]))
            cand.append(f)
    for f in set_rv.get("findings") or []:
        f = dict(f)
        f["source"] = "set"
        cand.append(f)
    cand += model.get("findings") or []
    cand += rule_f
    for i, f in enumerate(cand, start=1):
        f["cid"] = f"C-{i:03d}"
        f["severity"] = f.get("severity") if f.get("severity") in SEV_ORDER else "minor"
        anchored, seen = [], []
        for q in f.get("quotes") or []:
            if not (isinstance(q, str) and q.strip()):
                continue
            nq = normalize(q)
            if any(nq in x for x in seen):
                continue          # повтор или часть уже приведённой цитаты
            seen = [x for x in seen if x not in nq] + [nq]
            anchored = [a for a in anchored if normalize(a["text"]) not in nq]
            anchored.append({"text": q.strip(), "anchor": doc.locate(q)})
        f["anchored"] = anchored
        f["quotes_ok"] = sum(1 for a in anchored if a["anchor"].found)
    return cand


def gate(cand: List[Dict]) -> List[Dict]:
    """Жёсткие правила доказательности, применяемые кодом."""
    kept = []
    for f in cand:
        f["notes"] = []
        good = [a for a in f["anchored"] if a["anchor"].found]
        if not good:
            f["status"] = "no_evidence"
            f["notes"].append("ни одна цитата не найдена в документе")
            continue
        if len(good) < len(f["anchored"]):
            f["notes"].append(f"отброшено ненайденных цитат: {len(f['anchored']) - len(good)}")
            f["anchored"] = good
        kept.append(f)
    return kept


# ---------------------------------------------------------------------------- 6. перепроверка
def verify(llm: LLM, doc: Document, cand: List[Dict]) -> List[Dict]:
    payload = [{"id": f["cid"], "source": f["source"], "criterion": f.get("criterion"),
                "severity": f["severity"], "req_ids": f.get("req_ids"), "title": f.get("title"),
                "quotes": [a["text"] for a in f["anchored"]], "problem": f.get("problem"),
                **({"evidence": f["evidence"]} if f.get("evidence") else {})} for f in cand]
    verdicts: Dict[str, Dict] = {}
    queue = [payload[i:i + 35] for i in range(0, len(payload), 35)]
    while queue:
        part = queue.pop(0)
        try:
            data = llm.json(P.SYSTEM, P.verify_prompt(doc.text, _j(part)),
                            f"6/7 перепроверка ({part[0]['id']}–{part[-1]['id']})")
        except ValueError:
            if len(part) > 3:
                queue[:0] = [part[:len(part) // 2], part[len(part) // 2:]]
            continue
        for v in (data.get("verdicts", []) if isinstance(data, dict) else data):
            if isinstance(v, dict):
                verdicts[v.get("id")] = v
    for f in cand:
        if f.get("pinned"):
            # детерминированная находка (например, внедрённая инструкция) не отдаётся на суд модели:
            # та же инструкция могла бы повлиять и на рецензента
            f.update(verdict="confirm", verify_reason="закреплено правилом, перепроверка моделью не применяется")
            continue
        v = verdicts.get(f["cid"])
        if v is None:
            # без вердикта замечание не может считаться подтверждённым
            v = {"verdict": "reject", "reason": "перепроверка не вернула вердикт — замечание не подтверждено"}
        f["verdict"] = v.get("verdict", "confirm")
        f["verify_reason"] = v.get("reason", "")
        f["duplicate_of"] = v.get("duplicate_of")
        if v.get("severity") in SEV_ORDER:
            f["severity_before"] = f["severity"]
            f["severity"] = v["severity"]
        if v.get("blocked_decision"):
            f["blocked_decision"] = v["blocked_decision"]
        if v.get("owner_question"):
            f["owner_question"] = v["owner_question"]
        # Код удерживает правила критичности независимо от мнения модели
        if f["severity"] == "critical":
            if not (f.get("blocked_decision") or "").strip():
                f["severity"] = "major"
                f["notes"].append("понижено: не названо блокируемое решение")
            elif f.get("criterion") == "set_consistent" and len(f["anchored"]) < 2:
                f["severity"] = "major"
                f["notes"].append("понижено: противоречие подтверждено только одной цитатой")
    return cand


def finalize(cand: List[Dict]) -> Dict[str, List[Dict]]:
    confirmed = [f for f in cand if f["verdict"] == "confirm"]
    questions = [f for f in cand if f["verdict"] == "question"]
    rejected = [f for f in cand if f["verdict"] == "reject"]
    dups = [f for f in cand if f["verdict"] == "duplicate"]
    ids = {f["cid"] for f in confirmed + questions}
    # дубль, чей «основной» не выжил, возвращаем в строй
    for f in dups:
        if f.get("duplicate_of") not in ids:
            f["verdict"] = "confirm"
            confirmed.append(f)
            ids.add(f["cid"])
    dups = [f for f in dups if f["verdict"] == "duplicate"]
    # итоговая нумерация: по критичности, затем по силе доказательства
    confirmed.sort(key=lambda f: (SEV_ORDER[f["severity"]], SRC_ORDER.get(f["source"], 9), f["cid"]))
    for n, f in enumerate(confirmed, start=1):
        f["fid"] = f"F-{n:02d}"
    for n, f in enumerate(questions, start=1):
        f["fid"] = f"Q-{n:02d}"
    cmap = {f["cid"]: f.get("fid") for f in confirmed + questions}
    for f in dups:
        f["dup_fid"] = cmap.get(f.get("duplicate_of"))
        main = next((m for m in confirmed + questions if m["cid"] == f.get("duplicate_of")), None)
        if main is not None:
            main.setdefault("also", []).append(f["source"])
            main["req_ids"] = sorted(set((main.get("req_ids") or []) + (f.get("req_ids") or [])))
    return {"confirmed": confirmed, "questions": questions, "rejected": rejected, "duplicates": dups}


# ---------------------------------------------------------------------------- 7. чек-лист
def checklist(llm: LLM, doc: Document, confirmed: List[Dict]) -> Dict:
    short = [{"id": f["fid"], "severity": f["severity"], "criterion": f.get("criterion"), "title": f.get("title")}
             for f in confirmed]
    try:
        data = llm.json(P.SYSTEM, P.checklist_prompt(doc.text, _j(short)), "7/7 чек-лист банка")
    except ValueError:
        return {"present": False, "error": "модель не вернула JSON"}
    if not isinstance(data, dict) or not data.get("present"):
        return {"present": False}
    valid = {f["fid"] for f in confirmed}
    for it in data.get("items", []):
        it["refs"] = [r for r in it.get("refs") or [] if r in valid]
        it["anchor"] = doc.locate(it.get("item", ""))
    return data


# ---------------------------------------------------------------------------- запуск целиком
def run(llm: LLM, doc: Document, use_model: bool = True) -> Dict[str, Any]:
    reqs = segment(llm, doc)
    if not reqs:
        say("    требований не найдено — дальнейшая проверка невозможна")
        rule_f = run_rules(doc)
        cand = gate(collect({}, {}, {}, [f for f in rule_f if f.get("pinned")], doc))
        for f in cand:
            f.update(verdict="confirm", verify_reason="закреплено правилом")
        fin = finalize(cand)
        return {"requirements": [], "reviews": {}, "set": {}, "model": {"applicable": False, "skipped": True},
                "candidates_total": len(cand), "no_evidence": [], **fin, "checklist": {"present": False},
                "no_requirements": True}
    reviews = review(llm, doc, reqs)
    set_rv = review_set(llm, doc, reqs)
    model = executable_model(llm, doc, reqs) if use_model else {"applicable": False, "skipped": True}
    say("  · 5/7 детерминированные правила и привязка цитат")
    rule_f = run_rules(doc)
    cand = collect(reviews, set_rv, model, rule_f, doc)
    total = len(cand)
    no_ev = [f for f in cand if not any(a["anchor"].found for a in f["anchored"])]
    kept = gate(cand)
    say(f"    кандидатов: {total}, без подтверждённой цитаты отброшено: {len(no_ev)}")
    kept = verify(llm, doc, kept)
    fin = finalize(kept)
    say(f"    подтверждено: {len(fin['confirmed'])}, вопросов владельцу: {len(fin['questions'])}, "
        f"отклонено: {len(fin['rejected'])}, дублей: {len(fin['duplicates'])}")
    chk = checklist(llm, doc, fin["confirmed"])
    return {"requirements": reqs, "reviews": reviews, "set": set_rv, "model": model,
            "candidates_total": total, "no_evidence": no_ev, **fin, "checklist": chk}


def run_baseline(llm: LLM, doc: Document) -> Dict[str, Any]:
    """Сравнительный режим: один сильный запрос к той же модели, без этапов агента."""
    data = llm.json(P.SYSTEM, P.baseline_prompt(doc.text), "baseline: один запрос", max_tokens=48000)
    findings = []
    for i, f in enumerate(data.get("findings", []), start=1):
        f = dict(f)
        f["source"] = "baseline"
        f["anchored"] = [{"text": q, "anchor": doc.locate(q)} for q in f.get("quotes") or [] if isinstance(q, str)]
        f["quotes_ok"] = sum(1 for a in f["anchored"] if a["anchor"].found)
        findings.append(f)
    return {"requirements": data.get("requirements", []), "findings": findings, "verdict": data.get("verdict", "")}
