"""QAD 接口工具：价格 BatchGetQad58、订单状态 SalesOrderStatusWS。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from langchain_core.tools import BaseTool, tool

_DEFAULT_PRICE_URL = "http://172.30.109.112:8015/api/QadRealTime/BatchGetQad58"
_DEFAULT_ORDER_STATUS_URL = "http://172.30.109.112:8015/Qad/SalesOrderStatusWS"

# 兜底：与快码 QAD_ORDER_STATUS 一致（实时优先走 CSS 字典）
_BILL_STATUS_LABELS = {
    "01": "待确认",
    "02": "待解新",
    "05": "待解新",
    "06": "已解信",
    "10": "已解信",
    "12": "已解信",
    "15": "已开票",
    "20": "QAD已删除",
}

_status_label_cache: dict[str, str] | None = None


def _load_qad_order_status_labels() -> dict[str, str]:
    """优先从 CSS 快码 QAD_ORDER_STATUS 加载状态含义。"""
    global _status_label_cache
    if _status_label_cache is not None:
        return _status_label_cache
    labels = dict(_BILL_STATUS_LABELS)
    try:
        from agent.css.lookup import fetch_lookup_values

        result = fetch_lookup_values("QAD_ORDER_STATUS", "CSS")
        if result.get("ok"):
            for row in result.get("values") or []:
                code = str(row.get("lookupCode") or "").strip()
                meaning = str(row.get("meaning") or "").strip()
                if code and meaning:
                    labels[code] = meaning
    except Exception:  # noqa: BLE001
        pass
    _status_label_cache = labels
    return labels


def _status_label(code: str) -> str:
    return _load_qad_order_status_labels().get(str(code or "").strip(), "")


def _price_url() -> str:
    return (
        os.getenv("QAD_BATCH_GET_QAD58_URL")
        or os.getenv("QAD_PRICE_URL")
        or _DEFAULT_PRICE_URL
    ).strip()


def _order_status_url() -> str:
    return (
        os.getenv("QAD_SALES_ORDER_STATUS_URL")
        or os.getenv("QAD_ORDER_STATUS_URL")
        or _DEFAULT_ORDER_STATUS_URL
    ).strip()


def _normalize_bill_no(bill_no: str) -> tuple[str | None, str | None]:
    """校验 QAD 订单号：字母+数字共 8 位。"""
    raw = (bill_no or "").strip().upper()
    if not raw:
        return None, "缺少 QAD 订单号 bill_no"
    if not re.fullmatch(r"[A-Z0-9]{8}", raw):
        return None, "QAD 订单号须为字母+数字共 8 位，例如 AB12CD34"
    return raw, None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _interpret_row(row: dict[str, Any], *, sold_to: str, material_no: str) -> dict[str, Any]:
    cust_grp = str(row.get("tmpcmpt_custgrp") or "").strip()
    part_grp = str(row.get("tmpcmpt_partgrp") or "").strip()
    list_price = _to_float(row.get("tmpcmpt_listprice"))
    net_price = _to_float(row.get("tmpcmpt_netprice"))
    discount = _to_float(row.get("tmpcmpt_discount"))

    customer_missing = "customer does not exist" in cust_grp.lower()
    part_missing = "part does not exist" in part_grp.lower()

    issues: list[str] = []
    if customer_missing:
        issues.append(f"客户【{sold_to}】不存在：{cust_grp}")
    if part_missing:
        issues.append(f"物料【{material_no}】不存在：{part_grp}")

    # 有效价：净价或挂牌价 > 0 视为已配置价格
    has_price = (net_price is not None and net_price > 0) or (
        list_price is not None and list_price > 0
    )

    if issues:
        configured = False
        summary = "；".join(issues)
    elif has_price:
        configured = True
        summary = (
            f"客户【{sold_to}】物料【{material_no}】已配置价格："
            f"挂牌价 {list_price}，折扣 {discount}，净价 {net_price}"
        )
    else:
        configured = False
        summary = (
            f"客户【{sold_to}】与物料【{material_no}】可查到记录，"
            f"但挂牌价/净价均为 0 或空，视为未配置有效价格"
            f"（listprice={row.get('tmpcmpt_listprice')}, "
            f"netprice={row.get('tmpcmpt_netprice')}）"
        )

    return {
        "sold_to": sold_to,
        "material_no": material_no,
        "price_configured": configured,
        "has_valid_price": has_price,
        "customer_missing": customer_missing,
        "part_missing": part_missing,
        "list_price": list_price,
        "discount": discount,
        "net_price": net_price,
        "domain": row.get("tmpcmpt_domain"),
        "entity": row.get("tmpcmpt_entity"),
        "customer_group": cust_grp,
        "part_group": part_grp,
        "price_date": row.get("tmpcmpt_date"),
        "summary": summary,
        "message": summary,
        "raw": row,
    }


@tool
def qad_check_price_configured(
    customer_code: str,
    material_no: str,
) -> str:
    """查询客户+物料是否在 QAD 配置了价格（BatchGetQad58）。

    意图为「有没有价格 / 是否配置价格 / 查价」且已有客户编码与物料号时调用。
    入参对应接口：soldTo=客户编码，materialNo=物料号。

    Args:
        customer_code: 客户编码（SoldTo），如 BHKH
        material_no: 我司物料号，如 R1600RC30000C
    """
    sold_to = (customer_code or "").strip()
    part = (material_no or "").strip()
    if not sold_to:
        return json.dumps(
            {"ok": False, "error": "缺少客户编码 customer_code"},
            ensure_ascii=False,
        )
    if not part:
        return json.dumps(
            {"ok": False, "error": "缺少物料号 material_no"},
            ensure_ascii=False,
        )

    url = _price_url()
    payload = [{"soldTo": sold_to, "materialNo": part}]
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            res = client.post(url, json=payload)
            res.raise_for_status()
            body = res.json()
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {
                "ok": False,
                "error": f"QAD 价格接口调用失败：{exc}",
                "request_url": url,
                "request_params": payload,
            },
            ensure_ascii=False,
        )

    if not isinstance(body, dict):
        return json.dumps(
            {"ok": False, "error": "返回非 JSON 对象", "raw": body},
            ensure_ascii=False,
        )

    code = body.get("code")
    return_status = body.get("returnStatus")
    result = body.get("result")
    if code not in (200, "200") or return_status not in (1, "1"):
        return json.dumps(
            {
                "ok": False,
                "source": "qad",
                "request_url": url,
                "request_params": payload,
                "error": body.get("message") or f"接口失败 code={code} returnStatus={return_status}",
                "raw": body,
            },
            ensure_ascii=False,
        )

    rows = result if isinstance(result, list) else []
    if not rows:
        return json.dumps(
            {
                "ok": True,
                "source": "qad",
                "request_url": url,
                "request_params": payload,
                "price_configured": False,
                "summary": f"未返回价格明细：客户【{sold_to}】物料【{part}】",
                "message": f"未返回价格明细：客户【{sold_to}】物料【{part}】",
                "items": [],
            },
            ensure_ascii=False,
        )

    first = rows[0] if isinstance(rows[0], dict) else {}
    interpreted = _interpret_row(first, sold_to=sold_to, material_no=part)
    items = [
        _interpret_row(r, sold_to=sold_to, material_no=part)
        for r in rows
        if isinstance(r, dict)
    ]
    return json.dumps(
        {
            "ok": True,
            "source": "qad",
            "request_url": url,
            "request_params": payload,
            **interpreted,
            "items": items,
        },
        ensure_ascii=False,
    )


@tool
def qad_check_order_status(bill_no: str) -> str:
    """查询 QAD 销售订单状态（SalesOrderStatusWS）。

    用户说「CSC70173订单状态」「查订单状态 AB12CD34」「QAD单号状态」等时必须调用本工具，
    不要回复无法查询。订单号：字母+数字共 8 位。

    Args:
        bill_no: QAD 订单号（8 位字母数字，如 CSC70173）
    """
    normalized, err = _normalize_bill_no(bill_no)
    if err:
        return json.dumps({"ok": False, "error": err, "bill_no": bill_no}, ensure_ascii=False)

    url = _order_status_url()
    payload = {"billNo": normalized}
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            res = client.post(url, json=payload)
            res.raise_for_status()
            body = res.json()
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {
                "ok": False,
                "error": f"QAD 订单状态接口调用失败：{exc}",
                "request_url": url,
                "request_params": payload,
            },
            ensure_ascii=False,
        )

    if not isinstance(body, dict):
        return json.dumps(
            {"ok": False, "error": "返回非 JSON 对象", "raw": body},
            ensure_ascii=False,
        )

    code = body.get("code")
    return_status = body.get("returnStatus")
    result = body.get("result")
    if code not in (200, "200") or return_status not in (1, "1"):
        return json.dumps(
            {
                "ok": False,
                "source": "qad",
                "request_url": url,
                "request_params": payload,
                "error": body.get("message")
                or f"接口失败 code={code} returnStatus={return_status}",
                "raw": body,
            },
            ensure_ascii=False,
        )

    rows = result if isinstance(result, list) else []
    if not rows:
        return json.dumps(
            {
                "ok": True,
                "source": "qad",
                "request_url": url,
                "request_params": payload,
                "bill_no": normalized,
                "found": False,
                "summary": f"未查到 QAD 订单【{normalized}】的状态",
                "message": f"未查到 QAD 订单【{normalized}】的状态",
                "items": [],
            },
            ensure_ascii=False,
        )

    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status_code = str(row.get("billStatusCode") or "").strip()
        qad_bill = str(row.get("qadBillNo") or normalized).strip()
        label = _status_label(status_code)
        items.append(
            {
                "qad_bill_no": qad_bill,
                "bill_status_code": status_code,
                "bill_status_label": label or None,
                "raw": row,
            }
        )

    first = items[0]
    status_code = first["bill_status_code"]
    label = first.get("bill_status_label")
    if label:
        summary = f"QAD 订单【{normalized}】状态码 {status_code}（{label}）"
    else:
        summary = f"QAD 订单【{normalized}】状态码 {status_code}"

    return json.dumps(
        {
            "ok": True,
            "source": "qad",
            "request_url": url,
            "request_params": payload,
            "bill_no": normalized,
            "found": True,
            "bill_status_code": status_code,
            "bill_status_label": label,
            "summary": summary,
            "message": summary,
            "items": items,
        },
        ensure_ascii=False,
    )


QAD_TOOLS: list[BaseTool] = [
    qad_check_price_configured,
    qad_check_order_status,
]
