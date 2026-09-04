# 2026proposal

뉴고려병원 제안서 + 건강검진 안내문 통합 생성기.

## 실행

통합 앱:
```bash
streamlit run streamlit_app.py
```

안내문 전용 앱:
```bash
streamlit run flyer_app.py
```

## 주요 기능

- 기존 제안서 HTML 생성 유지
- 제안서 생성과 동시에 건강검진 안내문 PDF/PNG 생성
- `proposal_data.json` 다운로드
- 새로 생성된 제안서 HTML 내부에 구조화 검진 데이터 자동 저장
- 안내문 전용 앱에서 `proposal_data.json` 또는 새 제안서 HTML 업로드 시 자동 입력
- 과거 제안서 HTML은 확인 가능한 연락처만 추출하고 공식 2026 기본 검진항목으로 보완
- 봄/여름/업그레이드/가정의달/기관형/미니멀 테마
- 사용자 PNG/JPG 배경 업로드
- Pretendard Regular/Medium/SemiBold/Bold 자동 적용
- 실제 QR 생성 및 PDF 클릭 링크
- PDF는 텍스트 레이어를 유지하므로 검색/선택 가능
- PNG 동시 출력

## 데이터 기준

`healthcheck_data.py`가 공통항목, A/B/C 그룹, 건강형/소망형/믿음형/행복형/사랑형 기본값을 관리합니다.
안내문과 제안서 사이의 데이터 교환은 `proposal_data.json` 또는 제안서 HTML 내부의
`<script id="nk-proposal-data" type="application/json">...</script>`를 사용합니다.

## 롤백

안내문 기능 추가 직전 상태는 `backup-before-flyer-v1-20260904` 브랜치에 보존되어 있습니다.
