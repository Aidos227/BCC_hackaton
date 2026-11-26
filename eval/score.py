"""Скорер без LLM: сопоставляет замечания с заранее размеченными дефектами по цитатам.

Дефект считается найденным, если у одного замечания среди ПОДТВЕРЖДЁННЫХ кодом цитат
(найденных в документе) есть фрагмент из каждой группы якорей, а если заданы ключевые слова —
хотя бы одно из них встречается в тексте замечания. Выдуманные цитаты не засчитываются ни агенту,
ни сравниваемому одиночному запросу.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lsj.ingest import normalize  # noqa: E402


def findings_of(result: Dict) -> List[Dict]:
    """Единый вид замечаний для агента (confirmed) и baseline (findings)."""
    if "confirmed" in result:
        fs = result["confirmed"] + result.get("questions", [])
    else:
        fs = result.get("findings", [])
    out = []
    for f in fs:
        anchored = f.get("anchored") or []
        good = [a["text"] for a in anchored if (a.get("anchor") or {}).get("found")]
        out.append({"severity": f.get("severity"), "quotes_all": len(anchored), "quotes_good": good,
                    "text": " ".join(str(f.get(k) or "") for k in ("title", "problem", "owner_question", "evidence"))})
    return out


def hit(f: Dict, d: Dict) -> bool:
    q = " ‖ ".join(normalize(x) for x in f["quotes_good"])
    for group in d["groups"]:
        if not any(normalize(a) in q for a in group):
            return False
    if d["keywords"]:
        import re
        t = normalize(f["text"] + " " + q)
        # ключевое слово — с начала слова (get не должен совпадать с target)
        if not any(re.search(r"(?<![\w])" + re.escape(normalize(k)), t) for k in d["keywords"]):
            return False
    return bool(d["groups"] or d["keywords"]) and bool(f["quotes_good"] or not d["groups"])


def score(result: Dict, key: Dict) -> Dict:
    fs = findings_of(result)
    found = {}
    for d in key["defects"]:
        m = [f for f in fs if hit(f, d)]
        found[d["id"]] = {"hit": bool(m), "critical": any(f["severity"] == "critical" for f in m)}
    violations = []
    for d in key.get("absent", []):
        m = [f for f in fs if hit(f, d) and f["severity"] in ("critical", "major")]
        if m:
            violations.append(d["id"])
    total_q = sum(f["quotes_all"] for f in fs)
    good_q = sum(len(f["quotes_good"]) for f in fs)
    crit_exp = [d["id"] for d in key["defects"] if d.get("critical_expected")]
    return {
        "recall": sum(v["hit"] for v in found.values()) / max(1, len(found)),
        "found": found,
        "critical_recall": (sum(found[i]["critical"] for i in crit_exp) / len(crit_exp)) if crit_exp else None,
        "absent_violations": violations,
        "absent_total": len(key.get("absent", [])),
        "findings": len(fs),
        "critical": sum(1 for f in fs if f["severity"] == "critical"),
        "quote_validity": good_q / total_q if total_q else 1.0,
        "findings_without_valid_quote": sum(1 for f in fs if f["quotes_all"] and not f["quotes_good"]),
    }


if __name__ == "__main__":
    res = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    key = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(score(res, key), ensure_ascii=False, indent=1))
