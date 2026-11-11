"""CSS 快码经验目录 + baseLookupValuesService/find 实时查询。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent.css.client import CssAuthError, get_css_client

_DEFAULT_LOOKUP_URL = (
    "https://dms.aosmith.com.cn/api/baseServer/baseLookupValuesService/find"
)
_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "css_lookup_catalog.json"
)


def lookup_url() -> str:
    return (os.getenv("CSS_LOOKUP_URL") or _DEFAULT_LOOKUP_URL).strip()


def load_catalog() -> dict[str, Any]:
    if not _CATALOG_PATH.is_file():
        return {"version": 1, "items": []}
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"version": 1, "items": []}
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "items": []}


def find_catalog_item(
    lookup_type: str,
    system_code: str = "",
) -> dict[str, Any] | None:
    lt = (lookup_type or "").strip().upper()
    sc = (system_code or "").strip().upper()
    if not lt:
        return None
    for item in load_catalog().get("items") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("lookupType") or "").strip().upper() != lt:
            continue
        if sc and str(item.get("systemCode") or "").strip().upper() != sc:
            continue
        return item
    return None


def list_catalog_summaries(keyword: str = "") -> list[dict[str, Any]]:
    kw = (keyword or "").strip().lower()
    out: list[dict[str, Any]] = []
    for item in load_catalog().get("items") or []:
        if not isinstance(item, dict):
            continue
        blob = " ".join(
            str(item.get(k) or "")
            for k in ("lookupType", "systemCode", "name", "usage", "notes")
        )
        used = " ".join(str(x) for x in (item.get("usedIn") or []))
        text = f"{blob} {used}".lower()
        if kw and kw not in text:
            continue
        out.append(
            {
                "lookupType": item.get("lookupType"),
                "systemCode": item.get("systemCode"),
                "name": item.get("name"),
                "usage": item.get("usage"),
                "usedIn": item.get("usedIn") or [],
                "notes": item.get("notes") or "",
            }
        )
    return out


def fetch_lookup_values(
    lookup_type: str,
    system_code: str = "CSS",
    *,
    lan: str = "CN",
    delete_flag: int = 0,
    enabled_only: bool = True,
) -> dict[str, Any]:
    """带验签调用快码查询接口。"""
    lt = (lookup_type or "").strip()
    sc = (system_code or "").strip() or "CSS"
    if not lt:
        return {"ok": False, "error": "缺少 lookupType"}

    catalog = find_catalog_item(lt, sc) or find_catalog_item(lt, "")
    params: dict[str, Any] = {
        "lookupType": lt,
        "systemCode": sc,
        "deleteFlag": int(delete_flag),
        "lan": (lan or "CN").strip() or "CN",
    }
    url = lookup_url()
    try:
        client = get_css_client()
        raw = client.post_business(url, params, as_params_form=True)
    except CssAuthError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "request_url": url,
            "request_params": params,
            "catalog": catalog,
        }

    # 成功时常见 msg=操作成功，data=列表；无统一 status 字段
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, list):
        return {
            "ok": False,
            "error": raw.get("msg") if isinstance(raw, dict) else "快码返回异常",
            "request_url": url,
            "request_params": params,
            "catalog": catalog,
            "raw": raw,
        }

    values: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        enabled = str(row.get("enabledFlag") or "Y").upper()
        if enabled_only and enabled not in ("Y", "1", "TRUE"):
            continue
        values.append(
            {
                "lookupCode": row.get("lookupCode"),
                "meaning": row.get("meaning"),
                "description": row.get("description") or "",
                "enabledFlag": row.get("enabledFlag"),
                "startDateActive": row.get("startDateActive"),
                "endDateActive": row.get("endDateActive"),
                "lookupValuesId": row.get("lookupValuesId"),
            }
        )

    return {
        "ok": True,
        "source": "css",
        "request_url": url,
        "request_params": params,
        "catalog": catalog,
        "count": len(values),
        "values": values,
        "summary": (
            f"快码 {lt}/{sc} 共 {len(values)} 条"
            + (f"；用途：{catalog.get('usage')}" if catalog and catalog.get("usage") else "")
        ),
        "message": (
            f"快码 {lt}/{sc} 共 {len(values)} 条"
            + (f"；用途：{catalog.get('usage')}" if catalog and catalog.get("usage") else "")
        ),
    }
