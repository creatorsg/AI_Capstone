"""응급 상황 키워드 온톨로지 (응급 감지용)"""

# 응급 유형 분류 (응급 감지 및 향후 유형별 대응용)
EMERGENCY_ONTOLOGY: dict[str, list[str]] = {
    "RESPIRATORY_EMERGENCY": [
        "숨", "호흡", "헐떡", "청색증", "입술이 파래", "쌕쌕", "질식", "안 쉬어",
        "숨을 안 쉬어", "숨 안 쉼",
    ],
    "NEUROLOGICAL_EMERGENCY": [
        "경련", "발작", "눈이 돌아", "거품", "의식", "안 깨어", "축 쳐져", "불러도",
        "의식불명", "의식 없음", "온몸이 뻣뻣",
    ],
    "SEVERE_TRAUMA": [
        "피가 안 멈춰", "머리에서 피", "의식 잃", "높은 곳에서 떨어",
    ],
    "HIGH_FEVER": [
        "40도 이상", "41도", "42도",
    ],
    "GENERAL_EMERGENCY": [
        "응급",
    ],
}

# 전체 키워드 (check_emergency() 에서 사용)
ALL_EMERGENCY_KEYWORDS: list[str] = [
    kw for keywords in EMERGENCY_ONTOLOGY.values() for kw in keywords
]
