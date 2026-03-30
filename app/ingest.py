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