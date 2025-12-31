# proposal_engine.py
# 목적: (1) 기존 HTML 템플릿의 기본정보/색상/이미지 치환
#      (2) "자료 페이지 이미지"를 AI로 분석하여 '텍스트/표'로 추출한 뒤, 최종 HTML에 페이지로 추가
#
# 주의: 이 파일은 Streamlit Cloud에서도 그대로 동작하도록 "파일 시스템 + OpenAI API"만 사용합니다.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import base64
import json
import re


# -----------------------------
# 데이터 구조 (AI 추출 결과)
# -----------------------------
@dataclass
class ExtractedBlock:
    """한 페이지 안의 블록(문단/리스트/표)."""
    type: str  # "paragraph" | "bullets" | "table"
    text: Optional[str] = None
    items: Optional[List[str]] = None
    table: Optional[Dict[str, Any]] = None  # {"headers":[...], "rows":[[...], ...]}


@dataclass
class ExtractedPage:
    title: str
    subtitle: str = ""
    blocks: List[ExtractedBlock] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "blocks": [
                {
                    "type": b.type,
                    "text": b.text,
                    "items": b.items,
                    "table": b.table,
                }
                for b in (self.blocks or [])
            ],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ExtractedPage":
        blocks = []
        for b in d.get("blocks", []) or []:
            blocks.append(
                ExtractedBlock(
                    type=b.get("type", ""),
                    text=b.get("text"),
                    items=b.get("items"),
                    table=b.get("table"),
                )
            )
        return ExtractedPage(
            title=d.get("title", "").strip(),
            subtitle=(d.get("subtitle") or "").strip(),
            blocks=blocks,
        )


# -----------------------------
# 유틸
# -----------------------------
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_regex_replace(pattern: str, repl_fn: Callable[[re.Match], str], text: str, flags: int = 0) -> str:
    return re.sub(pattern, repl_fn, text, flags=flags)


def _b64_data_url_for_image(image_path: Path) -> str:
    # OpenAI 이미지 입력은 base64 data URL 또는 URL을 지원합니다.
    # (공식 문서: https://platform.openai.com/docs/guides/images-vision)
    suffix = image_path.suffix.lower().lstrip(".")
    if suffix == "jpg":
        suffix = "jpeg"
    mime = f"image/{suffix}"
    data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


# -----------------------------
# ProposalEngine
# -----------------------------
class ProposalEngine:
    def __init__(self, template_path: str = "proposal_template.html"):
        self.template_path = Path(template_path)

    # 1) 템플릿 로드
    def load_template(self) -> str:
        if not self.template_path.exists():
            raise FileNotFoundError(f"템플릿을 찾을 수 없습니다: {self.template_path}")
        return _read_text(self.template_path)

    # 2) 기본정보 치환(수신/제안/전화 등)
    def apply_basic_fields(self, html: str, recipient: str, proposer: str, tel: str) -> str:
        # 템플릿 안의 문구(예: "수신 :", "제안 :", "Tel.")를 찾아 바꿉니다.
        # 치환이 실패해도 앱이 멈추지 않도록, "패턴이 있으면 바꾸고 없으면 그냥 둡니다."

        def rep_recipient(m: re.Match) -> str:
            return f"{m.group(1)}{recipient}"

        def rep_proposer(m: re.Match) -> str:
            return f"{m.group(1)}{proposer}"

        def rep_tel(m: re.Match) -> str:
            # \1 + 숫자 시작 텍스트가 합쳐져 invalid group reference가 나는 문제를 피하려고
            # 반드시 함수 치환을 사용합니다.
            return f"{m.group(1)}{tel}"

        html = _safe_regex_replace(r"(\<strong\>\s*수신\s*:\s*\</strong\>\s*)([^<]+)", rep_recipient, html)
        html = _safe_regex_replace(r"(\<strong\>\s*제안\s*:\s*\</strong\>\s*)([^<]+)", rep_proposer, html)

        # Tel. 1833 - 9988 형태
        html = _safe_regex_replace(r"(Tel\.\s*)([0-9\s\-]+)", rep_tel, html)

        return html

    # 3) 색상(테마 변수) 치환: CSS 변수만 바꾸는 방식
    def apply_theme(self, html: str, theme: Dict[str, str]) -> str:
        # theme 예시:
        # {
        #   "--accent-blue": "#2196F3",
        #   "--accent-gold": "#C9A227",
        #   "--accent-navy": "#0B2A4A"
        # }
        for var, value in theme.items():
            # CSS 변수 정의 부분을 찾아 교체
            # 예: --accent-blue: #4A90E2;
            pat = rf"({re.escape(var)}\s*:\s*)([^;]+)(;)"
            html = re.sub(pat, rf"\1{value}\3", html)
        return html

    # 4) "AI로 추출된 페이지"를 HTML 페이지로 렌더링
    def render_extracted_page(self, page: ExtractedPage) -> str:
        blocks_html = []
        for b in (page.blocks or []):
            if b.type == "paragraph" and b.text:
                blocks_html.append(f'<p class="gen-p">{_html_escape(b.text)}</p>')
            elif b.type == "bullets" and b.items:
                lis = "\n".join(f"<li>{_html_escape(it)}</li>" for it in b.items if (it or "").strip())
                blocks_html.append(f"<ul class='gen-ul'>\n{lis}\n</ul>")
            elif b.type == "table" and b.table:
                blocks_html.append(_render_table(b.table))
            # 알 수 없는 타입은 무시(앱이 죽지 않게)

        subtitle_html = f'<p class="gen-sub">{_html_escape(page.subtitle)}</p>' if page.subtitle else ""

        return f"""
<div class="page generated-page">
  <div class="gen-wrap">
    <div class="gen-header">
      <h1 class="gen-title">{_html_escape(page.title)}</h1>
      {subtitle_html}
    </div>
    <div class="gen-body">
      {''.join(blocks_html)}
    </div>
  </div>
</div>
"""

    # 5) 최종 HTML에 페이지 추가
    def append_pages(self, html: str, pages: Sequence[ExtractedPage]) -> str:
        pages_html = "\n".join(self.render_extracted_page(p) for p in pages)

        # 문서 컨테이너 마지막에 붙입니다.
        marker = "</div>\n\n</body>"
        if marker in html:
            return html.replace(marker, f"{pages_html}\n{marker}", 1)

        # 위 마커가 없으면, 그냥 </body> 직전에 붙임
        if "</body>" in html:
            return html.replace("</body>", f"{pages_html}\n</body>", 1)

        # 정말 이상한 템플릿이라면 끝에 붙임
        return html + pages_html

    # 6) OpenAI Vision으로 이미지 -> 페이지(JSON) 추출
    def extract_pages_from_images(
        self,
        openai_client: Any,
        image_paths: Sequence[Path],
        model: str = "gpt-4o-mini",
        progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[ExtractedPage]:
        pages: List[ExtractedPage] = []
        total = len(image_paths)

        for i, p in enumerate(image_paths, start=1):
            if progress:
                progress(i, total, f"분석 중: {p.name}")

            page_dict = _openai_extract_one_page(openai_client, p, model=model)
            pages.append(ExtractedPage.from_dict(page_dict))

        return pages

    # 7) 추출 결과를 JSON으로 저장/로드 (반복 비용 절감용)
    def save_pages_json(self, pages: Sequence[ExtractedPage], json_path: str) -> None:
        data = [p.to_dict() for p in pages]
        _write_text(Path(json_path), json.dumps(data, ensure_ascii=False, indent=2))

    def load_pages_json(self, json_path: str) -> List[ExtractedPage]:
        p = Path(json_path)
        if not p.exists():
            return []
        data = json.loads(_read_text(p))
        return [ExtractedPage.from_dict(d) for d in (data or [])]


# -----------------------------
# HTML 렌더 헬퍼
# -----------------------------
def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _render_table(table: Dict[str, Any]) -> str:
    headers = table.get("headers") or []
    rows = table.get("rows") or []

    thead = ""
    if headers:
        ths = "".join(f"<th>{_html_escape(str(h))}</th>" for h in headers)
        thead = f"<thead><tr>{ths}</tr></thead>"

    trs = []
    for r in rows:
        tds = "".join(f"<td>{_html_escape(str(c))}</td>" for c in (r or []))
        trs.append(f"<tr>{tds}</tr>")
    tbody = f"<tbody>{''.join(trs)}</tbody>"

    return f"""
<div class="gen-table-wrap">
  <table class="gen-table">
    {thead}
    {tbody}
  </table>
</div>
"""


# -----------------------------
# OpenAI 호출 (이미지 1장 -> JSON)
# -----------------------------
def _openai_extract_one_page(openai_client: Any, image_path: Path, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """
    OpenAI Responses API를 사용합니다.
    - 이미지 입력 방식은 공식 문서의 data URL 형태를 따릅니다.
    - 출력은 반드시 JSON으로 받습니다.

    참고:
    - https://platform.openai.com/docs/guides/images-vision
    - https://github.com/openai/openai-python
    """
    img_url = _b64_data_url_for_image(image_path)

    prompt = (
        "당신은 한국어 제안서 페이지를 '텍스트/표/리스트'로 구조화하는 도우미입니다.\n"
        "업로드된 이미지는 제안서 1페이지입니다.\n"
        "목표: 이미지를 보고, 페이지의 '제목/부제/핵심 내용'을 HTML에 넣기 좋은 구조(JSON)로 추출하세요.\n\n"
        "출력 형식(반드시 JSON만):\n"
        "{\n"
        '  "title": "페이지 제목",\n'
        '  "subtitle": "부제(없으면 빈 문자열)",\n'
        '  "blocks": [\n'
        '    {"type": "paragraph", "text": "문단"},\n'
        '    {"type": "bullets", "items": ["항목1", "항목2"]},\n'
        '    {"type": "table", "table": {"headers": ["..."], "rows": [["..."], ["..."]]}}\n'
        "  ]\n"
        "}\n\n"
        "규칙:\n"
        "- 이미지에 있는 글자를 가능한 한 그대로 옮기되, 너무 작은 글씨로 정확히 읽기 어려우면 요약해서 써도 됩니다.\n"
        "- 표는 가능한 한 표 형태로 유지하세요.\n"
        "- 로고/장식용 아이콘/배경 이미지는 무시하고, 정보(텍스트)만 추출하세요.\n"
    )

    # openai-python README 예시 형식을 따르는 Responses API 호출
    response = openai_client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": img_url},
                ],
            }
        ],
    )

    # Responses API는 텍스트 결과를 여러 곳에 담을 수 있으므로,
    # 가장 안전하게 response.output_text를 사용합니다.
    text = getattr(response, "output_text", None)
    if not text:
        # 일부 버전에서 output_text가 없을 수도 있어 방어적으로 처리
        text = str(response)

    # JSON 파싱 (모델이 실수로 코드블럭을 넣는 경우가 있어 제거)
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except Exception as e:
        # 실패 시, 최소한의 형태로 감싸서 반환
        data = {
            "title": f"{image_path.stem}",
            "subtitle": "",
            "blocks": [{"type": "paragraph", "text": f"(JSON 파싱 실패) 원문:\n{cleaned[:1200]}"}],
        }

    # 필수 키 보정
    data.setdefault("title", image_path.stem)
    data.setdefault("subtitle", "")
    data.setdefault("blocks", [])

    return data
