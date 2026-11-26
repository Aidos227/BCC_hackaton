"""Тонкий клиент к LLM без SDK (только стандартная библиотека).

Провайдеры:
  gemini     — Google AI Studio (бесплатный тариф), ключ GEMINI_API_KEY
  anthropic  — Claude API, ключ ANTHROPIC_API_KEY
  openai     — любой OpenAI-совместимый endpoint (OpenAI, OpenRouter, Ollama, LM Studio…),
               ключ OPENAI_API_KEY, адрес OPENAI_BASE_URL
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MODELS = {
    "gemini": "gemini-3.6-flash",
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o-mini",
}


class LLMError(RuntimeError):
    pass


def load_dotenv(path: str | Path = ".env") -> None:
    """Минимальный загрузчик .env: KEY=VALUE, без перезаписи уже заданных переменных."""
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def detect_provider() -> str:
    explicit = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEYS") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL"):
        return "openai"
    raise LLMError(
        "Не найден ключ модели. Скопируйте .env.example в .env и впишите GEMINI_API_KEY "
        "(бесплатно: https://aistudio.google.com/apikey)."
    )


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    log: List[Dict[str, Any]] = field(default_factory=list)


class LLM:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None,
                 cache_dir: Optional[str] = None, temperature: Optional[float] = None, verbose: bool = True):
        self.provider = provider or detect_provider()
        if self.provider not in DEFAULT_MODELS:
            raise LLMError(f"Неизвестный провайдер: {self.provider}")
        env_model = {"gemini": "GEMINI_MODEL", "anthropic": "ANTHROPIC_MODEL", "openai": "OPENAI_MODEL"}[self.provider]
        self.model = model or os.environ.get(env_model) or DEFAULT_MODELS[self.provider]
        self.primary = self.model
        self.resolved_model = self.model   # реальная версия, которую вернул API
        self.models_used: List[str] = []
        raw_keys = os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self.keys = [k.strip() for k in raw_keys.replace(";", ",").split(",") if k.strip()] if self.provider == "gemini" else []
        self.key_index = 0
        self.cooldown: Dict[str, float] = {}
        fb_env = {"gemini": "GEMINI_FALLBACK_MODELS", "anthropic": "ANTHROPIC_FALLBACK_MODELS",
                  "openai": "OPENAI_FALLBACK_MODELS"}[self.provider]
        self.fallbacks = [m.strip() for m in os.environ.get(fb_env, "").split(",") if m.strip() and m.strip() != self.model]
        self.temperature = float(os.environ.get("LLM_TEMPERATURE", "0") if temperature is None else temperature)
        self.timeout = float(os.environ.get("LLM_TIMEOUT_SEC", "300"))
        self.max_retries = int(os.environ.get("LLM_MAX_RETRIES", "5"))
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.usage = Usage()
        self.verbose = verbose

    # ------------------------------------------------------------------ public
    def json(self, system: str, user: str, stage: str, max_tokens: int = 32000) -> Any:
        """Запрос, ответ которого обязан быть JSON. Одна повторная попытка при битом JSON."""
        text = self.complete(system, user, stage, max_tokens=max_tokens, want_json=True)
        try:
            return parse_json(text)
        except ValueError:
            self._dump(stage, text)
            fix = (user + "\n\nПредыдущий ответ не был корректным JSON. Верни ТОЛЬКО корректный JSON "
                   "по той же схеме, без пояснений и без ```.")
            text = self.complete(system, fix, stage + ":retry", max_tokens=max_tokens, want_json=True)
            try:
                return parse_json(text)
            except ValueError:
                self._dump(stage + "-retry", text)
                raise

    def _slot(self, model: str, k: int) -> str:
        """Имя слота «модель + ключ» для журнала остывания; сам ключ не пишется — только короткий хеш."""
        if not self.keys:
            return model
        return model + "#" + hashlib.sha256(self.keys[k].encode()).hexdigest()[:8]

    def _cd_path(self) -> Path:
        return Path(os.environ.get("LLM_DEBUG_DIR", ".cache")) / "cooldown.json"

    def _load_cooldown(self) -> None:
        try:
            data = json.loads(self._cd_path().read_text(encoding="utf-8"))
            for k, v in data.items():
                self.cooldown[k] = max(self.cooldown.get(k, 0), float(v))
        except (OSError, ValueError):
            pass

    def _save_cooldown(self) -> None:
        try:
            self._cd_path().parent.mkdir(parents=True, exist_ok=True)
            self._cd_path().write_text(json.dumps(self.cooldown), encoding="utf-8")
        except OSError:
            pass

    def _dump(self, stage: str, text: str) -> None:
        d = Path(os.environ.get("LLM_DEBUG_DIR", ".cache/raw"))
        try:
            d.mkdir(parents=True, exist_ok=True)
            name = re.sub(r"[^\w-]+", "_", stage)[:60]
            (d / f"{int(time.time())}_{name}.txt").write_text(text, encoding="utf-8")
            self._say(f"    ответ модели не JSON (сохранён в {d})")
        except OSError:
            pass

    def complete(self, system: str, user: str, stage: str, max_tokens: int = 32000,
                 want_json: bool = False) -> str:
        key = hashlib.sha256(json.dumps([self.provider, self.model, system, user, self.temperature],
                                        ensure_ascii=False).encode()).hexdigest()[:24]
        if self.cache_dir:
            cp = self.cache_dir / f"{key}.json"
            if cp.exists():
                data = json.loads(cp.read_text(encoding="utf-8"))
                self.resolved_model = data.get("model", self.resolved_model)
                self._say(f"  · {stage}: ответ из кэша")
                return data["text"]
        t0 = time.time()
        self._say(f"  · {stage}: запрос к {self.provider} …")
        fn = {"gemini": self._gemini, "anthropic": self._anthropic, "openai": self._openai}[self.provider]
        chain = [self.primary] + [m for m in self.fallbacks if m != self.primary]
        nkeys = max(1, len(self.keys))
        slots = [(m, k) for m in chain for k in range(nkeys)]
        last_err: Optional[LLMError] = None
        now = time.time()
        self._load_cooldown()
        live = [sl for sl in slots if self.cooldown.get(self._slot(*sl), 0) <= now] or slots[-1:]
        for i, (m, k) in enumerate(live):
            if self.cooldown.get(self._slot(m, k), 0) > time.time() and i < len(live) - 1:
                continue   # слот уже «остужен» в этом же вызове (например, 503 для всей модели)
            self.model, self.key_index = m, k
            # основной слот и последний запасной — с повторами, промежуточные — по одному разу
            last = i == len(live) - 1
            self._attempts = (max(self.max_retries, 5) + 1) if last else (self.max_retries + 1 if i == 0 else 1)
            if i:
                self._say(f"    пробую {m}" + (f" (ключ №{k + 1})" if nkeys > 1 else ""))
                t0 = time.time()
            try:
                text, tin, tout = fn(system, user, max_tokens, want_json)
                break
            except LLMError as e:
                last_err = e
                if getattr(e, "fatal", False) and nkeys == 1:
                    raise
                msg = str(e).lower()
                if "quota" in msg or getattr(e, "fatal", False):
                    # квота и отказ в доступе — свойство ключа: остужаем только этот ключ
                    self.cooldown[self._slot(m, k)] = time.time() + 3600
                elif "не найдена" in msg:
                    # модели нет у провайдера — это свойство модели, остужаем на всех ключах на сутки
                    for kk in range(nkeys):
                        self.cooldown[self._slot(m, kk)] = time.time() + 86400
                else:
                    # перегрузка (503) кратковременна и зависит от запроса: короткая пауза только для этого слота
                    self.cooldown[self._slot(m, k)] = time.time() + 120
                self._save_cooldown()
                self._say(f"    {m}" + (f" (ключ №{k + 1})" if nkeys > 1 else "") + f": {' '.join(str(e).split())[:200]}")
        else:
            raise last_err  # type: ignore[misc]
        if self.resolved_model not in self.models_used:
            self.models_used.append(self.resolved_model)
        dt = time.time() - t0
        self.usage.calls += 1
        self.usage.input_tokens += tin
        self.usage.output_tokens += tout
        self.usage.seconds += dt
        self.usage.log.append({"stage": stage, "model": self.resolved_model, "in": tin, "out": tout, "sec": round(dt, 1)})
        self._say(f"    готово за {dt:.0f} с, {self.resolved_model} (токены: вход {tin}, выход {tout})")
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(
                json.dumps({"text": text, "model": self.resolved_model}, ensure_ascii=False), encoding="utf-8")
        return text

    # --------------------------------------------------------------- providers
    def _gemini(self, system, user, max_tokens, want_json):
        if not self.keys:
            raise LLMError("GEMINI_API_KEY не задан")
        key = self.keys[self.key_index % len(self.keys)]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        cfg: Dict[str, Any] = {"temperature": self.temperature, "maxOutputTokens": max_tokens}
        if want_json:
            cfg["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": cfg,
        }
        data = self._post(url, body, {"x-goog-api-key": key})
        self.resolved_model = data.get("modelVersion", self.model)
        cands = data.get("candidates") or []
        if not cands:
            raise LLMError(f"Gemini не вернул ответ: {json.dumps(data, ensure_ascii=False)[:500]}")
        parts = cands[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        fr = cands[0].get("finishReason")
        if fr == "MAX_TOKENS":
            self._say("    ответ обрезан по лимиту токенов")
        if not text:
            raise LLMError(f"Пустой ответ Gemini, finishReason={cands[0].get('finishReason')}")
        um = data.get("usageMetadata", {})
        return text, um.get("promptTokenCount", 0), um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0)

    def _anthropic(self, system, user, max_tokens, want_json):
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY не задан")
        base = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com").rstrip("/")
        body = {"model": self.model, "max_tokens": min(max_tokens, 32000), "temperature": self.temperature,
                "system": system, "messages": [{"role": "user", "content": user}]}
        data = self._post(f"{base}/v1/messages", body,
                          {"x-api-key": key, "anthropic-version": "2023-06-01"})
        self.resolved_model = data.get("model", self.model)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage", {})
        return text, u.get("input_tokens", 0), u.get("output_tokens", 0)

    def _openai(self, system, user, max_tokens, want_json):
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        key = os.environ.get("OPENAI_API_KEY", "none")
        body: Dict[str, Any] = {"model": self.model, "temperature": self.temperature, "max_tokens": max_tokens,
                                "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": user}]}
        if want_json:
            body["response_format"] = {"type": "json_object"}
        data = self._post(f"{base}/chat/completions", body, {"Authorization": f"Bearer {key}"})
        self.resolved_model = data.get("model", self.model)
        text = data["choices"][0]["message"]["content"] or ""
        u = data.get("usage", {})
        return text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)

    # ------------------------------------------------------------------ http
    def _post(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        attempts = getattr(self, "_attempts", self.max_retries + 1)
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json; charset=utf-8", **headers}
        delay = 8.0
        last = ""
        for i in range(attempts):
            req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "replace")[:600]
                last = f"HTTP {e.code}: {msg}"
                if e.code in (429, 500, 502, 503, 504, 529) and i < attempts - 1:
                    wait = _retry_after(msg) or delay
                    self._say(f"    {e.code} от API, повтор через {wait:.0f} с")
                    time.sleep(wait)
                    delay = min(delay * 2, 90)
                    continue
                if e.code in (401, 403):
                    err = LLMError(f"Ключ отклонён ({e.code}). Проверьте ключ в .env. {msg}")
                    err.fatal = True
                    raise err
                if e.code == 404:
                    raise LLMError(f"Модель '{self.model}' не найдена у провайдера. Укажите другую в .env. {msg}")
                raise LLMError(last)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last = str(e)
                if i < attempts - 1:
                    self._say(f"    сеть: {e}; повтор через {delay:.0f} с")
                    time.sleep(delay)
                    delay = min(delay * 2, 90)
                    continue
        raise LLMError(f"API недоступен: {last}")

    def _say(self, msg: str) -> None:
        if self.verbose:
            print(msg, file=sys.stderr, flush=True)


def _retry_after(msg: str) -> Optional[float]:
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', msg)
    return float(m.group(1)) + 1 if m else None


_BARE = re.compile(r'^(\s*"[^"\n]+"\s*:[ \t]*)(?![ \t])(?!["\[{]|-?\d|true\b|false\b|null\b)(.+?)(,?)\s*$')


def repair_json(t: str) -> str:
    """Починка типичных огрехов слабых моделей: значение-строка без кавычек до конца строки."""
    out = []
    for line in t.splitlines():
        m = _BARE.match(line)
        if m:
            val = m.group(2).strip().replace("\\", "\\\\").replace('"', '\\"')
            line = f'{m.group(1)}"{val}"{m.group(3)}'
        out.append(line)
    return "\n".join(out)


def parse_json(text: str) -> Any:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    cands = [t, repair_json(t)]
    for c in cands:
        try:
            return json.loads(c, strict=False)
        except json.JSONDecodeError:
            pass
    for c in cands:
        a, b = c.find("{"), c.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(c[a:b + 1], strict=False)
            except json.JSONDecodeError:
                pass
    raise ValueError("Ответ модели не является JSON")
