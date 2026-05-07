"""ChromaDB 데이터 인제스트 스크립트

jaehwi 브랜치의 JSON 지식베이스 파일을 ChromaDB 벡터 저장소에 등록합니다.

사용법:
    python ingest.py

필요 환경변수:
    OPENAI_API_KEY  - OpenAI 임베딩 API 키

필요 파일 (data/ 디렉터리):
    data3_vaccine_final_knowledge_base.json  - 예방접종 지식베이스
    data5_welfare_childcare_kb.json          - 복지서비스 지식베이스
    data7_childcare_auto_kb.json             - 아이돌봄 지식베이스
    data1_cleaned_pediatrics_hospitals.json  - 소아청소년과 병원 (시설 컬렉션)
    data2_geocoded_night_hospitals.json      - 야간 소아과 병원 (시설 컬렉션)
    data4_geocoded_national_vaccine_hospitals_final.json - 예방접종 병원 (시설 컬렉션)
    data6_geocoded_childcare_facilities_final.json       - 아이돌봄센터 (시설 컬렉션)

실행 후 chroma_db/ 디렉터리가 생성됩니다.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

load_dotenv()

ROOT_DIR  = Path(__file__).resolve().parent
DATA_DIR  = ROOT_DIR / "data"
CHROMA_DIR = ROOT_DIR / "chroma_db"

# juhyeong vector_config 와 동일한 컬렉션 이름
KNOWLEDGE_COLLECTION = "parenting_knowledge"
FACILITY_COLLECTION  = "parenting_facility"

# ── 지식베이스 파일: KNOWLEDGE 컬렉션에 삽입 ──────────────────────────────────
KNOWLEDGE_FILES = [
    "data3_vaccine_final_knowledge_base.json",
    "data5_welfare_childcare_kb.json",
    "data7_childcare_auto_kb.json",
]

# ── 시설 파일: FACILITY 컬렉션에 삽입 ────────────────────────────────────────
FACILITY_FILES = [
    "data1_cleaned_pediatrics_hospitals.json",
    "data2_geocoded_night_hospitals.json",
    "data4_geocoded_national_vaccine_hospitals_final.json",
    "data6_geocoded_childcare_facilities_final.json",
]


def load_json(filepath: Path) -> list[dict]:
    """JSON 파일을 로드합니다. 파일이 없으면 빈 리스트 반환."""
    if not filepath.exists():
        print(f"  [SKIP] 파일 없음: {filepath.name}")
        return []
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # 단일 객체인 경우 리스트로 감싸기
        return [data]
    return data


def record_to_document(record: dict, source_file: str) -> Document | None:
    """
    JSON 레코드를 LangChain Document로 변환합니다.

    지원 형식:
      - 지식베이스: {"data_type": "knowledge_base", "title": ..., "content": ..., "category": ...}
      - 병원/시설:  {"name": ..., "address": ..., "tel": ..., ...}
    """
    data_type = record.get("data_type", "")

    if data_type == "knowledge_base":
        content  = record.get("content", "")
        title    = record.get("title", "")
        category = record.get("category", "unknown")
        if not content:
            return None
        return Document(
            page_content=content,
            metadata={
                "title":    title,
                "category": category,
                "source":   source_file,
                "doc_type": "knowledge_base",
            },
        )

    else:
        # 시설 데이터 (병원, 아이돌봄센터 등)
        name    = record.get("name") or record.get("병원명") or record.get("시설명") or "N/A"
        address = record.get("address") or record.get("주소") or record.get("도로명주소") or ""
        tel     = record.get("tel") or record.get("전화번호") or ""
        lat     = record.get("lat") or record.get("latitude") or ""
        lon     = record.get("lon") or record.get("longitude") or ""

        content = f"시설명: {name}\n주소: {address}\n전화: {tel}"
        if lat and lon:
            content += f"\n위도: {lat}, 경도: {lon}"

        return Document(
            page_content=content,
            metadata={
                "name":     name,
                "category": "hospital_locator",
                "source":   source_file,
                "doc_type": "facility",
            },
        )


def ingest_collection(files: list[str], collection_name: str, embeddings) -> int:
    """파일 목록을 읽어 Chroma 컬렉션에 인제스트합니다."""
    all_docs: list[Document] = []

    for filename in files:
        filepath = DATA_DIR / filename
        records  = load_json(filepath)
        docs     = [d for r in records if (d := record_to_document(r, filename)) is not None]
        print(f"  {filename}: {len(docs)}개 문서 변환")
        all_docs.extend(docs)

    if not all_docs:
        print(f"  [{collection_name}] 인제스트할 문서 없음, 건너뜀")
        return 0

    print(f"\n  [{collection_name}] 총 {len(all_docs)}개 문서 → ChromaDB 인제스트 중...")
    Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=str(CHROMA_DIR),
    )
    print(f"  [{collection_name}] 완료!")
    return len(all_docs)


def main():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY 가 설정되지 않았습니다.")
        print("  .env 파일에 OPENAI_API_KEY=sk-... 를 추가하세요.")
        sys.exit(1)

    print("=== ChromaDB 인제스트 시작 ===")
    print(f"  데이터 디렉터리: {DATA_DIR}")
    print(f"  ChromaDB 경로:  {CHROMA_DIR}\n")

    embeddings = OpenAIEmbeddings()

    # 지식베이스 컬렉션
    print("▶ KNOWLEDGE 컬렉션 (지식베이스)")
    k_count = ingest_collection(KNOWLEDGE_FILES, KNOWLEDGE_COLLECTION, embeddings)

    # 시설 컬렉션
    print("\n▶ FACILITY 컬렉션 (병원/시설)")
    f_count = ingest_collection(FACILITY_FILES, FACILITY_COLLECTION, embeddings)

    print(f"\n=== 인제스트 완료: 지식베이스 {k_count}개, 시설 {f_count}개 ===")
    print(f"  chroma_db/ 디렉터리가 생성되었습니다.")


if __name__ == "__main__":
    main()
