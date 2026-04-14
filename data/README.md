# data/ — jaehwi 브랜치 정적 데이터 파일 위치

이 디렉토리에 **jaehwi 브랜치**의 JSON 파일을 복사하면
백엔드 API가 자동으로 실제 데이터를 사용합니다.

## 파일 배치 방법

```
jaehwi 브랜치 clone 또는 파일 다운로드 후 아래 경로에 붙여넣기:

fount-project/data/
├── data1_cleaned_pediatrics_hospitals.json          ← 소아청소년과 병원 전국
├── data2_geocoded_night_hospitals.json              ← 야간/휴일 소아과
├── data3_vaccine_final_knowledge_base.json          ← 예방접종 지식 (RAG용)
├── data4_geocoded_national_vaccine_hospitals_final.json  ← 예방접종 지정병원
├── data5_welfare_childcare_kb.json                  ← 복지서비스 정책 (welfare API용)
├── data6_geocoded_childcare_facilities_final.json   ← 아이돌봄센터
└── data7_childcare_auto_kb.json                     ← 육아상식 월령별 (RAG용)
```

## 파일별 사용처

| 파일 | 사용 API | 비고 |
|---|---|---|
| data1 | `GET /hospitals/static/nearby` | GPS 필터링 |
| data2 | `GET /hospitals/static/nearby?category=야간소아과` | GPS 필터링 |
| data3 | `services/rag_service.py` | juhyeong 브랜치 연동 |
| data4 | `GET /hospitals/static/nearby?category=예방접종병원` | GPS 필터링 |
| data5 | `GET /welfare/` | 자동 감지 후 대체 |
| data6 | `GET /hospitals/static/nearby?category=아이돌봄센터` | GPS 필터링 |
| data7 | `services/rag_service.py` | juhyeong 브랜치 연동 |

## 확인 방법

파일 배치 후 서버 재시작 없이:
- `GET /welfare/status` → data5 로드 확인
- `GET /hospitals/static/status` → data1/2/4/6 로드 확인
