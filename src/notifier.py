# -*- coding: utf-8 -*-
import time
import datetime
import requests

def send_discord_webhook(webhook_url: str, embeds: list, content: str = None) -> bool:
    """
    디스코드 웹훅으로 메시지(Embeds)를 전송합니다.
    디스코드 제한: 1회 요청당 최대 10개의 embed 지원.
    """
    if not webhook_url:
        print("[!] DISCORD_WEBHOOK_URL이 설정되지 않아 콘솔 출력으로 대체합니다.")
        if content:
            print(f"Content: {content}")
        for idx, emb in enumerate(embeds, 1):
            print(f"--- [Embed {idx}] {emb.get('title')} ---")
            print(f"URL: {emb.get('url')}")
            for f in emb.get('fields', []):
                print(f"  {f['name']}: {f['value']}")
        return True

    # 10개씩 분할 전송
    chunk_size = 10
    total_sent = 0
    
    for i in range(0, len(embeds), chunk_size):
        chunk = embeds[i:i + chunk_size]
        payload = {"embeds": chunk}
        if content and i == 0:
            payload["content"] = content
            
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                total_sent += len(chunk)
            else:
                print(f"[!] 디스코드 전송 실패 (상태 코드: {resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            print(f"[!] 디스코드 전송 중 에러: {e}")
            return False
            
        if i + chunk_size < len(embeds):
            time.sleep(1.0) # Discord Rate limit 방지
            
    print(f"[*] 디스코드 알림 전송 완료: 총 {total_sent}개 상품")
    return True

def create_product_embed(product: dict, alert_type: str = "new") -> dict:
    """
    상품 1개에 대한 Discord Embed 딕셔너리를 생성합니다.
    alert_type:
      - 'restock': 재입고/재판 충전 (주황색)
      - 'new': 신규 등록 입고 (초록색)
    """
    is_restock = (alert_type == "restock")
    
    if is_restock:
        badge = "🔥 [재입고/재판]"
        color = 0xFF7A00  # 비비드 오렌지
    else:
        badge = "✨ [신규 입고]"
        color = 0x2ECC71  # 에메랄드 그린
        
    title = f"{badge} {product['title']}"
    # 디스코드 제목 길이 제한: 256자
    if len(title) > 250:
        title = title[:247] + "..."
        
    status_text = "🗓️ 예약 가능" if product.get('is_reserved') else "⚡ 즉시 구매 가능"
    
    fields = [
        {"name": "💰 정가", "value": product['price'] or "확인 필요", "inline": True}
    ]
    
    if product.get('discount_price'):
        fields.append({"name": "🏷️ 할인가", "value": product['discount_price'], "inline": True})
        
    fields.append({"name": "📦 상태", "value": status_text, "inline": True})
    fields.append({"name": "🔍 검색 키워드", "value": f"`{product['keyword']}`", "inline": True})
    
    embed = {
        "title": title,
        "url": product['link'],
        "color": color,
        "fields": fields,
        "footer": {
            "text": "건담붐 재고 감시 봇 | GitHub Actions"
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    if product.get('img_url'):
        embed["thumbnail"] = {"url": product['img_url']}
        
    return embed

def send_stock_alert(webhook_url: str, new_products: list, restocked_products: list):
    """
    신규 입고 및 재입고 상품들에 대해 디스코드 알림을 보냅니다.
    """
    embeds = []
    
    for prod in restocked_products:
        embeds.append(create_product_embed(prod, alert_type="restock"))
        
    for prod in new_products:
        embeds.append(create_product_embed(prod, alert_type="new"))
        
    if not embeds:
        return
        
    total_count = len(embeds)
    content = f"📢 **[건담붐 알림] 감시 중인 상품의 재고가 확인되었습니다! (총 {total_count}건)**"
    send_discord_webhook(webhook_url, embeds, content=content)

def send_system_message(webhook_url: str, title: str, description: str, color: int = 0x3498DB):
    """
    시스템 안내 메시지 전송 (초기화 또는 에러 등)
    """
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "footer": {
            "text": "건담붐 재고 감시 봇"
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    send_discord_webhook(webhook_url, [embed])
