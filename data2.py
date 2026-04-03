import requests
import xml.etree.ElementTree as ET
import json
import time

def fetch_night_pediatrics_data_without_coords():
    base_url = "https://apis.data.go.kr/B551182/spclMdlrtHospInfoService1/getChildNightMdlrtList1"
    service_key = "YOUR_API_KEY_HERE"
    
    integrated_data_list = []
    page = 1
    
    print("소아야간진료(달빛어린이병원) 데이터 수집 시작")
    
    while True:
        print(f"[{page}페이지] 데이터 요청 중...")
        
        params = {
            "ServiceKey": service_key,
            "pageNo": str(page),
            "numOfRows": "100" 
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code != 200:
            print(f"API 호출 실패: {response.status_code}")
            break
            
        root = ET.fromstring(response.text)
        result_code = root.find(".//resultCode")
        
        if result_code is None or result_code.text != "00":
            break

        items = root.findall(".//item")
        
        if not items:
            break
            
        for item in items:
            def get_val(tag):
                element = item.find(tag)
                return element.text if element is not None else ""
            
            # 1. 좌표 필터링 완전 제거
            # 2. RAG 검색용 텍스트 및 기본 메타데이터만 우선 저장
            cleaned_data = {
                "data_type": "facility_location",
                "category": "야간휴일소아과",
                "title": get_val("yadmNm"),
                "content": f"야간 및 휴일 진료가 가능한 {get_val('sidoCdNm')} {get_val('sgguCdNm')}의 소아과입니다. 주소는 {get_val('addr')}이며, 연락처는 {get_val('telno')}입니다.",
                "metadata": {
                    "hospital_type_code": get_val("clCd"),
                    "hospital_type_name": get_val("clCdNm"),
                    "sido": get_val("sidoCdNm"),
                    "sggu": get_val("sgguCdNm"),
                    "address": get_val("addr"),
                    "phone": get_val("telno"),
                    "ykiho": get_val("ykiho"), # 병원 고유 식별자 추가
                    "location": None # 좌표는 현재 없으므로 None 처리 (추후 업데이트)
                }
            }
            integrated_data_list.append(cleaned_data)
            
        page += 1
        time.sleep(1)

    save_path = "cleaned_night_pediatrics_hospitals.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(integrated_data_list, f, ensure_ascii=False, indent=4)
        
    print(f"\n총 {len(integrated_data_list)}건의 야간진료 병원 데이터가 {save_path}에 저장되었습니다.")

if __name__ == "__main__":
    fetch_night_pediatrics_data_without_coords()