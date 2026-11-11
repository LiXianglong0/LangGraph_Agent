"""弱模型场景：对高置信业务话术先预调工具，再交给 LLM 转述。"""

from __future__ import annotations

import json
import re
from typing import Any

# 「CSC70173订单状态」/「订单状态 CSC70173」/「查一下 QAD 单号 XXXXXXXX 状态」
_ORDER_STATUS_RE = re.compile(
    r"(?:"
    r"([A-Za-z0-9]{8})\s*的?\s*(?:QAD)?\s*订单状态"
    r"|"
    r"(?:QAD)?\s*订单状态[：:\s]*([A-Za-z0-9]{8})"
    r"|"
    r"(?:查(?:一下|下)?|查询|看看)\s*(?:QAD)?\s*(?:订单|单号)\s*([A-Za-z0-9]{8})"
    r")",
    re.IGNORECASE,
)


def extract_qad_bill_no(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _ORDER_STATUS_RE.search(raw)
    if m:
        for g in m.groups():
            if g:
                return g.upper()
    # 整句几乎就是 8 位单号 +「状态」
    m2 = re.fullmatch(r"\s*([A-Za-z0-9]{8})\s*(?:的?\s*状态)?\s*", raw)
    if m2 and ("状态" in raw or "订单" in raw):
        return m2.group(1).upper()
    return None


def prefetch_business_context(
    message: str,
    tool_names: list[str] | None,
) -> str | None:
    """若命中预调规则，返回可注入用户消息的工具结果文本；否则 None。"""
    names = set(tool_names or [])
    text = (message or "").strip()
    if not text:
        return None

    # 订单状态优先（避免 8 位单号被当成物料）
    if "qad_check_order_status" in names:
        bill = extract_qad_bill_no(text)
        if bill:
            from agent.qad.tools import qad_check_order_status

            raw = qad_check_order_status.invoke({"bill_no": bill})
            try:
                data: Any = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                data = {"raw": raw}
            return (
                f"用户问题：{text}\n\n"
                f"【已自动调用工具 qad_check_order_status】\n"
                f"{json.dumps(data, ensure_ascii=False)}\n\n"
                "请严格依据以上工具 JSON 用中文简洁回答订单状态；"
                "优先使用 summary / bill_status_code / bill_status_label；"
                "禁止说无法查询或让用户去别的系统查。"
            )

    # 可售：客户(字母+可选1-2位数字) + 物料(字母数字) + 可选中文订单类型
    if "css_check_sellable" in names or "css_explain_unsellable" in names:
        from agent.css.slots import extract_sellable_slots

        slots = extract_sellable_slots(text)
        if slots.get("intent_sellable") and slots.get("customer_code") and (
            slots.get("material_no") or slots.get("customer_material_no")
        ):
            # 无订单类型时默认普通订单(10)，并在结果中注明
            order_type = slots.get("order_type") or "10"
            defaulted = not bool(slots.get("order_type"))
            tool_name = (
                "css_explain_unsellable"
                if (
                    "不可售" in text
                    or "为什么不可" in text
                    or "为何不可" in text
                )
                and "css_explain_unsellable" in names
                else "css_check_sellable"
            )
            if tool_name not in names:
                tool_name = "css_check_sellable"

            from agent.css.tools import css_check_sellable, css_explain_unsellable

            fn = (
                css_explain_unsellable
                if tool_name == "css_explain_unsellable"
                else css_check_sellable
            )
            raw = fn.invoke(
                {
                    "customer_code": slots["customer_code"],
                    "order_type": order_type,
                    "material_no": slots.get("material_no") or "",
                    "customer_material_no": slots.get("customer_material_no") or "",
                }
            )
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                data = {"raw": raw}
            note = ""
            if defaulted:
                note = (
                    "\n说明：用户未给出订单类型，已默认按「普通订单(10)」诊断；"
                    "若需其他类型请用中文订单名或类型码再说一次。"
                )
            elif slots.get("order_type_match"):
                m = slots["order_type_match"]
                note = (
                    f"\n说明：订单类型「{slots.get('order_type_query')}」"
                    f"已匹配为 {m.get('order_type')} {m.get('order_type_desc')}。"
                )
            return (
                f"用户问题：{text}\n\n"
                f"【已自动解析槽位】{json.dumps(slots, ensure_ascii=False)}\n"
                f"【已自动调用工具 {tool_name}】\n"
                f"{json.dumps(data, ensure_ascii=False)}\n"
                f"{note}\n\n"
                "请严格依据工具 JSON 用中文回答是否可售/原因；"
                "带上客户、物料、订单类型；禁止说无法查询。"
            )

    return None
