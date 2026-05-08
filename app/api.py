"""FastAPI demo server for the parenting RAG chatbot."""

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from rag import answer_question  # noqa: E402

app = FastAPI(title="육아 RAG 챗봇 API", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"


class ChildProfile(BaseModel):
    name: str | None = None
    birth_date: str | None = None
    sex: str | None = None
    allergies: list[str] = []
    conditions: list[str] = []
    notes: str | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    child_profile: ChildProfile | None = None
    chat_history: list[ChatMessage] = []


class RetrievedDoc(BaseModel):
    content: str
    metadata: dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    debug_info: dict[str, Any]
    retrieved_docs: list[RetrievedDoc]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    profile = req.child_profile.model_dump() if req.child_profile else None
    history = [m.model_dump() for m in req.chat_history]

    try:
        answer, docs, debug_info = answer_question(
            question=req.question,
            child_profile=profile,
            chat_history=history,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    serialized = [
        RetrievedDoc(
            content=doc.page_content[:300],
            metadata={
                k: v
                for k, v in doc.metadata.items()
                if isinstance(v, str | int | float | bool | None)
            },
        )
        for doc in docs[:5]
    ]

    return ChatResponse(answer=answer, debug_info=debug_info, retrieved_docs=serialized)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
