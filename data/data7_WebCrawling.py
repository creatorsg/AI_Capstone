import requests
from bs4 import BeautifulSoup
import urllib3
import json
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def sweep_childcare_portal(start_no, end_no):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    scraped_data = []
    print(f"menuno {start_no}번부터 {end_no}번까지 자동 탐색을 시작합니다...\n")
    
    for menuno in range(start_no, end_no + 1):
        url = f"https://www.childcare.go.kr/?menuno={menuno}"
        try:
            res = requests.get(url, headers=headers, verify=False, timeout=5)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            if "데이터가 없습니다" in res.text or res.status_code != 200:
                continue
                
            # 노이즈 태그 제거
            for tag in soup(['header', 'footer', 'nav', 'script', 'style', 'noscript', 'aside', 'form']):
                tag.decompose()
                
            content_area = soup.select_one('.conts_area') or soup.select_one('#contents') or soup.select_one('.content') or soup.body
            
            page_title = ""
            
            if content_area:
                #  본문 영역 안에서 h3, h4 등의 실제 제목 태그를 우선 탐색
                title_tag = content_area.select_one('h3, h4, h2, .tit, .title')
                if title_tag:
                    page_title = title_tag.get_text(strip=True)
                
                raw_text = content_area.get_text(separator='\n', strip=True)
                
                # 본문 정제 및 노이즈 필터링
                clean_lines = []
                for line in raw_text.split('\n'):
                    line = line.strip()
                    # 메뉴판 관련 불필요 텍스트 철저히 제거
                    noise_words = ['확인', '취소', '닫기', '알림', '검색어를 입력해주세요.', '본문내용 바로가기', '대메뉴 바로가기', '푸터 바로가기', '통합검색', '검색 닫기', '검색']
                    if len(line) > 3 and line not in noise_words:
                        clean_lines.append(line)
                        
                if clean_lines:
                    # 태그로 제목을 못 찾았거나 '전체메뉴' 같은 이상한 값이면, 
                    # 본문의 텍스트 중 길이가 적당한(30자 이하) 첫 번째 줄을 제목으로 선정
                    if not page_title or "메뉴" in page_title or len(page_title) > 30:
                        for line in clean_lines:
                            if 2 < len(line) <= 30:
                                page_title = line
                                break
                                
                    # 그래도 제목이 없으면 번호로 대체
                    if not page_title or "메뉴" in page_title:
                        page_title = f"육아정보_{menuno}"
                        
                    final_text = '\n'.join(clean_lines)
                    
                    # 텍스트가 50자 이상인 유효한 페이지만 저장
                    if len(final_text) > 50:
                        print(f"[{page_title}] (menuno={menuno}) 수집 성공!")
                        scraped_data.append({
                            "data_type": "knowledge_base",
                            "category": "육아상식",
                            "title": page_title,
                            "content": final_text,
                            "metadata": {
                                "menuno": menuno,
                                "source": "아이사랑포털",
                                "url": url
                            }
                        })
            time.sleep(0.5) 
            
        except Exception as e:
            pass

    save_path = "childcare_auto_kb.json"
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(scraped_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n탐색 완료! 총 {len(scraped_data)}개의 육아 정보가 {save_path}에 수집되었습니다.")

if __name__ == "__main__":
    sweep_childcare_portal(418, 466)