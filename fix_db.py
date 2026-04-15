"""DB 컬럼 누락 수정 스크립트 - 한 번만 실행하면 됩니다."""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

db_url = os.getenv("MY_APP_DATABASE_URL", "postgresql://myuser:yourpassword_here@localhost:5432/kids_app")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

sqls = [
    "ALTER TABLE children ADD COLUMN IF NOT EXISTS allergies  JSON NOT NULL DEFAULT '[]'::json",
    "ALTER TABLE children ADD COLUMN IF NOT EXISTS conditions JSON NOT NULL DEFAULT '[]'::json",
    "ALTER TABLE children ADD COLUMN IF NOT EXISTS notes      TEXT DEFAULT ''",
    "ALTER TABLE children ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now()",
]

for sql in sqls:
    cur.execute(sql)
    print("OK:", sql[:60])

conn.commit()
cur.close()
conn.close()
print("\n완료! fix_db.py 는 삭제해도 됩니다.")
