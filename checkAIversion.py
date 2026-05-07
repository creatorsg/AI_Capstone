# 개발용 테스트 스크립트 (Gemini API 모델 확인)
# 사용: GEMINI_API_KEY=<your-key> python checkAIversion.py

import os
import google.generativeai as genai

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

genai.configure(api_key=api_key)
for m in genai.list_models():
    print(m.name)
