from pathlib import Path
import os

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv()

DATA_DIR = Path(dataraw)
PERSIST_DIR = chroma_db
COLLECTION_NAME = demo_docs


def load_documents()
    docs = []

    for path in DATA_DIR.glob()
        if path.suffix.lower() == .pdf
            loader = PyPDFLoader(str(path))
            docs.extend(loader.load())
        elif path.suffix.lower() in [.txt, .md]
            loader = TextLoader(str(path), encoding=utf-8)
            docs.extend(loader.load())

    return docs


def load_curated_cards():
    cards = [
        {
            "content": "24개월 아이는 두 단어 문장을 시도할 수 있습니다...",
            "metadata": {
                "category": "development",
                "topic": "language",
                "age_group": "24-36m",
                "source": "curated"
            }
        },
        {
            "content": "아이에게 열이 있을 때는 체온, 지속 시간, 처짐 여부를 확인하세요...",
            "metadata": {
                "category": "medical_basic",
                "topic": "fever",
                "age_group": "all",
                "source": "curated"
            }
        },
    ]
    return cards


def main()
    documents = load_documents()
    if not documents
        print(No documents found in dataraw)
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )
    splits = splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR,
    )

    vectorstore.add_documents(splits)
    print(fIngested {len(splits)} chunks into {PERSIST_DIR})


if __name__ == __main__
    main()