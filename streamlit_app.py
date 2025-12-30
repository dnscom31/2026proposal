import streamlit as st
import streamlit.components.v1 as components
import os
import sys
import re


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import shutil
import tempfile
import time
import json

# 이제 import가 정상적으로 될 것입니다.
from proposal_engine import ProposalEngine

# ---------------------------------------------------------
# 1. 초기 설정 및 세션 격리 (중요)
# ---------------------------------------------------------
st.set_page_config(page_title="뉴고려병원 제안서 생성기", page_icon="🏥", layout="wide")

# 원본 템플릿 파일이 있는 경로 (이 파이썬 파일과 같은 위치라고 가정)
BASE_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FILE = "proposal_template.html"

# 세션별 독립적인 작업 공간 생성 함수
def init_session_engine():
    # 1. 임시 디렉토리 생성
    temp_dir = tempfile.mkdtemp()
    
    # 2. 필수 폴더 구조 생성
    assets_dir = os.path.join(temp_dir, "proposal_assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    # 3. 원본 템플릿 복사 (없으면 에러)
    src_template = os.path.join(BASE_SRC_DIR, TEMPLATE_FILE)
    if os.path.exists(src_template):
        shutil.copy(src_template, os.path.join(assets_dir, TEMPLATE_FILE))
    else:
        st.error(f"⚠️ 원본 템플릿({TEMPLATE_FILE})을 찾을 수 없습니다.")
        return None, None

    # 4. 엔진 초기화 (임시 디렉토리를 base_dir로 설정)
    engine = ProposalEngine(temp_dir)
    return engine, temp_dir

if 'engine' not in st.session_state:
    with st.spinner("작업 공간을 생성 중입니다..."):
        engine, temp_dir = init_session_engine()
        st.session_state.engine = engine
        st.session_state.temp_dir = temp_dir
        # 기본값 초기화
        st.session_state['recipient'] = "임직원 검진 담당자 제위"
        st.session_state['proposer'] = "뉴고려병원 이준원 팀장"
        st.session_state['tel'] = "1833 - 9988"
        st.session_state['primary_color'] = "#4A148C"
        st.session_state['accent_color'] = "#D4AF37"
        st.session_state['attachment_images'] = []  # 추가 첨부 이미지(페이지) 경로 목록

engine = st.session_state.engine

# 스타일 조정
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 45px; background-color: #f8f9fa; border-radius: 5px; }
    .stTabs [aria-selected="true"] { background-color: #e3f2fd; border-bottom: 2px solid #4A148C; font-weight: bold; }
    div[data-testid="stExpander"] div[role="button"] p { font-size: 1.1rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("🏥 뉴고려병원 건강검진 제안서 생성기")
st.caption("Web Version v2.0 | Isolated Session")

# ---------------------------------------------------------
# 2. 사이드바: 공통 설정 (항상 보이는 영역)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 기본 설정")
    st.session_state['recipient'] = st.text_input("수신 (고객사)", st.session_state['recipient'])
    st.session_state['proposer'] = st.text_input("제안자", st.session_state['proposer'])
    st.session_state['tel'] = st.text_input("문의처", st.session_state['tel'])
    
    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        st.session_state['primary_color'] = st.color_picker("메인 색상", st.session_state['primary_color'])
    with c2:
        st.session_state['accent_color'] = st.color_picker("강조 색상", st.session_state['accent_color'])
    
    st.info("💡 사이드바의 설정은 모든 페이지에 공통 적용됩니다.")


st.divider()
st.subheader("💾 작업 저장/불러오기")
st.caption("웹앱은 GitHub 코드를 자동으로 수정하지 않습니다. 대신 현재 설정을 파일로 저장해두면, 나중에 다시 업로드해서 이어서 편집할 수 있습니다.")

# 저장(다운로드): 텍스트/색상/레이아웃/페이지 on/off만 저장합니다.
project_data = {
    "meta": {
        "recipient": st.session_state.get("recipient", ""),
        "proposer": st.session_state.get("proposer", ""),
        "tel": st.session_state.get("tel", ""),
        "primary_color": st.session_state.get("primary_color", ""),
        "accent_color": st.session_state.get("accent_color", ""),
    },
    "engine": {
        "layout_settings": engine.layout_settings,
        "page_enabled": engine.page_enabled,
    }
}
st.download_button(
    "📥 설정 파일(.json) 다운로드",
    data=json.dumps(project_data, ensure_ascii=False, indent=2),
    file_name="proposal_project_settings.json",
    mime="application/json",
    use_container_width=True
)

uploaded_project = st.file_uploader("설정 파일(.json) 업로드", type=["json"])
if uploaded_project:
    try:
        data = json.load(uploaded_project)
        meta = data.get("meta", {})
        eng = data.get("engine", {})

        # 세션 기본값 복원
        st.session_state["recipient"] = meta.get("recipient", st.session_state["recipient"])
        st.session_state["proposer"] = meta.get("proposer", st.session_state["proposer"])
        st.session_state["tel"] = meta.get("tel", st.session_state["tel"])
        st.session_state["primary_color"] = meta.get("primary_color", st.session_state["primary_color"])
        st.session_state["accent_color"] = meta.get("accent_color", st.session_state["accent_color"])

        # 레이아웃/페이지 구성 복원
        if isinstance(eng.get("layout_settings"), dict):
            engine.set_layout_settings(eng["layout_settings"])
        if isinstance(eng.get("page_enabled"), list):
            engine.set_page_enabled(eng["page_enabled"])

        st.success("설정 파일을 불러왔습니다. (이미지 파일은 포함되지 않으므로 필요 시 다시 업로드하세요.)")
        st.rerun()
    except Exception as e:
        st.error(f"설정 파일을 읽는 중 오류: {e}")
    
    # 미리보기/다운로드 버튼을 사이드바 하단에도 배치
    st.divider()
    if st.button("🔄 미리보기 갱신", use_container_width=True):
        st.rerun()

# ---------------------------------------------------------
# 3. 메인 탭 구성
# ---------------------------------------------------------
tab_layout, tab_images, tab_pages, tab_content, tab_export = st.tabs([
    "📐 레이아웃", "🖼️ 이미지", "📑 페이지 구성", "📝 상세 편집", "📤 내보내기"
])

# --- TAB 1: 레이아웃 ---
with tab_layout:
    st.subheader("레이아웃 & 여백 설정")
    st.caption("CSS 변수를 조절하여 문서 전체의 간격과 이미지 크기를 변경합니다.")
    
    cur = engine.layout_settings
    new_l = cur.copy()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 📄 문서 여백")
        new_l['page_padding_mm'] = st.slider("페이지 내부 여백 (mm)", 5, 40, cur['page_padding_mm'])
        new_l['page_gap_px'] = st.slider("페이지 사이 간격 (px)", 0, 50, cur['page_gap_px'])
        
        st.markdown("##### 🖼️ 기본 이미지")
        new_l['img_default_height_px'] = st.number_input("기본 이미지 높이 (px)", 100, 500, cur['img_default_height_px'])

    with col2:
        st.markdown("##### 📏 요소 간격")
        new_l['img_margin_v_px'] = st.number_input("이미지 상하 여백", 0, 50, cur['img_margin_v_px'])
        new_l['highlight_margin_v_px'] = st.number_input("강조박스 상하 여백", 0, 50, cur['highlight_margin_v_px'])
        new_l['table_cell_padding_px'] = st.number_input("표 내부 여백 (Cell Padding)", 2, 20, cur['table_cell_padding_px'])

    if st.button("설정 적용하기"):
        engine.set_layout_settings(new_l)
        st.success("레이아웃이 업데이트되었습니다.")

# --- TAB 2: 이미지 ---
with tab_images:
    st.subheader("이미지 교체")
    st.caption("업로드된 이미지는 설정된 레이아웃 크기에 맞춰 자동 리사이징됩니다.")

    # 2열 그리드로 표시
    keys = list(engine.image_map.keys())
    for i in range(0, len(keys), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j >= len(keys): break
            key = keys[i+j]
            data = engine.image_map[key]
            
            with cols[j]:
                with st.expander(f"📷 {key}", expanded=True):
                    # 현재 이미지 표시
                    if data["path"] and os.path.exists(data["path"]):
                        st.image(data["path"], use_container_width=True)
                    else:
                        st.warning("이미지 없음")
                    
                    # 업로드
                    uploaded = st.file_uploader(f"변경: {key}", type=['jpg', 'png'], key=f"up_{key}")
                    if uploaded:
                        # 임시 파일 저장 -> 엔진 처리
                        t_path = os.path.join(st.session_state.temp_dir, uploaded.name)
                        with open(t_path, "wb") as f: f.write(uploaded.getbuffer())
                        engine.copy_resize_to_local(key, t_path)
                        st.success("변경 완료!")
                        time.sleep(0.5)
                        st.rerun()

# --- TAB 3: 페이지 구성 ---
if not simple_mode:
    with tab_pages:
        c1, c2 = st.columns([3, 1])
        with c1: st.subheader("페이지 순서 및 활성화")
        with c2: 
            if st.button("➕ 페이지 추가"):
                engine.add_new_page()
                st.rerun()
    
        pages = engine.get_pages()
        enabled = engine.page_enabled
        
        for idx, page in enumerate(pages):
            with st.container(border=True):
                col_check, col_info, col_act = st.columns([0.5, 4, 1.5])
                
                is_on = enabled[idx] if idx < len(enabled) else True
                if col_check.checkbox(f"P{idx+1}", value=is_on, key=f"chk_{idx}") != is_on:
                    engine.set_page_enabled(idx, not is_on)
                    st.rerun()
                
                # 페이지 내용 요약 (HTML 태그 제거)
                preview_text = re.sub(r'<[^>]+>', ' ', page)[:60].strip()
                col_info.markdown(f"**Page {idx+1}**: {preview_text}...")
                
                # 컨트롤 버튼
                b1, b2, b3, b4 = col_act.columns(4)
                if b1.button("⬆️", key=f"u{idx}"): engine.move_page(idx, -1); st.rerun()
                if b2.button("⬇️", key=f"d{idx}"): engine.move_page(idx, 1); st.rerun()
                if b3.button("복제", key=f"cp{idx}"): engine.duplicate_page(idx); st.rerun()
                if b4.button("삭제", key=f"rm{idx}"): engine.delete_page(idx); st.rerun()
    
# --- TAB 4: 상세 편집 ---
if not simple_mode:
    with tab_content:
        mode = st.radio("편집 모드 선택", ["텍스트 내용", "표(Table) 데이터", "아이콘/리스트"], horizontal=True)
        st.divider()
        
        if mode == "텍스트 내용":
            pages = engine.get_pages()
            sel_p = st.selectbox("페이지 선택", range(len(pages)), format_func=lambda x: f"Page {x+1}")
            
            blocks = engine.list_text_blocks(sel_p)
            if not blocks:
                st.info("편집 가능한 텍스트 블록이 없습니다.")
                if st.button("새 블록 추가"): engine.add_text_block(sel_p); st.rerun()
            else:
                sel_b = st.selectbox("블록 선택", range(len(blocks)), format_func=lambda x: f"{blocks[x]['title']}")
                target = blocks[sel_b]
                
                with st.form("edit_text"):
                    nt = st.text_input("제목", target['title'])
                    nc = st.text_area("내용 (- 로 시작하면 리스트)", target['text'], height=200)
                    if st.form_submit_button("저장"):
                        engine.save_text_block(sel_p, target['id'], nt, nc)
                        st.success("저장됨")
                        st.rerun()
                if st.button("🗑️ 이 블록 삭제"):
                    engine.delete_text_block(sel_p, target['id'])
                    st.rerun()
    
        elif mode == "표(Table) 데이터":
            t_ids = engine.list_tables()
            if t_ids:
                tid = st.selectbox("테이블 선택", t_ids, format_func=lambda x: f"Table {x}")
                html_val = engine.get_table_html(tid)
                new_html = st.text_area("HTML 직접 편집", html_val, height=300)
                if st.button("표 저장"):
                    engine.set_table_html(tid, new_html)
                    st.success("저장되었습니다.")
            else:
                st.warning("테이블이 없습니다.")
    
        elif mode == "아이콘/리스트":
            grp = st.selectbox("그룹 선택", ["process_steps", "centers_list"])
            if grp == "process_steps":
                data = engine.get_process_steps()
                edited = st.data_editor(data, num_rows="dynamic", use_container_width=True)
                if st.button("프로세스 저장"):
                    engine.save_process_steps(edited)
                    st.success("저장됨")
            else:
                data = engine.get_centers_items()
                edited = st.data_editor(data, num_rows="dynamic", use_container_width=True)
                if st.button("센터 목록 저장"):
                    engine.save_centers_items(edited)
                    st.success("저장됨")
    

# --- TAB X: 첨부 이미지(페이지 추가) ---
with tab_attach:
    st.subheader("첨부 이미지로 페이지 추가")
    st.caption("여기에 업로드한 이미지들은 '내보내기'에서 제안서 맨 뒤에 페이지로 자동 추가됩니다. (HTML에 Base64로 포함되므로 별도 이미지 파일이 필요 없습니다.)")

    up_files = st.file_uploader(
        "이미지 여러 개 업로드 (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    # 업로드 처리: 임시폴더에 저장 후 경로를 세션에 유지
    if up_files:
        attach_dir = os.path.join(st.session_state.temp_dir, "proposal_assets", "attachments")
        os.makedirs(attach_dir, exist_ok=True)

        new_paths = []
        for uf in up_files:
            save_path = os.path.join(attach_dir, uf.name)
            with open(save_path, "wb") as f:
                f.write(uf.getbuffer())
            new_paths.append(save_path)

        # 기존 + 새 파일 합치되, 중복은 제거
        merged = list(dict.fromkeys(st.session_state['attachment_images'] + new_paths))
        st.session_state['attachment_images'] = merged
        st.success(f"첨부 이미지 {len(new_paths)}개 추가 완료")

    # 현재 첨부 목록
    paths = st.session_state.get('attachment_images', [])
    if not paths:
        st.info("아직 첨부 이미지가 없습니다.")
    else:
        st.markdown("**현재 첨부 이미지 목록(순서가 곧 페이지 순서입니다)**")
        for idx, p in enumerate(paths, 1):
            c1, c2 = st.columns([6, 1])
            with c1:
                st.write(f"{idx}. {os.path.basename(p)}")
                if os.path.exists(p):
                    st.image(p, use_container_width=True)
            with c2:
                if st.button("삭제", key=f"att_del_{idx}"):
                    st.session_state['attachment_images'] = [x for x in paths if x != p]
                    st.rerun()

        st.divider()
        st.markdown("**순서 변경**")
        move_idx = st.number_input("이동할 항목 번호", min_value=1, max_value=len(paths), value=1)
        direction = st.radio("이동 방향", ["위로", "아래로"], horizontal=True)
        if st.button("순서 적용"):
            i = int(move_idx) - 1
            if direction == "위로" and i > 0:
                paths[i-1], paths[i] = paths[i], paths[i-1]
            elif direction == "아래로" and i < len(paths)-1:
                paths[i+1], paths[i] = paths[i], paths[i+1]
            st.session_state['attachment_images'] = paths
            st.rerun()

# --- TAB 5: 내보내기 ---
with tab_export:
    st.subheader("최종 결과물 확인 및 다운로드")
    
    # HTML 생성
    try:
        final_html = engine.build_output_html(
            st.session_state['recipient'], st.session_state['proposer'],
            st.session_state['tel'], st.session_state['primary_color'],
            st.session_state['accent_color'],
            attachment_image_paths=st.session_state.get('attachment_images', [])
        )
        
        col_down, col_view = st.columns([1, 1])
        with col_down:
            st.download_button(
                "📥 HTML 파일 다운로드", 
                data=final_html, 
                file_name=f"제안서_{st.session_state['recipient']}.html",
                mime="text/html",
                use_container_width=True,
                type="primary"
            )
        
        st.markdown("---")
        st.markdown("**👇 미리보기 (실제 파일과 동일)**")
        components.html(final_html, height=800, scrolling=True)
        
    except Exception as e:
        st.error(f"생성 중 오류 발생: {e}")
