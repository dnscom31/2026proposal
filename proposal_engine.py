# proposal_engine.py
# -*- coding: utf-8 -*-
"""
Proposal Engine (Streamlit)
- 목적: 기본설정(수신/제안/전화), 색상/레이아웃, 이미지 교체, 그리고 '첨부(자료) 페이지 이미지'를
  기존 HTML 템플릿 끝에 계속 추가하여 최종 1개 HTML로 내보내기.
- 최종 HTML은 이미지가 base64로 포함되어, GitHub에 이미지 파일이 따로 없어도 단독으로 열립니다.
"""

from __future__ import annotations

import base64
import hashlib
import html as htmlmod
import io
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PIL import Image


def _safe_read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _safe_write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _safe_write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _safe_read_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "image/jpeg"


def _extract_sort_number(filename: str) -> Tuple[int, str]:
    """파일명 끝의 숫자를 정렬 키로 사용합니다."""
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"(\d+)\s*$", base)
    if m:
        return (int(m.group(1)), filename)
    m2 = re.findall(r"(\d+)", base)
    if m2:
        return (int(m2[-1]), filename)
    return (10**9, filename)


def _find_matching_div_close_range(html_text: str, div_open_start: int) -> Optional[Tuple[int, int]]:
    """div_open_start 위치의 <div ...>에 대응하는 </div>의 (start, end)를 찾습니다."""
    open_re = re.compile(r"<div\b", re.I)
    close_re = re.compile(r"</div\s*>", re.I)

    depth = 0
    pos = div_open_start

    while pos < len(html_text):
        m_open = open_re.search(html_text, pos)
        m_close = close_re.search(html_text, pos)

        if not m_open and not m_close:
            return None

        if m_close and (not m_open or m_close.start() < m_open.start()):
            depth -= 1
            if depth == 0:
                return (m_close.start(), m_close.end())
            pos = m_close.end()
        else:
            depth += 1
            pos = m_open.end()

    return None


def _ensure_root_var(html_text: str, var_name: str, value: str) -> str:
    """ :root { ... } 블록에 CSS 변수가 있으면 값만 교체, 없으면 추가합니다. """
    m = re.search(r":root\s*\{([^}]*)\}", html_text, flags=re.S)
    if not m:
        style_m = re.search(r"<style[^>]*>", html_text, flags=re.I)
        if not style_m:
            return html_text
        insert_at = style_m.end()
        add = f"\n:root{{\n  --{var_name}: {value};\n}}\n"
        return html_text[:insert_at] + add + html_text[insert_at:]

    block = m.group(1)
    if re.search(rf"--{re.escape(var_name)}\s*:", block):
        block2 = re.sub(
            rf"(--{re.escape(var_name)}\s*:\s*)([^;]+)(;)",
            rf"\g<1>{value}\g<3>",
            block,
            flags=re.I,
        )
    else:
        block2 = block + f"\n  --{var_name}: {value};"
    return html_text[: m.start(1)] + block2 + html_text[m.end(1) :]


def _ensure_attachment_css(html_text: str) -> str:
    css = """
    /* Attachment pages (full-page images appended at export) */
    .attachment-page { padding: 0 !important; }
    .attachment-page .page-header, .attachment-page .page-footer { display: none !important; }
    .attachment-img { width: 100%; height: 100%; object-fit: contain; display: block; }
    """

    if ".attachment-page" in html_text:
        return html_text

    m = re.search(r"</style\s*>", html_text, flags=re.I)
    if not m:
        return html_text
    return html_text[: m.start()] + css + "\n" + html_text[m.start() :]


def _append_attachment_pages_into_container(html_text: str, pages_html: str) -> str:
    idx = html_text.lower().find('<div class="document-container"')
    if idx == -1:
        m = re.search(r"</body\s*>", html_text, flags=re.I)
        if not m:
            return html_text + pages_html
        return html_text[: m.start()] + pages_html + "\n" + html_text[m.start():]

    close_range = _find_matching_div_close_range(html_text, idx)
    if not close_range:
        return html_text + pages_html

    close_start, _close_end = close_range
    return html_text[:close_start] + "\n" + pages_html + "\n" + html_text[close_start:]


@dataclass
class ImageSlot:
    key: str
    placeholder_filename: str
    target_size: Tuple[int, int]  # (width_px, height_px)


class ProposalEngine:
    def __init__(self, base_dir: str, attachments_src_dir: Optional[str] = None):
        self.base_dir = base_dir
        self.assets_dir = os.path.join(self.base_dir, "proposal_assets")
        self.images_dir = os.path.join(self.assets_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

        self.template_path = os.path.join(self.assets_dir, "proposal_template.html")
        self.settings_path = os.path.join(self.assets_dir, "proposal_settings.json")

        # GitHub(레포) 쪽 '자료 이미지 페이지' 폴더(읽기 전용)
        self.attachments_src_dir = attachments_src_dir

        self.image_slots: List[ImageSlot] = [
            ImageSlot("병원 전경", "placeholder_hospital_view.jpg", (1000, 300)),
            ImageSlot("인증마크 모음", "placeholder_cert_mark.jpg", (490, 150)),
            ImageSlot("검진센터 내부", "placeholder_center_interior.jpg", (1000, 220)),
            ImageSlot("MRI 장비", "placeholder_mri.jpg", (490, 180)),
            ImageSlot("CT 장비", "placeholder_ct.jpg", (490, 180)),
            ImageSlot("모바일 예약시스템", "placeholder_mobile_app.jpg", (1000, 250)),
            ImageSlot("출장검진 버스", "placeholder_bus.jpg", (490, 150)),
            ImageSlot("검진 진행 모습", "placeholder_program_a.jpg", (1000, 150)),
        ]

        self.layout_settings: Dict[str, int] = {
            "page_padding_mm": 20,
            "page_gap_px": 20,
            "img_box_height_px": 220,
            "img_margin_v_px": 10,
            "highlight_margin_v_px": 15,
            "table_margin_top_px": 10,
            "table_cell_padding_px": 7,
            "user_block_gap_px": 12,
            "img_h_300_px": 300,
            "img_h_250_px": 250,
            "img_h_180_px": 180,
            "img_h_150_px": 150,
        }

        self._load_settings()
        self._ensure_template_support()

    def _ensure_template_support(self) -> None:
        if not os.path.exists(self.template_path):
            return

        html_text = _safe_read_text(self.template_path)

        html_text = _ensure_root_var(html_text, "page-padding", f"{self.layout_settings['page_padding_mm']}mm")
        html_text = _ensure_root_var(html_text, "page-gap", f"{self.layout_settings['page_gap_px']}px")
        html_text = _ensure_root_var(html_text, "img-box-height", f"{self.layout_settings['img_box_height_px']}px")
        html_text = _ensure_root_var(html_text, "img-box-margin-v", f"{self.layout_settings['img_margin_v_px']}px")
        html_text = _ensure_root_var(html_text, "highlight-margin-v", f"{self.layout_settings['highlight_margin_v_px']}px")
        html_text = _ensure_root_var(html_text, "table-margin-top", f"{self.layout_settings['table_margin_top_px']}px")
        html_text = _ensure_root_var(html_text, "table-cell-padding", f"{self.layout_settings['table_cell_padding_px']}px")
        html_text = _ensure_root_var(html_text, "user-block-gap", f"{self.layout_settings['user_block_gap_px']}px")
        html_text = _ensure_root_var(html_text, "img-h-300", f"{self.layout_settings['img_h_300_px']}px")
        html_text = _ensure_root_var(html_text, "img-h-250", f"{self.layout_settings['img_h_250_px']}px")
        html_text = _ensure_root_var(html_text, "img-h-180", f"{self.layout_settings['img_h_180_px']}px")
        html_text = _ensure_root_var(html_text, "img-h-150", f"{self.layout_settings['img_h_150_px']}px")

        _safe_write_text(self.template_path, html_text)

    def _load_settings(self) -> None:
        data = _safe_read_json(self.settings_path) or {}
        layout = data.get("layout", {})
        if isinstance(layout, dict):
            for k, v in layout.items():
                try:
                    self.layout_settings[k] = int(v)
                except Exception:
                    pass

    def _save_settings(self) -> None:
        _safe_write_json(self.settings_path, {"layout": self.layout_settings})

    # -------------------------------
    # Public APIs used by streamlit_app
    # -------------------------------
    def set_layout_settings(self, new_settings: Dict[str, int]) -> None:
        self.layout_settings.update(new_settings)
        self._save_settings()
        self._ensure_template_support()

    def save_uploaded_image(self, slot_key: str, uploaded_bytes: bytes) -> str:
        slot = next((s for s in self.image_slots if s.key == slot_key), None)
        if not slot:
            raise ValueError(f"Unknown slot key: {slot_key}")

        img = Image.open(io.BytesIO(uploaded_bytes)).convert("RGB")
        target_w, target_h = slot.target_size
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        out_path = os.path.join(self.images_dir, slot.placeholder_filename)
        img.save(out_path, format="JPEG", quality=92)
        return out_path

    def list_attachment_images(self) -> List[str]:
        if not self.attachments_src_dir or not os.path.isdir(self.attachments_src_dir):
            return []
        files: List[str] = []
        for name in os.listdir(self.attachments_src_dir):
            p = os.path.join(self.attachments_src_dir, name)
            if os.path.isfile(p) and os.path.splitext(name.lower())[1] in [".jpg", ".jpeg", ".png", ".webp"]:
                files.append(p)
        files.sort(key=_extract_sort_number)
        return files

    def build_output_html(self, recipient: str, proposer: str, tel: str, primary: str, accent: str) -> str:
        if not os.path.exists(self.template_path):
            raise FileNotFoundError("proposal_template.html not found in session assets.")

        html_text = _safe_read_text(self.template_path)

        # 1) 기본정보 (invalid group reference 방지: repl 함수 사용)
        def _repl_rec(m: re.Match) -> str:
            return m.group(1) + htmlmod.escape(recipient)

        def _repl_prop(m: re.Match) -> str:
            return m.group(1) + htmlmod.escape(proposer)

        def _repl_tel(m: re.Match) -> str:
            return m.group(1) + htmlmod.escape(tel)

        html_text = re.sub(r"(<strong>수신\s*:\s*</strong>\s*)([^<]+)", _repl_rec, html_text)
        html_text = re.sub(r"(<strong>제안\s*:\s*</strong>\s*)([^<]+)", _repl_prop, html_text)
        html_text = re.sub(r"(Tel\.\s*)([0-9\s\-]+)", _repl_tel, html_text)

        # 2) 색상
        html_text = _ensure_root_var(html_text, "primary-purple", primary)
        html_text = _ensure_root_var(html_text, "accent-gold", accent)

        # 3) 교체 이미지(placeholder) -> base64 embed
        for slot in self.image_slots:
            local_path = os.path.join(self.images_dir, slot.placeholder_filename)
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                mime = _guess_mime(local_path)
                html_text = html_text.replace(
                    f'src="{slot.placeholder_filename}"',
                    f'src="data:{mime};base64,{b64}"',
                )

        # 4) 첨부(자료) 페이지 이미지들을 마지막에 계속 추가
        attachment_files = self.list_attachment_images()
        if attachment_files:
            html_text = _ensure_attachment_css(html_text)

            pages: List[str] = []
            for i, path in enumerate(attachment_files, start=1):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                mime = _guess_mime(path)
                pages.append(
                    '<div class="page attachment-page">\n'
                    f'  <img class="attachment-img" src="data:{mime};base64,{b64}" alt="Attachment {i}">\n'
                    '</div>'
                )

            pages_html = "\n".join(pages)
            html_text = _append_attachment_pages_into_container(html_text, pages_html)

        return html_text
