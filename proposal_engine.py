# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import base64
import html as html_lib
import json
import mimetypes
import re


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _safe_sub(pattern: str, repl_fn, text: str, flags: int = 0) -> str:
    return re.sub(pattern, repl_fn, text, flags=flags)


class ProposalEngine:
    def __init__(self, template_path: str = "proposal_template.html"):
        self.template_path = Path(template_path)

    def load_template(self) -> str:
        if not self.template_path.exists():
            raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {self.template_path}")
        return _read_text(self.template_path)

    def apply_basic_fields(self, html: str, *, recipient: str, proposer: str, tel: str, email: str) -> str:
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

        email_clean = (email or "").strip()
        if email_clean:
            html = _safe_sub(
                r'(Email\.\s*)([^<\n]+)',
                lambda m: m.group(1) + email_clean,
                html,
                flags=re.IGNORECASE,
            )
        else:
            html = _safe_sub(
                r'\s*<p[^>]*>\s*<i class="fas fa-envelope"[^>]*></i>\s*Email\.[\s\S]*?</p>\s*',
                lambda m: "",
                html,
                flags=re.IGNORECASE,
            )
        return html

    def apply_theme_vars(self, html: str, css_vars: Dict[str, str]) -> str:
        for var, value in css_vars.items():
            pattern = rf'({re.escape(var)}\s*:\s*)([^;]+)(;)'
            html = _safe_sub(pattern, lambda m, v=value: m.group(1) + v + m.group(3), html)
        return html

    def embed_attachment_images(self, html: str, assets_dir: str = "attachment_pages") -> str:
        base_dir = self.template_path.parent
        assets_prefix = assets_dir.rstrip("/") + "/"

        def _repl(match: re.Match) -> str:
            prefix, src, suffix = match.group(1), match.group(2), match.group(3)
            if src.startswith("data:") or src.startswith("http://") or src.startswith("https://"):
                return match.group(0)
            normalized = src.lstrip("./")
            if not normalized.startswith(assets_prefix):
                return match.group(0)
            file_path = base_dir / normalized
            if not file_path.exists():
                return match.group(0)
            mime, _ = mimetypes.guess_type(str(file_path))
            mime = mime or "image/jpeg"
            b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")
            return prefix + f"data:{mime};base64,{b64}" + suffix

        return re.sub(
            r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'])',
            _repl,
            html,
            flags=re.IGNORECASE,
        )

    def embed_proposal_data(self, html: str, data: Dict[str, Any]) -> str:
        """제안서 HTML에 안내문 생성용 구조화 데이터를 함께 저장합니다."""
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        block = f'\n<script id="nk-proposal-data" type="application/json">{payload}</script>\n'
        if re.search(r"</body\s*>", html, re.IGNORECASE):
            return re.sub(r"</body\s*>", block + "</body>", html, count=1, flags=re.IGNORECASE)
        return html + block

    @staticmethod
    def extract_proposal_data(html: str) -> Dict[str, Any] | None:
        """embed_proposal_data로 저장된 JSON을 다시 읽습니다."""
        m = re.search(
            r'<script[^>]+id=["\']nk-proposal-data["\'][^>]*>([\s\S]*?)</script>',
            html,
            flags=re.IGNORECASE,
        )
        if not m:
            return None
        raw = html_lib.unescape(m.group(1)).replace("<\\/", "</")
        try:
            value = json.loads(raw)
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def extract_legacy_basic_fields(html: str) -> Dict[str, str]:
        """과거 제안서 HTML에서 안전하게 확인 가능한 기본정보만 추출합니다."""
        out: Dict[str, str] = {}
        patterns = {
            "recipient": r'<strong>\s*수신\s*:\s*</strong>\s*([^<]+)',
            "proposer": r'<strong>\s*제안\s*:\s*</strong>\s*([^<]+)',
            "phone": r'Tel\.\s*([0-9\s\-]+)',
            "email": r'Email\.\s*([^<\n]+)',
        }
        for key, pattern in patterns.items():
            m = re.search(pattern, html, flags=re.IGNORECASE)
            if m:
                out[key] = re.sub(r"\s+", " ", m.group(1)).strip()
        return out
