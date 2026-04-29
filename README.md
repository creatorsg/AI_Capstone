# AI_Capstone
HansungUniversity AI_Capstone

## 실행 환경 및 실행법
* 윈도우
* 파이썬 가상환경 생성: py -3.10 -m venv .venv
* 가상환경 실행: .venv\Scripts\Activate.ps1
	* 실행 오류시 다음 입력 후 재실행: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
* 필요 라이브러리 다운: pip install -r requirements.txt
* 챗봇 실행: streamlit run app/main.py

## 폴더 설명
* APP 폴더: 소스코드
* Data: 벡터화 안된 데이터
* Chroma_db: 벡터화된 데이터
* .env: API 키
* 외에 data_test, deprecated_rag은 사용하지 않는 파일

## 코드 설명
* app/ingest.py JSON 데이터를 읽어서 메타데이터를 정규화하고 Chroma에 적재
* app/rag.py 질문 분석, 검색 라우팅, rerank, 답변 생성
* app/vector_config.py 벡터DB 경로와 컬렉션 이름 관리
* app/prompts.py 유저 쿼리의 의도 분석, 유저 쿼리 재작성, 답변을 위한 LLM 프롬프트들
* app/curated_docs.py최소한의 curated knowledge 샘플
