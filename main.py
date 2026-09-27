# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
import datetime
from src.scraper import scrape_keyword_all_pages
from src.notifier import send_stock_alert, send_system_message

# 콘솔 UTF-8 출력 보장
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "keywords.json")
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "last_stock.json")

def load_keywords():
    """키워드 설정 로드"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("keywords", ["gq"])
        except Exception as e:
            print(f"[!] 키워드 설정 파일 로드 실패: {e}")
    return ["gq"]

def load_previous_stock():
    """이전 재고 상태 로드"""
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] 이전 재고 데이터 로드 실패: {e}")
    return {"last_updated": None, "products": {}}

def save_current_stock(stock_data):
    """현재 재고 상태 저장"""
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(stock_data, f, ensure_ascii=False, indent=2)
    print(f"[*] 재고 상태 저장 완료 ({DATA_PATH})")

def main():
    parser = argparse.ArgumentParser(description="건담붐 재고 모니터링 봇")
    parser.add_argument("--keywords", nargs="+", help="특정 검색어 직접 지정 (예: --keywords gq 자쿠)")
    parser.add_argument("--notify-first-run", action="store_true", help="최초 실행 시에도 모든 재고 상품 알림 전송")
    parser.add_argument("--dry-run", action="store_true", help="디스코드 발송 건너뛰기 (콘솔 출력만)")
    args = parser.parse_args()

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if args.dry_run:
        print("[*] Dry-run 모드 활성화: 디스코드 웹훅 전송 안 함")
        webhook_url = ""

    keywords = args.keywords if args.keywords else load_keywords()
    print(f"[*] 모니터링 대상 키워드: {keywords}")

    # 이전 상태 로드
    stock_state = load_previous_stock()
    prev_products = stock_state.get("products", {})
    is_first_run = (len(prev_products) == 0)

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 현재 검색 결과 수집
    current_available_map = {}
    searched_keywords_set = set(keywords)

    for kw in keywords:
        result = scrape_keyword_all_pages(kw)
        for item in result['available']:
            p_no = item['product_no']
            # 여러 키워드에 겹치는 상품이 있을 수 있으므로 병합
            current_available_map[p_no] = item

    print(f"\n[*] 전체 키워드 검색 결과 구매/예약 가능 상품: 총 {len(current_available_map)}개")

    new_products = []
    restocked_products = []

    # 1. 신규 입고 및 재입고 판별
    for p_no, item in current_available_map.items():
        if p_no not in prev_products:
            # 이전에 아예 없던 상품
            new_products.append(item)
            prev_products[p_no] = {
                "title": item["title"],
                "price": item["price"],
                "discount_price": item["discount_price"],
                "link": item["link"],
                "img_url": item["img_url"],
                "is_reserved": item["is_reserved"],
                "is_available": True,
                "keyword": item["keyword"],
                "first_seen": now_str,
                "last_seen": now_str
            }
        else:
            prev_info = prev_products[p_no]
            # 이전에 품절 상태(is_available == False)였는데 지금 재고가 생긴 경우 -> 재입고!
            if not prev_info.get("is_available", False):
                restocked_products.append(item)
                print(f"[🔥 재입고 감지!] {item['title']}")
                prev_info["is_available"] = True
                prev_info["restocked_at"] = now_str
            
            # 정보 갱신
            prev_info["price"] = item["price"]
            prev_info["discount_price"] = item["discount_price"]
            prev_info["is_reserved"] = item["is_reserved"]
            prev_info["last_seen"] = now_str

    # 2. 품절 전환 감지
    # 이번에 감시한 키워드에 속했던 상품 중, 이번 검색 결과에서 빠진 상품은 품절 처리
    soldout_count = 0
    for p_no, p_info in prev_products.items():
        if p_info.get("keyword") in searched_keywords_set:
            if p_no not in current_available_map and p_info.get("is_available", False):
                p_info["is_available"] = False
                p_info["soldout_at"] = now_str
                soldout_count += 1

    print(f"[*] 변동 현황: 신규 상품 {len(new_products)}개, 재입고 {len(restocked_products)}개, 품절 전환 {soldout_count}개")

    # 3. 디스코드 알림 처리
    if is_first_run:
        print("[*] 최초 실행 감지: 이전 데이터가 없어 베이스라인 데이터를 생성했습니다.")
        if args.notify_first_run or os.environ.get("NOTIFY_FIRST_RUN") == "true":
            print("[*] 최초 실행 알림 발송 모드가 켜져 있어 모든 상품 알림을 전송합니다.")
            send_stock_alert(webhook_url, new_products, [])
        else:
            # 첫 실행 시 수십 개 스팸을 방지하고 안내 메시지만 발송
            if webhook_url:
                send_system_message(
                    webhook_url,
                    title="🤖 건담붐 재고 모니터링 봇 시작",
                    description=(
                        f"건담붐 재고 모니터링이 시작되었습니다!\n"
                        f"- 감시 키워드: `{', '.join(keywords)}`\n"
                        f"- 현재 등록된 구매/예약 가능 상품: **{len(current_available_map)}개**\n\n"
                        f"앞으로 **새로운 상품이 입고되거나 품절 상품이 재판/재입고**되면 즉시 알림을 보내드립니다."
                    ),
                    color=0x3498DB
                )
    else:
        # 일반 실행: 재입고 및 신규 입고 상품이 있을 때만 알림 전송!
        if restocked_products or new_products:
            print(f"[*] 알림 전송 대상 발견! (재입고: {len(restocked_products)}건, 신규: {len(new_products)}건)")
            send_stock_alert(webhook_url, new_products, restocked_products)
        else:
            print("[*] 새로운 입고 또는 재입고 상품이 없습니다. (알림 생략)")

    # 4. 상태 저장
    stock_state["last_updated"] = now_str
    stock_state["products"] = prev_products
    save_current_stock(stock_state)

if __name__ == "__main__":
    main()
