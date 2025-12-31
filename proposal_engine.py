# proposal_engine.py
# -*- coding: utf-8 -*-
"""
목적:
- 기존 proposal_template.html을 읽어
  1) 기본 정보(수신/제안/Tel) 치환
  2) CSS 변수(색상) 치환
  3) 이미지 src를 업로드 이미지(data URL)로 교체
- "이미지(자료) → 텍스트 추출" 기능은 포함하지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import base64
import re


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _b64_data_url(binary: bytes, mime: str) -> str:
    b64 = base64.b64encode(binary).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _safe_sub(pattern: str, repl_fn, text: str, flags: int = 0) -> str:
    # 치환 문자열에서 \1 + 숫자처럼 합쳐져 "invalid group reference"가 발생하지 않게
    # 항상 함수 치환(lambda)을 사용합니다.
    return re.sub(pattern, repl_fn, text, flags=flags)


@dataclass
class ImageReplacement:
    original_src: str
    data_url: str
    mime: str


class ProposalEngine:
    def __init__(self, template_path: str = "proposal_template.html"):
        self.template_path = Path(template_path)

    def load_template(self) -> str:
        if not self.template_path.exists():
            raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {self.template_path}")
        return _read_text(self.template_path)

    def apply_basic_fields(self, html: str, *, recipient: str, proposer: str, tel: str) -> str:
        # 템플릿의 실제 문구에 맞춰 정규식이 필요합니다.
        # (현재는 기존 코드에서 쓰던 패턴을 안전한 방식으로 유지)
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
        html = _safe_sub(
            r'(Tel\.\s*)([0-9\s\-]+)',
            lambda m: m.group(1) + tel,
            html,
            flags=re.IGNORECASE,
        )
        return html

    def apply_theme_vars(self, html: str, css_vars: Dict[str, str]) -> str:
        # 예: {"--accent-blue": "#4A90E2"} 형태로 전달
        for var, value in css_vars.items():
            # --var-name: <anything>;
            pattern = rf'({re.escape(var)}\s*:\s*)([^;]+)(;)'
            html = _safe_sub(pattern, lambda m, v=value: m.group(1) + v + m.group(3), html)
        return html

    def list_image_srcs(self, html: str) -> List[str]:
        # 템플릿 내부 <img ... src="..."> 목록 추출
        # (중복 제거, data: URL 제외)
        srcs = re.findall(r'<img[^>]+src="([^"]+)"', html, flags=re.IGNORECASE)
        uniq: List[str] = []
        for s in srcs:
            if s.startswith("data:"):
                continue
            if s not in uniq:
                uniq.append(s)
        return uniq

    def replace_images(self, html: str, replacements: List[ImageReplacement]) -> str:
        # src="원본" 문자열을 src="data:..."로 교체
        for rpl in replacements:
            # src="...원본..." 형태를 정확히 치환
            html = html.replace(f'src="{rpl.original_src}"', f'src="{rpl.data_url}"')
        return html

    def make_image_replacement(self, original_src: str, file_bytes: bytes, mime: str) -> ImageReplacement:
        return ImageReplacement(
            original_src=original_src,
            data_url=_b64_data_url(file_bytes, mime),
            mime=mime,
        )
