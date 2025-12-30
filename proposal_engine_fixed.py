# proposal_engine.py
# -*- coding: utf-8 -*-
"""
Proposal Maker Engine for Streamlit
- Removed Tkinter dependencies
- Focuses on file I/O, Regex replacement, and Image processing
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageOps

# -----------------------------
# Marker patterns (template editing)
# -----------------------------
# Page markers: <!--PAGE_START:1--> ... <!--PAGE_END:1-->
PAGE_BLOCK_RE = re.compile(
    r"<!--\s*PAGE_START:(\d+)\s*-->(.*?)<!--\s*PAGE_END:\1\s*-->",
    re.S | re.I,
)

# Table markers: <!--TABLE_START:1--> <table>...</table> <!--TABLE_END:1-->
TABLE_BLOCK_RE = re.compile(
    r"<!--\s*TABLE_START:(\d+)\s*-->(.*?)<!--\s*TABLE_END:\1\s*-->",
    re.S | re.I,
)

# Icon group markers: <!--ICON_GROUP_START:key--> ... <!--ICON_GROUP_END:key-->
ICON_GROUP_RE = re.compile(
    r"<!--\s*ICON_GROUP_START:([A-Za-z0-9_\-]+)\s*-->(.*?)<!--\s*ICON_GROUP_END:\1\s*-->",
    re.S | re.I,
)

RAW_PAGE_START_RE = re.compile(r'<div\s+class="page\b', re.I)
RAW_TABLE_RE = re.compile(r'<table[^>]*>.*?</table>', re.S | re.I)


# -----------------------------
# Utilities
# -----------------------------
def _safe_read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _safe_write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

def _remove_all_markers(html_text: str) -> str:
    """Remove internal edit markers from the final HTML output."""
    html_text = re.sub(r"<!--\s*PAGE_(?:START|END):\d+\s*-->", "", html_text, flags=re.I)
    html_text = re.sub(r"<!--\s*TABLE_(?:START|END):\d+\s*-->", "", html_text, flags=re.I)
    html_text = re.sub(r"<!--\s*ICON_GROUP_(?:START|END):[A-Za-z0-9_\-]+\s*-->", "", html_text, flags=re.I)
    return html_text

def _find_matching_div_end(html_text: str, start_idx: int) -> int:
    depth = 0
    pos = start_idx
    open_re = re.compile(r"<div\b", re.I)
    close_re = re.compile(r"</div\s*>", re.I)

    while pos < len(html_text):
        m_open = open_re.search(html_text, pos)
        m_close = close_re.search(html_text, pos)

        if not m_close:
            return -1

        if m_open and m_open.start() < m_close.start():
            depth += 1
            pos = m_open.end()
        else:
            depth -= 1
            pos = m_close.end()
            if depth == 0:
                return pos
    return -1

def _set_root_var(html_text: str, var_name: str, value_with_unit: str) -> str:
    m = re.search(r":root\s*\{([^}]*)\}", html_text, re.S)
    if not m:
        return html_text
    block = m.group(1)
    if re.search(rf"--{re.escape(var_name)}\s*:", block):
        def _repl(m2: re.Match) -> str:
            return m2.group(1) + value_with_unit + m2.group(3)
        block2 = re.sub(rf"(--{re.escape(var_name)}\s*:\s*)([^;]+)(;)", _repl, block)
    else:
        block2 = block + f"\n        --{var_name}: {value_with_unit};"
    return html_text[: m.start(1)] + block2 + html_text[m.end(1) :]

def _ensure_layout_support(html_text: str) -> str:
    defaults = {
        "page-padding": "20mm", "page-gap": "20px", "img-box-height": "220px",
        "img-box-margin-v": "10px", "highlight-margin-v": "15px", "table-margin-top": "10px",
        "table-cell-padding": "7px", "user-block-gap": "12px", "img-h-300": "300px",
        "img-h-250": "250px", "img-h-180": "180px", "img-h-150": "150px",
    }
    for k, v in defaults.items():
        html_text = _set_root_var(html_text, k, v)
    
    # CSS rules updates (simplified regex for stability)
    html_text = re.sub(r"(\.page\s*\{[^}]*?)padding:\s*20mm\s*;", r"\1padding: var(--page-padding);", html_text, flags=re.S)
    html_text = re.sub(r"(\.page\s*\{[^}]*?)margin-bottom:\s*20px\s*;?", r"\1margin-bottom: var(--page-gap);", html_text, flags=re.S)
    html_text = re.sub(r"(\.img-box\s*\{[^}]*?)height:\s*220px\s*;", r"\1height: var(--img-box-height);", html_text, flags=re.S)
    
    # User text blocks styles
    if ".user-text-block" not in html_text:
        extra = """
    .img-h-300 { height: var(--img-h-300); }
    .img-h-250 { height: var(--img-h-250); }
    .img-h-180 { height: var(--img-h-180); }
    .img-h-150 { height: var(--img-h-150); }
    .user-text-block { margin-top: var(--user-block-gap); padding: 12px; border: 1px dashed #ccc; border-radius: 8px; background: #fff; }
    .user-text-title { font-weight: 700; margin-bottom: 6px; color: var(--primary-purple); }
    .user-text-block p { margin: 6px 0; }
    .user-text-block ul { margin: 6px 0 6px 18px; }
"""
        html_text = html_text.replace("</style>", extra + "\n</style>")

    replacements = {300: "img-h-300", 250: "img-h-250", 180: "img-h-180", 150: "img-h-150"}
    for px, cls in replacements.items():
        html_text = re.sub(rf'<div\s+class="img-box"\s+style="\s*height\s*:\s*{px}px\s*;\s*"\s*>', rf'<div class="img-box {cls}">', html_text)
    
    return html_text

def plain_text_to_safe_html(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    blocks, buf, list_buf = [], [], []

    def flush_p():
        nonlocal buf
        if buf:
            blocks.append("<p>" + "<br>".join([html.escape(x) for x in buf]) + "</p>")
            buf = []
    def flush_l():
        nonlocal list_buf
        if list_buf:
            blocks.append("<ul>" + "".join([f"<li>{html.escape(x)}</li>" for x in list_buf]) + "</ul>")
            list_buf = []

    for raw in lines:
        line = raw.strip("\n")
        if not line.strip():
            flush_l(); flush_p(); continue
        if line.lstrip().startswith("- "):
            flush_p(); list_buf.append(line.lstrip()[2:].strip())
        else:
            flush_l(); buf.append(line)
    flush_l(); flush_p()
    return "\n".join(blocks) if blocks else "<p></p>"

def safe_html_to_plain_text(html_fragment: str) -> str:
    s = re.sub(r"<\s*li[^>]*>", "- ", html_fragment, flags=re.I)
    s = re.sub(r"</\s*(li|ul|p)\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<\s*br\s*/?\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()

def ensure_page_markers(html_text: str) -> str:
    """Ensure <!--PAGE_START:n--> ... <!--PAGE_END:n--> markers exist."""
    if re.search(r"<!--\s*PAGE_START:\d+\s*-->", html_text, flags=re.I):
        return html_text

    out: List[str] = []
    last_pos = 0
    page_no = 1

    for m in RAW_PAGE_START_RE.finditer(html_text):
        div_start = m.start()
        div_end = _find_matching_div_end(html_text, div_start)
        if div_end == -1:
            continue

        block = html_text[div_start:div_end]
        is_cover = ("cover-page" in block) or ("cover-title" in block) or ("cover-year" in block)

        out.append(html_text[last_pos:div_start])

        if is_cover and page_no == 1:
            out.append(block)
        else:
            out.append(f"<!--PAGE_START:{page_no}-->\n{block}\n<!--PAGE_END:{page_no}-->")
            page_no += 1

        last_pos = div_end

    out.append(html_text[last_pos:])
    return "".join(out)


def ensure_table_markers(html_text: str) -> str:
    """Ensure <!--TABLE_START:n--> ... <!--TABLE_END:n--> markers exist."""
    if re.search(r"<!--\s*TABLE_START:\d+\s*-->", html_text, flags=re.I):
        return html_text

    out: List[str] = []
    last_pos = 0
    table_no = 1

    for m in RAW_TABLE_RE.finditer(html_text):
        out.append(html_text[last_pos:m.start()])
        table_html = m.group(0)
        out.append(f"<!--TABLE_START:{table_no}-->\n{table_html}\n<!--TABLE_END:{table_no}-->")
        last_pos = m.end()
        table_no += 1

    out.append(html_text[last_pos:])
    return "".join(out)


def ensure_icon_markers(html_text: str) -> str:
    """Ensure icon group markers exist (no-op for current template)."""
    return html_text


@dataclass
class TemplateDocument:
    prefix: str
    pages: List[str]
    suffix: str
    @staticmethod
    def from_html(html_text: str) -> "TemplateDocument":
        html_text = ensure_page_markers(html_text) # Ensure markers exist
        matches = list(PAGE_BLOCK_RE.finditer(html_text))
        if not matches: return TemplateDocument(prefix=html_text, pages=[], suffix="")
        return TemplateDocument(
            prefix=html_text[: matches[0].start()],
            pages=[m.group(2).strip() for m in matches],
            suffix=html_text[matches[-1].end() :]
        )
    def to_html(self) -> str:
        # Renumber pages automatically and keep page markers.
        pages_html: List[str] = []
        for i, page in enumerate(self.pages, 1):
            page = re.sub(r"(>Page\s*)\d+(\s*<)", rf"\g<1>{i}\2", page)
            pages_html.append(f"<!--PAGE_START:{i}-->\n{page}\n<!--PAGE_END:{i}-->\n")
        return self.prefix + "".join(pages_html) + self.suffix

# -----------------------------
# Main Engine
# -----------------------------
class ProposalEngine:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.assets_dir = os.path.join(self.base_dir, "proposal_assets")
        self.images_dir = os.path.join(self.assets_dir, "images")
        self.originals_dir = os.path.join(self.images_dir, "originals")
        os.makedirs(self.originals_dir, exist_ok=True)
        
        self.settings_path = os.path.join(self.assets_dir, "proposal_settings.json")
        self.template_path = os.path.join(self.assets_dir, "proposal_template.html")
        
        self.image_map = {
            "병원 전경": {"placeholder": "placeholder_hospital_view.jpg", "path": ""},
            "인증마크 모음": {"placeholder": "placeholder_cert_mark.jpg", "path": ""},
            "검진센터 내부": {"placeholder": "placeholder_center_interior.jpg", "path": ""},
            "MRI 장비": {"placeholder": "placeholder_mri.jpg", "path": ""},
            "CT 장비": {"placeholder": "placeholder_ct.jpg", "path": ""},
            "모바일 예약시스템": {"placeholder": "placeholder_mobile_app.jpg", "path": ""},
            "출장검진 버스": {"placeholder": "placeholder_bus.jpg", "path": ""},
            "검진 진행 모습": {"placeholder": "placeholder_program_a.jpg", "path": ""},
        }
        self.image_originals = {}
        self.layout_settings = {
            "page_padding_mm": 20, "page_gap_px": 20, "img_default_height_px": 220,
            "img_margin_v_px": 10, "highlight_margin_v_px": 15, "table_margin_top_px": 10,
            "table_cell_padding_px": 7, "user_block_gap_px": 12,
            "img_h_300_px": 300, "img_h_250_px": 250, "img_h_180_px": 180, "img_h_150_px": 150,
        }
        self.page_enabled = []
        self._recompute_image_target_sizes()
        self._ensure_template_file()
        self._load_settings()

    def _recompute_image_target_sizes(self):
        s = self.layout_settings
        self.image_target_sizes = {
            "병원 전경": (1000, int(s.get("img_h_300_px", 300))),
            "인증마크 모음": (490, int(s.get("img_h_150_px", 150))),
            "검진센터 내부": (1000, int(s.get("img_default_height_px", 220))),
            "MRI 장비": (490, int(s.get("img_h_180_px", 180))),
            "CT 장비": (490, int(s.get("img_h_180_px", 180))),
            "모바일 예약시스템": (1000, int(s.get("img_h_250_px", 250))),
            "출장검진 버스": (490, int(s.get("img_h_150_px", 150))),
            "검진 진행 모습": (1000, int(s.get("img_h_150_px", 150))),
        }

    def _ensure_template_file(self):
        # Assumes template is already in assets folder via setup in streamlit_app
        if os.path.exists(self.template_path):
            html_text = _safe_read_text(self.template_path)
            html_text = ensure_page_markers(html_text)
            html_text = ensure_table_markers(html_text)
            html_text = ensure_icon_markers(html_text)
            html_text = _ensure_layout_support(html_text)
            _safe_write_text(self.template_path, html_text)

    def load_template_html(self) -> str:
        return _safe_read_text(self.template_path)

    def save_template_html(self, html_text: str):
        _safe_write_text(self.template_path, html_text)

    def get_document(self) -> TemplateDocument:
        return TemplateDocument.from_html(self.load_template_html())
    
    def save_document(self, doc: TemplateDocument):
        self.save_template_html(doc.to_html())

    def _load_settings(self):
        if not os.path.exists(self.settings_path):
            doc = self.get_document()
            self.page_enabled = [True] * len(doc.pages)
            self._apply_layout_settings_to_template()
            self.save_settings()
            return
        
        with open(self.settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.layout_settings.update(data.get("layout", {}))
        self._recompute_image_target_sizes()
        self.image_originals = data.get("images_original", {})
        
        # Restore resized paths if they exist
        for key, fname in self.image_originals.items():
            if key in self.image_map:
                orig_path = os.path.join(self.originals_dir, fname)
                if os.path.exists(orig_path):
                    self.image_map[key]["path"] = self._ensure_resized_from_original(key, orig_path)

        enabled = data.get("page_enabled")
        doc = self.get_document()
        if enabled:
            self.page_enabled = enabled + [True] * (len(doc.pages) - len(enabled))
        else:
            self.page_enabled = [True] * len(doc.pages)

    def save_settings(self):
        data = {
            "page_enabled": self.page_enabled,
            "layout": self.layout_settings,
            "images_original": self.image_originals
        }
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def set_layout_settings(self, new_settings: Dict[str, int]):
        self.layout_settings.update(new_settings)
        self._recompute_image_target_sizes()
        self._apply_layout_settings_to_template()
        
        # Re-process images
        for key, orig_name in self.image_originals.items():
            orig_path = os.path.join(self.originals_dir, orig_name)
            if os.path.exists(orig_path):
                self.image_map[key]["path"] = self._ensure_resized_from_original(key, orig_path)
        self.save_settings()

    def _apply_layout_settings_to_template(self):
        html_text = self.load_template_html()
        html_text = _ensure_layout_support(html_text)
        s = self.layout_settings
        mapping = {
            "page-padding": f"{s['page_padding_mm']}mm", "page-gap": f"{s['page_gap_px']}px",
            "img-box-height": f"{s['img_default_height_px']}px", "img-box-margin-v": f"{s['img_margin_v_px']}px",
            "highlight-margin-v": f"{s['highlight_margin_v_px']}px", "table-margin-top": f"{s['table_margin_top_px']}px",
            "table-cell-padding": f"{s['table_cell_padding_px']}px", "user-block-gap": f"{s['user_block_gap_px']}px",
            "img-h-300": f"{s['img_h_300_px']}px", "img-h-250": f"{s['img_h_250_px']}px",
            "img-h-180": f"{s['img_h_180_px']}px", "img-h-150": f"{s['img_h_150_px']}px"
        }
        for k, v in mapping.items():
            html_text = _set_root_var(html_text, k, v)
        self.save_template_html(html_text)

    def _ensure_resized_from_original(self, key, orig_path):
        target = self.image_target_sizes.get(key, (1000, 220))
        h = _hash_file(orig_path)
        out_name = f"{re.sub(r'[^0-9a-zA-Z가-힣]', '_', key)}_{h}_{target[0]}x{target[1]}.jpg"
        out_path = os.path.join(self.images_dir, out_name)
        
        if not os.path.exists(out_path):
            with Image.open(orig_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                
                # Resize Cover
                iw, ih = img.size
                tr = target[0] / target[1]
                sr = iw / ih
                if sr > tr:
                    nw = int(ih * tr)
                    left = (iw - nw) // 2
                    img = img.crop((left, 0, left + nw, ih))
                else:
                    nh = int(iw / tr)
                    top = (ih - nh) // 2
                    img = img.crop((0, top, iw, top + nh))
                
                img.resize(target, Image.LANCZOS).save(out_path, "JPEG", quality=90)
        return out_path

    def copy_resize_to_local(self, key: str, src_path: str) -> str:
        h = _hash_file(src_path)
        ext = os.path.splitext(src_path)[1]
        orig_name = f"{re.sub(r'[^0-9a-zA-Z가-힣]', '_', key)}_{h}{ext}"
        orig_path = os.path.join(self.originals_dir, orig_name)
        shutil.copy2(src_path, orig_path)
        
        self.image_originals[key] = orig_name
        return self._ensure_resized_from_original(key, orig_path)

    # Page Ops
    def get_pages(self): return self.get_document().pages
    
    def set_page_enabled(self, idx, enabled):
        doc = self.get_document()
        if len(self.page_enabled) != len(doc.pages): self.page_enabled = [True] * len(doc.pages)
        if 0 <= idx < len(self.page_enabled):
            self.page_enabled[idx] = enabled
            self.save_settings()

    def move_page(self, idx, direction):
        doc = self.get_document()
        j = idx + direction
        if 0 <= idx < len(doc.pages) and 0 <= j < len(doc.pages):
            doc.pages[idx], doc.pages[j] = doc.pages[j], doc.pages[idx]
            self.page_enabled[idx], self.page_enabled[j] = self.page_enabled[j], self.page_enabled[idx]
            self.save_document(doc); self.save_settings()

    def add_new_page(self):
        doc = self.get_document()
        new_page = """<div class="page"><div class="page-header"><h2>새 페이지</h2></div><div class="user-text-block" data-block-id="np_{0}"><div class="user-text-title">제목</div><p>내용을 입력하세요</p></div><div class="page-footer"><span>NEW</span><span>Page 0</span></div></div>""".format(len(doc.pages)+1)
        doc.pages.append(new_page)
        self.page_enabled.append(True)
        self.save_document(doc); self.save_settings()

    def delete_page(self, idx):
        doc = self.get_document()
        if 0 <= idx < len(doc.pages):
            doc.pages.pop(idx)
            self.page_enabled.pop(idx)
            self.save_document(doc); self.save_settings()
    
    def duplicate_page(self, idx):
        doc = self.get_document()
        if 0 <= idx < len(doc.pages):
            doc.pages.insert(idx+1, doc.pages[idx])
            self.page_enabled.insert(idx+1, True)
            self.save_document(doc); self.save_settings()

    # Text Blocks
    def list_text_blocks(self, page_idx):
        doc = self.get_document()
        if not (0 <= page_idx < len(doc.pages)):
            return []
        html_t = doc.pages[page_idx]

        blocks = []
        for m in re.finditer(r'<div\s+class="user-text-block"[^>]*data-block-id="([^"]+)"[^>]*>', html_t):
            start = m.start()
            end = _find_matching_div_end(html_t, start)
            if end == -1:
                continue
            chunk = html_t[start:end]

            title_m = re.search(r'<div\s+class="user-text-title"[^>]*>(.*?)</div>', chunk, flags=re.S)
            title = html.unescape(re.sub(r"<[^>]+>", "", title_m.group(1)).strip()) if title_m else ""

            body_m = re.search(r'</div>\s*(.*?)\s*</div>\s*$', chunk, flags=re.S)
            body_html = body_m.group(1) if body_m else ""
            blocks.append({
                "id": m.group(1),
                "title": title or "(제목 없음)",
                "text": safe_html_to_plain_text(body_html),
            })
        return blocks

    def save_text_block(self, page_idx, bid, title, text):
        doc = self.get_document()
        if not (0 <= page_idx < len(doc.pages)):
            return
        html_t = doc.pages[page_idx]

        m = re.search(rf'<div\s+class="user-text-block"[^>]*data-block-id="{re.escape(bid)}"[^>]*>', html_t)
        if not m:
            return

        start = m.start()
        end = _find_matching_div_end(html_t, start)
        if end == -1:
            return

        wrapper = html_t[start:end]

        wrapper = re.sub(
            r'(<div\s+class="user-text-title"[^>]*>)(.*?)(</div>)',
            rf'\1{html.escape(title)}\3',
            wrapper,
            count=1,
            flags=re.S,
        )

        body = plain_text_to_safe_html(text)
        wrapper = re.sub(
            r'(</div>\s*)(.*?)(\s*</div>\s*)$',
            rf'\1\n{body}\n\3',
            wrapper,
            count=1,
            flags=re.S,
        )

        doc.pages[page_idx] = html_t[:start] + wrapper + html_t[end:]
        self.save_document(doc)

    def add_text_block(self, page_idx):
        doc = self.get_document()
        if not (0 <= page_idx < len(doc.pages)): return
        bid = f"p{page_idx}_b{os.urandom(4).hex()}"
        block = f'<div class="user-text-block" data-block-id="{bid}"><div class="user-text-title">제목</div><p>내용</p></div>'
        doc.pages[page_idx] += block
        self.save_document(doc)

    def delete_text_block(self, page_idx, bid):
        doc = self.get_document()
        html_t = doc.pages[page_idx]
        m = re.search(rf'<div\s+class="user-text-block"[^>]*data-block-id="{re.escape(bid)}"[^>]*>', html_t)
        if m:
            end = _find_matching_div_end(html_t, m.start())
            if end != -1:
                doc.pages[page_idx] = html_t[:m.start()] + html_t[end:]
                self.save_document(doc)

    # Tables & Icons
    def list_tables(self): return [int(m.group(1)) for m in TABLE_BLOCK_RE.finditer(self.load_template_html())]
    
    def get_table_html(self, t_no):
        for m in TABLE_BLOCK_RE.finditer(self.load_template_html()):
            if int(m.group(1)) == t_no: return m.group(2).strip()
        return ""
    
    def set_table_html(self, t_no, content):
        h = self.load_template_html()

        def repl(m):
            if int(m.group(1)) != int(t_no):
                return m.group(0)
            return f"<!--TABLE_START:{t_no}-->\n{content}\n<!--TABLE_END:{t_no}-->"

        self.save_template_html(TABLE_BLOCK_RE.sub(repl, h))

    def get_process_steps(self):
        h = self.load_template_html()
        m = None
        for gm in ICON_GROUP_RE.finditer(h):
            if gm.group(1) == "process_steps":
                m = gm
                break
        if not m:
            return []

        group_html = m.group(2)
        items = []
        for im in re.finditer(
            r'<i[^>]*class="([^"]+)"[^>]*>.*?</i>\s*<br\s*/?>\s*<strong>(.*?)</strong>',
            group_html,
            flags=re.S | re.I,
        ):
            items.append({"icon": im.group(1).strip(), "label": html.unescape(im.group(2)).strip()})
        return items

    def save_process_steps(self, items):
        container_style = "margin-top: 30px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center;"
        item_style = "background:#f4f4f4; padding:15px; border-radius:8px;"
        icon_style = "font-size:20pt; color:var(--secondary-purple); margin-bottom:10px;"

        inner = ""
        for x in items:
            icon_cls = html.escape(str(x.get("icon", "")).strip())
            label = html.escape(str(x.get("label", "")).strip())
            inner += (
                f'<div style="{item_style}">'
                f'<i class="{icon_cls}" style="{icon_style}"></i><br>'
                f'<strong>{label}</strong>'
                f'</div>'
            )

        block = f'<div style="{container_style}">{inner}</div>'
        self._save_icon_group("process_steps", block)

    def get_centers_items(self):
        h = self.load_template_html()
        m = None
        for gm in ICON_GROUP_RE.finditer(h):
            if gm.group(1) == "centers_list":
                m = gm
                break
        if not m:
            return []

        group_html = m.group(2)
        items = []
        for im in re.finditer(
            r"<li[^>]*>\s*<i[^>]*class=\"([^\"]+)\"[^>]*></i>\s*([^<]+)\s*</li>",
            group_html,
            flags=re.S | re.I,
        ):
            items.append({"icon": im.group(1).strip(), "label": html.unescape(im.group(2)).strip()})
        return items

    def save_centers_items(self, items):
        inner = ""
        for x in items:
            icon_cls = html.escape(str(x.get("icon", "")).strip())
            label = html.escape(str(x.get("label", "")).strip())
            inner += f'<li><i class="{icon_cls}"></i> {label}</li>'
        block = f'<ul style="display: flex; justify-content: space-around; list-style: none; font-weight: bold;">{inner}</ul>'
        self._save_icon_group("centers_list", block)

    def _save_icon_group(self, key, content):
        h = self.load_template_html()

        def repl(m):
            if m.group(1) != key:
                return m.group(0)
            return f"<!--ICON_GROUP_START:{key}-->\n{content}\n<!--ICON_GROUP_END:{key}-->"

        self.save_template_html(ICON_GROUP_RE.sub(repl, h))

    # Build
    def build_output_html(self, recipient, proposer, tel, primary, accent):
        doc = self.get_document()
        # Filter enabled pages
        doc.pages = [p for i, p in enumerate(doc.pages) if i < len(self.page_enabled) and self.page_enabled[i]]
        html_text = doc.to_html()
        
        replacements = {
            r"(<strong>수신\s*:\s*</strong>\s*)([^<]+)": rf"\1{recipient}",
            r"(<strong>제안\s*:\s*</strong>\s*)([^<]+)": rf"\1{proposer}",
            r"(Tel\.\s*)([0-9\s\-]+)": rf"\1{tel}",
            r"--primary-purple:\s*#[0-9A-Fa-f]{6}\s*;": f"--primary-purple: {primary};",
            r"--accent-gold:\s*#[0-9A-Fa-f]{6}\s*;": f"--accent-gold: {accent};"
        }
        for pat, rep in replacements.items():
            html_text = re.sub(pat, rep, html_text)
        
        for key, meta in self.image_map.items():
            if meta["path"] and os.path.exists(meta["path"]):
                with open(meta["path"], "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                html_text = html_text.replace(f'src="{meta["placeholder"]}"', f'src="data:image/jpeg;base64,{b64}"')
        
        return _remove_all_markers(html_text)
