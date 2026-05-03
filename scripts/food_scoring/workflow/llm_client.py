"""TWCC LLM client: JSON mode, retry, SQLite cache, optional concurrency.

Reuses the same env vars as test_api.py:
  TWCC_API_URL / TWCC_API_KEY / TWCC_MODEL / TWCC_TIMEOUT / TWCC_MAX_RETRY

Extra rate-limit / circuit-breaker controls:
  TWCC_RATE_LIMIT_SLEEP   seconds to sleep on HTTP 429 (default 60)
  TWCC_MAX_FAILURES       consecutive chat_json failures that halt the pipeline (default 3)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("TWCC_API_URL")
API_KEY = os.getenv("TWCC_API_KEY")
MODEL = os.getenv("TWCC_MODEL")
TIMEOUT = int(os.getenv("TWCC_TIMEOUT", "90"))
MAX_RETRY = int(os.getenv("TWCC_MAX_RETRY", "3"))
RATE_LIMIT_SLEEP = int(os.getenv("TWCC_RATE_LIMIT_SLEEP", "60"))
MAX_CONSECUTIVE_FAILURES = int(os.getenv("TWCC_MAX_FAILURES", "3"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_DB = CACHE_DIR / "llm_cache.sqlite"

_db_lock = threading.Lock()

# Circuit breaker state (shared across threads)
_failures_lock = threading.Lock()
_consec_failures = 0


class CircuitBreakerError(SystemExit):
    """Halts the entire pipeline.

    Subclasses SystemExit (BaseException) so it bypasses ``except Exception``
    handlers in stage scripts and immediately exits the interpreter.
    """


def _record_success() -> None:
    global _consec_failures
    with _failures_lock:
        _consec_failures = 0


def _record_failure(reason: str) -> None:
    """Increment the consecutive-failure counter; raise CircuitBreakerError if
    threshold is hit. Always called when a chat_json invocation fails terminally.
    """
    global _consec_failures
    with _failures_lock:
        _consec_failures += 1
        n = _consec_failures
    if n >= MAX_CONSECUTIVE_FAILURES:
        msg = (
            f"\n[CIRCUIT BREAKER] {n} consecutive LLM failures reached threshold "
            f"({MAX_CONSECUTIVE_FAILURES}); halting pipeline.\n"
            f"  last error: {reason}\n"
            f"  partial progress (KB / cache / CSV) was preserved; rerun to resume."
        )
        print(msg, file=sys.stderr)
        raise CircuitBreakerError(msg)


def _looks_like_rate_limit(text: str) -> bool:
    t = (text or "").lower()
    return "429" in t or "rate" in t or "limit" in t or "quota" in t or "throttl" in t


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB, timeout=30, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_cache (
            key TEXT PRIMARY KEY,
            system_prompt TEXT,
            user_prompt TEXT,
            max_tokens INTEGER,
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def _cache_key(system_prompt: str, user_prompt: str, max_tokens: int, model: str) -> str:
    payload = f"{model}\n--\n{max_tokens}\n--\n{system_prompt}\n--\n{user_prompt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str):
    with _db_lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT response FROM llm_cache WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()


def _cache_put(key, system_prompt, user_prompt, max_tokens, response):
    with _db_lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO llm_cache "
                "(key, system_prompt, user_prompt, max_tokens, response) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, system_prompt, user_prompt, max_tokens, response),
            )
            conn.commit()
        finally:
            conn.close()


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_json(text: str):
    """Try to parse as JSON; if that fails, locate the first balanced {...} or [...] block."""
    text = _strip_json_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start < 0:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    raise json.JSONDecodeError("could not extract JSON from response", text, 0)


def _call_api(system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    url = f"{API_URL.rstrip('/')}/models/conversation"
    headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_k": 50,
            "top_p": 1.0,
            "frequence_penalty": 1.0,
        },
    }

    last_err = None
    for attempt in range(1, MAX_RETRY + 2):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)

            # Rate-limit detection: HTTP 429 -> long sleep, then retry
            if resp.status_code == 429:
                last_err = f"HTTP 429 rate-limited"
                print(
                    f"[Attempt {attempt}] HTTP 429 rate limit; sleeping {RATE_LIMIT_SLEEP}s ...",
                    file=sys.stderr,
                )
                time.sleep(RATE_LIMIT_SLEEP)
                continue

            resp.raise_for_status()
            result = resp.json()
            text = (
                result.get("generated_text")
                or result.get("output")
                or (result.get("choices", [{}])[0].get("message", {}) or {}).get("content")
                or ""
            )
            if text:
                return text
            raise RuntimeError(f"empty response body: {result}")
        except (requests.RequestException, RuntimeError) as e:
            last_err = e
            err_str = str(e)
            print(f"[Attempt {attempt}] API error: {e}", file=sys.stderr)
            if attempt <= MAX_RETRY:
                if _looks_like_rate_limit(err_str):
                    print(
                        f"  -> looks like rate limit, sleeping {RATE_LIMIT_SLEEP}s",
                        file=sys.stderr,
                    )
                    time.sleep(RATE_LIMIT_SLEEP)
                else:
                    time.sleep(2 * attempt)
    raise RuntimeError(f"API call failed after {MAX_RETRY + 1} attempts: {last_err}")


def chat_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    json_retries: int = 2,
    use_cache: bool = True,
):
    """Call LLM and parse the response as JSON.

    On JSON parse failure, retries with an explicit reminder.
    On terminal failure (API or JSON), increments the circuit breaker counter;
    if the threshold is reached, raises CircuitBreakerError (SystemExit) which
    halts the entire pipeline. Successful calls reset the counter.
    """
    key = _cache_key(system_prompt, user_prompt, max_tokens, MODEL or "")
    if use_cache:
        cached = _cache_get(key)
        if cached:
            try:
                parsed = _extract_json(cached)
                _record_success()
                return parsed
            except json.JSONDecodeError:
                pass  # cached entry is unparseable; fall through

    last_err = None
    usr_prompt = user_prompt
    for attempt in range(json_retries + 1):
        try:
            text = _call_api(system_prompt, usr_prompt, max_tokens, temperature)
            parsed = _extract_json(text)
            if use_cache:
                _cache_put(key, system_prompt, user_prompt, max_tokens, text)
            _record_success()
            return parsed
        except json.JSONDecodeError as e:
            last_err = e
            print(f"[JSON retry {attempt + 1}] parse failed: {e}", file=sys.stderr)
            usr_prompt = (
                user_prompt
                + "\n\n[重要] 上一次回應無法被 json.loads 解析，"
                "請只回傳合法 JSON，不要任何其他文字、註解或 markdown 程式碼框。"
            )
        except RuntimeError as e:
            # _call_api already exhausted its own retries; don't retry at this level
            last_err = e
            break

    # Terminal failure for this chat_json call. May raise CircuitBreakerError.
    _record_failure(str(last_err))
    raise RuntimeError(f"chat_json failed: {last_err}")


def batch_chat_json(tasks, max_workers: int = 3, **chat_kwargs):
    """Run many chat_json calls concurrently.

    tasks: iterable of (key, system_prompt, user_prompt)
    Returns dict[key -> result_or_Exception].

    If the circuit breaker trips inside any task, cancels remaining tasks and
    re-raises CircuitBreakerError so the caller exits.
    """
    results = {}
    tasks = list(tasks)
    total = len(tasks)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_key = {
            ex.submit(chat_json, sys_p, usr_p, **chat_kwargs): k
            for k, sys_p, usr_p in tasks
        }
        try:
            for i, fut in enumerate(as_completed(future_to_key), 1):
                k = future_to_key[fut]
                try:
                    results[k] = fut.result()
                except CircuitBreakerError:
                    raise  # bubble out of the loop
                except Exception as e:
                    results[k] = e
                    print(f"[batch] {k} failed: {e}", file=sys.stderr)
                print(f"[batch] {i}/{total} done", file=sys.stderr)
        except CircuitBreakerError:
            print(
                f"[batch] aborting: completed {len(results)}/{total} before circuit breaker tripped",
                file=sys.stderr,
            )
            ex.shutdown(wait=False, cancel_futures=True)
            raise
    return results


def assert_env():
    missing = [v for v in ("TWCC_API_URL", "TWCC_API_KEY", "TWCC_MODEL") if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"missing env vars: {missing}. Check .env")


if __name__ == "__main__":
    assert_env()
    print("env OK")
    print("model :", MODEL)
    print("cache :", CACHE_DB)
