import asyncio
import os
import time
import re
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from config import USER_StringSession,PRIVATE_channel_id

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
async def get_fast_fwd_name(msg):
                    # 1. 优先从内存已有的属性中取，这不需要联网
                    if not msg.fwd_from: return ""
                    
                    # 尝试直接读取字段，不发起请求
                    name = msg.fwd_from.from_name
                    if name: return name
                    
                    # 2. 如果没有名字，只有 ID，则尝试从本地缓存获取，不强行联网
                    try:
                        # 仅当 client 已经缓存过该实体时，这个调用才不耗时
                        entity = await msg.client.get_entity(msg.fwd_from.from_id)
                        return getattr(entity, 'title', '') or getattr(entity, 'first_name', '')
                    except:
                        return "" # 拿不到就放弃，不要为了一个名字让整个系统停摆
                    

async def get_last_forwarded_id(client, target_id, source_channel_id):
    """
    探测目标频道，找到来自该源频道的最后一条消息 ID (水位线)
    """
    try:
        # 扫描目标频道最近的 20 条消息
        async for msg in client.iter_messages(target_id, limit=20):
            if msg.forward and msg.forward.chat_id:
                # 检查这条转发是否来自当前正在处理的源频道
                # 注意：这里需要比对 ID
                if msg.forward.chat_id == source_channel_id:
                    # 返回原始消息的 ID
                    return msg.forward.channel_post
    except Exception as e:
        print(f"[!] 水位线探测失败: {e}")
    return None

async def main():
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH, proxy=proxy)
    
    async with client:
        now = time.time()
        # 即使有了 min_id，保留 12 小时作为兜底窗口也是好的实践
        lookback_seconds = 12 * 3600 
        
        for channel_name, rules in CHANNEL_RULES.items():
            try:
                # 获取源频道实体
                source_entity = await client.get_entity(channel_name)
                print(f"[*] 正在处理: {source_entity.title} (ID: {source_entity.id})")
                
                # --- 关键步骤：获取水位线 ---
                last_id = await get_last_forwarded_id(client, TARGET_FEED, source_entity.id)
                if last_id:
                    print(f"[+] 找到水位线: {last_id}，将只同步新消息")
                else:
                    print(f"[-] 未找到历史水位线，将按时间窗口回溯")

                blocked_group_ids = set()
                message_buffer = []
                kw_pattern = re.compile('|'.join(rules['blocked_keywords']), re.IGNORECASE) if rules['blocked_keywords'] else None

                # 使用 min_id 参数，由 Telegram 服务端完成精确去重
                async for msg in client.iter_messages(
                    source_entity, 
                    limit=100, 
                    min_id=last_id if last_id else 0  # 核心：只抓比 last_id 新的消息
                ):
                    # 依然保留时间窗口兜底，防止首次运行抓取过多
                    if (now - msg.date.timestamp()) > lookback_seconds:
                        break

                    content = (msg.text or "").lower()
                    fwd_name = await get_fast_fwd_name(msg)

                    is_blocked = (
                        (kw_pattern and kw_pattern.search(content)) or 
                        any(name.lower() in fwd_name.lower() for name in rules['blocked_senders'])
                    )

                    if is_blocked:
                        if msg.grouped_id:
                            blocked_group_ids.add(msg.grouped_id)
                        continue
                    
                    message_buffer.append(msg)

                # --- 组过滤与转发逻辑 (保持不变) ---
                final_buffer = [m for m in message_buffer if not (m.grouped_id and m.grouped_id in blocked_group_ids)]
                final_buffer.reverse()

                if final_buffer:
                    print(f"[*] 准备转发 {len(final_buffer)} 条新精华...")
                    for m in final_buffer:
                        await client.forward_messages(TARGET_FEED, m)
                        await asyncio.sleep(0.5)
                else:
                    print(f"[*] 没有检测到新消息。")

            except Exception as e:
                print(f"[!] 频道 {channel_name} 异常: {e}")


if __name__ == '__main__':
    print('start to twirl')
    asyncio.run(main())
