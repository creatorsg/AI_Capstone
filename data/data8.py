import requests
import json
import xml.etree.ElementTree as ET
import time

def fetch_all_pharmacies(service_key):
    url = "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyFullDown"
    all_pharmacies = []
    page = 1
    rows_per_page = 1000 # 한 번에 가져올 최대량

    print("전국 약국 전수 수집 및 운영시간 데이터 생성을 시작합니다...")

    while True:
        params = {
            'serviceKey': service_key,
            'pageNo': str(page),
            'numOfRows': str(rows_per_page)
        }

        try:
            response = requests.get(url, params=params)
            root = ET.fromstring(response.content)
            items = root.findall('.//item')

            if not items: # 더 이상 가져올 데이터가 없으면 중단
                break

            for item in items:
                try:
                    title = item.findtext('dutyName')
                    address = item.findtext('dutyAddr')

                    # 운영시간 텍스트 생성 로직
                    days = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
                    day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "holiday"]
                    hours_list = []
                    hours_structured = {}
                    is_night = False

                    for i, (day, key) in enumerate(zip(days, day_keys), 1):
                        start = item.findtext(f'dutyTime{i}s')
                        end = item.findtext(f'dutyTime{i}c')
                        if start and end:
                            f_start = f"{start[:2]}:{start[2:]}"
                            f_end = f"{end[:2]}:{end[2:]}"
                            hours_list.append(f"{day}요일({f_start}~{f_end})")
                            hours_structured[key] = {"start": int(start), "end": int(end)}

                            if int(end) > 2200:
                                is_night = True

                    hours_text = ", ".join(hours_list) if hours_list else "정보 없음"
                    category = "공공심야약국" if is_night else "약국"

                    lon = item.findtext('wgs84Lon')
                    lat = item.findtext('wgs84Lat')
                    location = {
                        "type": "Point",
                        "coordinates": [float(lon), float(lat)]
                    } if lon and lat else None

                    entry = {
                        "data_type": "facility_location",
                        "category": category,
                        "title": title,
                        "content": f"{title}은(는) {category}입니다. 운영시간: {hours_text}. 주소: {address}.",
                        "metadata": {
                            "address": address,
                            "phone": item.findtext('dutyTel1'),
                            "hpid": item.findtext('hpid'),
                            "operating_hours": hours_text,
                            "hours_structured": hours_structured,
                            "location": location
                        }
                    }
                    all_pharmacies.append(entry)
                except Exception as e:
                    print(f"항목 스킵 (hpid={item.findtext('hpid')}): {e}")
                    continue

            print(f"현재 {page}페이지 수집 완료... (누적 {len(all_pharmacies)}건)")
            page += 1
            time.sleep(0.1) # 서버 과부하 방지

        except Exception as e:
            print(f"페이지 {page} 에러: {e}")
            break

    # 결과 저장
    save_path = "data8_national_pharmacies_full.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(all_pharmacies, f, ensure_ascii=False, indent=4)
    
    print(f"총 {len(all_pharmacies)}건 수집 완료! {save_path}에 저장되었습니다.")

if __name__ == "__main__":
    HIRA_KEY = "YOUR_API_KEY_HERE"
    fetch_all_pharmacies(HIRA_KEY)