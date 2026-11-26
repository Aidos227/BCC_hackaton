"""Чтение входного документа (PDF / MD / TXT / DOCX) и привязка цитат к месту в источнике.

Привязка цитат выполняется кодом, а не моделью: каждая цитата, которую вернула модель,
ищется в тексте документа после нормализации пробелов, кавычек, тире и регистра.
Найденная цитата получает страницу и строку; ненайденная помечается как непроверенная.
"""
from __future__ import annotations

import re
import unicodedata
import zipfile
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class Line:
    page: int          # 1-based; для MD/TXT всегда 1
    number: int        # 1-based номер строки внутри страницы (для MD — внутри файла)
    text: str


@dataclass
class Anchor:
    found: bool
    page: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    exact: bool = False   # True — найдено целиком; False — найдено по частям через «…»

    def label(self, kind: str) -> str:
        if not self.found:
            return "цитата не найдена"
        loc = f"стр. {self.page}, " if kind == "pdf" else ""
        if self.line_start == self.line_end:
            return f"{loc}строка {self.line_start}"
        return f"{loc}строки {self.line_start}–{self.line_end}"


@dataclass
class Document:
    path: Path
    kind: str                      # pdf | md | txt | docx
    title: str
    lines: List[Line]
    pages: int
    intake: "Intake" = field(default=None, repr=False)  # type: ignore[assignment]
    _norm: str = field(default="", repr=False)
    _map: List[int] = field(default_factory=list, repr=False)   # индекс символа norm -> индекс строки

    @property
    def text(self) -> str:
        """Текст с разметкой страниц и номеров строк — то, что видит модель."""
        out, cur = [], None
        for ln in self.lines:
            if self.kind == "pdf" and ln.page != cur:
                cur = ln.page
                out.append(f"=== Страница {cur} ===")
            out.append(ln.text)
        return "\n".join(out)

    @property
    def plain(self) -> str:
        return "\n".join(l.text for l in self.lines)

    def build_index(self) -> None:
        chars, mapping = [], []
        for i, ln in enumerate(self.lines):
            n = normalize(ln.text)
            if not n:
                continue
            if chars:
                chars.append(" ")
                mapping.append(i)
            chars.extend(n)
            mapping.extend([i] * len(n))
        self._norm = "".join(chars)
        self._map = mapping

    def locate(self, quote: str) -> Anchor:
        if not self._norm:
            self.build_index()
        q = normalize(quote)
        if len(q) < 3:
            return Anchor(False)
        pos = self._norm.find(q)
        if pos >= 0:
            return self._anchor(pos, pos + len(q) - 1, exact=True)
        # Цитата с пропусками: части через «…» или «...» должны идти по порядку.
        parts = [p.strip() for p in re.split(r"…|\.\.\.", quote) if len(normalize(p)) >= 6]
        if len(parts) >= 2:
            start, cursor, first = None, 0, None
            for p in parts:
                np_ = normalize(p)
                k = self._norm.find(np_, cursor)
                if k < 0:
                    return Anchor(False)
                if first is None:
                    first = k
                cursor = k + len(np_)
            return self._anchor(first, cursor - 1, exact=False)
        return Anchor(False)

    def _anchor(self, a: int, b: int, exact: bool) -> Anchor:
        la, lb = self.lines[self._map[a]], self.lines[self._map[b]]
        return Anchor(True, la.page, la.number, lb.number if lb.page == la.page else la.number, exact)


logging.getLogger("pypdf").setLevel(logging.ERROR)   # предупреждения о повреждениях идут в диагноз, а не в консоль

_QUOTES = dict.fromkeys(map(ord, "«»„“”‟\"'`’‘‚"), None)
_DASHES = {ord(c): "-" for c in "‐‑‒–—―−"}


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("­", "").replace("ё", "е").replace("Ё", "Е")
    s = s.translate(_QUOTES).translate(_DASHES)
    s = re.sub(r"[*_`|#>•]", " ", s)            # разметка Markdown и маркеры списков
    s = re.sub(r"(?<=\d)\s+(?=\d{3}\b)", "", s)  # 1 000 000 -> 1000000
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\s+([.,;:!?)])", r"\1", s)
    s = re.sub(r"([(])\s+", r"\1", s)
    return s


class IntakeError(Exception):
    """Документ нельзя проверить. Несёт диагноз входного контроля для отчёта."""

    def __init__(self, intake: "Intake"):
        super().__init__("; ".join(intake.problems) or "документ не прочитан")
        self.intake = intake


@dataclass
class Intake:
    """Входной контроль: что именно агент смог прочитать и насколько можно доверять тексту."""
    status: str = "ok"                 # ok | partial | unreadable
    detected: str = ""                 # что за файл по содержимому
    encoding: str = ""
    size: int = 0
    pages_declared: Optional[int] = None
    pages_with_text: int = 0
    chars: int = 0
    readable_ratio: float = 1.0
    bad_pages: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    advice: List[str] = field(default_factory=list)

    def degrade(self, problem: str, advice: str = "") -> None:
        if self.status == "ok":
            self.status = "partial"
        self.problems.append(problem)
        if advice and advice not in self.advice:
            self.advice.append(advice)

    def fail(self, problem: str, advice: str = "") -> "IntakeError":
        self.status = "unreadable"
        self.problems.append(problem)
        if advice and advice not in self.advice:
            self.advice.append(advice)
        return IntakeError(self)


def sniff(head: bytes) -> str:
    if b"%PDF" in head[:1024]:
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    if head.startswith((b"\xd0\xcf\x11\xe0",)):
        return "ole"          # старый .doc / .xls
    if head[:4] in (b"\x89PNG", b"GIF8") or head[:3] == b"\xff\xd8\xff":
        return "image"
    return "text"


def text_quality(text: str) -> Tuple[float, int, int]:
    """Доля «нормальных» символов, число (cid:N) и символов-заменителей."""
    cid = len(re.findall(r"\(cid:\d+\)", text))
    repl = text.count("\ufffd")
    body = [c for c in text if not c.isspace()]
    if not body:
        return 0.0, cid, repl
    good = sum(1 for c in body if c.isalnum() or c in ".,;:!?()[]{}«»\"'-–—/\\%№₸$€+=<>*#|_@&^~`→•…")
    ok_ratio = good / len(body)
    if cid:
        ok_ratio = min(ok_ratio, 1 - min(1.0, cid * 8 / max(1, len(body))))
    return ok_ratio, cid, repl


def _read_pdf(path: Path, intake: Intake) -> Tuple[List[Line], int]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
    reader = None
    try:
        reader = PdfReader(str(path), strict=True)
        if not reader.is_encrypted:
            _ = len(reader.pages)
    except Exception:
        try:
            reader = PdfReader(str(path), strict=False)
            if not reader.is_encrypted:
                _ = len(reader.pages)
            intake.degrade("структура PDF повреждена; файл прочитан в щадящем режиме, часть содержимого может быть потеряна",
                           "Запросить у автора исходный PDF заново.")
        except Exception as e:
            raise intake.fail(f"PDF не открывается — файл повреждён или обрезан ({type(e).__name__}: {str(e)[:120]})",
                              "Проверить, что файл скачан полностью; запросить исходный PDF.")
    if reader.is_encrypted:
        try:
            ok = reader.decrypt("")
        except Exception as e:
            if "cryptography" in str(e).lower():
                raise intake.fail("PDF зашифрован алгоритмом AES; для расшифровки нужен пакет cryptography",
                                  "Выполнить: python -m pip install cryptography — и повторить запуск.")
            ok = 0
        if not ok:
            raise intake.fail("PDF защищён паролем на открытие", "Снять пароль или прислать незащищённую копию.")
        intake.problems.append("PDF был зашифрован без пароля на открытие — расшифрован автоматически")
    try:
        n_pages = len(reader.pages)
    except Exception:
        n_pages = 0
    intake.pages_declared = n_pages
    lines: List[Line] = []
    all_text = []
    for pno in range(1, n_pages + 1):
        try:
            raw = reader.pages[pno - 1].extract_text() or ""
        except (PyPdfError, Exception) as e:
            intake.bad_pages.append(f"стр. {pno}: не извлекается ({type(e).__name__})")
            continue
        ratio, cid, repl = text_quality(raw)
        if len(raw.strip()) < 15:
            intake.bad_pages.append(f"стр. {pno}: нет текстового слоя (скан или пустая)")
            continue
        if ratio < 0.6 or cid > 5 or repl > 5:
            intake.bad_pages.append(f"стр. {pno}: текст искажён (сломанная кодировка шрифта)")
            continue
        intake.pages_with_text += 1
        all_text.append(raw)
        n = 0
        for t in raw.splitlines():
            t = re.sub(r"[ \t]+", " ", t).strip()
            if not t:
                continue
            n += 1
            lines.append(Line(pno, n, t))
    if intake.bad_pages:
        intake.degrade(f"не использованы страницы: {'; '.join(intake.bad_pages)}",
                       "Для сканов — распознать текст (OCR); для искажённых страниц — пересохранить PDF из исходника.")
    return lines, n_pages


def _read_docx(path: Path, intake: Intake) -> Tuple[List[Line], int]:
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                intake.degrade(f"архив DOCX повреждён (файл {bad})", "Пересохранить документ в Word.")
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except zipfile.BadZipFile:
        raise intake.fail("DOCX повреждён: это не корректный zip-архив", "Пересохранить документ в Word.")
    except KeyError:
        raise intake.fail("в архиве нет word/document.xml — это не документ Word", "Прислать .docx, .pdf или .md.")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
    lines, n = [], 0
    for p in paras:
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, flags=re.S))
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            n += 1
            lines.append(Line(1, n, t))
    return lines, 1


def _decode_text(data: bytes, intake: Intake) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        intake.encoding = "utf-16"
        return data.decode("utf-16", "replace")
    ctrl = sum(1 for b in data[:20000] if b < 32 and b not in (9, 10, 13))
    if b"\x00" in data[:20000] or ctrl > len(data[:20000]) // 100:
        raise intake.fail("файл двоичный, а не текстовый (управляющие байты)", "Проверить, тот ли файл передан.")
    try:
        intake.encoding = "utf-8"
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    txt = data.decode("cp1251", "replace")
    intake.encoding = "cp1251"
    intake.problems.append("файл не в UTF-8; прочитан как Windows-1251")
    return txt


def load(path: str | Path) -> Document:
    """Чтение с входным контролем. Непредвиденная ошибка разбора тоже становится диагнозом, а не трейсбеком."""
    try:
        return _load(path)
    except (IntakeError, FileNotFoundError):
        raise
    except Exception as e:
        intake = Intake()
        raise intake.fail(f"файл не удалось разобрать: {type(e).__name__}: {str(e)[:160]}",
                          "Пересохранить документ в PDF или Markdown и повторить.")


def _load(path: str | Path) -> Document:
    p = Path(path)
    intake = Intake()
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    if p.is_dir():
        raise FileNotFoundError(f"Это папка, а не файл: {p}")
    data = p.read_bytes()
    intake.size = len(data)
    if not data.strip():
        raise intake.fail("файл пустой", "Проверить, тот ли файл передан.")
    ext = p.suffix.lower()
    real = sniff(data[:2048])
    intake.detected = {"pdf": "PDF", "zip": "zip-архив (DOCX)", "ole": "старый формат Office (.doc/.xls)",
                       "image": "изображение", "text": "текст"}[real]
    expected = {".pdf": "pdf", ".docx": "zip", ".md": "text", ".markdown": "text", ".txt": "text"}.get(ext)
    if expected is None and real == "text":
        expected = "text"
    if expected and real != expected:
        intake.problems.append(f"расширение {ext or '(нет)'} не соответствует содержимому: это {intake.detected}")
    if real == "ole":
        raise intake.fail("старый формат .doc/.xls не поддерживается", "Сохранить как .docx или PDF.")
    if real == "image":
        raise intake.fail("это изображение, а не документ с текстом", "Прислать PDF/DOCX с текстом или распознать (OCR).")
    if real == "pdf":
        lines, pages = _read_pdf(p, intake)
        kind = "pdf"
    elif real == "zip":
        lines, pages = _read_docx(p, intake)
        kind = "docx"
    else:
        raw = _decode_text(data, intake)
        ratio, _, repl = text_quality(raw)
        if ratio < 0.6 or repl > max(5, len(raw) // 200):
            raise intake.fail("текст нечитаем (неизвестная кодировка или двоичные данные)",
                              "Сохранить документ в UTF-8 или прислать PDF.")
        lines = [Line(1, i, t.rstrip()) for i, t in enumerate(raw.splitlines(), start=1)]
        pages = 1
        kind = "md" if ext in (".md", ".markdown") else "txt"
        intake.pages_with_text = 1
    text = "\n".join(l.text for l in lines)
    intake.chars = len(text)
    intake.readable_ratio = round(text_quality(text)[0], 3)
    if not any(l.text.strip() for l in lines):
        raise intake.fail("из документа не извлечён текст (скан без текстового слоя или пустые страницы)",
                          "Распознать текст (OCR) или прислать документ с текстовым слоем.")
    title = next((re.sub(r"^#+\s*", "", l.text).strip() for l in lines if l.text.strip()), p.stem)
    doc = Document(p, kind, title, lines, pages)
    doc.intake = intake
    doc.build_index()
    return doc
