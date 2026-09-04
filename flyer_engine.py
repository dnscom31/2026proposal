# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from healthcheck_data import normalize_project_data

THEMES = {
    "여름": {"bg": "#DDF5FF", "primary": "#0577B8", "accent": "#00A8E8", "soft": "#EDF9FF", "text": "#12324A"},
    "봄": {"bg": "#FFF0F5", "primary": "#B84371", "accent": "#EE7DA8", "soft": "#FFF8FB", "text": "#3D2430"},
    "업그레이드": {"bg": "#FFF0CF", "primary": "#B7442D", "accent": "#F06A3A", "soft": "#FFF9ED", "text": "#472B25"},
    "가정의달": {"bg": "#DDEEFF", "primary": "#225AA8", "accent": "#FF7F6C", "soft": "#F7FBFF", "text": "#20324B"},
    "기관형": {"bg": "#E8F7E5", "primary": "#24943A", "accent": "#36B7D9", "soft": "#F7FFF5", "text": "#1E3C25"},
    "미니멀": {"bg": "#F3F5F7", "primary": "#263238", "accent": "#607D8B", "soft": "#FFFFFF", "text": "#202428"},
}

FONT_URLS = {
    "regular": "https://raw.githubusercontent.com/wefonts/Pretendard/main/Pretendard-Regular.ttf",
    "medium": "https://raw.githubusercontent.com/wefonts/Pretendard/main/Pretendard-Medium.ttf",
    "semibold": "https://raw.githubusercontent.com/wefonts/Pretendard/main/Pretendard-SemiBold.ttf",
    "bold": "https://raw.githubusercontent.com/wefonts/Pretendard/main/Pretendard-Bold.ttf",
}


def _hex_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _font_cache_dir() -> Path:
    root = Path(tempfile.gettempdir()) / "nkproposal_fonts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_pretendard_fonts() -> Dict[str, str]:
    out: Dict[str, str] = {}
    cache = _font_cache_dir()
    for weight, url in FONT_URLS.items():
        path = cache / f"Pretendard-{weight}.ttf"
        if not path.exists() or path.stat().st_size < 100_000:
            urllib.request.urlretrieve(url, path)
        out[weight] = str(path)
    return out


def _register_pdf_fonts(fonts: Dict[str, str]) -> Dict[str, str]:
    names = {
        "regular": "Pretendard-Regular-NK",
        "medium": "Pretendard-Medium-NK",
        "semibold": "Pretendard-SemiBold-NK",
        "bold": "Pretendard-Bold-NK",
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for key, name in names.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, fonts[key]))
    return names


def _wrap_pdf(text: str, font_name: str, font_size: float, max_width: float) -> List[str]:
    text = str(text or "").strip()
    if not text:
        return [""]
    words = text.split()
    if len(words) <= 1:
        words = list(text)
        joiner = ""
    else:
        joiner = " "
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + joiner + word
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _fit_pdf_line(c: canvas.Canvas, text: str, x: float, y: float, max_width: float,
                  font_name: str, size: float, min_size: float = 5.5) -> float:
    actual = size
    while actual > min_size and pdfmetrics.stringWidth(text, font_name, actual) > max_width:
        actual -= 0.3
    c.setFont(font_name, actual)
    c.drawString(x, y, text)
    return actual


def _make_qr(url: str, box_size: int = 8) -> Image.Image | None:
    url = (url or "").strip()
    if not url:
        return None
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=box_size, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


class FlyerEngine:
    def __init__(self) -> None:
        self.fonts = ensure_pretendard_fonts()
        self.pdf_fonts = _register_pdf_fonts(self.fonts)

    @property
    def theme_names(self) -> List[str]:
        return list(THEMES.keys())

    def _theme(self, name: str) -> Dict[str, str]:
        return THEMES.get(name, THEMES["여름"])

    def render_pdf(self, data: Dict[str, Any], background_bytes: bytes | None = None) -> bytes:
        d = normalize_project_data(data)
        theme = self._theme(d.get("theme", "여름"))
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        W, H = A4

        c.setFillColor(theme["bg"])
        c.rect(0, 0, W, H, stroke=0, fill=1)
        if background_bytes:
            try:
                bg = Image.open(io.BytesIO(background_bytes)).convert("RGB")
                tmp = io.BytesIO()
                bg.save(tmp, format="JPEG", quality=92)
                tmp.seek(0)
                c.drawImage(ImageReader(tmp), 0, 0, width=W, height=H, mask="auto")
            except Exception:
                pass
        else:
            c.setFillColor(theme["accent"])
            c.setFillAlpha(0.12)
            c.circle(W - 65, H - 70, 95, stroke=0, fill=1)
            c.circle(70, 65, 115, stroke=0, fill=1)
            c.setFillAlpha(1)

        primary, accent, text, soft = theme["primary"], theme["accent"], theme["text"], theme["soft"]
        margin = 28

        c.setFillColor(primary)
        title = d.get("title") or "건강검진 안내문"
        title_size = 26
        while title_size > 17 and pdfmetrics.stringWidth(title, self.pdf_fonts["bold"], title_size) > W - 2 * margin:
            title_size -= 1
        c.setFont(self.pdf_fonts["bold"], title_size)
        c.drawString(margin, H - 55, title)

        c.setFont(self.pdf_fonts["medium"], 9.5)
        c.setFillColor(text)
        meta = "  |  ".join(x for x in [
            d.get("target", ""),
            f"검진기간 {d.get('period','')}" if d.get("period") else "",
            f"접수기간 {d.get('application_period','')}" if d.get("application_period") else "",
        ] if x)
        _fit_pdf_line(c, meta, margin, H - 76, W - 2 * margin, self.pdf_fonts["medium"], 9.5, 7)

        y_event_top = H - 92
        c.setFillColor("#FFFFFF")
        c.roundRect(margin, y_event_top - 58, W - 2 * margin, 52, 9, stroke=0, fill=1)
        c.setStrokeColor(accent)
        c.setLineWidth(1.4)
        c.roundRect(margin, y_event_top - 58, W - 2 * margin, 52, 9, stroke=1, fill=0)
        c.setFillColor(primary)
        c.setFont(self.pdf_fonts["semibold"], 11)
        c.drawString(margin + 12, y_event_top - 22, d.get("event_title") or "EVENT")
        c.setFillColor(text)
        for i, line in enumerate(d.get("event_lines", [])[:2]):
            _fit_pdf_line(c, "• " + str(line), margin + 92, y_event_top - 22 - i * 16,
                          W - 2 * margin - 106, self.pdf_fonts["semibold"], 9.5, 7)

        table_top = y_event_top - 72
        row_h = 31
        packages = d.get("packages", [])[:5]
        table_h = 31 + row_h * len(packages)
        c.setFillColor("#FFFFFF")
        c.roundRect(margin, table_top - table_h, W - 2 * margin, table_h, 9, stroke=0, fill=1)
        c.setFillColor(primary)
        c.roundRect(margin, table_top - 31, W - 2 * margin, 31, 9, stroke=0, fill=1)
        c.setFillColor("#FFFFFF")
        c.setFont(self.pdf_fonts["bold"], 11)
        c.drawString(margin + 12, table_top - 20, "세부항목")
        c.drawCentredString(W - 94, table_top - 20, "남")
        c.drawCentredString(W - 50, table_top - 20, "여")

        y = table_top - 31
        for idx, p in enumerate(packages):
            y -= row_h
            if idx % 2 == 0:
                c.setFillColor(soft)
                c.rect(margin, y, W - 2 * margin, row_h, stroke=0, fill=1)
            c.setFillColor(primary)
            c.setFont(self.pdf_fonts["bold"], 9.5)
            c.drawString(margin + 12, y + 10, str(p.get("name", "")))
            c.setFillColor(text)
            _fit_pdf_line(c, str(p.get("detail", "")), margin + 80, y + 10, W - 2 * margin - 185,
                          self.pdf_fonts["medium"], 8.4, 6.5)
            c.setFont(self.pdf_fonts["bold"], 9.2)
            c.drawCentredString(W - 94, y + 10, str(p.get("male_price", "")))
            c.drawCentredString(W - 50, y + 10, str(p.get("female_price", "")))

        common_top = table_top - table_h - 10
        common_h = 62
        c.setFillColor("#FFFFFF")
        c.roundRect(margin, common_top - common_h, W - 2 * margin, common_h, 7, stroke=0, fill=1)
        c.setFillColor(primary)
        c.setFont(self.pdf_fonts["bold"], 10.5)
        c.drawString(margin + 10, common_top - 17, "공통항목")
        c.setFillColor(text)
        common_lines = _wrap_pdf(d.get("common_items", ""), self.pdf_fonts["regular"], 6.8, W - 2 * margin - 20)
        c.setFont(self.pdf_fonts["regular"], 6.8)
        for i, line in enumerate(common_lines[:5]):
            c.drawString(margin + 10, common_top - 32 - i * 10, line)

        group_top = common_top - common_h - 10
        group_bottom = 118
        group_h = group_top - group_bottom
        gap = 8
        left_w = (W - 2 * margin - gap) * 0.52
        right_w = W - 2 * margin - gap - left_w

        def panel(x, yb, width, height, label):
            c.setFillColor("#FFFFFF")
            c.roundRect(x, yb, width, height, 7, stroke=0, fill=1)
            c.setFillColor(primary)
            c.rect(x, yb + height - 24, width, 24, stroke=0, fill=1)
            c.setFillColor("#FFFFFF")
            c.setFont(self.pdf_fonts["bold"], 11)
            c.drawString(x + 9, yb + height - 17, label)

        panel(margin, group_bottom, left_w, group_h, "A그룹")
        panel(margin + left_w + gap, group_bottom + group_h * 0.43 + gap / 2, right_w, group_h * 0.57 - gap / 2, "B그룹")
        panel(margin + left_w + gap, group_bottom, right_w, group_h * 0.43 - gap / 2, "C그룹")

        a_items = d.get("groups", {}).get("A", [])
        a_x = margin + 9
        a_y = group_top - 37
        col_w = (left_w - 18) / 2
        c.setFillColor(text)
        c.setFont(self.pdf_fonts["regular"], 6.7)
        per_col = max(1, (len(a_items) + 1) // 2)
        for i, item in enumerate(a_items[:22]):
            col = i // per_col
            row = i % per_col
            _fit_pdf_line(c, item, a_x + col * col_w, a_y - row * 13, col_w - 4,
                          self.pdf_fonts["regular"], 6.7, 5.6)

        bx = margin + left_w + gap + 9
        by = group_top - 37
        b_items = d.get("groups", {}).get("B", [])
        b_panel_w = right_w - 18
        b_col_w = b_panel_w / 2
        b_per_col = max(1, (len(b_items) + 1) // 2)
        for i, item in enumerate(b_items[:12]):
            col = i // b_per_col
            row = i % b_per_col
            _fit_pdf_line(c, item, bx + col * b_col_w, by - row * 13, b_col_w - 4,
                          self.pdf_fonts["regular"], 6.35, 5.4)

        cy = group_bottom + group_h * 0.43 - 37
        c_items = d.get("groups", {}).get("C", [])
        c_col_w = b_panel_w / 2
        c_per_col = max(1, (len(c_items) + 1) // 2)
        for i, item in enumerate(c_items[:10]):
            col = i // c_per_col
            row = i % c_per_col
            _fit_pdf_line(c, item, bx + col * c_col_w, cy - row * 13, c_col_w - 4,
                          self.pdf_fonts["regular"], 6.3, 5.2)

        footer_y = 18
        qr = _make_qr(d.get("qr_url", ""))
        if qr:
            qbuf = io.BytesIO()
            qr.save(qbuf, format="PNG")
            qbuf.seek(0)
            c.drawImage(ImageReader(qbuf), margin, footer_y, width=78, height=78, mask="auto")
            if d.get("qr_url"):
                c.linkURL(d["qr_url"], (margin, footer_y, margin + 78, footer_y + 78), relative=0)

        c.setFillColor(primary)
        c.setFont(self.pdf_fonts["bold"], 19)
        c.drawString(margin + 90, footer_y + 48, f"검진문의 {d.get('phone','1833-9988')}")
        c.setFillColor(text)
        c.setFont(self.pdf_fonts["regular"], 7.2)
        note_x = margin + 90
        note_y = footer_y + 31
        for note in d.get("notes", [])[:3]:
            _fit_pdf_line(c, "• " + note, note_x, note_y, W - note_x - margin,
                          self.pdf_fonts["regular"], 7.2, 5.8)
            note_y -= 11

        c.showPage()
        c.save()
        return buf.getvalue()

    def render_png(self, data: Dict[str, Any], background_bytes: bytes | None = None,
                   width: int = 1240, height: int = 1754) -> bytes:
        d = normalize_project_data(data)
        theme = self._theme(d.get("theme", "여름"))
        if background_bytes:
            try:
                img = Image.open(io.BytesIO(background_bytes)).convert("RGB")
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            except Exception:
                img = Image.new("RGB", (width, height), _hex_rgb(theme["bg"]))
        else:
            img = Image.new("RGB", (width, height), _hex_rgb(theme["bg"]))
            draw0 = ImageDraw.Draw(img, "RGBA")
            draw0.ellipse((width - 420, -80, width + 100, 440), fill=(*_hex_rgb(theme["accent"]), 25))
            draw0.ellipse((-180, height - 420, 390, height + 120), fill=(*_hex_rgb(theme["accent"]), 25))

        draw = ImageDraw.Draw(img, "RGBA")
        f = {"r": self.fonts["regular"], "m": self.fonts["medium"], "s": self.fonts["semibold"], "b": self.fonts["bold"]}

        def font(key, size):
            return ImageFont.truetype(f[key], size)

        primary = _hex_rgb(theme["primary"])
        accent = _hex_rgb(theme["accent"])
        text = _hex_rgb(theme["text"])
        soft = _hex_rgb(theme["soft"])
        M = 58

        def rounded(box, fill, radius=18, outline=None, ow=2):
            draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=ow)

        def fit_text(txt, xy, max_w, key="m", size=26, min_size=16, fill=text):
            sz = size
            while sz > min_size and draw.textbbox((0, 0), txt, font=font(key, sz))[2] > max_w:
                sz -= 1
            draw.text(xy, txt, font=font(key, sz), fill=fill)
            return sz

        fit_text(d.get("title") or "건강검진 안내문", (M, 60), width - 2*M, "b", 58, 38, primary)
        meta = "  |  ".join(x for x in [
            d.get("target", ""),
            f"검진기간 {d.get('period','')}" if d.get("period") else "",
            f"접수기간 {d.get('application_period','')}" if d.get("application_period") else "",
        ] if x)
        fit_text(meta, (M, 132), width - 2*M, "m", 22, 16, text)

        rounded((M, 180, width-M, 300), (255,255,255,235), outline=accent, ow=3)
        draw.text((M+24, 202), d.get("event_title") or "EVENT", font=font("s", 27), fill=primary)
        for i, line in enumerate(d.get("event_lines", [])[:2]):
            fit_text("• " + line, (M+205, 204+i*42), width-2*M-230, "s", 24, 16, text)

        pt, ph = 328, 402
        rounded((M, pt, width-M, pt+ph), (255,255,255,238))
        draw.rounded_rectangle((M, pt, width-M, pt+58), radius=18, fill=(*primary,255))
        draw.text((M+20, pt+13), "세부항목", font=font("b", 29), fill="white")
        draw.text((width-225, pt+13), "남", font=font("b", 26), fill="white")
        draw.text((width-125, pt+13), "여", font=font("b", 26), fill="white")
        row_y = pt + 64
        row_h = 66
        for i, p in enumerate(d.get("packages", [])[:5]):
            if i % 2 == 0:
                draw.rectangle((M, row_y, width-M, row_y+row_h), fill=(*soft,235))
            draw.text((M+20, row_y+16), p.get("name",""), font=font("b", 23), fill=primary)
            fit_text(p.get("detail",""), (M+165, row_y+16), width-2*M-420, "m", 21, 15, text)
            draw.text((width-245, row_y+16), p.get("male_price",""), font=font("b", 22), fill=text)
            draw.text((width-140, row_y+16), p.get("female_price",""), font=font("b", 22), fill=text)
            row_y += row_h

        ct = pt + ph + 22
        ch = 135
        rounded((M, ct, width-M, ct+ch), (255,255,255,238))
        draw.text((M+18, ct+14), "공통항목", font=font("b", 25), fill=primary)
        common = d.get("common_items","")
        max_chars = 88
        lines = []
        remaining = common
        while remaining:
            cut = min(max_chars, len(remaining))
            if cut < len(remaining):
                sep = max(remaining.rfind(" | ", 0, cut), remaining.rfind(" ", 0, cut))
                if sep > 30:
                    cut = sep + 1
            lines.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        for i, line in enumerate(lines[:4]):
            fit_text(line, (M+18, ct+50+i*24), width-2*M-36, "r", 16, 13, text)

        gt = ct + ch + 22
        gb = height - 220
        gap = 18
        left_w = int((width-2*M-gap)*0.52)
        right_w = width-2*M-gap-left_w
        rounded((M, gt, M+left_w, gb), (255,255,255,240))
        rounded((M+left_w+gap, gt, width-M, gt+(gb-gt)*0.58-gap/2), (255,255,255,240))
        rounded((M+left_w+gap, gt+(gb-gt)*0.58+gap/2, width-M, gb), (255,255,255,240))
        for x1,y1,x2,label in [
            (M,gt,M+left_w,"A그룹"),
            (M+left_w+gap,gt,width-M,"B그룹"),
            (M+left_w+gap,int(gt+(gb-gt)*0.58+gap/2),width-M,"C그룹"),
        ]:
            draw.rectangle((x1,y1,x2,y1+48), fill=(*primary,255))
            draw.text((x1+14,y1+8), label, font=font("b", 27), fill="white")

        a = d.get("groups",{}).get("A",[])
        per_col=max(1,(len(a)+1)//2)
        for i,item in enumerate(a[:22]):
            col=i//per_col; row=i%per_col
            fit_text(item,(M+14+col*(left_w//2),gt+62+row*30),left_w//2-18,"r",16,13,text)

        bx=M+left_w+gap+14
        b=d.get("groups",{}).get("B",[])
        bper=max(1,(len(b)+1)//2)
        for i,item in enumerate(b[:12]):
            col=i//bper; row=i%bper
            fit_text(item,(bx+col*((right_w-28)//2),gt+62+row*29),(right_w-28)//2-8,"r",15,12,text)

        ctop=int(gt+(gb-gt)*0.58+gap/2)
        citems=d.get("groups",{}).get("C",[])
        cper=max(1,(len(citems)+1)//2)
        for i,item in enumerate(citems[:10]):
            col=i//cper; row=i%cper
            fit_text(item,(bx+col*((right_w-28)//2),ctop+62+row*29),(right_w-28)//2-8,"r",15,12,text)

        fy=height-190
        qr=_make_qr(d.get("qr_url",""),box_size=7)
        if qr:
            qr=qr.resize((145,145),Image.Resampling.NEAREST)
            img.paste(qr,(M,fy))
        draw.text((M+170,fy+20),f"검진문의 {d.get('phone','1833-9988')}",font=font("b",38),fill=primary)
        ny=fy+76
        for note in d.get("notes",[])[:3]:
            fit_text("• "+note,(M+170,ny),width-M-(M+170),"r",16,13,text)
            ny+=27

        out=io.BytesIO()
        img.save(out,format="PNG",optimize=True)
        return out.getvalue()
