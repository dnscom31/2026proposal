# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import streamlit as st

from healthcheck_data import official_2026_copy, normalize_project_data
from proposal_engine import ProposalEngine
from flyer_engine import FlyerEngine, THEMES

st.set_page_config(page_title="건강검진 안내문 제작기", layout="wide")
st.title("건강검진 안내문 제작기")
st.caption("제안서 없이 단독 사용하거나 proposal_data.json / 제안서 HTML을 불러와 안내문을 생성합니다.")

proposal_engine = ProposalEngine("proposal_template.html")


def lines(value):
    return "\n".join(value) if isinstance(value, list) else str(value or "")


def parse_lines(value):
    return [x.strip() for x in str(value or "").splitlines() if x.strip()]


mode = st.radio(
    "시작 방식",
    ["공식 2026 기본값", "proposal_data.json", "제안서 HTML"],
    horizontal=True,
)
data = official_2026_copy()

if mode == "proposal_data.json":
    f = st.file_uploader("JSON 업로드", type=["json"])
    if f:
        data = normalize_project_data(json.loads(f.getvalue().decode("utf-8-sig")))
elif mode == "제안서 HTML":
    f = st.file_uploader("HTML 업로드", type=["html", "htm"])
    if f:
        raw = f.getvalue().decode("utf-8", errors="replace")
        embedded = proposal_engine.extract_proposal_data(raw)
        if embedded:
            data = normalize_project_data(embedded)
            st.success("제안서의 검진 데이터를 자동으로 불러왔습니다.")
        else:
            legacy = proposal_engine.extract_legacy_basic_fields(raw)
            if legacy.get("phone"):
                data["phone"] = legacy["phone"].replace(" ", "")
            st.warning("과거 제안서라 구조화 데이터가 없어 공식 기본 검진항목을 사용합니다.")

c1, c2, c3 = st.columns(3)
with c1:
    data["title"] = st.text_input("안내문 제목", data["title"])
    data["target"] = st.text_input("대상", data["target"])
with c2:
    data["period"] = st.text_input("검진기간", data["period"])
    data["application_period"] = st.text_input("접수기간", data["application_period"])
with c3:
    data["phone"] = st.text_input("문의전화", data["phone"])
    data["qr_url"] = st.text_input("QR 주소", data["qr_url"])

data["theme"] = st.selectbox(
    "테마", list(THEMES.keys()),
    index=list(THEMES.keys()).index(data.get("theme", "여름"))
    if data.get("theme", "여름") in THEMES else 0
)
data["event_title"] = st.text_input("이벤트 제목", data["event_title"])
data["event_lines"] = parse_lines(st.text_area("혜택 문구", lines(data["event_lines"]), height=90))
data["common_items"] = st.text_area("공통항목", data["common_items"], height=120)

with st.expander("검진 패키지 / 금액", expanded=True):
    edited = []
    for i, p in enumerate(data["packages"]):
        cols = st.columns([1, 4.5, 1, 1])
        edited.append({
            "name": cols[0].text_input("유형", p["name"], key=f"n{i}"),
            "detail": cols[1].text_input("내용", p["detail"], key=f"d{i}"),
            "male_price": cols[2].text_input("남", p["male_price"], key=f"m{i}"),
            "female_price": cols[3].text_input("여", p["female_price"], key=f"f{i}"),
        })
    data["packages"] = edited

with st.expander("A/B/C 그룹", expanded=False):
    ca, cb, cc = st.columns(3)
    data["groups"]["A"] = parse_lines(ca.text_area("A그룹", lines(data["groups"]["A"]), height=360))
    data["groups"]["B"] = parse_lines(cb.text_area("B그룹", lines(data["groups"]["B"]), height=360))
    data["groups"]["C"] = parse_lines(cc.text_area("C그룹", lines(data["groups"]["C"]), height=360))

data["notes"] = parse_lines(st.text_area("하단 안내", lines(data["notes"]), height=80))
bg = st.file_uploader("배경 이미지 (선택)", type=["png", "jpg", "jpeg"])

if st.button("안내문 생성", type="primary"):
    try:
        engine = FlyerEngine()
        background = bg.getvalue() if bg else None
        st.session_state.pdf = engine.render_pdf(data, background)
        st.session_state.png = engine.render_png(data, background)
        st.session_state.data_json = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        st.success("생성 완료")
    except Exception as e:
        st.error(f"생성 실패: {e}")

if st.session_state.get("png"):
    st.image(st.session_state.png, use_container_width=True)
    c1, c2, c3 = st.columns(3)
    c1.download_button("PDF", st.session_state.pdf, "건강검진_안내문.pdf", "application/pdf")
    c2.download_button("PNG", st.session_state.png, "건강검진_안내문.png", "image/png")
    c3.download_button("JSON", st.session_state.data_json, "proposal_data.json", "application/json")
