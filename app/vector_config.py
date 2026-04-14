from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PERSIST_DIR = ROOT_DIR / "chroma_db"

KNOWLEDGE_COLLECTION_NAME = "parenting_knowledge"
FACILITY_COLLECTION_NAME = "parenting_facility"
