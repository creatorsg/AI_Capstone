from fastapi import FastAPI
from sqlalchemy import create_engine, text
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from database import engine
import database
import models

models.Base.metadata.create_all(bind=engine)
app = FastAPI()

DB_URL = "postgresql://myuser:mypassword@localhost:5432/kids_app"
engine = create_engine(DB_URL)

@app.get("/")
def read_root():
    return {"status": "FastAPI is Running!"}

@app.get("/db-check")
def check_db():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            return {"db_status": "Connected!", "version": result.fetchone()[0]}
    except Exception as e:
        return {"db_status": "Error", "message": str(e)}

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/chat/")
def chat_with_ai(child_id: int, question: str):
    
    return {
        "child_id": child_id,
        "question": question,
        "answer": "안녕하세요! 아이의 데이터를 분석하여 답변을 준비 중입니다. (임시 응답)",
        "status": "success"
    }


@app.post("/children/")
def create_child(name: str, gender: str, birth_date: date, db: Session = Depends(get_db)):
    new_child = models.Child(name=name, gender=gender, birth_date=birth_date)
    db.add(new_child)
    db.commit()
    db.refresh(new_child)
    return {"message": "아이 정보가 성공적으로 등록되었습니다!", "data": new_child}

@app.get("/children/")
def get_children(db: Session = Depends(get_db)):
    children = db.query(models.Child).all()
    return children