# app/ingest.py

import json
import hashlib
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from curated_docs import CURATED_DOCS
from vector_config import (
    DATA_DIR,
    FACILITY_COLLECTION_NAME,
    KNOWLEDGE_COLLECTION_NAME,
    PERSIST_DIR,
)

load_dotenv()

BATCH_SIZE = 500
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
            continue

        for item in load_json_records(path):
            content = str(item.get("content", "")).strip()
            if not content:
                continue

            metadata = build_base_metadata(path, item, config)
            document = Document(page_content=content, metadata=metadata)

            if config["collection"] == "knowledge":
                knowledge_docs.append(document)
            else:
                facility_docs.append(document)

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


def split_raw_documents(raw_docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
    )

    split_docs = splitter.split_documents(raw_docs)

    for i, doc in enumerate(split_docs):
        doc.metadata["chunk_id"] = make_chunk_id(doc.page_content, doc.metadata)
        doc.metadata["chunk_index"] = i

    return split_docs


def prepare_documents() -> list[Document]:
    raw_docs = load_raw_documents()
    curated_docs = load_curated_documents()

    split_raw = split_raw_documents(raw_docs)

    for doc in curated_docs:
        doc.metadata["chunk_id"] = make_chunk_id(doc.page_content, doc.metadata)
        doc.metadata["chunk_index"] = 0

    all_docs = curated_docs + split_raw

    # 단순 중복 제거
    seen = set()
    deduped = []
    for doc in all_docs:
        cid = doc.metadata["chunk_id"]
        if cid not in seen:
            seen.add(cid)
            deduped.append(doc)

    return deduped


def main():
    documents = prepare_documents()

    if not documents:
        print("No documents found.")
        return

    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR,
    )

    # 재실행 시 중복 적재를 피하려면 reset_collection 고려 가능
    vectorstore.add_documents(documents)

    print(f"Ingested {len(documents)} documents/chunks into {PERSIST_DIR}")
    return docs


def split_knowledge_documents(raw_docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
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
        embedding_function=OpenAIEmbeddings(),
        persist_directory=str(PERSIST_DIR),
    )


def upsert_documents(collection_name: str, documents: list[Document]) -> None:
    if not documents:
        return

    vectorstore = get_vectorstore(collection_name)

    for start in range(0, len(documents), BATCH_SIZE):
        batch = documents[start:start + BATCH_SIZE]
        ids = [doc.metadata["chunk_id"] for doc in batch]
        vectorstore.add_documents(batch, ids=ids)


def main():
    knowledge_docs, facility_docs = prepare_documents()

    if not knowledge_docs and not facility_docs:
        print("No documents found.")
        return

    upsert_documents(KNOWLEDGE_COLLECTION_NAME, knowledge_docs)
    upsert_documents(FACILITY_COLLECTION_NAME, facility_docs)

    print(
        f"Ingested {len(knowledge_docs)} knowledge docs into {KNOWLEDGE_COLLECTION_NAME} "
        f"and {len(facility_docs)} facility docs into {FACILITY_COLLECTION_NAME} "
        f"at {PERSIST_DIR}"
    )


if __name__ == "__main__":
    main()