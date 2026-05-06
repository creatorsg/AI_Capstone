# app/ingest.py

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from tqdm import tqdm

from curated_docs import CURATED_DOCS
from vector_config import (
    DATA_DIR,
    EMBEDDING_MODEL,
    FACILITY_COLLECTION_NAME,
    KNOWLEDGE_COLLECTION_NAME,
    MANIFEST_PATH,
    PERSIST_DIR,
)

load_dotenv()

BATCH_SIZE = 500
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
DEFAULT_AGE_GROUP = "0-60m"

JSON_DATASETS = {
    "data3_vaccine_final_knowledge_base.json": {
        "collection": "knowledge",
        "doc_type": "vaccination_knowledge",
        "source": "질병관리청",
        "topic": "schedule",
    },
    "data5_welfare_childcare_kb.json": {
        "collection": "knowledge",
        "doc_type": "policy_knowledge",
        "source": "복지로",
        "category": "policy",
        "topic": "welfare",
    },
    "data7_childcare_auto_kb.json": {
        "collection": "knowledge",
        "doc_type": "childcare_article",
        "source": "아이사랑포털",
    },
    "data1_cleaned_pediatrics_hospitals.json": {
        "collection": "facility",
        "doc_type": "pediatrics_facility",
        "source": "건강보험심사평가원",
        "topic": "pediatrics",
    },
    "data2_geocoded_night_hospitals.json": {
        "collection": "facility",
        "doc_type": "night_hospital_facility",
        "source": "건강보험심사평가원",
        "topic": "night_care",
    },
    "data4_geocoded_national_vaccine_hospitals_final.json": {
        "collection": "facility",
        "doc_type": "vaccination_facility",
        "source": "질병관리청",
        "topic": "vaccination",
    },
    "data6_geocoded_childcare_facilities_final.json": {
        "collection": "facility",
        "doc_type": "childcare_facility",
        "source": "아이돌봄서비스",
        "topic": "childcare_service",
    },
}

AGE_GROUP_PATTERNS = [
    (re.compile(r"신생아|0\s*[~-]\s*1개월"), "0-6m"),
    (re.compile(r"1\s*[~-]\s*3개월|1~3개월"), "0-6m"),
    (re.compile(r"4\s*[~-]\s*6개월|4~6개월"), "0-6m"),
    (re.compile(r"7\s*[~-]\s*9개월|7~9개월"), "6-12m"),
    (re.compile(r"10\s*[~-]\s*12개월|10~12개월"), "6-12m"),
    (re.compile(r"13\s*[~-]\s*24개월|13~24개월"), "12-24m"),
    (re.compile(r"25\s*[~-]\s*36개월|25~36개월"), "24-36m"),
    (re.compile(r"37\s*[~-]\s*60개월|37~60개월"), "36-60m"),
    (re.compile(r"24개월"), "24-36m"),
    (re.compile(r"이른둥이"), "0-6m"),
]

TOPIC_PATTERNS = {
    "fever": [r"발열", r"\b열\b", r"38\.\d", r"체온"],
    "cough": [r"기침", r"콧물", r"가래"],
    "vomiting": [r"구토", r"토함", r"토해"],
    "diarrhea": [r"설사", r"묽은 변"],
    "constipation": [r"변비", r"배변"],
    "language": [r"언어", r"말", r"옹알", r"단어"],
    "play": [r"놀이", r"장난감", r"학습"],
    "social": [r"사회성", r"애착", r"관계", r"소통"],
    "growth": [r"성장", r"발달", r"신체적 성장", r"개월"],
    "sleep": [r"수면", r"잠", r"밤에", r"자주 깨", r"낮잠"],
    "food": [r"식사", r"이유식", r"수유", r"먹", r"젖병"],
    "crying": [r"울음", r"보채", r"떼쓰", r"칭얼"],
    "safety": [r"안전", r"예방", r"영아돌연사", r"사고"],
    "welfare": [r"지원", r"복지", r"수당", r"바우처", r"돌봄"],
    "schedule": [r"접종", r"접종시기", r"접종대상", r"예방접종"],
}


def make_chunk_id(text: str, metadata: dict) -> str:
    raw = text + "||" + str(sorted(metadata.items()))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def load_json_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"{path.name} must contain a JSON array.")

    return data


def infer_age_group(title: str, text: str) -> str:
    haystack = f"{title}\n{text}"
    for pattern, age_group in AGE_GROUP_PATTERNS:
        if pattern.search(haystack):
            return age_group
    return DEFAULT_AGE_GROUP


def infer_topic(text: str, fallback: str = "general") -> str:
    for topic, patterns in TOPIC_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            return topic
    return fallback


def infer_childcare_category(text: str, topic: str) -> str:
    if topic in {"language", "play", "social", "growth"}:
        return "development"
    if topic in {"sleep", "food", "crying", "safety"}:
        return "daily_parenting"
    if topic in {"fever", "cough", "vomiting", "diarrhea", "constipation"}:
        return "medical_basic"

    if re.search(r"성장|발달|언어|놀이|애착|소통", text):
        return "development"
    if re.search(r"수면|식사|이유식|울음|생활|루틴|안전", text):
        return "daily_parenting"
    if re.search(r"발열|기침|콧물|구토|설사|변비|진료", text):
        return "medical_basic"

    return "daily_parenting"


def normalize_category_and_topic(
    path: Path,
    title: str,
    text: str,
    base_category: str | None = None,
    base_topic: str | None = None,
) -> tuple[str, str]:
    if path.name == "data3_vaccine_final_knowledge_base.json":
        return "vaccination", base_topic or infer_topic(text, "schedule")

    if path.name == "data5_welfare_childcare_kb.json":
        return "policy", base_topic or "welfare"

    if path.name == "data7_childcare_auto_kb.json":
        topic = base_topic or infer_topic(f"{title}\n{text}", "general")
        return infer_childcare_category(f"{title}\n{text}", topic), topic

    if path.name in {
        "data1_cleaned_pediatrics_hospitals.json",
        "data2_geocoded_night_hospitals.json",
        "data4_geocoded_national_vaccine_hospitals_final.json",
        "data6_geocoded_childcare_facilities_final.json",
    }:
        return "hospital_locator", base_topic or "hospital"

    return base_category or "general", base_topic or infer_topic(f"{title}\n{text}", "general")


def normalize_source(path: Path, item: dict, fallback_source: str) -> str:
    metadata = item.get("metadata", {})
    return (
        metadata.get("source")
        or metadata.get("department")
        
        or fallback_source
    )


def flatten_metadata(metadata: dict) -> dict:
    flat = {}

    for key, value in metadata.items():
        if value is None:
            continue

        if key == "location" and isinstance(value, dict):
            coords = value.get("coordinates")
            if value.get("type"):
                flat["location_type"] = value["type"]
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                flat["longitude"] = float(coords[0])
                flat["latitude"] = float(coords[1])
            continue

        if isinstance(value, dict):
            nested = flatten_metadata({f"{key}_{sub_key}": sub_value for sub_key, sub_value in value.items()})
            flat.update(nested)
        elif isinstance(value, (list, tuple, set)):
            flat[key] = ", ".join(str(item) for item in value)
        elif isinstance(value, Path):
            flat[key] = str(value)
        elif isinstance(value, (str, int, float, bool)):
            flat[key] = value
        else:
            flat[key] = str(value)

    return flat


def build_base_metadata(path: Path, item: dict, config: dict) -> dict:
    title = str(item.get("title", "")).strip()
    content = str(item.get("content", "")).strip()
    original_metadata = item.get("metadata", {})

    category, topic = normalize_category_and_topic(
        path,
        title=title,
        text=content,
        base_category=config.get("category"),
        base_topic=config.get("topic"),
    )

    base_metadata = {
        "title": title or path.stem,
        "source": normalize_source(path, item, config["source"]),
        "doc_type": config["doc_type"],
        "data_type": item.get("data_type", "unknown"),
        "category": category,
        "topic": topic,
        "age_group": infer_age_group(title, content),
        "language": "ko",
        "source_file": path.name,
        "original_category": item.get("category", ""),
    }
    base_metadata.update(flatten_metadata(original_metadata))
    return base_metadata


def load_json_documents() -> tuple[list[Document], list[Document]]:
    knowledge_docs = []
    facility_docs = []

    for filename, config in JSON_DATASETS.items():
        path = DATA_DIR / filename
        if not path.exists():
            print(f"  ⚠ 파일 없음, 건너뜀: {filename}")
            continue

        records = load_json_records(path)
        before = len(knowledge_docs) + len(facility_docs)

        for item in records:
            content = str(item.get("content", "")).strip()
            if not content:
                continue

            metadata = build_base_metadata(path, item, config)
            document = Document(page_content=content, metadata=metadata)

            if config["collection"] == "knowledge":
                knowledge_docs.append(document)
            else:
                facility_docs.append(document)

        added = len(knowledge_docs) + len(facility_docs) - before
        tag = "knowledge" if config["collection"] == "knowledge" else "facility"
        print(f"  ✓ {filename}  →  {added}개 ({tag})")

    return knowledge_docs, facility_docs


def load_curated_documents() -> list[Document]:
    docs = []

    for item in CURATED_DOCS:
        docs.append(
            Document(
                page_content=item["content"],
                metadata={
                    "title": item["title"],
                    **item["metadata"],
                }
            )
        )

    return docs


def split_knowledge_documents(raw_docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    return splitter.split_documents(raw_docs)


def attach_chunk_metadata(documents: list[Document]) -> list[Document]:
    for index, doc in enumerate(documents):
        source_file = doc.metadata.get("source_file")
        if source_file in JSON_DATASETS:
            base_category = doc.metadata.get("category")
            base_topic = doc.metadata.get("topic")
            if source_file == "data7_childcare_auto_kb.json":
                base_category = None
                base_topic = None

            category, topic = normalize_category_and_topic(
                Path(source_file),
                title=doc.metadata.get("title", ""),
                text=doc.page_content,
                base_category=base_category,
                base_topic=base_topic,
            )
            doc.metadata["category"] = category
            doc.metadata["topic"] = topic
            doc.metadata["age_group"] = infer_age_group(
                doc.metadata.get("title", ""),
                doc.page_content,
            )

        doc.metadata = flatten_metadata(doc.metadata)
        doc.metadata["chunk_id"] = make_chunk_id(doc.page_content, doc.metadata)
        doc.metadata["chunk_index"] = index
    return documents


def dedupe_documents(documents: list[Document]) -> list[Document]:
    seen = set()
    deduped = []

    for doc in documents:
        cid = doc.metadata["chunk_id"]
        if cid not in seen:
            seen.add(cid)
            deduped.append(doc)

    return deduped


def prepare_documents() -> tuple[list[Document], list[Document]]:
    knowledge_docs, facility_docs = load_json_documents()
    curated_docs = load_curated_documents()

    split_knowledge = split_knowledge_documents(knowledge_docs)
    prepared_curated = attach_chunk_metadata(curated_docs)
    prepared_knowledge = attach_chunk_metadata(split_knowledge)
    prepared_facility = attach_chunk_metadata(facility_docs)

    deduped_knowledge = dedupe_documents(prepared_curated + prepared_knowledge)
    deduped_facility = dedupe_documents(prepared_facility)

    return deduped_knowledge, deduped_facility


def get_vectorstore(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL),
        persist_directory=str(PERSIST_DIR),
    )


def upsert_documents(collection_name: str, documents: list[Document]) -> None:
    if not documents:
        return

    vectorstore = get_vectorstore(collection_name)
    total_batches = (len(documents) + BATCH_SIZE - 1) // BATCH_SIZE

    with tqdm(
        total=len(documents),
        desc=f"  {collection_name}",
        unit="chunks",
        ncols=80,
    ) as bar:
        for start in range(0, len(documents), BATCH_SIZE):
            batch = documents[start:start + BATCH_SIZE]
            ids = [doc.metadata["chunk_id"] for doc in batch]
            vectorstore.add_documents(batch, ids=ids)
            bar.update(len(batch))


def write_manifest(knowledge_count: int, facility_count: int) -> None:
    manifest = {
        "embedding_model": EMBEDDING_MODEL,
        "ingested_at": datetime.now().isoformat(),
        "hyperparameters": {
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "batch_size": BATCH_SIZE,
        },
        "collections": {
            KNOWLEDGE_COLLECTION_NAME: {"doc_count": knowledge_count},
            FACILITY_COLLECTION_NAME: {"doc_count": facility_count},
        },
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"매니페스트 저장: {MANIFEST_PATH}")


def main():
    print("=" * 60)
    print("RAG 인제스트 시작")
    print(f"임베딩 모델: {EMBEDDING_MODEL}")
    print(f"저장 경로:   {PERSIST_DIR}")
    print("=" * 60)

    # Step 1: JSON 파일 로딩
    print("\n[1/5] JSON 파일 로딩...")
    knowledge_docs, facility_docs = load_json_documents()
    print(f"  → knowledge {len(knowledge_docs)}개 / facility {len(facility_docs)}개 로드 완료")

    if not knowledge_docs and not facility_docs:
        print("로드된 문서가 없습니다. data/ 경로를 확인하세요.")
        return

    # Step 2: 큐레이션 문서
    print("\n[2/5] 큐레이션 문서 로딩...")
    curated_docs = load_curated_documents()
    print(f"  → {len(curated_docs)}개")

    # Step 3: 청킹
    print(f"\n[3/5] knowledge 문서 청킹 (chunk_size=800, overlap=120)...")
    split_knowledge = split_knowledge_documents(knowledge_docs)
    print(f"  → {len(knowledge_docs)}개 → {len(split_knowledge)}개 청크")

    # Step 4: 메타데이터 부착 및 중복 제거
    print("\n[4/5] 메타데이터 처리 및 중복 제거...")
    prepared_curated  = attach_chunk_metadata(curated_docs)
    prepared_knowledge = attach_chunk_metadata(split_knowledge)
    prepared_facility  = attach_chunk_metadata(facility_docs)

    deduped_knowledge = dedupe_documents(prepared_curated + prepared_knowledge)
    deduped_facility  = dedupe_documents(prepared_facility)

    print(f"  → knowledge: {len(prepared_curated) + len(prepared_knowledge)}개 → 중복 제거 후 {len(deduped_knowledge)}개")
    print(f"  → facility:  {len(prepared_facility)}개 → 중복 제거 후 {len(deduped_facility)}개")

    # Step 5: ChromaDB 업로드
    print(f"\n[5/5] ChromaDB 업로드 (배치 크기: {BATCH_SIZE})...")
    upsert_documents(KNOWLEDGE_COLLECTION_NAME, deduped_knowledge)
    upsert_documents(FACILITY_COLLECTION_NAME,  deduped_facility)

    # 매니페스트
    write_manifest(len(deduped_knowledge), len(deduped_facility))

    print("\n" + "=" * 60)
    print("인제스트 완료")
    print(f"  knowledge collection : {len(deduped_knowledge):,}개 청크")
    print(f"  facility  collection : {len(deduped_facility):,}개 청크")
    print("=" * 60)


if __name__ == "__main__":
    main()
