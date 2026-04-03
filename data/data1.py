import requests
import xml.etree.ElementTree as ET
import json
import time

def fetch_and_clean_pediatrics_data():
    base_url = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"

    service_key = "YOUR_API_KEY_HERE"
    
    integrated_data_list = []
    page = 1
    total_count = 0
    
    while True:
        print(f"[{page}페이지] 데이터 수집 및 전처리 중...")
        
        params = {
            "ServiceKey": service_key,
            "pageNo": str(page),
            "numOfRows": "1000",  # 한 번에 최대한 많이 가져오도록 설정
            "dgsbjtCd": "11"      #  소아청소년과 코드
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code != 200:
            print(f"API 호출 에러: {response.status_code}")
            break
            
        root = ET.fromstring(response.text)
        result_code = root.find(".//resultCode")
        
        if result_code is None or result_code.text != "00":
            print("데이터 응답 오류 또는 마지막 페이지 도달")
            break
            
        # 첫 페이지에서 총 건수 파악
        if page == 1:
            tc_element = root.find(".//totalCount")
            if tc_element is not None:
                total_count = int(tc_element.text)
                print(f"총 수집 대상 병원 수: {total_count}건")

        items = root.findall(".//item")
        
        # 더 이상 가져올 아이템이 없으면 루프 종료
        if not items:
            break
            
        for item in items:
            def get_val(tag):
                element = item.find(tag)
                return element.text if element is not None else ""
            
            lon = get_val("XPos")
            lat = get_val("YPos")
            
            # 전처리 1: XPos, YPos 좌표값이 없는 데이터는 지도 표시 및 거리 계산이 불가능하므로 제거 (나중 gps연동해서 병원 위치 띄어주기용)
            if not lon or not lat:
                continue
                
            # 전처리 2: RAG DB 및 MongoDB 저장을 위한 구조화
            # 추후 문서, 텍스트 데이터와 합칠 때 title, content를 공통 검색 대상으로 사용
            cleaned_data = {
                "data_type": "facility_location",
                "category": "소아청소년과",
                "title": get_val("yadmNm"),
                "content": f"{get_val('sidoCdNm')} {get_val('sgguCdNm')}에 위치한 {get_val('clCdNm')}입니다. 주소는 {get_val('addr')}이며, 연락처는 {get_val('telno')}입니다.",
                "metadata": {
                    "hospital_type_code": get_val("clCd"),
                    "hospital_type_name": get_val("clCdNm"),
                    "sido": get_val("sidoCdNm"),
                    "sggu": get_val("sgguCdNm"),
                    "address": get_val("addr"),
                    "phone": get_val("telno"),
                    "homepage": get_val("hospUrl"),
                    "location": {
                        "type": "Point",
                        "coordinates": [float(lon), float(lat)]
                    }
                }
            }
            integrated_data_list.append(cleaned_data)
            
        page += 1
        time.sleep(1) # 공공데이터 api 서버 트래픽 제한 방지

    # 최종 전처리된 데이터를 JSON 파일로 저장
    save_path = "cleaned_pediatrics_hospitals.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(integrated_data_list, f, ensure_ascii=False, indent=4)
        
    print(f"\n작업 완료. 총 {len(integrated_data_list)}건의 유효한 데이터가 {save_path}에 저장되었습니다.")

if __name__ == "__main__":
    fetch_and_clean_pediatrics_data()