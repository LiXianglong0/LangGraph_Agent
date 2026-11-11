"""可售物料槽位解析：客户编码 / 物料号 / 订单类型（汉字模糊匹配字典）。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

# 客户：字母开头，整段以字母为主，末尾可带 1～2 位数字（如 ZHXSYLD1、BHKH）
_CUSTOMER_RE = re.compile(r"\b([A-Za-z]{2,}[0-9]{0,2})\b")
# 物料：含字母与数字（可含下划线），长度通常 ≥6，避免把短客户码当物料
_MATERIAL_RE = re.compile(r"\b([A-Za-z0-9_]{6,})\b")
# 订单类型汉字片段（含「订单/类型」等）
_ORDER_CN_RE = re.compile(
    r"([\u4e00-\u9fff]{2,20}(?:订单|类型)?|普通订单|服务商|保外|保内|商用|工程|备货)"
)

_SELLABLE_INTENT = re.compile(
    r"(可售|可销售|不可售|为什么不可|为何不可|"
    r"能否下单|能不能下单|能不能下|是否可以下单|可不可以下单|可否下单|"
    r"能不能卖|是否可卖|可以下单|下单)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _order_type_dict() -> list[tuple[str, str]]:
    """返回 [(lookupCode, meaning), ...]，失败则空列表。"""
    try:
        from agent.css.lookup import fetch_lookup_values

        result = fetch_lookup_values("ORDER_TYPE_CSS", "CSS")
        if not result.get("ok"):
            return []
        out: list[tuple[str, str]] = []
        for row in result.get("values") or []:
            code = str(row.get("lookupCode") or "").strip()
            meaning = str(row.get("meaning") or "").strip()
            if code:
                out.append((code, meaning))
        return out
    except Exception:  # noqa: BLE001
        return []


def clear_order_type_cache() -> None:
    _order_type_dict.cache_clear()


def resolve_order_type(text: str) -> dict[str, Any] | None:
    """将订单类型码或中文名解析为字典项；支持模糊匹配。"""
    raw = (text or "").strip()
    if not raw:
        return None

    items = _order_type_dict()
    if not items:
        # 纯数字码无法查字典时仍可直通
        if re.fullmatch(r"[0-9A-Za-z]{1,12}", raw):
            return {
                "order_type": raw,
                "order_type_desc": "",
                "match": "passthrough",
                "score": 1.0,
            }
        return None

    # 1) 精确匹配 code
    for code, meaning in items:
        if raw == code or raw.upper() == code.upper():
            return {
                "order_type": code,
                "order_type_desc": meaning,
                "match": "exact_code",
                "score": 1.0,
            }

    # 2) 精确匹配 meaning
    for code, meaning in items:
        if raw == meaning:
            return {
                "order_type": code,
                "order_type_desc": meaning,
                "match": "exact_meaning",
                "score": 1.0,
            }

    # 3) 包含关系（汉字模糊）
    candidates: list[tuple[float, str, str, str]] = []
    for code, meaning in items:
        if not meaning:
            continue
        if raw in meaning or meaning in raw:
            # 更短 meaning 被完整包含时分数更高
            score = min(len(raw), len(meaning)) / max(len(raw), len(meaning))
            score = max(score, 0.75)
            candidates.append((score, code, meaning, "contains"))
        else:
            ratio = SequenceMatcher(None, raw, meaning).ratio()
            if ratio >= 0.55:
                candidates.append((ratio, code, meaning, "fuzzy"))

    if not candidates:
        # 仍可能是纯码
        if re.fullmatch(r"[0-9A-Za-z]{1,12}", raw):
            return {
                "order_type": raw,
                "order_type_desc": "",
                "match": "passthrough",
                "score": 1.0,
            }
        return None

    candidates.sort(key=lambda x: (-x[0], -len(x[2])))
    score, code, meaning, how = candidates[0]
    return {
        "order_type": code,
        "order_type_desc": meaning,
        "match": how,
        "score": round(score, 3),
        "candidates": [
            {"order_type": c, "order_type_desc": m, "score": round(s, 3)}
            for s, c, m, _ in candidates[:5]
        ],
    }


def _is_customer_token(tok: str) -> bool:
    t = tok.strip()
    if not re.fullmatch(r"[A-Za-z]{2,}[0-9]{0,2}", t):
        return False
    # 排除纯物料感很强的（同时含多数字且很长）
    if len(t) >= 10 and sum(ch.isdigit() for ch in t) >= 3:
        return False
    return True


def _is_material_token(tok: str, customer: str = "") -> bool:
    t = tok.strip()
    if customer and t.upper() == customer.upper():
        return False
    if not re.fullmatch(r"[A-Za-z0-9_]{6,}", t):
        return False
    # 必须字母+数字都出现（或含下划线的料号）
    has_letter = any(ch.isalpha() for ch in t)
    has_digit = any(ch.isdigit() for ch in t)
    if not (has_letter and has_digit):
        return False
    # 8 位纯字母数字更像 QAD 单号，可售场景若同时有「订单状态」另处理
    if re.fullmatch(r"[A-Za-z0-9]{8}", t) and "_" not in t:
        # 仍可能是短物料；有下划线才更像料号；8位无下划线时降低优先级
        if sum(ch.isdigit() for ch in t) <= 2:
            return False
    return True


def extract_sellable_slots(text: str) -> dict[str, Any]:
    """从自然语言抽取客户/物料/订单类型。"""
    raw = (text or "").strip()
    intent = bool(_SELLABLE_INTENT.search(raw))

    tokens = re.findall(r"[A-Za-z0-9_]+", raw)
    customer = ""
    material = ""
    for tok in tokens:
        if not customer and _is_customer_token(tok):
            customer = tok.upper()
            continue
        if not material and _is_material_token(tok, customer):
            material = tok.upper() if tok.isascii() else tok
            # 物料号保留原大小写更安全
            material = tok
            continue

    # 若只识别到一个像客户、一个像物料但顺序反了：客户较短、物料更长更复杂
    if customer and not material:
        for tok in tokens:
            if tok.upper() == customer:
                continue
            if _is_material_token(tok, customer):
                material = tok
                break

    order_query = ""
    # 优先抓「XX订单」整词
    m_orders = re.findall(r"[\u4e00-\u9fff]{2,16}订单", raw)
    if m_orders:
        # 去掉「是否可以下单」里的「下单」误伤：只保留真正像类型的
        for cand in m_orders:
            if cand in ("可以下单", "能否下单", "可否下单", "是否下单"):
                continue
            if "下单" in cand and len(cand) <= 4:
                continue
            order_query = cand
            break
    if not order_query:
        # 再试字典 meaning 是否出现在句子中（长匹配优先）
        best = ""
        for _code, meaning in _order_type_dict():
            if meaning and meaning in raw and len(meaning) > len(best):
                best = meaning
        order_query = best

    resolved = resolve_order_type(order_query) if order_query else None

    return {
        "intent_sellable": intent,
        "customer_code": customer,
        "material_no": material,
        "order_type_query": order_query,
        "order_type": (resolved or {}).get("order_type") or "",
        "order_type_desc": (resolved or {}).get("order_type_desc") or "",
        "order_type_match": resolved,
    }


def normalize_order_type_arg(order_type: str) -> tuple[str, dict[str, Any] | None]:
    """工具入参：码或中文 → 标准 order_type code。"""
    raw = (order_type or "").strip()
    if not raw:
        return "", None
    # 已是纯码
    if re.fullmatch(r"[0-9A-Za-z]{1,12}", raw) and not re.search(r"[\u4e00-\u9fff]", raw):
        resolved = resolve_order_type(raw)
        return (resolved or {}).get("order_type") or raw, resolved
    resolved = resolve_order_type(raw)
    if resolved:
        return str(resolved["order_type"]), resolved
    return raw, None
