import requests
import xml.etree.ElementTree as ET
import json
import time

def get_hospitals_pagination_master():
    service_key = 'YOUR_API_KEY_HERE'
    base_url = 'http://apis.data.go.kr/1790387/orglist3/'
    
    print("[1/3] 전국 시도 목록 조회 시작...")
    res = requests.get(f"{base_url}getCondBrtcCd3", params={'serviceKey': service_key})
    sido_items = ET.fromstring(res.content).findall('.//item')
    
    sido_list = []
    for item in sido_items:
        c = item.findtext('cd')
        n = item.findtext('cdNm')
        if c: sido_list.append({'full_code': c, 'short_code': c[:2], 'name': n})

    all_hospitals = []

    print("[2/3] 전국 시군구 순회 및 병원 데이터 추출 시작 (100개씩 쪼개서 수집)")
    for sido in sido_list:
        print(f"\n▶ {sido['name']} 탐색 중...")
        
        # SGG(시군구) 목록은 10자리(full_code)로 요청
        res = requests.get(f"{base_url}getCondSggCd3", params={'serviceKey': service_key, 'brtcCd': sido['full_code']})
        sgg_items = ET.fromstring(res.content).findall('.//item')
        
        for sgg in sgg_items:
            sgg_full_cd = sgg.findtext('cd') 
            sgg_nm = sgg.findtext('cdNm')
            if not sgg_full_cd: continue
            
            sgg_hospital_count = 0
            page_no = 1
            
            while True:
                params = {
                    'serviceKey': service_key,
                    'pageNo': str(page_no),
                    'numOfRows': '100', # 서버의 한계인 100으로 고정
                    'brtcCd': sido['short_code'], # 앞 2자리 (11)
                    'sggCd': sgg_full_cd[:5]      # 앞 5자리 (11680)
                }
                
                try:
                    res_org = requests.get(f"{base_url}getOrgList3", params=params)
                    root = ET.fromstring(res_org.content)
                    items = root.findall('.//item')
                    
                    if not items:
                        break
                        
                    for item in items:
                        h_name = item.findtext('orgnm') or item.findtext('orgNm') or "이름없음"
                        h_addr = item.findtext('orgAddr') or "주소없음"
                        h_tel = item.findtext('orgTlno') or "전화번호없음"
                        
                        vcn_names = [v.text for v in item.findall('.//vcnNm') if v.text]
                        v_list_str = ", ".join(vcn_names)

                        all_hospitals.append({
                            "data_type": "facility_location",
                            "category": "어린이예방접종지정",
                            "title": h_name,
                            "content": f"{h_name}은(는) 국가예방접종 지정 의료기관입니다. 주소: {h_addr}, 전화: {h_tel}. 접종 가능 백신: {v_list_str}",
                            "metadata": {
                                "address": h_addr,
                                "phone": h_tel,
                                "target_vaccines": v_list_str,
                                "city": sido['name'],
                                "district": sgg_nm
                            }
                        })
                    
                    sgg_hospital_count += len(items)
                    page_no += 1
                    time.sleep(0.05)
                    
                except Exception as e:
                    print(f"   [에러] {sgg_nm} {page_no}페이지 처리 실패: {e}")
                    break
            
            # 한 지역구의 모든 페이지 수집이 끝나면 결과 출력
            if sgg_hospital_count > 0:
                print(f"   > {sgg_nm}: 총 {sgg_hospital_count}개 병원 저장 완료 (페이지: {page_no-1})")
            else:
                print(f"   > {sgg_nm}: 병원 없음")

    # 최종 파일 저장
    save_path = "national_vaccine_hospitals_final.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(all_hospitals, f, ensure_ascii=False, indent=4)
        
    print(f"\n전국 총 {len(all_hospitals)}개 병원 데이터가 수집되었습니다")

if __name__ == "__main__":
    get_hospitals_pagination_master()