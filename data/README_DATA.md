# 육아 챗봇을 위한 데이터 수집 및 전처리

## 1. 목표

다양한 형태의 공공 데이터 및 웹 텍스트를 수집, 정제하여 챗봇 Vector DB 및 RAG 시스템에 즉시 활용 가능한 최적화된 JSON 형태로 구축

---

## 2. 주요 수행 업무

### 위치 기반 시설 데이터 정제

**대상 데이터:** 소아청소년과 병원, 야간/휴일 소아과, 국가예방접종 지정 의료기관, 아이돌봄 서비스 제공기관

**수행 내용:**
- 결측치 및 이상치 제거를 통한 원본 데이터 정제
- Kakao Developers를 이용해 문자열 주소 데이터를 위도 및 경도 좌표계로 변환하여 공간 데이터화 완료
- data4의 경우 주소가 주어져 주소기반으로 변환 12,383개 데이터 중, 좌표가 정상적으로 생성된 데이터는 12,284개. 나머지인 99개 데이터는 주소 불분명 등의 이유로 좌표 정보가 포함되지 않았으나, 나머지 정보는 모두 포함되어 있음
- data6의 경우 주소가 주어지지 않아 city, district, title을 합쳐서 검색 232개 데이터 중, 좌표가 정상적으로 생성된 데이터는 206개. 나머지인 26개 데이터는 주소 불분명 등의 이유로 좌표 정보가 포함되지 않았으나, 나머지 정보는 모두 포함되어 있음
- 사용자 위치 기반 병원 필터링 및 지도 API 연동이 가능하도록 구조화

---

### RAG 지식베이스 텍스트 데이터 구축

**대상 데이터:** 예방접종 상세 정보, 복지서비스 요약, 아이사랑포털 육아상식

**수행 내용:**
- Python 및 BeautifulSoup을 활용하여 아이사랑포털 내 수십 개의 육아상식 페이지 자동 크롤링 파이프라인 구축
- 웹 페이지 내 불필요한 노이즈(메뉴바, 숨김 태그 등)를 제거하고 핵심 본문(Content)만 추출
- HTML 구조를 분석하여 브라우저 탭 또는 본문 내 실제 카테고리 제목을 동적으로 추출 및 매핑

---

### 파이프라인 최적화

- 모든 데이터를 AI 모델이 이해하기 쉬운 `metadata`와 `content`의 통일된 규격으로 포맷팅
- 웹 크롤링 데이터의 경우, 향후 챗봇이 사용자에게 정확한 출처를 제공할 수 있도록 메타데이터 내에 원본 출처(Source), URL, 분류(Category) 정보를 삽입하여 저작권 및 신뢰도 문제 사전 대비
- 데이터의 목적(검색용 vs 지식용)에 따라 파일을 명확히 분리하여 AI 엔지니어의 후속 작업(Chunking, Embedding) 효율성 극대화

---

## 3. 최종 산출물 (총 7건의 JSON 파일)

| 파일명 | 설명 |
|--------|------|
| `data1_cleaned_pediatrics_hospitals.json` | 소아청소년과 |
| `data2_geocoded_night_hospitals.json` | 야간/휴일 소아과 |
| `data3_vaccine_final_knowledge_base.json` | 예방접종 지식 |
| `data4_geocoded_national_vaccine_hospitals_final.json` | 예방접종 병원 |
| `data5_welfare_childcare_kb.json` | 복지서비스 |
| `data6_childcare_facilities.json` | 아이돌봄센터 |
| `data7_childcare_auto_kb.json` | 육아상식 월령별 성장 및 돌보기 |

---

## 사용 데이터 및 출처

| # | 데이터명 | URL |
|---|----------|-----|
| 1 | 건강보험심사평가원_병원정보서비스 | [링크](https://www.data.go.kr/data/15001698/openapi.do#/) |
| 2 | 건강보험심사평가원_특수진료병원정보서비스(소아야간진료api) | [링크](https://www.data.go.kr/data/15001674/openapi.do#/API%20%EB%AA%A9%EB%A1%9D/getChildNightMdlrtList1) |
| 3 | 질병관리청_예방접종(대상 감염병 관련) 정보 | [링크](https://www.data.go.kr/data/15084296/openapi.do#tab_layer_detail_function) |
| 4 | 질병관리청_어린이 국가예방접종 지원사업 위탁의료기관 현황 정보 | [링크](https://www.data.go.kr/data/15084303/openapi.do?recommendDataYn=Y#/) |
| 5 | 한국사회보장정보원_복지서비스정보 | [링크](https://www.data.go.kr/data/15083323/fileData.do) |
| 6 | 성평등가족부_아이돌봄서비스제공기관 | [링크](https://www.data.go.kr/tcs/dss/selectFileDataDetailView.do?publicDataPk=15063160) |
| 7 | 아이사랑포털 육아상식 크롤링 | [링크](https://www.childcare.go.kr/?menuno=418) |

---

## 데이터 분류

### 1. 위치 및 메타데이터 중심 (지도 연동 및 필터링 검색용)

- `data1_cleaned_pediatrics_hospitals.json` — 소아청소년과 병원
- `data2_geocoded_night_hospitals.json` — 야간/휴일 소아과
- `data4_geocoded_national_vaccine_hospitals_final.json` — 예방접종 지정병원
- `data6_childcare_facilities.json` — 아이돌봄 제공기관

### 2. 지식 및 본문 중심 (AI 챗봇 RAG 답변용)

- `data3_vaccine_final_knowledge_base.json` — 예방접종 상세 지식
- `data5_welfare_childcare_kb.json` — 복지서비스 요약
- `data7_childcare_auto_kb.json` — 아이사랑포털 육아상식 월령별 성장 및 돌보기

---

## 이용허락범위 (저작권)

- **1, 2번:** 제3자 권리 포함 — 저작권 표시, 저작자 표시 / 공공저작물: 출처표시 (제1유형)
- **7번:** 웹 크롤링
- **나머지:** 제한 없음
