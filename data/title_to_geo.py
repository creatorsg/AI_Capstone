import requests
import json
import time

def add_coordinates_to_data6(json_filepath, kakao_api_key):
    # 1. 좌표 없는 data6 파일 읽어오기
    try:
        with open(json_filepath, "r", encoding="utf-8") as f:
            facility_data = json.load(f)
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {json_filepath}")
        return

    # 키워드 검색 API 엔드포인트로 변경 (시설명 검색에 더 유리)
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    
    updated_data = []
    success_count = 0
    
    print(f"총 {len(facility_data)}건의 데이터에 대해 카카오 API 키워드 좌표 변환을 시작합니다.")

    for idx, facility in enumerate(facility_data):
        # city, district, title을 합쳐서 검색 쿼리 생성
        city = facility["metadata"].get("city", "")
        district = facility["metadata"].get("district", "")
        title = facility.get("title", "")
        
        # 검색어 예: "서울 강남구 강남구가족센터"
        search_query = f"{city} {district} {title}".strip()
        
        params = {"query": search_query}
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                if result["documents"]:
                    # 가장 검색 결과가 높은 첫 번째 항목의 좌표 추출
                    lon = float(result["documents"][0]["x"])
                    lat = float(result["documents"][0]["y"])
                    
                    facility["metadata"]["location"] = {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                    success_count += 1
                else:
                    print(f"[{idx+1}] 좌표 변환 실패 (검색 결과 없음): {search_query}")
            else:
                print(f"[{idx+1}] 카카오 API 호출 에러: 상태 코드 {response.status_code}")
        except Exception as e:
            print(f"[{idx+1}] 예상치 못한 에러 발생: {str(e)}")
            
        updated_data.append(facility)
        
        # API 과부하 방지를 위한 미세한 지연
        time.sleep(0.1) 

    # 2. 결과 저장
    save_path = "data6_geocoded_childcare_facilities_final.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=4)
        
    print(f"작업 완료: 총 {success_count}건 좌표 변환 성공. 결과가 {save_path}에 저장되었습니다.")

if __name__ == "__main__":
    target_file = "data6_childcare_facilities.json"
    # 본인의 카카오 API 키를 입력하세요.
    my_kakao_key = "YOUR_API_KEY_HERE" 
    
    add_coordinates_to_data6(target_file, my_kakao_key)