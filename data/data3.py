import requests
import xml.etree.ElementTree as ET
import json
import time

def build_vaccine_final_kb():
    service_key = 'YOUR_API_KEY_HERE'
    base_url = 'http://apis.data.go.kr/1790387/vcninfo'
    
    # 1. 전체 코드 리스트 가져오기
    list_url = f"{base_url}/getCondVcnCd"
    res = requests.get(list_url, params={'serviceKey': service_key, 'numOfRows': '100'})
    root = ET.fromstring(res.content)
    items = root.findall('.//item')
    
    code_list = []
    for item in items:
        cd = item.findtext('cd')
        nm = item.findtext('cdNm')
        if cd: code_list.append({'cd': cd, 'nm': nm})

    print(f"[시스템] 총 {len(code_list)}개의 항목에 대해 상세 지식 추출을 시작합니다.")

    # 2. 각 코드별 상세 정보(title, message) 수집
    final_knowledge_base = []
    detail_url = f"{base_url}/getVcnInfo"

    for idx, vaccine in enumerate(code_list):
        print(f"[{idx+1}/{len(code_list)}] {vaccine['nm']} 데이터 수집 중...")
        
        # 확인된 파라미터 'vcnCd' 사용
        params = {'serviceKey': service_key, 'vcnCd': vaccine['cd']}
        
        try:
            response = requests.get(detail_url, params=params)
            d_root = ET.fromstring(response.content)
            item = d_root.find('.//item')
            
            if item is not None:
                # 확인된 태그 'title'과 'message' 사용
                v_title = item.findtext('title') or vaccine['nm']
                v_message = item.findtext('message') or "상세 정보가 없습니다."

                final_knowledge_base.append({
                    "data_type": "knowledge_base",
                    "category": "예방접종",
                    "title": v_title,
                    "content": v_message, # AI가 읽을 핵심 본문
                    "metadata": {
                        "disease_code": vaccine['cd'],
                        "source": "질병관리청"
                    }
                })
            
            # 서버 부하 방지를 위해 살짝 쉬어줍니다.
            time.sleep(0.3)
            
        except Exception as e:
            print(f"{vaccine['nm']} 처리 중 오류 발생: {e}")
            continue

    # 3. 최종 JSON 저장
    save_path = "vaccine_final_knowledge_base.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(final_knowledge_base, f, ensure_ascii=False, indent=4)
    
    print(f"\n[성공] 모든 데이터가 {save_path}에 저장되었습니다.")

if __name__ == "__main__":
    build_vaccine_final_kb()