"""
Запуск Lighthouse CLI и извлечение метрик (FCP, TBT, SI, LCP, CLS).
Логика перенесена из autoLighthouse; использует стандартный logging.
"""
import shutil
import uuid
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
from playwright.sync_api import sync_playwright

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


def _get_navigation_timings_playwright(
    url: str,
    headers: dict | None,
    timeout_ms: int = 30000,
    context_mode: dict[str, Any] | None = None,
) -> tuple[float | None, float | None, ]:
    """
    Открывает url в Playwright/Chromium и возвращает DNS/TCP тайминги навигации
    из performance.getEntriesByType('navigation')[0].
    Возвращает (dns_ms, tcp_ms); при ошибке — (None, None).
    """
    try:
        chrome_path = os.environ.get("CHROME_PATH")
        if context_mode is None:
            context_mode = {
                "viewport": {"width": 1920, "height": 1080},
                "device_scale_factor": 1,
                "is_mobile": False,
            }
        launch_options: dict[str, Any] = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        }
        if chrome_path:
            launch_options["executable_path"] = chrome_path

        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_options)
            try:
                context = browser.new_context(**context_mode)
                logger.info(
                    "Playwright mode: is_mobile=%s, viewport=%sx%s, dpr=%s",
                    context_mode["is_mobile"],
                    context_mode["viewport"]["width"],
                    context_mode["viewport"]["height"],
                    context_mode["device_scale_factor"],
                )
                if headers:
                    context.set_extra_http_headers(headers)
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=timeout_ms)
                result = page.evaluate(
                    """() => {
                    const nav = performance.getEntriesByType('navigation')[0];
                    if (!nav) return { dns_ms: null, tcp_ms: null };
                    const dns = nav.domainLookupEnd - nav.domainLookupStart;
                    const tcp = nav.connectEnd - nav.connectStart;
                    return {
                        dns_ms: (dns >= 0 && isFinite(dns)) ? dns : null,
                        tcp_ms: (tcp >= 0 && isFinite(tcp)) ? tcp : null
                    };
                }"""
                )
                if not result or not isinstance(result, dict):
                    return (None, None)
                dns_ms = result.get("dns_ms")
                tcp_ms = result.get("tcp_ms")
                if dns_ms is not None:
                    dns_ms = float(dns_ms)
                if tcp_ms is not None:
                    tcp_ms = float(tcp_ms)
                return (dns_ms, tcp_ms)
            finally:
                browser.close()
    except Exception as e:
        logger.warning("Playwright navigation timings failed: %s", e)
        return (None, None)


def _run_once(cmd: list[str], timeout_sec: int) -> dict[str, Any]:
    """Одиночный запуск lighthouse (с ретраями от tenacity)."""
    lighthouse_stats = subprocess.run(
        cmd, capture_output=True, text=True, check=True, timeout=timeout_sec
    )
    return json.loads(lighthouse_stats.stdout)


def _get_modes_from_metadata(metadata: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Достаёт режим Lighthouse из metadata и формирует два контекста:
    - playwright_mode: параметры для Playwright context.new_context(...)
    - lighthouse_mode: параметры/флаги для Lighthouse CLI

    Поддерживаемые опциональные ключи в metadata:
    - lighthouse_device: "mobile" | "desktop"
    - lighthouse_mobile: bool (приоритет выше lighthouse_device)
    - lighthouse_viewport: {"width": int, "height": int, "deviceScaleFactor"?: int|float, "dpr"?: int|float}
    - lighthouse_cpuSlowdownMultiplier: int|float
    """
    lighthouse_device_raw = metadata.get("lighthouse_device")
    lighthouse_mobile_raw = metadata.get("lighthouse_mobile")

    is_mobile = False
    if isinstance(lighthouse_device_raw, str):
        is_mobile = lighthouse_device_raw.strip().lower() == "mobile"
    if isinstance(lighthouse_mobile_raw, bool):
        is_mobile = lighthouse_mobile_raw

    default_desktop_viewport = {"width": 1920, "height": 1080, "deviceScaleFactor": 1}
    default_mobile_viewport = {"width": 375, "height": 812, "deviceScaleFactor": 2}
    viewport_defaults = default_mobile_viewport if is_mobile else default_desktop_viewport

    viewport_override = metadata.get("lighthouse_viewport")
    width = viewport_defaults["width"]
    height = viewport_defaults["height"]
    device_scale_factor = viewport_defaults["deviceScaleFactor"]
    if isinstance(viewport_override, dict):
        if isinstance(viewport_override.get("width"), int):
            width = viewport_override["width"]
        if isinstance(viewport_override.get("height"), int):
            height = viewport_override["height"]
        dpr_val = viewport_override.get("deviceScaleFactor", viewport_override.get("dpr"))
        if isinstance(dpr_val, (int, float)):
            device_scale_factor = dpr_val

    cpu_slowdown = metadata.get("lighthouse_cpuSlowdownMultiplier", 1)
    if not isinstance(cpu_slowdown, (int, float)):
        cpu_slowdown = 1

    # Важно: в вашей версии Lighthouse допустимые значения --preset:
    # "desktop", "perf", "experimental". Поэтому для эмуляции mobile
    # используем emulated-form-factor + screenEmulation.*, а preset оставляем desktop.
    preset = "desktop"
    emulated_form_factor = "mobile" if is_mobile else "desktop"
    mobile_lh_flag = "true" if is_mobile else "false"

    playwright_mode: dict[str, Any] = {
        "is_mobile": is_mobile,
        "viewport": {"width": width, "height": height},
        "device_scale_factor": device_scale_factor,
    }
    lighthouse_mode: dict[str, Any] = {
        "preset": preset,
        "emulated_form_factor": emulated_form_factor,
        "mobile": is_mobile,
        "mobile_lh_flag": mobile_lh_flag,
        "screen": {
            "width": width,
            "height": height,
            "deviceScaleFactor": device_scale_factor,
        },
        "throttling": {"cpuSlowdownMultiplier": cpu_slowdown},
    }
    return playwright_mode, lighthouse_mode


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
        metrics: {fcp_ms, fcp_s, tbt_ms, tbt_s, si_ms, si_s, lcp_ms, lcp_s, cls, dns_ms, dns_s, tcp_ms, tcp_s}.
    """
    metadata = metadata or {}
    headers = headers or {}
    tmp_path = None

    playwright_mode, lighthouse_mode = _get_modes_from_metadata(metadata)
    preset = lighthouse_mode["preset"]
    emulated_form_factor = lighthouse_mode["emulated_form_factor"]
    is_mobile = lighthouse_mode["mobile"]
    mobile_lh_flag = lighthouse_mode.get("mobile_lh_flag") or ("true" if is_mobile else "false")
    width = lighthouse_mode["screen"]["width"]
    height = lighthouse_mode["screen"]["height"]
    device_scale_factor = lighthouse_mode["screen"]["deviceScaleFactor"]
    cpu_slowdown = lighthouse_mode["throttling"]["cpuSlowdownMultiplier"]

    # Флаги для headless в контейнере: --no-sandbox, --disable-gpu
    user_data_dir = f"/tmp/chrome-profile-{uuid.uuid4().hex}"
    chrome_flags = f"--headless --no-sandbox --disable-cache --user-data-dir={user_data_dir} --disable-gpu"
    base_cmd = [
        "lighthouse",
        url,
        "--quiet",
        f"--preset={preset}",
        f"--form-factor={emulated_form_factor}",
        f"--screenEmulation.width={width}",
        f"--screenEmulation.height={height}",
        f"--screenEmulation.deviceScaleFactor={device_scale_factor}",
        f"--screenEmulation.mobile={mobile_lh_flag}",
        f"--throttling.cpuSlowdownMultiplier={cpu_slowdown}",
        f"--chrome-flags={chrome_flags}",
        "--output=json",
        "--output-path=stdout",
        "--only-audits=first-contentful-paint,total-blocking-time,speed-index,largest-contentful-paint,cumulative-layout-shift",
    ]
    logger.info(
        "Lighthouse mode: preset=%s, formFactor=%s, mobile=%s, screen=%sx%s, dpr=%s",
        preset,
        emulated_form_factor,
        is_mobile,
        width,
        height,
        device_scale_factor,
    )
    chrome_path = os.environ.get("CHROME_PATH")
    if chrome_path:
        base_cmd.append(f"--chrome-path={chrome_path}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(10),
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

        dns_ms, tcp_ms = _get_navigation_timings_playwright(
            url,
            headers or None,
            timeout_ms=30000,
            context_mode=playwright_mode,
        )
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
            "dns_ms": dns_ms,
            "dns_s": round(dns_ms / 1000, 2) if dns_ms is not None else None,
            "tcp_ms": tcp_ms,
            "tcp_s": round(tcp_ms / 1000, 2) if tcp_ms is not None else None,
        }

        return {
            "dt_created": datetime.now(timezone.utc) #время сбора метрики
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "status": "success",
            "metadata": metadata,
            "url": url,
            "metrics": metrics,
            "playwright_mode": playwright_mode,
            "lighthouse_mode": lighthouse_mode,
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
            "playwright_mode": playwright_mode,
            "lighthouse_mode": lighthouse_mode,
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
            "playwright_mode": playwright_mode,
            "lighthouse_mode": lighthouse_mode,
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
            "playwright_mode": playwright_mode,
            "lighthouse_mode": lighthouse_mode,
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
            "playwright_mode": playwright_mode,
            "lighthouse_mode": lighthouse_mode,
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
            "playwright_mode": playwright_mode,
            "lighthouse_mode": lighthouse_mode,
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
        # Удаляем временный профиль Chrome
        shutil.rmtree(user_data_dir, ignore_errors=True)
