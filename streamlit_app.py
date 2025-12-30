import streamlit as st
import os
import shutil
import base64
from proposal_engine import ProposalEngine

# ---------------------------------------------------------
# 1. 초기 설정 및 엔진 로드
# ---------------------------------------------------------
st.set_page_config(
    page_title="뉴고려병원 제안서 생성기",
    page_icon="🏥",
    layout="wide"
)

# 캐시를 사용해 엔진을 한 번만 로드하고 세션 내에서 유지
if 'engine' not in st.session_state:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 엔진 초기화 (필요한 폴더 생성 등 수행)
    st.session_state.engine = ProposalEngine(base_dir)

engine = st.session_state.engine

# CSS 스타일링 (폰트 등)
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px 4px 0 0; gap: 1px;}
    .stTabs [aria-selected="true"] { background-color: #ffffff; border-top: 2px solid #4A148C; }
    </style>
""", unsafe_allow_html=True)

st.title("🏥 뉴고려병원 건강검진 제안서 생성기")
st.caption("Web Version v1.0 | Streamlit")

# ---------------------------------------------------------
# 2. 탭 구성
# ---------------------------------------------------------
tab_basic, tab_layout, tab_images, tab_pages, tab_content, tab_export = st.tabs([
    "기본 정보", "레이아웃/디자인", "이미지 관리", "페이지 순서", "세부 내용 편집", "제안서 생성(다운로드)"
])

# ---------------------------------------------------------
# TAB 1: 기본 정보 & 색상
# ---------------------------------------------------------
with tab_basic:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 기본 정보 입력")
        recipient = st.text_input("수신 (고객사)", value="임직원 검진 담당자 제위")
        proposer = st.text_input("제안자 (담당자)", value="뉴고려병원 이준원 팀장")
        tel = st.text_input("상담 전화번호", value="1833 - 9988")
        
        # 세션에 값 저장
        st.session_state['recipient'] = recipient
        st.session_state['proposer'] = proposer
        st.session_state['tel'] = tel

    with col2:
        st.subheader("🎨 브랜드 컬러")
        primary_color = st.color_picker("메인 컬러 (Primary)", "#4A148C")
        accent_color = st.color_picker("포인트 컬러 (Accent)", "#D4AF37")
        
        st.session_state['primary_color'] = primary_color
        st.session_state['accent_color'] = accent_color
        
        st.info("※ 선택한 색상은 최종 HTML 생성 시 반영됩니다.")

# ---------------------------------------------------------
# TAB 2: 레이아웃 설정
# ---------------------------------------------------------
with tab_layout:
    st.subheader("📏 여백 및 크기 조정 (CSS 변수)")
    st.caption("변경 즉시 엔진 설정에 저장되며, 이미지 재가공이 발생할 수 있습니다.")
    
    current_layout = engine.get_layout_settings()
    new_layout = current_layout.copy()
    
    col_l1, col_l2, col_l3 = st.columns(3)
    
    with col_l1:
        st.markdown("**기본 여백**")
        new_layout['page_padding_mm'] = st.number_input("페이지 안쪽 여백 (mm)", 5, 50, current_layout['page_padding_mm'])
        new_layout['page_gap_px'] = st.number_input("페이지 간격 (화면용 px)", 0, 100, current_layout['page_gap_px'])
        new_layout['user_block_gap_px'] = st.number_input("텍스트 블록 위 공백 (px)", 0, 100, current_layout['user_block_gap_px'])

    with col_l2:
        st.markdown("**콘텐츠 간격**")
        new_layout['img_default_height_px'] = st.number_input("기본 이미지 높이 (px)", 100, 600, current_layout['img_default_height_px'])
        new_layout['img_margin_v_px'] = st.number_input("이미지 위/아래 여백 (px)", 0, 100, current_layout['img_margin_v_px'])
        new_layout['highlight_margin_v_px'] = st.number_input("강조박스 위/아래 여백 (px)", 0, 100, current_layout['highlight_margin_v_px'])

    with col_l3:
        st.markdown("**특수 이미지 높이**")
        new_layout['img_h_300_px'] = st.number_input("대형 (300px 영역)", 100, 800, current_layout['img_h_300_px'])
        new_layout['img_h_250_px'] = st.number_input("중형 (250px 영역)", 100, 800, current_layout['img_h_250_px'])
        new_layout['img_h_180_px'] = st.number_input("소형 (180px 영역)", 50, 500, current_layout['img_h_180_px'])

    # 변경 사항 적용 버튼
    if st.button("레이아웃 설정 저장 및 적용"):
        try:
            engine.set_layout_settings(new_layout)
            st.success("레이아웃 설정이 저장되었습니다.")
        except Exception as e:
            st.error(f"오류 발생: {e}")

# ---------------------------------------------------------
# TAB 3: 이미지 관리
# ---------------------------------------------------------
with tab_images:
    st.subheader("🖼️ 이미지 교체")
    st.info("이미지를 업로드하면 자동으로 리사이징되어 프로젝트 폴더에 저장됩니다.")
    
    # 이미지 목록 순회
    for key, data in engine.image_map.items():
        with st.expander(f"📷 {key}", expanded=False):
            col_img1, col_img2 = st.columns([1, 2])
            
            current_path = data.get("path")
            
            with col_img1:
                if current_path and os.path.exists(current_path):
                    st.image(current_path, caption="현재 적용된 이미지")
                else:
                    st.warning("이미지 미설정")
            
            with col_img2:
                uploaded_file = st.file_uploader(f"'{key}' 이미지 업로드", type=['jpg', 'png', 'jpeg'], key=f"uploader_{key}")
                
                if uploaded_file is not None:
                    # 임시 파일로 저장 후 엔진에 전달
                    temp_dir = os.path.join(engine.assets_dir, "temp_upload")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, uploaded_file.name)
                    
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    try:
                        # 엔진이 알아서 원본 저장/리사이징/설정저장 수행
                        final_path = engine.copy_resize_to_local(key, temp_path)
                        engine.image_map[key]["path"] = final_path
                        engine.save_settings()
                        st.success(f"{key} 이미지가 업데이트되었습니다!")
                        st.rerun() # 새로고침하여 이미지 반영
                    except Exception as e:
                        st.error(f"이미지 처리 실패: {e}")

# ---------------------------------------------------------
# TAB 4: 페이지 관리
# ---------------------------------------------------------
with tab_pages:
    st.subheader("📑 페이지 순서 및 활성화")
    
    col_ctrl, col_list = st.columns([1, 2])
    
    with col_ctrl:
        st.markdown("##### 페이지 제어")
        if st.button("➕ 새 페이지 추가"):
            engine.add_new_page()
            st.rerun()
            
    with col_list:
        pages = engine.get_pages()
        enabled_status = engine.page_enabled
        
        # 페이지 리스트 출력
        for idx, page_html in enumerate(pages):
            # 페이지 제목 추출 (간단히 h2 태그 내용이나 인덱스 사용)
            title_display = f"Page {idx+1}"
            
            # 페이지 컨테이너
            with st.container():
                c1, c2, c3, c4 = st.columns([0.5, 3, 0.5, 0.5])
                
                # 활성화 체크박스
                is_enabled = enabled_status[idx] if idx < len(enabled_status) else True
                new_enabled = c1.checkbox("사용", value=is_enabled, key=f"chk_page_{idx}", label_visibility="collapsed")
                
                if new_enabled != is_enabled:
                    engine.set_page_enabled(idx, new_enabled)
                    st.rerun()
                
                # 페이지 미리보기 텍스트 (앞부분만)
                clean_text = page_html.replace("<", "&lt;").replace(">", "&gt;")[:100] + "..."
                c2.markdown(f"**{title_display}** : `{clean_text}`")
                
                # 순서 이동 버튼
                if c3.button("⬆️", key=f"up_{idx}"):
                    engine.move_page(idx, -1)
                    st.rerun()
                if c4.button("⬇️", key=f"down_{idx}"):
                    engine.move_page(idx, 1)
                    st.rerun()
                    
                # 삭제/복제 (Expander 안에 숨김)
                with st.expander("추가 옵션 (복제/삭제)"):
                    if st.button("복제하기", key=f"dup_{idx}"):
                        engine.duplicate_page(idx)
                        st.rerun()
                    if st.button("삭제하기", key=f"del_{idx}"):
                        engine.delete_page(idx)
                        st.rerun()
            st.divider()

# ---------------------------------------------------------
# TAB 5: 내용 편집 (텍스트/표/아이콘)
# ---------------------------------------------------------
with tab_content:
    sub_tab_text, sub_tab_table, sub_tab_icon = st.tabs(["텍스트 블록", "표(Table)", "아이콘 목록"])
    
    # --- 1. 텍스트 블록 ---
    with sub_tab_text:
        st.markdown("#### 📝 페이지별 텍스트 블록 편집")
        
        pages = engine.get_pages()
        page_opts = [f"Page {i+1}" for i in range(len(pages))]
        selected_page_idx = st.selectbox("편집할 페이지 선택", range(len(pages)), format_func=lambda x: page_opts[x])
        
        blocks = engine.list_text_blocks(selected_page_idx)
        
        if not blocks:
            st.info("이 페이지에는 편집 가능한 텍스트 블록이 없습니다.")
            if st.button("새 텍스트 블록 추가"):
                engine.add_text_block(selected_page_idx)
                st.rerun()
        else:
            block_opts = [f"{b['id']} | {b['title']}" for b in blocks]
            selected_block_idx = st.selectbox("편집할 블록 선택", range(len(blocks)), format_func=lambda x: block_opts[x])
            
            target_block = blocks[selected_block_idx]
            
            with st.form(key="text_edit_form"):
                new_title = st.text_input("블록 제목", value=target_block['title'])
                new_text = st.text_area("내용 (줄바꿈: 문단구분, '- ': 글머리기호)", value=target_block['text'], height=200)
                
                if st.form_submit_button("저장"):
                    engine.save_text_block(selected_page_idx, target_block['id'], new_title, new_text)
                    st.success("텍스트 블록이 저장되었습니다.")
                    st.rerun()

            col_del, _ = st.columns([1, 4])
            if col_del.button("이 블록 삭제"):
                engine.delete_text_block(selected_page_idx, target_block['id'])
                st.warning("블록이 삭제되었습니다.")
                st.rerun()
    
    # --- 2. 표 편집 ---
    with sub_tab_table:
        st.markdown("#### 📊 HTML 테이블 직접 편집")
        tables = engine.list_tables()
        if not tables:
            st.warning("감지된 테이블이 없습니다.")
        else:
            table_opts = [f"TABLE {t}" for t in tables]
            selected_table_num = st.selectbox("편집할 테이블 선택", tables, format_func=lambda x: f"Table {x}")
            
            current_html = engine.get_table_html(selected_table_num)
            
            new_table_html = st.text_area("HTML 코드 편집", value=current_html, height=300)
            
            c_t1, c_t2, c_t3 = st.columns(3)
            if c_t1.button("표 저장"):
                engine.set_table_html(selected_table_num, new_table_html)
                st.success("표가 저장되었습니다.")
            
            if c_t2.button("행 추가 (빈 줄)"):
                engine.add_empty_row_to_table(selected_table_num)
                st.rerun()
                
            if c_t3.button("내용 비우기"):
                engine.clear_table(selected_table_num)
                st.rerun()

    # --- 3. 아이콘 목록 ---
    with sub_tab_icon:
        st.markdown("#### 🧩 아이콘/센터 목록 관리")
        
        icon_type = st.radio("편집 대상", ["검진 프로세스 (Process Steps)", "진료 센터 목록 (Centers List)"])
        
        if icon_type == "검진 프로세스 (Process Steps)":
            items = engine.get_process_steps()
            save_func = engine.save_process_steps
        else:
            items = engine.get_centers_items()
            save_func = engine.save_centers_items
            
        # 리스트 에디터 (데이터프레임 방식이 편집하기 편함)
        edit_data = []
        for it in items:
            edit_data.append({"icon": it['icon'], "label": it['label']})
            
        edited_df = st.data_editor(edit_data, num_rows="dynamic", use_container_width=True)
        
        if st.button("아이콘 목록 저장"):
            # DF -> List[Dict] 변환
            new_items = [{"icon": r["icon"], "label": r["label"]} for r in edited_df]
            save_func(new_items)
            st.success("저장되었습니다.")

# ---------------------------------------------------------
# TAB 6: 내보내기
# ---------------------------------------------------------
with tab_export:
    st.subheader("📤 제안서 최종 생성")
    
    st.markdown("""
    1. 위의 탭들에서 내용을 모두 수정한 후 아래 버튼을 누르세요.
    2. 생성된 HTML 파일은 모든 이미지와 스타일이 내장되어 있어 **인터넷 없이도 열립니다.**
    """)
    
    # 미리보기 기능 (HTML이 복잡해서 전체 렌더링은 iframe으로 제한적일 수 있음)
    if st.checkbox("미리보기 생성 (렌더링에 시간이 걸릴 수 있습니다)"):
        try:
            preview_html = engine.build_output_html(
                recipient=st.session_state.get('recipient', "고객사"),
                proposer=st.session_state.get('proposer', "담당자"),
                tel=st.session_state.get('tel', "000-0000"),
                primary_color=st.session_state.get('primary_color', "#4A148C"),
                accent_color=st.session_state.get('accent_color', "#D4AF37")
            )
            st.components.v1.html(preview_html, height=800, scrolling=True)
        except Exception as e:
            st.error(f"미리보기 생성 중 오류: {e}")

    # 다운로드 버튼
    # 버튼 클릭 시점에 HTML 생성
    final_html = engine.build_output_html(
        recipient=st.session_state.get('recipient', ""),
        proposer=st.session_state.get('proposer', ""),
        tel=st.session_state.get('tel', ""),
        primary_color=st.session_state.get('primary_color', "#4A148C"),
        accent_color=st.session_state.get('accent_color', "#D4AF37")
    )
    
    # 파일명 생성
    file_name = f"제안서_{st.session_state.get('recipient', 'Client')}.html"
    
    st.download_button(
        label="📥 HTML 제안서 다운로드",
        data=final_html,
        file_name=file_name,
        mime="text/html"
    )
