"""Офлайн-тесты механики агента без обращения к LLM: чтение, привязка цитат, песочница,
конвейер с подставной моделью, сборка отчёта. Запуск: python -m unittest discover -s tests"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reqagent.ingest import load  # noqa: E402
from reqagent.llm import Usage, parse_json  # noqa: E402
from reqagent.pipeline import run  # noqa: E402
from reqagent.report import render  # noqa: E402
from reqagent.sandbox import UnsafeCode, check_code, run_model  # noqa: E402

DOC = ROOT / "docs" / "requirements.pdf"

MODEL_CODE = '''
def run(s, interp):
    spent = s.get("spent", 0)
    limit = s.get("limit")
    month = s.get("purchase_month")  # R-02: месяц по дате совершения покупки
    if s.get("kind") == "transfer":
        return {"counter": spent, "_trace": ["R-02"]}
    if limit is None:
        raise Undefined("порог не задан", ["R-01"])
    new = spent + s.get("amount", 0)
    return {"counter": new, "month": month, "push": 1 if spent < limit <= new else 0, "_trace": ["R-02", "R-03"]}
'''


class FakeLLM:
    provider, model, resolved_model, temperature = "fake", "fake", "fake-1", 0.0

    def __init__(self):
        self.usage = Usage()

    def json(self, system, user, stage, max_tokens=0):
        self.usage.calls += 1
        if stage.startswith("1/7"):
            return {"requirements": [
                {"doc_id": "Ф-2", "section": "ФТ", "type": "функциональное", "summary": "месяц по дате покупки",
                 "quote": "Месяц определяется по дате совершения покупки в Алматы."},
                {"doc_id": "Ф-3", "section": "ФТ", "type": "функциональное", "summary": "push при достижении",
                 "quote": "Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push."},
                {"doc_id": None, "section": "Критерии", "type": "критерий приёмки", "summary": "переход месяца",
                 "quote": "Февральский счётчик вырос на 4 000 ₸"}]}
        if stage.startswith("2/7"):
            return {"reviews": [{"id": "R-01", "criteria": {"necessary": "ok", "unambiguous": "issue"},
                                 "findings": [{"criterion": "unambiguous", "severity": "major", "title": "Выдумка",
                                               "quotes": ["этой цитаты нет в документе"], "problem": "x"}]}]}
        if stage.startswith("3/7"):
            return {"set_criteria": {"set_consistent": {"verdict": "issue", "comment": "см."}}, "findings": [
                {"criterion": "set_consistent", "severity": "critical", "req_ids": ["R-01", "R-03"],
                 "title": "Месяц покупки против критерия", "quotes": ["Месяц определяется по дате совершения покупки в Алматы",
                                                                      "Февральский счётчик вырос на 4 000 ₸"],
                 "problem": "Январь против февраля", "blocked_decision": "ожидаемый результат теста", "fix": "выбрать"}]}
        if stage.startswith("4/7 сценарии"):
            return {"applicable": True, "summary": "счётчик", "outputs": {"month": "месяц учёта"},
                    "interpretations": [], "scenarios": [
                        {"id": "S1", "source": "acceptance", "title": "переход месяца",
                         "quote": "Покупка 31 января в 23:58 на 4 000 ₸", "targets": ["R-01"],
                         "situation": "покупка 31.01 23:58, проведена 01.02 00:03",
                         "input": {"spent": 0, "limit": 50000, "amount": 4000, "purchase_month": "2026-01",
                                   "purchase_day": 31, "time": "23:58"},
                         "expected": {"month": "2026-02"}},
                        {"id": "S2", "source": "boundary", "title": "без порога", "input": {"amount": 1},
                         "situation": "порог не задан", "expected": None, "targets": ["R-02"]}]}
        if stage.startswith("4/7 трассировка"):
            assert "Февральский" not in user.split("Ситуации:")[1].split("Выделенные требования")[0]
            return {"traces": [
                {"id": "S1", "rule_outcomes": [{"req_id": "R-01", "quote": "Месяц определяется по дате совершения покупки в Алматы",
                                                "outcome": "январь"}],
                 "derived": "январь", "conflict": False, "undetermined": "",
                 "blocked_decision": "ожидаемый результат"},
                {"id": "S2", "rule_outcomes": [], "derived": "", "acceptance": "n/a", "conflict": False,
                 "undetermined": "порог не задан"}]}
        if stage.startswith("4/7 сравнение"):
            return {"verdicts": [{"id": "S1", "verdict": "mismatch", "difference": "месяц"}]}
        if stage.startswith("4/7 код"):
            assert '"expected"' not in user.split("Сценарии и выходы:")[1].split("Выделенные требования")[0]
            return {"rules": [], "code": MODEL_CODE}
        if stage.startswith("6/7"):
            data = json.loads(user.split("Черновые замечания:\n", 1)[1].split("\n\nДокумент:", 1)[0])
            return {"verdicts": [{"id": d["id"], "verdict": "confirm", "severity": d["severity"],
                                  "reason": "ok", "blocked_decision": "что ожидать в тесте"} for d in data]}
        if stage.startswith("7/7"):
            return {"present": True, "items": [{"item": "Поддерживается версионность документа / зафиксирована",
                                                "available": "Нет", "passed": "Нет", "refs": ["F-01"], "comment": "нет версии"}]}
        raise AssertionError(stage)


class Offline(unittest.TestCase):
    def test_anchor_pdf(self):
        d = load(DOC)
        a = d.locate("Месяц определяется по дате совершения покупки в Алматы")
        self.assertTrue(a.found)
        self.assertEqual(a.page, 1)
        self.assertFalse(d.locate("Месяц определяется по дате проведения покупки").found)

    def test_sandbox_blocks(self):
        for bad in ["import os", "open('x')", "().__class__", "__import__('os')", "eval('1')"]:
            with self.assertRaises(UnsafeCode):
                check_code(bad)

    def test_sandbox_runs(self):
        runs = run_model(MODEL_CODE, [{"id": "S", "input": {"spent": 1, "limit": 2, "amount": 1}}], [])
        self.assertEqual(runs[0]["status"], "ok")
        self.assertEqual(runs[0]["result"]["push"], 1)

    def test_pipeline_end_to_end(self):
        d = load(DOC)
        llm = FakeLLM()
        res = run(llm, d)
        self.assertIn("Выдумка", [f["title"] for f in res["no_evidence"]])   # выдуманная цитата отброшена
        crit = [f for f in res["confirmed"] if f["severity"] == "critical"]
        both = [f for f in crit if f["source"] == "oracle" and "вычисление" in f.get("methods", "")]
        self.assertTrue(both)   # трассировка и вычисление модели подтвердили одно и то же расхождение
        self.assertTrue(any(f["criterion"] == "complete" for f in res["confirmed"]))
        md = render(d, res, {"Документ": d.title})
        self.assertIn("## 2. Как агент нарезал требования", md)
        self.assertIn("Чек-лист", md)
        with tempfile.TemporaryDirectory() as t:
            Path(t, "r.md").write_text(md, encoding="utf-8")

    def test_parse_json(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})


if __name__ == "__main__":
    unittest.main()


class EmptyLLM(FakeLLM):
    def json(self, system, user, stage, max_tokens=0):
        if stage.startswith("1/7"):
            return {"requirements": []}
        raise AssertionError("после пустой нарезки модель вызываться не должна: " + stage)


class NotRequirements(unittest.TestCase):
    def test_recipe_gives_impossible_verdict(self):
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "eval" / "make_damaged.py")], check=True, capture_output=True)
        d = load(ROOT / "eval" / "fixtures" / "damaged" / "recipe_not_requirements.md")
        res = run(EmptyLLM(), d)
        md = render(d, res, {"Документ": d.title})
        self.assertIn("проверка невозможна", md)
        self.assertNotIn("готов к разработке", md)

    def test_injection_survives_without_requirements(self):
        d = load(ROOT / "eval" / "fixtures" / "damaged" / "injection.md")
        res = run(EmptyLLM(), d)
        self.assertTrue(any(f["criterion"] == "injection" for f in res["confirmed"]))
