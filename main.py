import requests
import time
from datetime import datetime
import telebot
from apscheduler.schedulers.blocking import BlockingScheduler
import os

# ================== 配置区（从 Railway 环境变量读取） ==================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MCAP_THRESHOLD = int(os.getenv('MCAP_THRESHOLD', 50000))   # 默认 5万美元
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 45))      # 检查间隔（秒）

# 已推送过的 token 地址（防止重复推送）
seen_tokens = set()

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def get_new_solana_pairs():
    """获取 Solana 最新交易对（优化版）"""
    try:
        # 使用 DexScreener search 接口
        url = "https://api.dexscreener.com/latest/dex/search?q=solana"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        # 安全获取 pairs，防止 None
        pairs = data.get("pairs") or []
        
        print(f"[{datetime.now()}] API 返回 {len(pairs)} 个交易对")
        
        new_pairs = []
        current_time = time.time() * 1000  # 当前时间戳（毫秒）
        
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
                
            # 只保留 Solana 链
            if pair.get("chainId") != "solana":
                continue
                
            # 判断是否是较新的 pair（pairCreatedAt 存在且在最近 2 小时内）
            created_at = pair.get("pairCreatedAt")
            if created_at and (current_time - float(created_at) < 7200_000):  # 2小时 = 7200000 毫秒
                new_pairs.append(pair)
        
        print(f"[{datetime.now()}] 过滤后得到 {len(new_pairs)} 个最近创建的 Solana pair")
        return new_pairs
        
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] 网络请求失败: {e}")
        return []
    except Exception as e:
        print(f"[{datetime.now()}] 数据解析出错: {e}")
        return []


def send_telegram_alert(pair):
    """发送 Telegram 通知"""
    try:
        base = pair.get("baseToken", {})
        name = base.get("name", "Unknown")
        symbol = base.get("symbol", "???")
        token_address = base.get("address", "")
        pair_address = pair.get("pairAddress", "")
        
        # 新 meme 币常用 fdv 作为早期市值参考
        mcap = float(pair.get("fdv") or pair.get("marketCap") or 0)
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        volume_h24 = float(pair.get("volume", {}).get("h24", 0))
        
        dexscreener_url = f"https://dexscreener.com/solana/{pair_address}"
        
        message = f"""🚀 **新 Meme 币突破市值阈值！**

**名称**: {name} (${symbol})
**市值/FDV**: ${mcap:,.0f}
**流动性**: ${liquidity:,.0f}
**24h 成交量**: ${volume_h24:,.0f}

**Token 地址**:
`{token_address}`

**查看交易**:
[DexScreener]({dexscreener_url})

推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        bot.send_message(
            TELEGRAM_CHAT_ID, 
            message, 
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        print(f"✅ 已推送: {name} (${symbol}) | MCAP: ${mcap:,.0f}")
        
    except Exception as e:
        print(f"发送 Telegram 消息失败: {e}")


def check_new_memecoins():
    """主检查函数"""
    print(f"[{datetime.now()}] ===== 开始新一轮检查 =====")
    
    pairs = get_new_solana_pairs()
    
    if not pairs:
        print(f"[{datetime.now()}] 本次未获取到有效 pair 数据")
        return
    
    count = 0
    for pair in pairs:
        base = pair.get("baseToken", {})
        token_address = base.get("address")
        
        if not token_address or token_address in seen_tokens:
            continue
            
        mcap = float(pair.get("fdv") or pair.get("marketCap") or 0)
        
        # 同时增加最低流动性过滤，避免纯垃圾币
        liquidity = float(pair.get("liquidity", {}).get("usd", 0))
        
        if mcap >= MCAP_THRESHOLD and liquidity > 5000:
            send_telegram_alert(pair)
            seen_tokens.add(token_address)
            count += 1
    
    print(f"[{datetime.now()}] 本轮检查完成，推送 {count} 个符合条件的新币\n")


# ================== 启动调度器 ==================
if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 错误：TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未在环境变量中设置！")
        exit(1)
    
    print(f"🚀 Solana 新 Meme 币市值监控已启动")
    print(f"   市值阈值: ${MCAP_THRESHOLD:,} USD")
    print(f"   检查间隔: {CHECK_INTERVAL} 秒")
    print("-" * 60)
    
    # 启动时先运行一次
    check_new_memecoins()
    
    scheduler = BlockingScheduler()
    scheduler.add_job(check_new_memecoins, 'interval', seconds=CHECK_INTERVAL)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("脚本已停止运行")
