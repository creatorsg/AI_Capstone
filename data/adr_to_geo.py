import requests
import json
import time

def add_coordinates_to_json(json_filepath, kakao_api_key):
    # 1. 앞서 수집한 좌표 없는 JSON 파일 읽어오기
    try:
        with open(json_filepath, "r", encoding="utf-8") as f:
            hospital_data = json.load(f)
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {json_filepath}")
        return

    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    
    updated_data = []
    success_count = 0
    
    print(f"총 {len(hospital_data)}건의 데이터에 대해 카카오 API 좌표 변환을 시작합니다.")

    for idx, hosp in enumerate(hospital_data):
        address = hosp["metadata"]["address"]
        
        # 주소 정제: "(영등포동4가)" 같은 괄호 부분이나 상세 주소가 포함되면 카카오 API 검색 실패율이 높아지므로 쉼표 기준으로 자름
        clean_address = address.split(",")[0] if "," in address else address
        
        params = {"query": clean_address}
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            result = response.json()
            if result["documents"]:
                # 카카오 API는 x를 경도(lon), y를 위도(lat)로 반환함
                lon = float(result["documents"][0]["x"])
                lat = float(result["documents"][0]["y"])
                
                # MongoDB GeoJSON 스키마에 맞게 업데이트
                hosp["metadata"]["location"] = {
                    "type": "Point",
                    "coordinates": [lon, lat]
                }
                success_count += 1
            else:
                print(f"[{idx+1}] 좌표 변환 실패 (검색 결과 없음): {clean_address}")
        else:
            print(f"[{idx+1}] 카카오 API 호출 에러: 상태 코드 {response.status_code}")
            
        updated_data.append(hosp)
        
        time.sleep(0.1) 

    # 2. 좌표가 추가된 완성본 데이터를 새로운 파일로 저장
    save_path = "data4_geocoded_national_vaccine_hospitals_final.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=4)
        
    print(f"작업 완료: 총 {success_count}건 좌표 변환 성공. 결과가 {save_path}에 저장되었습니다.")

if __name__ == "__main__":
    target_file = "data4_national_vaccine_hospitals_final.json"
    my_kakao_key = "YOUR_REGISTERED_API_KEY_HERE" 
    
    add_coordinates_to_json(target_file, my_kakao_key)