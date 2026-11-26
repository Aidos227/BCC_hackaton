"""Входной контроль на испорченных файлах и ротация ключей — без обращения к LLM.
Файлы создаёт eval/make_damaged.py (тест сам вызывает генератор)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lsj.ingest import IntakeError, load  # noqa: E402
from lsj.llm import LLM, LLMError  # noqa: E402
from lsj.rules import run_rules  # noqa: E402

DMG = ROOT / "eval" / "fixtures" / "damaged"

# файл → (ожидаемый статус, фрагмент диагноза)
EXPECT = {
    "truncated_head.pdf": ("unreadable", "повреждён или обрезан"),
    "truncated_tail.pdf": ("unreadable", "повреждён или обрезан"),
    "encrypted_password.pdf": ("unreadable", "паролем"),
    "encrypted_nopassword.pdf": ("ok", "расшифрован"),
    "scan_no_text.pdf": ("unreadable", "не извлечён текст"),
    "partial_scan.pdf": ("partial", "стр. 3: нет текстового слоя"),
    "image_renamed.pdf": ("unreadable", "изображение"),
    "binary_renamed.md": ("unreadable", "двоичный"),
    "empty.md": ("unreadable", "пустой"),
    "cp1251.md": ("ok", "Windows-1251"),
    "mojibake.md": ("unreadable", "нечитаем"),
    "broken.docx": ("unreadable", "DOCX повреждён"),
}


class Intake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "eval" / "make_damaged.py")], check=True, capture_output=True)

    def test_each_damaged_file_gets_a_diagnosis(self):
        for name, (status, hint) in EXPECT.items():
            with self.subTest(name):
                try:
                    d = load(DMG / name)
                    got, text = d.intake.status, "; ".join(d.intake.problems)
                except IntakeError as e:
                    got, text = e.intake.status, str(e)
                self.assertEqual(got, status, text)
                self.assertIn(hint, text)

    def test_cli_writes_report_even_for_unreadable_file(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "r.md"
            env = {**os.environ, "GEMINI_API_KEY": "x"}
            r = subprocess.run([sys.executable, "-m", "lsj", str(DMG / "truncated_head.pdf"), str(out)],
                               cwd=ROOT, capture_output=True, env=env)
            self.assertEqual(r.returncode, 4)
            self.assertNotIn(b"Traceback", r.stderr)
            md = out.read_text(encoding="utf-8")
            self.assertIn("проверка невозможна", md)
            self.assertIn("Входной контроль", md)

    def test_injection_is_detected_and_pinned(self):
        f = [x for x in run_rules(load(DMG / "injection.md")) if x["criterion"] == "injection"]
        self.assertEqual(len(f), 1)
        self.assertTrue(f[0]["pinned"])
        self.assertEqual(f[0]["severity"], "critical")
        clean = [x for x in run_rules(load(ROOT / "docs" / "requirements.pdf")) if x["criterion"] == "injection"]
        self.assertEqual(clean, [])


class KeyRotation(unittest.TestCase):
    def test_quota_on_first_key_switches_to_second(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ.update({"GEMINI_API_KEY": "k-one,k-two", "LLM_DEBUG_DIR": t, "LLM_PROVIDER": "gemini",
                               "GEMINI_FALLBACK_MODELS": "", "LLM_MAX_RETRIES": "0"})
            llm = LLM(verbose=False)
            used = []

            def fake(system, user, max_tokens, want_json):
                key = llm.keys[llm.key_index]
                used.append(key)
                if key == "k-one":
                    raise LLMError("HTTP 429: You exceeded your current quota")
                return '{"ok": 1}', 1, 1

            llm._gemini = fake
            self.assertEqual(llm.json("s", "u", "t"), {"ok": 1})
            self.assertEqual(used, ["k-one", "k-two"])
            used.clear()
            llm.json("s", "u2", "t")            # первый ключ «остужен» — сразу второй
            self.assertEqual(used, ["k-two"])
            for k in ("GEMINI_API_KEY", "LLM_DEBUG_DIR", "LLM_PROVIDER", "GEMINI_FALLBACK_MODELS", "LLM_MAX_RETRIES"):
                os.environ.pop(k, None)


if __name__ == "__main__":
    unittest.main()
