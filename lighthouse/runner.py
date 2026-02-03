"""
Запуск Lighthouse CLI и извлечение метрик (FCP, TBT, SI, LCP, CLS).
Логика перенесена из autoLighthouse; использует стандартный logging.
"""
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

logger = logging.getLogger(__name__)


def _safe_metric(audits: dict, key: str) -> float | None:
    """
    Безопасно достаёт numericValue из аудита Lighthouse.
    Возвращает float или None, если метрика отсутствует/битая.
    """
    metric = audits.get(key)
    if not metric:
        return None
    value = metric.get("numericValue")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_once(cmd: list[str], timeout_sec: int) -> dict[str, Any]:
    """Одиночный запуск lighthouse (с ретраями от tenacity)."""
    lighthouse_stats = subprocess.run(
        cmd, capture_output=True, text=True, check=True, timeout=timeout_sec
    )
    return json.loads(lighthouse_stats.stdout)


def run_lighthouse(
    url: str,
    metadata: dict[str, Any] | None = None,
    timeout_sec: int = 240,
    headers: dict | None = None,
) -> dict[str, Any]:
    """
    Запускает Lighthouse CLI для url и возвращает структурированный результат.

    Args:
        url: ссылка на ресурс
        metadata: поля, добавляемые к результату (для ELK: project, page_type и т.д.)
        timeout_sec: таймаут команды в секундах
        headers: заголовки для --extra-headers (передаются через временный JSON-файл)

    Returns:
        dict с ключами: @timestamp, status, metadata, url, metrics, error, message.
        metrics: {fcp_ms, fcp_s, tbt_ms, tbt_s, si_ms, si_s, lcp_ms, lcp_s, cls}.
    """
    metadata = metadata or {}
    headers = headers or {}
    tmp_path = None

    # Флаги для headless в контейнере: --no-sandbox, --disable-gpu
    chrome_flags = "--headless --no-sandbox --disable-cache --user-data-dir=/dev/null --disable-gpu"
    base_cmd = [
        "lighthouse",
        url,
        "--quiet",
        f"--chrome-flags={chrome_flags}",
        "--output=json",
        "--output-path=stdout",
        "--only-audits=first-contentful-paint,total-blocking-time,speed-index,largest-contentful-paint,cumulative-layout-shift",
    ]
    chrome_path = os.environ.get("CHROME_PATH")
    if chrome_path:
        base_cmd.append(f"--chrome-path={chrome_path}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(
            (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError),
        ),
        reraise=True,
    )
    def run_cmd():
        return _run_once(base_cmd, timeout_sec)

    try:
        if headers:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp:
                json.dump(headers, tmp)
                tmp_path = tmp.name
            logger.info("Created temporary headers file: %s", tmp_path)
            base_cmd.append(f"--extra-headers={tmp_path}")

        data = run_cmd()

        fcb = _safe_metric(data["audits"], "first-contentful-paint")
        tbt = _safe_metric(data["audits"], "total-blocking-time")
        si = _safe_metric(data["audits"], "speed-index")
        lcp = _safe_metric(data["audits"], "largest-contentful-paint")
        cls = _safe_metric(data["audits"], "cumulative-layout-shift")

        metrics = {
            "fcp_ms": fcb,
            "fcp_s": round(fcb / 1000, 2) if fcb is not None else None,
            "tbt_ms": tbt,
            "tbt_s": round(tbt / 1000, 2) if tbt is not None else None,
            "si_ms": si,
            "si_s": round(si / 1000, 2) if si is not None else None,
            "lcp_ms": lcp,
            "lcp_s": round(lcp / 1000, 2) if lcp is not None else None,
            "cls": cls,
        }

        return {
            "@timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "status": "success",
            "metadata": metadata,
            "url": url,
            "metrics": metrics,
            "error": None,
            "message": None,
        }

    except subprocess.CalledProcessError as eCPE:
        return {
            "@timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "url": url,
            "status": "error",
            "metadata": metadata,
            "metrics": None,
            "error": "Lighthouse failed",
            "message": f"stderr: {eCPE.stderr.strip()[:500]} | stdout: {eCPE.stdout.strip()[:500]}",
        }
    except subprocess.TimeoutExpired as eTE:
        return {
            "@timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "url": url,
            "status": "error",
            "metadata": metadata,
            "metrics": None,
            "error": "Lighthouse timeout",
            "message": str(eTE),
        }
    except FileNotFoundError as eFNF:
        return {
            "@timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "url": url,
            "status": "error",
            "metadata": metadata,
            "metrics": None,
            "error": "Lighthouse binary not found",
            "message": str(eFNF),
        }
    except json.JSONDecodeError as eJSDE:
        return {
            "@timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "url": url,
            "status": "error",
            "metadata": metadata,
            "metrics": None,
            "error": "Invalid JSON from Lighthouse",
            "message": str(eJSDE),
        }
    except Exception as e:
        return {
            "@timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "url": url,
            "status": "error",
            "metadata": metadata,
            "metrics": None,
            "error": "Unexpected exception",
            "message": str(e),
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                logger.info("Removed temporary headers file: %s", tmp_path)
            except OSError as e:
                logger.warning("Failed to remove temporary file %s: %s", tmp_path, e)
