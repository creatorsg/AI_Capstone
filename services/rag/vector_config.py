"""ChromaDB 벡터 저장소 설정

원본: juhyeong 브랜치 app/vector_config.py
수정: ROOT_DIR 경로를 fount-project 루트로 조정 (.parent 한 단계 추가)
"""
from pathlib import Path

# services/rag/vector_config.py → services/rag/ → services/ → fount-project/
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
PERSIST_DIR = ROOT_DIR / "chroma_db"

KNOWLEDGE_COLLECTION_NAME = "parenting_knowledge"
FACILITY_COLLECTION_NAME = "parenting_facility"
