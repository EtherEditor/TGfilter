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
    """
    全维度提取文本。
    注意：Telethon 中 msg.message 同时包含了 Text 和 Media Caption。
    """
    texts = []
    
    # 1. 核心文案 (涵盖了纯文本消息和图片的 Caption)
    if msg.message:
        texts.append(msg.message)
    
    # 2. 穿透网页预览 (解决图 1 中预览区域的文字)
    if msg.media and hasattr(msg.media, 'webpage') and msg.media.webpage:
        wp = msg.media.webpage
        texts.append(getattr(wp, 'title', '') or '')
        texts.append(getattr(wp, 'description', '') or '')

    # 3. 文件名穿透 (处理直接发文件不带字的情况)
    if msg.file and msg.file.name:
        texts.append(msg.file.name)

    # 4. 这里的逻辑专门针对“转发”的消息
    # 如果消息是转发的，msg.message 已经包含了原消息的文字，
    # 但为了保险，我们可以显式合并
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
    """
    从目标频道寻找来自特定源频道的最后一条原始消息 ID。
    """
    try:
        # 扫描范围扩大到 50，确保能跨过某些系统消息
        async for msg in client.iter_messages(target_id, limit=50):
            # 必须检查是否是转发消息
            if msg.forward:
                # 获取转发源的 ID (Telethon 内部统一为数字)
                fwd_chat_id = msg.forward.chat_id
                if fwd_chat_id == source_channel_id:
                    # 返回该消息在原频道中的 ID
                    return msg.forward.channel_post
    except Exception as e:
        print(f"[!] 水位线探测异常: {e}")
    return None

# --- 主逻辑 ---
async def main():
    # 针对 Matrix 架构：如果是云端运行，只处理环境变量指定的频道
    current_target = os.getenv('CURRENT_CHANNEL')
    # 如果是本地运行，可以降级为处理 CHANNEL_RULES 里的第一个 Key
    if not current_target:
        current_target = list(CHANNEL_RULES.keys())[0]

    rules = CHANNEL_RULES.get(current_target)
    if not rules:
        print(f"[!] 频道 {current_target} 未在规则表中定义")
        return

    # 初始化客户端，云端 proxy 会自动识别为 None
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH, proxy=proxy)
    
    async with client:
        print(f"[*] 任务启动 -> 频道: {current_target}")
        now = time.time()
        lookback = 1.5 * 3600 # 1.5 小时
        
        try:
            source_entity = await client.get_entity(current_target)
            # 1. 精确获取水位线
            last_id = await get_last_forwarded_id(client, TARGET_FEED, source_entity.id)
            print(f"[*] 当前水位线: {last_id or '无 (全量扫描)'}")

            blocked_group_ids = set()
            message_buffer = []
            # 引入单次运行内的 ID 去重集合，防止重复转发
            processed_ids = set() 
            
            kw_pattern = re.compile('|'.join(rules['blocked_keywords']), re.IGNORECASE) if rules['blocked_keywords'] else None

            # 2. 使用 min_id 实现服务端高效增量抓取
            async for msg in client.iter_messages(source_entity, limit=100, min_id=last_id or 0):
                # 逻辑 A：时间切断 (防止首次运行抓取过多)
                if (now - msg.date.timestamp()) > lookback:
                    break
                
                # 逻辑 B：全文本穿透判定
                content = get_all_text(msg)
                fwd_name = await get_fast_fwd_name(msg)

                is_blocked = (
                    (kw_pattern and kw_pattern.search(content)) or 
                    any(n.lower() in fwd_name.lower() for n in rules['blocked_senders'])
                )

                if is_blocked:
                    if msg.grouped_id: blocked_group_ids.add(msg.grouped_id)
                    continue
                
                # 逻辑 C：消息 ID 本地去重
                if msg.id not in processed_ids:
                    message_buffer.append(msg)
                    processed_ids.add(msg.id)

            # 3. 二次组过滤：剔除包含违规图的多图帖子
            final_buffer = [m for m in message_buffer if not (m.grouped_id and m.grouped_id in blocked_group_ids)]
            final_buffer.reverse()

            if final_buffer:
                print(f"[+] 发现 {len(final_buffer)} 条新精华，开始按序转发...")
                for m in final_buffer:
                    try:
                        await client.forward_messages(TARGET_FEED, m)
                        await asyncio.sleep(0.8) # 增加延迟，防止触发 TG Flood
                    except Exception as e:
                        print(f"[!] 转发 ID {m.id} 失败: {e}")
            else:
                print(f"[-] {current_target} 暂无新内容。")

        except Exception as e:
            print(f"[!] 致命错误: {e}")

if __name__ == '__main__':
    print('start to twirl')
    asyncio.run(main())
