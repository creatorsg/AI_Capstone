import prompts
if risk_level == "high":
    emergency_prefix = (
        "현재 설명만으로는 응급 가능성을 배제할 수 없습니다. "
        "즉시 소아과 또는 응급실 진료를 우선적으로 고려하세요.\n\n"
    )