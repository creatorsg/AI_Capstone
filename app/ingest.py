from pathlib import Path
import hashlib

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from curated_docs import CURATED_DOCS

load_dotenv()

DATA_DIR = Path("data_test/raw")
PERSIST_DIR = "chroma_db"
COLLECTION_NAME = "parenting_docs"


def make_chunk_id(text: str, metadata: dict) -> str:
    raw = text + "||" + str(sorted(metadata.items()))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def infer_category_from_path(path: Path) -> tuple[str, str]:
    """
    파일명/경로 기반의 매우 단순한 category/topic 추론.
    추후에는 수동 매핑 테이블로 고도화 가능.
    """
    name = path.stem.lower()

    if "vaccine" in name or "vaccination" in name:
        return "vaccination", "schedule"
    if "fever" in name or "illness" in name or "symptom" in name:
        return "medical_basic", "fever"
    if "sleep" in name:
        return "daily_parenting", "sleep"
    if "food" in name or "meal" in name:
        return "daily_parenting", "food"
    if "development" in name or "language" in name or "play" in name:
        return "development", "general"

    return "general", "general"


def load_raw_documents() -> list[Document]:
    docs = []

    for path in DATA_DIR.glob("**/*"):
        if path.is_dir():
            continue

        if path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(path))
            loaded = loader.load()
        elif path.suffix.lower() in [".txt", ".md"]:
            loader = TextLoader(str(path), encoding="utf-8")
            loaded = loader.load()
        else:
            continue

        category, topic = infer_category_from_path(path)

        for doc in loaded:
            doc.metadata.update({
                "source": str(path),
                "doc_type": "raw_doc",
                "category": category,
                "topic": topic,
                "age_group": "0-60m",
                "language": "ko",
                "title": path.stem,
            })
            docs.append(doc)

    return docs


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


if __name__ == "__main__":
    main()