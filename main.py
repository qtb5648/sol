import requests
import time
from datetime import datetime
import telebot
from apscheduler.schedulers.blocking import BlockingScheduler
import os

# ================== 配置区（从环境变量读取） ==================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MCAP_THRESHOLD = int(os.getenv('MCAP_THRESHOLD', 50000))   # 默认 5万美元，可在 Railway 修改
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 45))      # 秒

seen_tokens = set()

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def get_new_solana_pairs():
    try:
        # DexScreener 搜索 Solana（实际监控新币建议结合 New Pairs 页面逻辑）
        # 推荐优化：https://api.dexscreener.com/latest/dex/pairs/solana + 具体 pair 或搜索
        response = requests.get("https://api.dexscreener.com/latest/dex/search?q=solana", timeout=15)
        response.raise_for_status()
        data = response.json()
        pairs = data.get("pairs", [])
        
        new_pairs = []
        for pair in pairs[:50]:   # 限制数量，避免过多
            if pair.get("chainId") == "solana":
                # 判断新币：pairCreatedAt 或 age 字段（单位通常是秒或毫秒）
                created_at = pair.get("pairCreatedAt") or pair.get("age") or 0
                if created_at and (time.time() * 1000 - created_at < 3600_000):  # 最近1小时
                    new_pairs.append(pair)
        return new_pairs
    except Exception as e:
        print(f"API 请求失败: {e}")
        return []

def send_telegram_alert(pair):
    try:
        base = pair.get("baseToken", {})
        name = base.get("name", "Unknown")
        symbol = base.get("symbol", "???")
        address = base.get("address", "")
        pair_addr = pair.get("pairAddress", "")
        mcap = pair.get("fdv") or pair.get("marketCap") or 0
        liq = pair.get("liquidity", {}).get("usd", 0)
        vol = pair.get("volume", {}).get("h24", 0)
        
        url = f"https://dexscreener.com/solana/{pair_addr}"
        
        message = f"""🚀 **新 Meme 币突破市值阈值！**

**币名**: {name} (${symbol})
**市值/FDV**: ${mcap:,.0f}
**流动性**: ${liq:,.0f}
**24h 成交量**: ${vol:,.0f}

**Token 地址**:
`{address}`
**交易链接**: [打开 DexScreener]({url})

推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        print(f"✅ 已推送: {name} - ${mcap:,.0f}")
    except Exception as e:
        print(f"发送消息失败: {e}")

def check_new_memecoins():
    print(f"[{datetime.now()}] 检查新 Solana meme 币...")
    pairs = get_new_solana_pairs()
    count = 0
    for pair in pairs:
        addr = pair.get("baseToken", {}).get("address")
        if not addr or addr in seen_tokens:
            continue
        mcap = pair.get("fdv") or pair.get("marketCap") or 0
        if mcap >= MCAP_THRESHOLD:
            send_telegram_alert(pair)
            seen_tokens.add(addr)
            count += 1
    print(f"本次检查完成，发现 {count} 个符合条件的新币")

# ================== 启动调度器 ==================
if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 错误：TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未设置！")
        exit(1)
    
    print(f"🚀 Solana Meme 币监控启动 | 阈值: ${MCAP_THRESHOLD:,} | 间隔: {CHECK_INTERVAL}s")
    check_new_memecoins()   # 先运行一次
    
    scheduler = BlockingScheduler()
    scheduler.add_job(check_new_memecoins, 'interval', seconds=CHECK_INTERVAL)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("脚本停止运行")