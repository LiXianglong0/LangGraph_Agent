"""RAGFlow HTTP 客户端（与 Agent 进程分离部署）。"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


@dataclass
class RagflowSettings:
    """RAGFlow 连接配置；未启用时不发起真实请求。"""

    enabled: bool = False
    base_url: str = "http://127.0.0.1"
    api_key: str = ""
    dataset_ids: list[str] = field(default_factory=list)
    page_size: int = 6
    similarity_threshold: float = 0.2
    timeout_sec: float = 30.0

    def is_ready(self) -> bool:
        """判断是否具备最小可用配置。"""
        return bool(
            self.enabled
            and self.base_url.strip()
            and self.api_key.strip()
            and self.dataset_ids
        )


@dataclass
class SourceDoc:
    """检索命中的去重后源文件（index 与回答中的 [n] 一一对应）。"""

    index: int
    document_id: str
    dataset_id: str
    name: str
    score: float | None = None


@dataclass
class RetrieveResult:
    """检索文本 + 可下载源文件列表。"""

    text: str
    sources: list[SourceDoc] = field(default_factory=list)


class RagflowClient:
    """调用 RAGFlow OpenAPI：检索与文档下载。"""

    def __init__(self, settings: RagflowSettings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.api_key.strip()}",
        }

    def retrieve(self, question: str) -> str:
        """按问题检索知识库片段，返回供模型阅读的纯文本。"""
        return self.retrieve_with_sources(question).text

    def retrieve_with_sources(self, question: str) -> RetrieveResult:
        """检索并解析命中的源文件（去重），供前端展示下载。"""
        if not self.settings.is_ready():
            return RetrieveResult(
                text=(
                    "RAGFlow 未启用或配置不完整。"
                    "请在页面/环境中开启 enabled，并填写 base_url、api_key、dataset_ids。"
                )
            )

        url = self.settings.base_url.rstrip("/") + "/api/v1/retrieval"
        payload = {
            "question": question,
            "dataset_ids": self.settings.dataset_ids,
            "page_size": self.settings.page_size,
            "similarity_threshold": self.settings.similarity_threshold,
        }

        try:
            with httpx.Client(timeout=self.settings.timeout_sec) as client:
                resp = client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                body = resp.json()
        except httpx.HTTPError as exc:
            return RetrieveResult(text=f"RAGFlow 请求失败：{exc}")

        if isinstance(body, dict) and body.get("code", 0) not in (0, None):
            return RetrieveResult(
                text=f"RAGFlow 返回错误：{body.get('message') or body}"
            )

        data = body.get("data") if isinstance(body, dict) else None
        chunks: list = []
        if isinstance(data, dict):
            chunks = data.get("chunks") or []
        elif isinstance(data, list):
            chunks = data

        if not chunks:
            return RetrieveResult(text="未检索到相关知识片段。")

        fallback_ds = self.settings.dataset_ids[0] if self.settings.dataset_ids else ""
        # 先按「首次出现」为每个文档分配稳定序号 [1][2]…，与下方文件列表一致
        order: list[str] = []
        meta: dict[str, dict] = {}

        parsed_chunks: list[dict] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                parsed_chunks.append({"raw": chunk})
                continue
            content = (
                chunk.get("content_with_weight")
                or chunk.get("content")
                or chunk.get("text")
                or ""
            )
            doc_name = (
                chunk.get("document_keyword")
                or chunk.get("docnm_kwd")
                or chunk.get("document_name")
                or "未命名文档"
            )
            score_raw = chunk.get("similarity") or chunk.get("score")
            try:
                score = float(score_raw) if score_raw is not None else None
            except (TypeError, ValueError):
                score = None
            doc_id = str(
                chunk.get("document_id")
                or chunk.get("doc_id")
                or chunk.get("documentId")
                or ""
            ).strip()
            ds_id = str(
                chunk.get("dataset_id")
                or chunk.get("kb_id")
                or chunk.get("kbId")
                or fallback_ds
            ).strip()
            # 无 id 时用文件名兜底，保证仍能编号
            key = doc_id or f"name:{doc_name}"
            if key not in meta:
                order.append(key)
                meta[key] = {
                    "document_id": doc_id or key,
                    "dataset_id": ds_id,
                    "name": str(doc_name),
                    "score": score,
                }
            else:
                prev_score = meta[key]["score"]
                if score is not None and (
                    prev_score is None or score > prev_score
                ):
                    meta[key]["score"] = score

            parsed_chunks.append(
                {
                    "key": key,
                    "content": content,
                    "name": str(doc_name),
                    "score": score,
                }
            )

        index_of = {key: i + 1 for i, key in enumerate(order)}
        sources = [
            SourceDoc(
                index=index_of[key],
                document_id=str(meta[key]["document_id"]),
                dataset_id=str(meta[key]["dataset_id"] or fallback_ds),
                name=str(meta[key]["name"]),
                score=meta[key]["score"],
            )
            for key in order
        ]

        catalog = "【引用编号与文件对应表】\n" + "\n".join(
            f"[{s.index}] {s.name}"
            + (f"（相关度 {s.score}）" if s.score is not None else "")
            for s in sources
        )

        lines: list[str] = [catalog, "【检索片段】"]
        for i, item in enumerate(parsed_chunks, start=1):
            if "raw" in item:
                lines.append(f"(片段{i}) {item['raw']}")
                continue
            n = index_of[item["key"]]
            head = f"(片段{i}) 引用[{n}] 文件:{item['name']}"
            if item["score"] is not None:
                head += f" 相关度:{item['score']}"
            lines.append(f"{head}\n{item['content']}".strip())

        return RetrieveResult(text="\n\n".join(lines), sources=sources)

    def download_document(self, dataset_id: str, document_id: str) -> tuple[bytes, str]:
        """下载知识库原文件，返回 (内容, 建议文件名)。"""
        if not self.settings.api_key.strip() or not self.settings.base_url.strip():
            raise ValueError("RAGFlow API Key / 地址未配置")
        ds = dataset_id.strip()
        doc = document_id.strip()
        if not ds or not doc:
            raise ValueError("dataset_id 与 document_id 不能为空")

        url = (
            f"{self.settings.base_url.rstrip('/')}"
            f"/api/v1/datasets/{ds}/documents/{doc}"
        )
        headers = {"Authorization": f"Bearer {self.settings.api_key.strip()}"}
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(headers=headers, url=url)
            resp.raise_for_status()
            # 若返回 JSON 错误体
            ctype = (resp.headers.get("content-type") or "").lower()
            if "application/json" in ctype:
                body = resp.json()
                raise RuntimeError(body.get("message") or str(body))

            filename = doc
            cd = resp.headers.get("content-disposition") or ""
            if "filename=" in cd:
                # filename="xxx.pdf" 或 filename*=UTF-8''xxx
                part = cd.split("filename=")[-1].strip().strip('"')
                if part.startswith("UTF-8''"):
                    from urllib.parse import unquote

                    part = unquote(part[7:])
                if part:
                    filename = part
            return resp.content, filename
