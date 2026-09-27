# -*- coding: utf-8 -*-
import time
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://gundamboom.com/product/search.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

def extract_product_no(link: str) -> str:
    """상품 링크에서 product_no 추출"""
    match = re.search(r'product_no=(\d+)', link)
    return match.group(1) if match else ""

def scrape_keyword_all_pages(keyword: str, max_pages: int = 50, delay: float = 0.5) -> dict:
    """
    특정 키워드로 건담붐의 모든 페이지를 검색하여
    재고 있는 상품(품절 제외)과 품절 상품 목록을 수집합니다.
    """
    # 건담붐은 CP949 / EUC-KR 인코딩 사용
    encoded_kw = urllib.parse.quote(keyword.encode('cp949', errors='replace'))
    
    seen_product_nos = set()
    available_products = []
    soldout_products = []
    
    print(f"[*] '{keyword}' 검색 시작 (전체 페이지 탐색 중...)")
    
    for page in range(1, max_pages + 1):
        # poomjulX=true 파라미터를 사용하여 사이트 단에서 품절을 1차 제외
        req_url = f"{BASE_URL}?search={encoded_kw}&poomjulX=true&page={page}"
        
        try:
            resp = requests.get(req_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[!] {page}페이지 요청 실패: {e}")
            break
            
        html = resp.content.decode('cp949', errors='replace')
        soup = BeautifulSoup(html, 'html.parser')
        
        # 상품 리스트 태그
        dls = soup.select('.product_list2 dl')
        if not dls:
            # 더 이상 상품이 없는 경우 탐색 종료
            break
            
        new_items_in_page = 0
        
        for dl in dls:
            # 링크 및 상품 고유번호
            name_tag = dl.select_one('dd.name a')
            raw_link = name_tag['href'] if name_tag and 'href' in name_tag.attrs else ''
            product_no = extract_product_no(raw_link)
            
            if not product_no or product_no in seen_product_nos:
                continue
                
            seen_product_nos.add(product_no)
            new_items_in_page += 1
            
            # 상품 제목
            title = dl.get('title', '').strip()
            if not title and name_tag:
                title = name_tag.get_text(strip=True)
                
            # 전체 URL 완성
            if raw_link.startswith('/'):
                full_link = f"https://gundamboom.com{raw_link}"
            elif raw_link.startswith('http'):
                full_link = raw_link
            else:
                full_link = f"https://gundamboom.com/{raw_link}"
                
            # 가격 정보
            price_tag = dl.select_one('dd.price p.right')
            price = price_tag.get_text(strip=True) if price_tag else "0원"
            
            # 할인가 정보
            price09_tag = dl.select_one('dd.price09 p.right')
            discount_price = price09_tag.get_text(strip=True) if price09_tag else ""
            
            # 이미지
            img_tag = dl.select_one('dt img')
            img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else ""
            if img_url.startswith('//'):
                img_url = f"https:{img_url}"
                
            # 품절 여부 (2차 검증: 혹시 poomjulX=true 에도 섞여 있는 경우)
            is_soldout = False
            if dl.find('img', src=lambda s: s and 'ic_soldout.png' in s):
                is_soldout = True
            elif '품절' in dl.get_text():
                is_soldout = True
                
            # 예약 상품 여부
            is_reserved = bool(dl.find('img', alt=lambda a: a and '예약' in a))
            
            product_info = {
                'product_no': product_no,
                'title': title,
                'price': price,
                'discount_price': discount_price,
                'link': full_link,
                'img_url': img_url,
                'is_reserved': is_reserved,
                'is_soldout': is_soldout,
                'keyword': keyword
            }
            
            if is_soldout:
                soldout_products.append(product_info)
            else:
                available_products.append(product_info)
                
        # 이번 페이지에서 새로 추가된 상품이 없으면 (예: 마지막 페이지 도달 후 동일 페이지 반복 등)
        if new_items_in_page == 0:
            break
            
        # 서버 과부하 방지 딜레이
        time.sleep(delay)
        
    print(f"[*] '{keyword}' 탐색 완료: 총 {len(available_products)}개 재고/예약 상품 확인됨")
    return {
        'keyword': keyword,
        'available': available_products,
        'soldout': soldout_products
    }
