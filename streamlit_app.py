# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Dict, Tuple

import streamlit as st

from proposal_engine import ProposalEngine
from healthcheck_data import official_2026_copy, normalize_project_data
from flyer_engine import FlyerEngine, THEMES

st.set_page_config(page_title="뉴고려병원 제안서·안내문 생성기", layout="wide")
st.title("뉴고려병원 제안서 · 건강검진 안내문 생성기")
st.caption("제안서와 안내문을 같은 검진 데이터로 생성하거나, 안내문만 독립적으로 제작할 수 있습니다.")

proposal_engine = ProposalEngine(template_path="proposal_template.html")


def _lines(value):
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    return str(value or "")


def _parse_lines(text: str):
    return [x.strip() for x in str(text or "").splitlines() if x.strip()]


def _project_editor(data: Dict[str, Any], prefix: str, allow_theme: bool = True) -> Dict[str, Any]:
    d = normalize_project_data(data)

    c1, c2, c3 = st.columns(3)
    with c1:
        d["title"] = st.text_input("안내문 제목", value=d["title"], key=f"{prefix}_title")
        d["target"] = st.text_input("지원/검진 대상", value=d["target"], key=f"{prefix}_target")
    with c2:
        d["period"] = st.text_input("검진기간", value=d["period"], key=f"{prefix}_period", placeholder="26.01.01 ~ 26.03.31")
        d["application_period"] = st.text_input(
            "접수기간", value=d["application_period"], key=f"{prefix}_application_period",
            placeholder="필요 없으면 비워두세요"
        )
    with c3:
        d["phone"] = st.text_input("검진 문의", value=d["phone"], key=f"{prefix}_phone")
        d["qr_url"] = st.text_input("QR 연결 주소", value=d["qr_url"], key=f"{prefix}_qr")

    c4, c5 = st.columns([1, 2])
    with c4:
        d["event_title"] = st.text_input("이벤트 제목", value=d["event_title"], key=f"{prefix}_event_title")
        if allow_theme:
            names = list(THEMES.keys())
            current = d.get("theme", "여름")
            d["theme"] = st.selectbox(
                "디자인 테마", names,
                index=names.index(current) if current in names else 0,
                key=f"{prefix}_theme"
            )
    with c5:
        d["event_lines"] = _parse_lines(
            st.text_area(
                "이벤트/혜택 문구 (한 줄에 하나)",
                value=_lines(d.get("event_lines", [])),
                height=90,
                key=f"{prefix}_event_lines",
            )
        )

    with st.expander("공통항목", expanded=False):
        d["common_items"] = st.text_area(
            "공통검사 내용",
            value=d["common_items"],
            height=125,
            key=f"{prefix}_common",
        )

    with st.expander("검진 패키지 / 금액", expanded=True):
        edited_packages = []
        for i, package in enumerate(d.get("packages", [])):
            cols = st.columns([1.0, 4.7, 1.0, 1.0])
            with cols[0]:
                name = st.text_input("유형", value=package.get("name", ""), key=f"{prefix}_pkg_name_{i}")
            with cols[1]:
                detail = st.text_input("세부항목", value=package.get("detail", ""), key=f"{prefix}_pkg_detail_{i}")
            with cols[2]:
                male = st.text_input("남", value=package.get("male_price", ""), key=f"{prefix}_pkg_m_{i}")
            with cols[3]:
                female = st.text_input("여", value=package.get("female_price", ""), key=f"{prefix}_pkg_f_{i}")
            edited_packages.append({
                "name": name, "detail": detail, "male_price": male, "female_price": female
            })
        d["packages"] = edited_packages

    with st.expander("A/B/C 선택검사", expanded=False):
        ca, cb, cc = st.columns(3)
        with ca:
            d["groups"]["A"] = _parse_lines(st.text_area(
                "A그룹 (한 줄에 하나)", value=_lines(d["groups"]["A"]),
                height=340, key=f"{prefix}_group_a"
            ))
        with cb:
            d["groups"]["B"] = _parse_lines(st.text_area(
                "B그룹 (한 줄에 하나)", value=_lines(d["groups"]["B"]),
                height=340, key=f"{prefix}_group_b"
            ))
        with cc:
            d["groups"]["C"] = _parse_lines(st.text_area(
                "C그룹 (한 줄에 하나)", value=_lines(d["groups"]["C"]),
                height=340, key=f"{prefix}_group_c"
            ))

    with st.expander("하단 안내 문구", expanded=False):
        d["notes"] = _parse_lines(st.text_area(
            "안내 문구 (한 줄에 하나)",
            value=_lines(d.get("notes", [])),
            height=90,
            key=f"{prefix}_notes",
        ))
    return d


def _build_flyer(data: Dict[str, Any], background_file) -> Tuple[bytes, bytes]:
    background = background_file.getvalue() if background_file is not None else None
    engine = FlyerEngine()
    return engine.render_pdf(data, background), engine.render_png(data, background)


def _proposal_html(recipient: str, proposer: str, tel: str, email: str,
                   colors: Dict[str, str], project_data: Dict[str, Any]) -> str:
    html = proposal_engine.load_template()
    html = proposal_engine.apply_basic_fields(
        html, recipient=recipient, proposer=proposer, tel=tel, email=email
    )
    html = proposal_engine.apply_theme_vars(html, colors)
    html = proposal_engine.embed_attachment_images(html)
    html = proposal_engine.embed_proposal_data(html, project_data)
    return html


tab_combo, tab_flyer = st.tabs(["제안서 + 안내문 동시 생성", "안내문 전용 제작"])


with tab_combo:
    st.subheader("1. 제안서 기본정보")
    p1, p2 = st.columns(2)
    with p1:
        recipient = st.text_input("수신", value="임직원 검진 담당자 제위", key="combo_recipient")
        proposer = st.text_input("제안", value="뉴고려병원 이준원 팀장", key="combo_proposer")
    with p2:
        tel = st.text_input("제안서 Tel.", value="1833 - 9988", key="combo_tel")
        email = st.text_input("Email.", value="", key="combo_email")

    with st.expander("제안서 색상", expanded=False):
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            primary_purple = st.color_picker("--primary-purple", "#4A148C", key="combo_c1")
        with pc2:
            secondary_purple = st.color_picker("--secondary-purple", "#7B1FA2", key="combo_c2")
        with pc3:
            accent_gold = st.color_picker("--accent-gold", "#D4AF37", key="combo_c3")

    st.subheader("2. 제안서와 안내문이 공유할 검진 데이터")
    combo_data = _project_editor(official_2026_copy(), "combo")
    combo_data["phone"] = combo_data.get("phone") or tel.replace(" ", "")

    st.subheader("3. 안내문 배경")
    combo_bg = st.file_uploader(
        "배경 이미지 업로드 (PNG/JPG, 선택사항). 업로드하지 않으면 선택한 테마 배경을 사용합니다.",
        type=["png", "jpg", "jpeg"], key="combo_bg"
    )

    if st.button("제안서 + 안내문 생성", type="primary", key="combo_generate"):
        try:
            html = _proposal_html(
                recipient, proposer, tel, email,
                {
                    "--primary-purple": primary_purple,
                    "--secondary-purple": secondary_purple,
                    "--accent-gold": accent_gold,
                },
                combo_data,
            )
            flyer_pdf, flyer_png = _build_flyer(combo_data, combo_bg)
            st.session_state["combo_html"] = html
            st.session_state["combo_pdf"] = flyer_pdf
            st.session_state["combo_png"] = flyer_png
            st.session_state["combo_json"] = json.dumps(
                combo_data, ensure_ascii=False, indent=2
            ).encode("utf-8")
            st.success("제안서 HTML과 안내문 PDF/PNG를 생성했습니다.")
        except Exception as e:
            st.error(f"생성 실패: {e}")

    if st.session_state.get("combo_html"):
        st.subheader("제안서 미리보기")
        st.components.v1.html(st.session_state["combo_html"], height=600, scrolling=True)

        st.subheader("안내문 미리보기")
        st.image(st.session_state["combo_png"], use_container_width=True)

        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.download_button(
                "제안서 HTML", st.session_state["combo_html"].encode("utf-8"),
                "2026_뉴고려병원_제안서.html", "text/html", key="dl_combo_html"
            )
        with d2:
            st.download_button(
                "안내문 PDF", st.session_state["combo_pdf"],
                "건강검진_안내문.pdf", "application/pdf", key="dl_combo_pdf"
            )
        with d3:
            st.download_button(
                "안내문 PNG", st.session_state["combo_png"],
                "건강검진_안내문.png", "image/png", key="dl_combo_png"
            )
        with d4:
            st.download_button(
                "검진 데이터 JSON", st.session_state["combo_json"],
                "proposal_data.json", "application/json", key="dl_combo_json"
            )


with tab_flyer:
    st.subheader("안내문만 독립적으로 제작")
    source_mode = st.radio(
        "내용 불러오기",
        ["공식 2026 기본값", "proposal_data.json 업로드", "이 프로그램에서 만든 제안서 HTML 업로드"],
        horizontal=True,
        key="flyer_source_mode",
    )

    source_data = official_2026_copy()
    import_message = ""

    if source_mode == "proposal_data.json 업로드":
        uploaded_json = st.file_uploader("JSON 파일", type=["json"], key="flyer_json")
        if uploaded_json:
            try:
                source_data = normalize_project_data(json.loads(uploaded_json.getvalue().decode("utf-8-sig")))
                import_message = "JSON의 검진 데이터를 불러왔습니다."
            except Exception as e:
                st.error(f"JSON을 읽지 못했습니다: {e}")

    elif source_mode == "이 프로그램에서 만든 제안서 HTML 업로드":
        uploaded_html = st.file_uploader("제안서 HTML 파일", type=["html", "htm"], key="flyer_html")
        if uploaded_html:
            raw_html = uploaded_html.getvalue().decode("utf-8", errors="replace")
            embedded = proposal_engine.extract_proposal_data(raw_html)
            if embedded:
                source_data = normalize_project_data(embedded)
                import_message = "제안서 안의 구조화된 검진 데이터를 자동으로 불러왔습니다."
            else:
                legacy = proposal_engine.extract_legacy_basic_fields(raw_html)
                source_data = official_2026_copy()
                if legacy.get("phone"):
                    source_data["phone"] = legacy["phone"].replace(" ", "")
                import_message = (
                    "과거 형식 제안서라 구조화 데이터가 없습니다. 확인 가능한 연락처만 불러오고 "
                    "검진항목은 공식 2026 기본값을 적용했습니다."
                )

    if import_message:
        st.info(import_message)

    flyer_data = _project_editor(source_data, "standalone")
    standalone_bg = st.file_uploader(
        "배경 이미지 업로드 (PNG/JPG, 선택사항)",
        type=["png", "jpg", "jpeg"], key="standalone_bg"
    )

    if st.button("안내문 생성", type="primary", key="standalone_generate"):
        try:
            pdf, png = _build_flyer(flyer_data, standalone_bg)
            st.session_state["standalone_pdf"] = pdf
            st.session_state["standalone_png"] = png
            st.session_state["standalone_json"] = json.dumps(
                flyer_data, ensure_ascii=False, indent=2
            ).encode("utf-8")
            st.success("안내문을 생성했습니다.")
        except Exception as e:
            st.error(f"안내문 생성 실패: {e}")

    if st.session_state.get("standalone_png"):
        st.image(st.session_state["standalone_png"], use_container_width=True)
        s1, s2, s3 = st.columns(3)
        with s1:
            st.download_button(
                "PDF 다운로드", st.session_state["standalone_pdf"],
                "건강검진_안내문.pdf", "application/pdf", key="dl_standalone_pdf"
            )
        with s2:
            st.download_button(
                "PNG 다운로드", st.session_state["standalone_png"],
                "건강검진_안내문.png", "image/png", key="dl_standalone_png"
            )
        with s3:
            st.download_button(
                "JSON 저장", st.session_state["standalone_json"],
                "proposal_data.json", "application/json", key="dl_standalone_json"
            )
