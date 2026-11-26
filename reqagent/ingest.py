"""Чтение входного документа (PDF / MD / TXT / DOCX) и привязка цитат к месту в источнике.

Привязка цитат выполняется кодом, а не моделью: каждая цитата, которую вернула модель,
ищется в тексте документа после нормализации пробелов, кавычек, тире и регистра.
Найденная цитата получает страницу и строку; ненайденная помечается как непроверенная.
"""
from __future__ import annotations

import re
import unicodedata
import zipfile
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


def _read_pdf(path: Path) -> Tuple[List[Line], int]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    lines: List[Line] = []
    for pno, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        n = 0
        for t in raw.splitlines():
            t = re.sub(r"[ \t]+", " ", t).strip()
            if not t:
                continue
            n += 1
            lines.append(Line(pno, n, t))
    return lines, len(reader.pages)


def _read_docx(path: Path) -> Tuple[List[Line], int]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
    lines, n = [], 0
    for p in paras:
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, flags=re.S))
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            n += 1
            lines.append(Line(1, n, t))
    return lines, 1


def load(path: str | Path) -> Document:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    ext = p.suffix.lower()
    if ext == ".pdf":
        lines, pages = _read_pdf(p)
        kind = "pdf"
    elif ext == ".docx":
        lines, pages = _read_docx(p)
        kind = "docx"
    elif ext in (".md", ".markdown", ".txt"):
        raw = p.read_text(encoding="utf-8-sig")
        lines = [Line(1, i, t.rstrip()) for i, t in enumerate(raw.splitlines(), start=1)]
        pages = 1
        kind = "md" if ext != ".txt" else "txt"
    else:
        raise ValueError(f"Формат {ext} не поддерживается. Поддерживаются: .pdf, .md, .txt, .docx")
    if not any(l.text.strip() for l in lines):
        raise ValueError("Из документа не извлечён текст (возможно, это скан без текстового слоя).")
    title = next((re.sub(r"^#+\s*", "", l.text).strip() for l in lines if l.text.strip()), p.stem)
    doc = Document(p, kind, title, lines, pages)
    doc.build_index()
    return doc
