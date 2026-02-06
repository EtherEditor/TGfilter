import asyncio
import os
import time
import re
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

# --- 环境变量读取 (SOTA 安全实践) ---
API_ID = int(os.getenv('TG_API_ID', 2040))
API_HASH = os.getenv('TG_API_HASH', 'b18441a1ff607e10a989891a5462e627')
SESSION_STR = os.getenv('TG_STRING_SESSION')
TARGET_FEED = os.getenv('PRIVATE_CHANNEL_ID')
# 云端运行不需要本地代理，将其设为 None
proxy = None

# ================= 频道规则配置表 =================
# 不同的频道对应不同的黑名单特征
CHANNEL_RULES = {
    'Seele_Leaks': {
        'blocked_keywords': ['ZZZ', 'HI3', 'AKEndfield', 'Endfield'],
        'blocked_senders': ['广告源']
    },

    # 'HXG_Leak': {
    #     'blocked_keywords': ['ZZZ', 'HI3', 'AKEndfield', 'Endfield'],
    #     'blocked_senders': ['广告源']
    # },
    
     'homokeqing': {
        'blocked_keywords': ['ZZZ', 'HI3', 'AKEndfield', 'Endfield'],
        'blocked_senders': ['广告源']
     }
    
}

# ================= 核心逻辑引擎 =================
def get_all_text(msg):
    """【同步函数】全维度提取文本，解决 HI3 过滤失效。千万不要 await 它！"""
    texts = []
    if msg.text: texts.append(msg.text)
    # 穿透到转发来源的原始消息
    if msg.message and msg.message not in texts: texts.append(msg.message)
    # 穿透到网页预览
    if msg.media and hasattr(msg.media, 'webpage') and msg.media.webpage:
        texts.append(getattr(msg.media.webpage, 'description', '') or '')
        texts.append(getattr(msg.media.webpage, 'title', '') or '')
    return " ".join(filter(None, texts)).lower()


async def get_fast_fwd_name(msg):
    """【异步函数】快速获取转发源名称"""
    if not msg.fwd_from: return ""
    name = msg.fwd_from.from_name
    if name: return name
    try:
        entity = await msg.client.get_entity(msg.fwd_from.from_id)
        return getattr(entity, 'title', '') or getattr(entity, 'first_name', '')
    except: return ""

async def get_last_forwarded_id(client, target_id, source_channel_id):
    """【异步函数】探测水位线，防止重复转发"""
    try:
        async for msg in client.iter_messages(target_id, limit=30):
            if msg.forward and msg.forward.chat_id == source_channel_id:
                return msg.forward.channel_post # 返回原始消息 ID
    except: pass
    return None

# --- 主逻辑 ---

async def main():
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH, proxy=proxy)
    
    async with client:
        print("[*] 成功连接 Telegram。开始处理队列...")
        now = time.time()
        lookback = 7 * 3600 # 1.5 小时窗口冗余
        
        for channel_name, rules in CHANNEL_RULES.items():
            try:
                source_entity = await client.get_entity(channel_name)
                # 获取该频道的上次同步水位线
                last_id = await get_last_forwarded_id(client, TARGET_FEED, source_entity.id)
                
                print(f"[*] 频道: {channel_name} | 水位线: {last_id or '无'}")
                
                blocked_group_ids = set()
                message_buffer = []
                kw_pattern = re.compile('|'.join(rules['blocked_keywords']), re.IGNORECASE) if rules['blocked_keywords'] else None

                # 使用 min_id 实现服务端去重
                async for msg in client.iter_messages(source_entity, limit=100, min_id=last_id or 0):
                    if (now - msg.date.timestamp()) > lookback:
                        break
                    
                    # 【核心修复】get_all_text 是普通函数，这里没有 await！
                    content = get_all_text(msg)
                    fwd_name = await get_fast_fwd_name(msg)

                    is_blocked = (
                        (kw_pattern and kw_pattern.search(content)) or 
                        any(n.lower() in fwd_name.lower() for n in rules['blocked_senders'])
                    )

                    if is_blocked:
                        if msg.grouped_id: blocked_group_ids.add(msg.grouped_id)
                        continue
                    
                    message_buffer.append(msg)

                # 二次过滤：剔除组内违规项
                final_buffer = [m for m in message_buffer if not (m.grouped_id and m.grouped_id in blocked_group_ids)]
                final_buffer.reverse()

                if final_buffer:
                    print(f"[+] 转发 {len(final_buffer)} 条新精华...")
                    for m in final_buffer:
                        await client.forward_messages(TARGET_FEED, m)
                        await asyncio.sleep(0.6)
                else:
                    print(f"[-] {channel_name} 无新消息。")

            except Exception as e:
                print(f"[!] 频道 {channel_name} 运行异常: {e}")


if __name__ == '__main__':
    print('start to twirl')
    asyncio.run(main())
