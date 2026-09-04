# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
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
    return "\n".join(str(x) for x in value) if isinstance(value, list) else str(value or "")


def parse_lines(value):
    return [x.strip() for x in str(value or "").splitlines() if x.strip()]


def seed(data):
    d = normalize_project_data(data)
    values = {
        "sa_title": d["title"], "sa_target": d["target"], "sa_period": d["period"],
        "sa_application_period": d["application_period"], "sa_phone": d["phone"],
        "sa_qr": d["qr_url"], "sa_theme": d.get("theme", "여름"),
        "sa_event_title": d["event_title"], "sa_event_lines": lines(d["event_lines"]),
        "sa_common": d["common_items"], "sa_group_a": lines(d["groups"]["A"]),
        "sa_group_b": lines(d["groups"]["B"]), "sa_group_c": lines(d["groups"]["C"]),
        "sa_notes": lines(d["notes"]),
    }
    for i, p in enumerate(d["packages"]):
        values[f"sa_n{i}"] = p["name"]
        values[f"sa_d{i}"] = p["detail"]
        values[f"sa_m{i}"] = p["male_price"]
        values[f"sa_f{i}"] = p["female_price"]
    for key, value in values.items():
        st.session_state[key] = value


mode = st.radio(
    "시작 방식",
    ["공식 2026 기본값", "proposal_data.json", "제안서 HTML"],
    horizontal=True,
    key="sa_mode",
)
data = official_2026_copy()
source_sig = "official-2026"
message = ""

if mode == "proposal_data.json":
    f = st.file_uploader("JSON 업로드", type=["json"], key="sa_json_upload")
    if f:
        raw = f.getvalue()
        try:
            data = normalize_project_data(json.loads(raw.decode("utf-8-sig")))
            source_sig = "json:" + hashlib.sha1(raw).hexdigest()
            message = "JSON의 검진 데이터를 불러왔습니다."
        except Exception as e:
            st.error(f"JSON을 읽지 못했습니다: {e}")
    else:
        source_sig = "json:none"

elif mode == "제안서 HTML":
    f = st.file_uploader("HTML 업로드", type=["html", "htm"], key="sa_html_upload")
    if f:
        raw_bytes = f.getvalue()
        source_sig = "html:" + hashlib.sha1(raw_bytes).hexdigest()
        raw = raw_bytes.decode("utf-8", errors="replace")
        embedded = proposal_engine.extract_proposal_data(raw)
        if embedded:
            data = normalize_project_data(embedded)
            message = "제안서의 구조화 검진 데이터를 자동으로 불러왔습니다."
        else:
            legacy = proposal_engine.extract_legacy_basic_fields(raw)
            if legacy.get("phone"):
                data["phone"] = legacy["phone"].replace(" ", "")
            message = "과거 제안서라 구조화 데이터가 없어 공식 2026 기본 검진항목을 적용했습니다."
    else:
        source_sig = "html:none"

if st.session_state.get("sa_source_sig") != source_sig:
    seed(data)
    st.session_state["sa_source_sig"] = source_sig

if message:
    st.info(message)

c1, c2, c3 = st.columns(3)
with c1:
    data["title"] = st.text_input("안내문 제목", value=data["title"], key="sa_title")
    data["target"] = st.text_input("대상", value=data["target"], key="sa_target")
with c2:
    data["period"] = st.text_input("검진기간", value=data["period"], key="sa_period")
    data["application_period"] = st.text_input("접수기간", value=data["application_period"], key="sa_application_period")
with c3:
    data["phone"] = st.text_input("문의전화", value=data["phone"], key="sa_phone")
    data["qr_url"] = st.text_input("QR 주소", value=data["qr_url"], key="sa_qr")

theme_names = list(THEMES.keys())
data["theme"] = st.selectbox(
    "테마", theme_names,
    index=theme_names.index(data.get("theme", "여름")) if data.get("theme", "여름") in theme_names else 0,
    key="sa_theme",
)
data["event_title"] = st.text_input("이벤트 제목", value=data["event_title"], key="sa_event_title")
data["event_lines"] = parse_lines(st.text_area(
    "혜택 문구", value=lines(data["event_lines"]), height=90, key="sa_event_lines"
))
data["common_items"] = st.text_area("공통항목", value=data["common_items"], height=120, key="sa_common")

with st.expander("검진 패키지 / 금액", expanded=True):
    edited = []
    for i, p in enumerate(data["packages"]):
        cols = st.columns([1, 4.5, 1, 1])
        edited.append({
            "name": cols[0].text_input("유형", value=p["name"], key=f"sa_n{i}"),
            "detail": cols[1].text_input("내용", value=p["detail"], key=f"sa_d{i}"),
            "male_price": cols[2].text_input("남", value=p["male_price"], key=f"sa_m{i}"),
            "female_price": cols[3].text_input("여", value=p["female_price"], key=f"sa_f{i}"),
        })
    data["packages"] = edited

with st.expander("A/B/C 그룹", expanded=False):
    ca, cb, cc = st.columns(3)
    data["groups"]["A"] = parse_lines(ca.text_area("A그룹", value=lines(data["groups"]["A"]), height=360, key="sa_group_a"))
    data["groups"]["B"] = parse_lines(cb.text_area("B그룹", value=lines(data["groups"]["B"]), height=360, key="sa_group_b"))
    data["groups"]["C"] = parse_lines(cc.text_area("C그룹", value=lines(data["groups"]["C"]), height=360, key="sa_group_c"))

data["notes"] = parse_lines(st.text_area("하단 안내", value=lines(data["notes"]), height=80, key="sa_notes"))
bg = st.file_uploader("배경 이미지 (선택)", type=["png", "jpg", "jpeg"], key="sa_bg")

if st.button("안내문 생성", type="primary", key="sa_generate"):
    try:
        engine = FlyerEngine()
        background = bg.getvalue() if bg else None
        st.session_state["sa_pdf"] = engine.render_pdf(data, background)
        st.session_state["sa_png"] = engine.render_png(data, background)
        st.session_state["sa_data_json"] = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        st.success("생성 완료")
    except Exception as e:
        st.error(f"생성 실패: {e}")

if st.session_state.get("sa_png"):
    st.image(st.session_state["sa_png"], use_container_width=True)
    c1, c2, c3 = st.columns(3)
    c1.download_button("PDF", st.session_state["sa_pdf"], "건강검진_안내문.pdf", "application/pdf", key="sa_dl_pdf")
    c2.download_button("PNG", st.session_state["sa_png"], "건강검진_안내문.png", "image/png", key="sa_dl_png")
    c3.download_button("JSON", st.session_state["sa_data_json"], "proposal_data.json", "application/json", key="sa_dl_json")
