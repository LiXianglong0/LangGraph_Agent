"""CSS / SAAF 平台客户端：登录取 certificate（验签 key），供后续业务接口使用。"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import httpx

# 默认正式环境登录地址（可被 .env 覆盖）
_DEFAULT_LOGIN_URL = (
    "https://dms.aosmith.com.cn/api/baseServer/baseLoginService/login"
)
_DEFAULT_DOMAIN = "https://dms.aosmith.com.cn"


class CssAuthError(RuntimeError):
    """登录或验签失败。"""


class CssClient:
    """线程安全的验签缓存客户端。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._certificate: str = ""
        self._fetched_at: float = 0.0
        self._last_used_at: float = 0.0
        # 验签空闲超时：默认 30 分钟未使用则重新登录（可用 CSS_CERT_TTL_SEC 覆盖）
        self._idle_ttl_sec = float(os.getenv("CSS_CERT_TTL_SEC", "1800"))

    def _login_url(self) -> str:
        return (
            os.getenv("CSS_LOGIN_URL") or _DEFAULT_LOGIN_URL
        ).strip()

    def _credentials(self) -> tuple[str, str]:
        user = (os.getenv("CSS_USER_NAME") or "").strip()
        pwd = (os.getenv("CSS_PASSWORD") or "").strip()
        if not user or not pwd:
            raise CssAuthError(
                "未配置 CSS 登录账号：请在 .env 设置 CSS_USER_NAME / CSS_PASSWORD"
            )
        return user, pwd

    def _expired(self, now: float) -> bool:
        """超过空闲有效期（默认 30 分钟未使用）则失效。"""
        if not self._certificate:
            return True
        anchor = self._last_used_at or self._fetched_at
        return (now - anchor) >= self._idle_ttl_sec

    def _touch(self, now: float | None = None) -> None:
        self._last_used_at = now if now is not None else time.time()

    def _clear_cache(self) -> None:
        self._certificate = ""
        self._fetched_at = 0.0
        self._last_used_at = 0.0

    def login(self, force: bool = False) -> str:
        """获取验签 certificate；30 分钟未使用则重新登录。"""
        with self._lock:
            now = time.time()
            if not force and not self._expired(now):
                self._touch(now)
                return self._certificate

            user, pwd = self._credentials()
            url = self._login_url()
            domain = (os.getenv("CSS_DOMAIN") or _DEFAULT_DOMAIN).strip()
            # 文档要求：参数必须以 params 为 key，value 为 JSON 对象
            params_obj: dict[str, str] = {"userName": user, "pwd": pwd}
            if domain:
                params_obj["domain"] = domain
            form = {"params": json.dumps(params_obj, ensure_ascii=False)}

            try:
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    res = client.post(
                        url,
                        data=form,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                    res.raise_for_status()
                    body = res.json()
            except Exception as exc:  # noqa: BLE001
                raise CssAuthError(f"CSS 登录请求失败：{exc}") from exc

            if not isinstance(body, dict):
                raise CssAuthError(f"CSS 登录返回非 JSON 对象：{body!r}")

            # 文档：S 成功；E 异常；M 密码失效；D 密码永久有效
            # 实测 status=M 时仍可能返回 certificate，故以 certificate 为准
            status = str(body.get("status") or "")
            data = body.get("data") or {}
            cert = ""
            if isinstance(data, dict):
                cert = str(data.get("certificate") or "").strip()

            if status == "E" or not cert:
                raise CssAuthError(
                    f"CSS 登录失败 status={status} msg={body.get('msg')} cert_empty={not bool(cert)}"
                )

            self._certificate = cert
            self._fetched_at = now
            self._touch(now)
            return cert

    def get_certificate(self, force: bool = False) -> str:
        return self.login(force=force)

    def auth_headers(self, force: bool = False) -> dict[str, str]:
        """常见携带方式：certificate 头；具体业务接口若不同可再扩展。"""
        cert = self.get_certificate(force=force)
        return {
            "certificate": cert,
            "Certificate": cert,
        }

    def post_business(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        as_params_form: bool = True,
    ) -> dict[str, Any]:
        """带验签调用业务接口；失败时清缓存重登再试一次。"""
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                headers = self.auth_headers(force=(attempt > 0))
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    if as_params_form:
                        res = client.post(
                            url,
                            data={
                                "params": json.dumps(payload, ensure_ascii=False),
                            },
                            headers={
                                "Content-Type": "application/x-www-form-urlencoded",
                                **headers,
                            },
                        )
                    else:
                        res = client.post(url, json=payload, headers=headers)
                    res.raise_for_status()
                    data = res.json()
                    # 业务调用成功也续期空闲计时
                    with self._lock:
                        self._touch()
                    return data if isinstance(data, dict) else {"raw": data}
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt == 0:
                    with self._lock:
                        self._clear_cache()
                    continue
                break
        raise CssAuthError(f"CSS 业务调用失败：{last_err}")


_client: CssClient | None = None
_client_lock = threading.Lock()


def get_css_client() -> CssClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = CssClient()
        return _client
