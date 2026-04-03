import pandas as pd
import json

def process_targeted_welfare_services():
    print("[1/2] 육아/아동 타겟 복지서비스 정보 변환 시작...")
    
    file_name = "한국사회보장정보원_복지서비스정보_20250722.csv"
    try:
        df_welfare = pd.read_csv(file_name, encoding='cp949')
    except:
        df_welfare = pd.read_csv(file_name, encoding='utf-8')
    
    df_welfare = df_welfare.fillna("정보 없음")
    
    # 1. 육아, 아동과 관련된 핵심 키워드 리스트 설정
    target_keywords = ['아동', '영유아', '보육', '육아', '어린이', '임신', '출산', '부모', '가족', '돌봄', '다자녀', '한부모', '청소년', '아이', '난임', '보육료', '양육비']
    
    # 2. 키워드를 OR 조건(|)으로 묶어서 정규표현식 패턴 생성
    pattern = '|'.join(target_keywords)
    
    # 3. '서비스명'이나 '서비스요약'에 키워드가 하나라도 포함된 데이터만 필터링
    # str.contains를 사용하여 패턴 매칭 (na=False는 빈값 무시)
    mask = df_welfare['서비스명'].str.contains(pattern, na=False) | df_welfare['서비스요약'].str.contains(pattern, na=False)
    
    # 필터링된 데이터프레임 생성
    filtered_df = df_welfare[mask]
    
    welfare_json_list = []
    for _, row in filtered_df.iterrows():
        title = row['서비스명']
        summary = row['서비스요약']
        dept = row['소관부처명']
        contact = row['대표문의']
        url = row['서비스URL']
        
        content_text = f"{title}은(는) {dept}에서 주관하는 서비스입니다. {summary} 관련 문의는 {contact}로 하시면 되며, 상세 내용은 {url}에서 확인할 수 있습니다."
        
        welfare_json_list.append({
            "data_type": "knowledge_base",
            "category": "복지서비스",
            "title": title,
            "content": content_text,
            "metadata": {
                "service_id": row['서비스아이디'],
                "department": dept,
                "contact": contact,
                "url": url
            }
        })
        
    with open("welfare_childcare_kb.json", "w", encoding="utf-8") as f:
        json.dump(welfare_json_list, f, ensure_ascii=False, indent=4)
        
    print(f"  -> 원본 {len(df_welfare)}건 중 육아/아동 관련 데이터 {len(welfare_json_list)}건 필터링 및 변환 완료! (welfare_childcare_kb.json)")

def process_childcare_facilities():
    print("\n[2/2] 아이돌봄서비스 제공기관 변환 시작...")
    
    file_name = "성평등가족부_아이돌봄서비스제공기관_20250630.csv"
    try:
        df_care = pd.read_csv(file_name, encoding='cp949')
    except:
        df_care = pd.read_csv(file_name, encoding='utf-8')
    
    df_care = df_care.fillna("정보 없음")
    
    care_json_list = []
    for _, row in df_care.iterrows():
        center_name = row['센터명']
        city = row['시도']
        district = row['시군구']
        phone = row['대표번호']
        fax = row['팩스번호']
        
        content_text = f"{center_name}은(는) {city} {district} 지역의 아이돌봄서비스 제공기관입니다. 연락처는 {phone}입니다."
        
        care_json_list.append({
            "data_type": "facility_location",
            "category": "아이돌봄서비스",
            "title": center_name,
            "content": content_text,
            "metadata": {
                "city": city,
                "district": district,
                "phone": phone,
                "fax": fax
            }
        })
        
    with open("childcare_facilities.json", "w", encoding="utf-8") as f:
        json.dump(care_json_list, f, ensure_ascii=False, indent=4)
    print(f"  -> 아이돌봄 센터 {len(care_json_list)}건 변환 완료! (childcare_facilities.json)")

if __name__ == "__main__":
    process_targeted_welfare_services()
    process_childcare_facilities()
    print("\n모든 작업이 완료되었습니다.")