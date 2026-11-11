"""CSS 可售物料工具：先验签，再调 diagnoseMaterialSellable 诊断可售/不可售原因。"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_core.tools import BaseTool, tool

from agent.css.client import CssAuthError, get_css_client
from agent.css.lookup import fetch_lookup_values, list_catalog_summaries
from agent.css.slots import normalize_order_type_arg

_DEFAULT_DIAGNOSE_PATH = (
    "/api/orderInterfaceServer/errorMsgInfoService/diagnoseMaterialSellable"
)
_DEFAULT_DOMAIN = "https://dms.aosmith.com.cn"


def _normalize_slots(
    customer_code: str,
    order_type: str,
    material_no: str = "",
    customer_material_no: str = "",
    platform_id: str = "",
    source_tag: str = "",
) -> dict[str, Any]:
    ot_code, ot_meta = normalize_order_type_arg(order_type)
    return {
        "customer_code": (customer_code or "").strip().upper(),
        "order_type": ot_code,
        "order_type_input": (order_type or "").strip(),
        "order_type_resolved": ot_meta,
        "material_no": (material_no or "").strip(),
        "customer_material_no": (customer_material_no or "").strip(),
        "platform_id": (platform_id or "").strip(),
        "source_tag": (source_tag or "").strip(),
    }


def _validate_slots(slots: dict[str, Any]) -> str | None:
    if not slots.get("customer_code"):
        return "缺少客户编码 customer_code（字母为主，末尾可带1-2位数字）"
    if not slots.get("order_type"):
        return (
            "缺少订单类型 order_type（可传类型码如 10，或中文如「普通订单」，"
            "将按 ORDER_TYPE_CSS 模糊匹配）"
        )
    ot_in = str(slots.get("order_type_input") or "")
    if ot_in and any("\u4e00" <= ch <= "\u9fff" for ch in ot_in) and not slots.get(
        "order_type_resolved"
    ):
        return (
            f"未能在订单类型字典中匹配到「{ot_in}」，"
            "请换更完整的名称（如普通订单）或直接传类型码"
        )
    if not slots.get("material_no") and not slots.get("customer_material_no"):
        return "物料号 material_no 与客户物料号 customer_material_no 至少填一个（字母数字组合）"
    return None


def _is_order_type_code(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9A-Za-z]{1,12}", (value or "").strip()))


def _to_diagnose_params(slots: dict[str, str]) -> dict[str, Any]:
    """映射为 diagnoseMaterialSellable 入参；物料号与客户物料号二选一。"""
    # 文档：不能同时传；现网优先保留客户物料号
    pmc = slots["material_no"]
    cust_pmc = slots["customer_material_no"]
    if pmc and cust_pmc:
        pmc = ""

    params: dict[str, Any] = {
        "customerCode": slots["customer_code"],
        "orderType": slots["order_type"],
    }
    if pmc:
        params["pmcCode"] = pmc
    if cust_pmc:
        params["customerPmcCode"] = cust_pmc
    if slots["source_tag"]:
        params["sourceTag"] = slots["source_tag"]
    if slots["platform_id"]:
        try:
            params["platformId"] = int(slots["platform_id"])
        except ValueError:
            params["platformId"] = slots["platform_id"]
    return params


def _diagnose_url() -> str:
    full = (os.getenv("CSS_DIAGNOSE_URL") or os.getenv("CSS_API_CHECK_URL") or "").strip()
    if full:
        return full
    domain = (os.getenv("CSS_DOMAIN") or _DEFAULT_DOMAIN).rstrip("/")
    path = (os.getenv("CSS_DIAGNOSE_PATH") or _DEFAULT_DIAGNOSE_PATH).strip()
    if not path.startswith("/"):
        path = "/" + path
    return f"{domain}{path}"


def _ensure_certificate() -> dict[str, Any]:
    client = get_css_client()
    cert = client.get_certificate()
    return {
        "ok": True,
        "step": "login",
        "certificate_preview": f"{cert[:6]}…{cert[-4:]}" if len(cert) > 12 else cert,
        "certificate_len": len(cert),
        "idle_ttl_sec": int(client._idle_ttl_sec),
        "login_url": client._login_url(),
        "hint": "certificate 自上次使用起 30 分钟未用会自动重新登录",
    }


def _summarize_steps(steps: Any, *, limit: int = 12) -> list[dict[str, str]]:
    if not isinstance(steps, list):
        return []
    out: list[dict[str, str]] = []
    for item in steps[:limit]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": str(item.get("name") or ""),
                "status": str(item.get("status") or ""),
                "detail": str(item.get("detail") or ""),
            }
        )
    return out


def _normalize_diagnose_result(
    raw: dict[str, Any],
    *,
    slots: dict[str, str],
    auth_meta: dict[str, Any],
    request_url: str,
    params: dict[str, Any],
    focus: str,
) -> dict[str, Any]:
    status = str(raw.get("status") or "")
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    msg = str(raw.get("msg") or "")

    if status in ("E", "M") or not data:
        return {
            "ok": False,
            "source": "css",
            "auth": auth_meta,
            "request_url": request_url,
            "request_params": params,
            "slots": slots,
            "status": status,
            "error": msg or f"诊断接口失败 status={status}",
            "raw": raw,
        }

    sellable = bool(data.get("sellable"))
    reason_codes = data.get("reasonCodes") or []
    reason_descs = data.get("reasonDescs") or []
    if not isinstance(reason_codes, list):
        reason_codes = [str(reason_codes)]
    if not isinstance(reason_descs, list):
        reason_descs = [str(reason_descs)]

    summary = str(data.get("summary") or "")
    if not summary:
        if sellable:
            summary = "可销售"
        elif reason_descs:
            summary = "不可销售：" + "；".join(str(x) for x in reason_descs)
        else:
            summary = "不可销售"

    result: dict[str, Any] = {
        "ok": True,
        "source": "css",
        "focus": focus,
        "auth": auth_meta,
        "request_url": request_url,
        "request_params": params,
        "slots": slots,
        "status": status,
        "sellable": sellable,
        "summary": summary,
        "message": summary,
        "reason_codes": [str(x) for x in reason_codes],
        "reasons": [str(x) for x in reason_descs],
        "customer_code": data.get("customerCode") or data.get("effectiveCustomerCode"),
        "original_customer_code": data.get("originalCustomerCode"),
        "effective_customer_code": data.get("effectiveCustomerCode"),
        "order_type": data.get("orderType"),
        "order_type_desc": data.get("orderTypeDesc"),
        "source_tag": data.get("sourceTag"),
        "source_tag_desc": data.get("sourceTagDesc"),
        "pmc_code": data.get("pmcCode") or data.get("resolvedPmcCode"),
        "customer_pmc_code": data.get("customerPmcCode"),
        "steps": _summarize_steps(data.get("steps")),
    }
    if focus == "reason" and sellable:
        result["hint"] = "诊断结果为可销售，无不可售原因。"
    return result


def _diagnose(slots: dict[str, str], *, focus: str) -> dict[str, Any]:
    auth_meta = _ensure_certificate()
    url = _diagnose_url()
    params = _to_diagnose_params(slots)
    try:
        client = get_css_client()
        raw = client.post_business(url, params, as_params_form=True)
        return _normalize_diagnose_result(
            raw,
            slots=slots,
            auth_meta=auth_meta,
            request_url=url,
            params=params,
            focus=focus,
        )
    except CssAuthError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "auth": auth_meta,
            "slots": slots,
            "request_url": url,
            "request_params": params,
        }


@tool
def css_fetch_certificate() -> str:
    """获取 CSS/SAAF 平台验签 key（certificate）。

    在调用可售查询等业务接口之前执行；通常由可售工具内部自动调用，也可单独用于排查登录。
    """
    try:
        meta = _ensure_certificate()
        return json.dumps(meta, ensure_ascii=False)
    except CssAuthError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)


@tool
def css_check_sellable(
    customer_code: str,
    order_type: str,
    material_no: str = "",
    customer_material_no: str = "",
    platform_id: str = "",
    source_tag: str = "",
) -> str:
    """查询物料对指定客户/订单类型是否可售。

    流程：先登录 CSS 获取 certificate，再调用 diagnoseMaterialSellable。
    客户编码多为字母，末尾可带1-2位数字；物料号为字母数字组合；
    订单类型可传码（10）或中文（普通订单），中文按 ORDER_TYPE_CSS 模糊匹配。

    Args:
        customer_code: 客户编码（如 ZHXSYLD1）
        order_type: 订单类型码或中文名（如 10 / 普通订单 / 保外补货）
        material_no: 我司物料号 pmcCode（与客户物料号二选一）
        customer_material_no: 客户物料号 customerPmcCode
        platform_id: 可选平台 ID
        source_tag: 可选产品来源；不传则由订单设置解析
    """
    slots = _normalize_slots(
        customer_code,
        order_type,
        material_no,
        customer_material_no,
        platform_id,
        source_tag,
    )
    miss = _validate_slots(slots)
    if miss:
        return json.dumps({"ok": False, "error": miss, "slots": slots}, ensure_ascii=False)

    try:
        result = _diagnose(slots, focus="check")
        return json.dumps(result, ensure_ascii=False)
    except CssAuthError as exc:
        return json.dumps({"ok": False, "error": str(exc), "slots": slots}, ensure_ascii=False)


@tool
def css_explain_unsellable(
    customer_code: str,
    order_type: str,
    material_no: str = "",
    customer_material_no: str = "",
    platform_id: str = "",
    source_tag: str = "",
) -> str:
    """查询物料不可销售的原因说明（原因码 + 中文说明 + 检查步骤）。

    客户编码、物料号规则同 css_check_sellable；订单类型支持中文模糊匹配字典。

    Args:
        customer_code: 客户编码
        order_type: 订单类型码或中文名
        material_no: 我司物料号
        customer_material_no: 客户物料号
        platform_id: 可选平台 ID
        source_tag: 可选产品来源
    """
    slots = _normalize_slots(
        customer_code,
        order_type,
        material_no,
        customer_material_no,
        platform_id,
        source_tag,
    )
    miss = _validate_slots(slots)
    if miss:
        return json.dumps({"ok": False, "error": miss, "slots": slots}, ensure_ascii=False)

    try:
        result = _diagnose(slots, focus="reason")
        return json.dumps(result, ensure_ascii=False)
    except CssAuthError as exc:
        return json.dumps({"ok": False, "error": str(exc), "slots": slots}, ensure_ascii=False)


@tool
def css_list_lookup_catalog(keyword: str = "") -> str:
    """列出本地已登记的 CSS 快码经验（lookupType / 用途 / 使用场景）。

    意图为「有哪些字典 / 快码经验 / 某个业务用哪个 lookupType」时先调用本工具。
    码值本身需再用 css_lookup_values 实时拉取。

    Args:
        keyword: 可选关键词，按用途、lookupType、场景过滤
    """
    items = list_catalog_summaries(keyword)
    return json.dumps(
        {
            "ok": True,
            "source": "catalog",
            "count": len(items),
            "items": items,
            "hint": "查询具体码值请调用 css_lookup_values(lookup_type, system_code)",
        },
        ensure_ascii=False,
    )


@tool
def css_lookup_values(
    lookup_type: str,
    system_code: str = "CSS",
    lan: str = "CN",
    enabled_only: bool = True,
) -> str:
    """按 lookupType 查询 CSS 快码字典项（baseLookupValuesService/find）。

    先验签再请求；若本地经验目录有登记，会附带用途说明。
    意图为「查字典 / 查快码 / 某 lookupType 有哪些值」且已有 lookupType 时调用。

    Args:
        lookup_type: 快码类型，如 SERVICE_PROVIDER_LX_FILTER
        system_code: 系统码，默认 CSS
        lan: 语言，默认 CN
        enabled_only: 仅返回 enabledFlag=Y 的项
    """
    result = fetch_lookup_values(
        lookup_type,
        system_code,
        lan=lan or "CN",
        enabled_only=bool(enabled_only),
    )
    return json.dumps(result, ensure_ascii=False)


CSS_TOOLS: list[BaseTool] = [
    css_fetch_certificate,
    css_check_sellable,
    css_explain_unsellable,
    css_list_lookup_catalog,
    css_lookup_values,
]
