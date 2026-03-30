from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate

load_dotenv()

PERSIST_DIR = "chroma_db"
COLLECTION_NAME = "demo_docs"

PROMPT = ChatPromptTemplate.from_template(
    """You are a helpful assistant.
Use only the context below to answer the question.
If the answer is not in the context, say you don't know.

Context:
{context}

Question:
{question}
"""
)


def get_retriever():
    embeddings = OpenAIEmbeddings()
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR,
    )
    return vectorstore.as_retriever(search_kwargs={"k": 4})


def answer_question(question: str):
    retriever = get_retriever()
    docs = retriever.invoke(question)

    context = "\n\n".join([doc.page_content for doc in docs])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = PROMPT.format(context=context, question=question)
    response = llm.invoke(prompt)

    return response.content, docs