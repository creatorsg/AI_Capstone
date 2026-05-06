# app/curated_docs.py

'''
curated_docs.py는 현재 사용 중입니다. metadata.py랑 다르게 그냥 삭제하면 app/ingest.py가 바로 깨질 가능성이 큽니다.

확인된 흐름은 이렇습니다.


app/ingest.py (line 14)
에서 from curated_docs import CURATED_DOCS로 import함

app/ingest.py (line 275)
의 load_curated_documents()가 CURATED_DOCS를 LangChain Document로 변환함

app/ingest.py (line 346)
에서 실제 적재 준비에 포함됨

app/ingest.py (line 353)
에서 prepared_curated + prepared_knowledge로 실제 지식 문서에 합쳐짐
결론: 파일만 삭제하면 안 됩니다.
가짜 데이터셋을 이제 제거하려면 ingest.py에서 curated_docs import, load_curated_documents(), prepared_curated, prepared_curated + prepared_knowledge 부분을 같이 정리해야 합니다.

그리고 한 가지 더 중요합니다: 이미 python app/ingest.py를 돌린 적이 있다면, 이 fake docs가 chroma_db 안에 이미 들어가 있을 수 있어요. 코드에서 제거해도 기존 벡터DB에서는 자동으로 사라지지 않아서, 검색 결과에서 완전히 빼려면 Chroma DB를 비우고 다시 ingest 하는 쪽이 깔끔합니다.
'''


CURATED_DOCS = [
    {
        "title": "24개월 언어 발달",
        "content": (
            "24개월 무렵 아이는 의미 있는 단어를 점점 더 사용하고, "
            "두 단어를 이어 말하려는 시도를 보일 수 있습니다. "
            "보호자는 짧고 쉬운 문장으로 자주 말 걸기, 그림책을 함께 보기, "
            "아이의 말과 행동을 따라 말로 확장해주기 등을 해볼 수 있습니다. "
            "의미 있는 단어가 거의 없거나, 이름을 불러도 반응이 매우 적거나, "
            "이전에 하던 표현이 줄어드는 경우에는 전문가 상담을 고려해야 합니다."
        ),
        "metadata": {
            "doc_type": "development_card",
            "category": "development",
            "topic": "language",
            "age_group": "24-36m",
            "source": "curated",
            "language": "ko",
        },
    },
    {
        "title": "발열 시 기본 관찰 포인트",
        "content": (
            "아이가 열이 날 때는 체온 수치뿐 아니라 아이의 전반적인 상태를 함께 보는 것이 중요합니다. "
            "열이 언제부터 시작되었는지, 기침/콧물/구토/설사 같은 동반 증상이 있는지, "
            "물을 마시는지, 축 처져 있는지, 호흡이 힘들어 보이는지 등을 확인해야 합니다. "
            "경련, 의식 저하, 호흡 곤란, 반복 구토, 심한 처짐이 있으면 즉시 진료가 필요합니다."
        ),
        "metadata": {
            "doc_type": "symptom_card",
            "category": "medical_basic",
            "topic": "fever",
            "age_group": "0-60m",
            "source": "curated",
            "language": "ko",
        },
    },
    {
        "title": "밤에 자주 깨는 경우 확인할 점",
        "content": (
            "영유아가 밤에 자주 깨는 경우 수면 루틴, 낮잠 패턴, 수면 환경, 최근 컨디션 변화를 함께 살펴보는 것이 좋습니다. "
            "취침 시간이 너무 늦지 않은지, 낮잠이 너무 길거나 짧지 않은지, 자기 전 자극적인 활동이 많지 않은지 확인해볼 수 있습니다. "
            "발열이나 통증, 코막힘 같은 몸 상태 문제도 밤중 각성을 늘릴 수 있습니다."
        ),
        "metadata": {
            "doc_type": "daily_parenting_card",
            "category": "daily_parenting",
            "topic": "sleep",
            "age_group": "0-60m",
            "source": "curated",
            "language": "ko",
        },
    },
    {
        "title": "예방접종 질문 안내",
        "content": (
            "예방접종 관련 질문에서는 아이의 현재 연령, 이전 접종 이력, 최근 건강 상태를 함께 확인하는 것이 중요합니다. "
            "예방접종 일정은 국가 예방접종 지침을 기준으로 확인해야 하며, 접종 지연이나 누락 여부는 실제 기록을 바탕으로 판단해야 합니다."
        ),
        "metadata": {
            "doc_type": "vaccination_card",
            "category": "vaccination",
            "topic": "schedule",
            "age_group": "0-60m",
            "source": "curated",
            "language": "ko",
        },
    },
    {
        "title": "정부 지원 및 복지 정보 안내",
        "content": (
            "영유아 부모를 위한 정부 지원과 복지 제도는 아이의 연령, 거주 지역, 가구 상황에 따라 다를 수 있습니다. "
            "보육료 지원, 양육수당, 발달 관련 지원 서비스, 예방접종 지원 등은 최신 공공기관 정보를 확인해야 합니다."
        ),
        "metadata": {
            "doc_type": "policy_card",
            "category": "policy",
            "topic": "welfare",
            "age_group": "0-60m",
            "source": "curated",
            "language": "ko",
        },
    },
]