from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PERSIST_DIR = ROOT_DIR / "chroma_db"

KNOWLEDGE_COLLECTION_NAME = "parenting_knowledge"
FACILITY_COLLECTION_NAME = "parenting_facility"

# 임베딩 모델을 바꿀 때는 여기만 수정하세요.
# ingest.py 재실행 후 chroma_db를 통째로 삭제하고 다시 만들어야 합니다.
EMBEDDING_MODEL = "text-embedding-3-large"

MANIFEST_PATH = PERSIST_DIR / "ingest_manifest.json"
