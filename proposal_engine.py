# proposal_engine.py
# -*- coding: utf-8 -*-
"""
목적:
- proposal_template.html을 읽어
  1) 기본 정보(수신/제안/Tel/Email) 치환
  2) CSS 변수(색상) 치환
  3) 레포(attachment_pages/)에 있는 이미지를 자동으로 data URL(base64)로 임베딩
     → Streamlit 미리보기/다운로드 HTML에서도 이미지가 항상 표시되도록 처리

주의:
- "이미지 업로드/교체" UI 기능은 제거된 버전입니다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict
import base64
import mimetypes
import re


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _safe_sub(pattern: str, repl_fn, text: str, flags: int = 0) -> str:
    # 치환 문자열에서 \1 + 숫자처럼 합쳐져 "invalid group reference"가 발생하지 않게
    # 항상 함수 치환(lambda)을 사용합니다.
    return re.sub(pattern, repl_fn, text, flags=flags)


class ProposalEngine:
    def __init__(self, template_path: str = "proposal_template.html"):
        self.template_path = Path(template_path)

    def load_template(self) -> str:
        if not self.template_path.exists():
            raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {self.template_path}")
        return _read_text(self.template_path)

    def apply_basic_fields(self, html: str, *, recipient: str, proposer: str, tel: str, email: str) -> str:
        # 수신/제안
        html = _safe_sub(
            r'(<strong>\s*수신\s*:\s*</strong>\s*)([^<]+)',
            lambda m: m.group(1) + recipient,
            html,
            flags=re.IGNORECASE,
        )
        html = _safe_sub(
            r'(<strong>\s*제안\s*:\s*</strong>\s*)([^<]+)',
            lambda m: m.group(1) + proposer,
            html,
            flags=re.IGNORECASE,
        )

        # Tel.
        html = _safe_sub(
            r'(Tel\.\s*)([0-9\s\-]+)',
            lambda m: m.group(1) + tel,
            html,
            flags=re.IGNORECASE,
        )

        # Email.
        email_clean = (email or "").strip()
        if email_clean:
            html = _safe_sub(
                r'(Email\.\s*)([^<\n]+)',
                lambda m: m.group(1) + email_clean,
                html,
                flags=re.IGNORECASE,
            )
        else:
            # 이메일을 입력하지 않으면, 마지막 페이지의 이메일 줄 자체를 제거
            html = _safe_sub(
                r'\s*<p[^>]*>\s*<i class="fas fa-envelope"[^>]*></i>\s*Email\.[\s\S]*?</p>\s*',
                lambda m: "",
                html,
                flags=re.IGNORECASE,
            )

        return html

    def apply_theme_vars(self, html: str, css_vars: Dict[str, str]) -> str:
        # 예: {"--accent-blue": "#4A90E2"} 형태로 전달
        for var, value in css_vars.items():
            pattern = rf'({re.escape(var)}\s*:\s*)([^;]+)(;)'
            html = _safe_sub(pattern, lambda m, v=value: m.group(1) + v + m.group(3), html)
        return html

    def embed_attachment_images(self, html: str, assets_dir: str = "attachment_pages") -> str:
        """
        Streamlit 미리보기/다운로드 HTML에서 이미지가 항상 보이도록,
        <img src="attachment_pages/..."> 형태를 data URL(base64)로 자동 변환합니다.

        - 레포(attachment_pages/)에 있는 이미지 파일만 사용합니다.
        - 템플릿/테마/폰트 등의 스타일은 변경하지 않고 src만 변경합니다.
        """
        base_dir = self.template_path.parent
        assets_prefix = assets_dir.rstrip("/") + "/"

        def _repl(match: re.Match) -> str:
            prefix, src, suffix = match.group(1), match.group(2), match.group(3)

            # 이미 data URL이거나 외부 URL이면 그대로 둡니다.
            if src.startswith("data:") or src.startswith("http://") or src.startswith("https://"):
                return match.group(0)

            normalized = src.lstrip("./")
            if not normalized.startswith(assets_prefix):
                return match.group(0)

            file_path = (base_dir / normalized)
            if not file_path.exists():
                return match.group(0)

            mime, _ = mimetypes.guess_type(str(file_path))
            if mime is None:
                mime = "image/jpeg"

            b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
            data_uri = f"data:{mime};base64,{b64}"
            return prefix + data_uri + suffix

        return re.sub(
            r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'])',
            _repl,
            html,
            flags=re.IGNORECASE,
        )
