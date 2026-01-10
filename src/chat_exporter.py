import os
import time
import json
import re
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
from .utils import safe_filename, download_file
from .api_client import LLSpaceClient
from .config import MAX_WORKERS

class ChatExporter:
    def __init__(self, client: LLSpaceClient, update_callback):
        self.client = client
        self.update_callback = update_callback
        self.stop_event = threading.Event()

    def run(self, conversations, output_root=None, max_workers=MAX_WORKERS):
        if output_root is None:
            output_root = os.getcwd()
            
        total_covs = len(conversations)
        success_count = 0
        
        for idx, cov in enumerate(conversations):
            if self.stop_event.is_set():
                break
                
            cov_title = cov.get("cov_title") or str(cov.get("cov_id"))
            cov_id = cov.get("cov_id")
            
            self.update_callback(idx, total_covs, f"正在处理会话: {cov_title}", (idx / total_covs) * 100)
            
            try:
                self._export_conversation(cov, output_root, max_workers)
                success_count += 1
            except Exception as e:
                logging.error(f"导出会话 {cov_title} 失败: {e}")
                
        return output_root, success_count

    def _export_conversation(self, cov, output_root, max_workers=MAX_WORKERS):
        cov_id = cov.get("cov_id")
        cov_title = cov.get("cov_title") or str(cov_id)
        safe_title = safe_filename(cov_title)
        
        cov_dir = os.path.join(output_root, safe_title)
        os.makedirs(cov_dir, exist_ok=True)
        
        cards_dir = os.path.join(cov_dir, "cards")
        os.makedirs(cards_dir, exist_ok=True)
        
        # 获取所有消息
        messages = self._fetch_all_messages(cov_id)
        messages.sort(key=lambda x: x.get("time", 0))
        
        # 处理消息中的卡片链接
        processed_messages = [None] * len(messages)
        total_msgs = len(messages)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {executor.submit(self._process_message, msg, cards_dir): i for i, msg in enumerate(messages)}
            
            completed_count = 0
            for future in as_completed(future_to_idx):
                if self.stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                    
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    processed_messages[idx] = result
                except Exception as e:
                    logging.error(f"处理消息出错: {e}")
                    # Keep original message on error
                    processed_messages[idx] = messages[idx]

                completed_count += 1
                if completed_count % 20 == 0:
                     self.update_callback(-1, -1, f"正在处理消息 ({completed_count}/{total_msgs}) - {cov_title}", -1)
        
        # Filter out None if stopped early
        processed_messages = [m for m in processed_messages if m is not None]
            
        # 生成文件
        self._generate_json(processed_messages, cov, cov_dir, safe_title)
        self._generate_markdown(processed_messages, cov, cov_dir, safe_title)
        self._generate_html(processed_messages, cov, cov_dir, safe_title)

    def _fetch_all_messages(self, cov_id):
        messages = []
        divide_id = None
        
        while True:
            if self.stop_event.is_set():
                break
                
            resp = self.client.get_messages(cov_id, divide_id)
            if not resp or not resp.get("messages"):
                break
                
            batch = resp.get("messages", [])
            messages.extend(batch)
            
            divide_id = batch[-1].get("id")
            
            # 如果返回的消息少于分页大小（通常是20或50），说明没有更多了
            # 但为了保险，还是依赖循环直到空
            if len(batch) < 5: # 假设很小就是没了
                break
                
        return messages

    def _process_message(self, msg, cards_dir):
        # 复制一份以免修改原始数据
        new_msg = msg.copy()
        text = new_msg.get("text", "")
        scheme = new_msg.get("scheme", "")
        
        # 处理头像
        avatar_url = new_msg.get("avatar")
        if not avatar_url and isinstance(new_msg.get("sender"), dict):
            avatar_url = new_msg.get("sender").get("avatar")
            
        if avatar_url:
            try:
                # 简单的文件名生成
                ext = os.path.splitext(urlparse(avatar_url).path)[1] or ".jpg"
                # 使用 URL 的 hash 或其他唯一标识作为文件名，避免重复下载
                # 这里简单使用 URL 的最后一部分，如果太长则截断
                filename = safe_filename(os.path.basename(urlparse(avatar_url).path))
                if not filename:
                    filename = f"avatar_{int(time.time())}"
                if len(filename) > 50:
                    filename = filename[-50:]
                if not filename.endswith(ext):
                    filename += ext
                    
                local_path = os.path.join(cards_dir, filename)
                
                # 检查文件是否存在，不存在则下载
                if not os.path.exists(local_path):
                    download_file(avatar_url, local_path)
                    
                new_msg["local_avatar"] = f"cards/{filename}"
            except Exception as e:
                logging.error(f"下载头像失败 {avatar_url}: {e}")
        
        # 检查是否是卡片链接
        # 格式: "scheme": "llspace://card/3397076?card_cat=1"
        # 且 text 中含有 <a>...</a> (根据需求描述)
        
        if scheme and scheme.startswith("llspace://card/") and "<a>" in text and "</a>" in text:
            try:
                # 提取 card_id
                parsed = urlparse(scheme)
                path_parts = parsed.path.split('/')
                if len(path_parts) >= 2:
                    card_id = path_parts[-1] or path_parts[-2] # handle trailing slash
                    
                    # 获取卡片详情
                    card_detail = self.client.get_card_detail(card_id)
                    if card_detail:
                        card_url = card_detail.get("url")
                        card_title = card_detail.get("title", "未命名卡片")
                        
                        if card_url:
                            # 下载快照
                            self._process_web_snapshot(card_url, cards_dir, card_id)
                            
                            # 替换文本中的链接
                            # 假设 text 是 "Check this out: <a>Title</a>"
                            # 替换为 Markdown/HTML 友好的本地链接标记
                            # 这里我们先在 new_msg 中存储本地路径，生成文件时再替换格式
                            
                            local_path = f"cards/{card_id}.html"
                            new_msg["local_card_path"] = local_path
                            new_msg["card_title"] = card_title
                            
            except Exception as e:
                logging.error(f"处理卡片链接失败: {e}")
                
        return new_msg

    def _process_web_snapshot(self, url, web_dir, card_id):
        # 检查是否已存在，避免重复下载
        html_path = os.path.join(web_dir, f"{card_id}.html")
        if os.path.exists(html_path):
            return

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # 该页面的资源目录
            res_subdir_name = f"{card_id}_files"
            res_dir = os.path.join(web_dir, res_subdir_name)
            os.makedirs(res_dir, exist_ok=True)
            
            # 重写图片链接
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    if src.startswith('//'): src = 'https:' + src
                    if src.startswith('http'):
                        filename = safe_filename(os.path.basename(urlparse(src).path)) or "image.jpg"
                        if len(filename) > 50: filename = filename[-50:]
                        local_path = os.path.join(res_dir, filename)
                        download_file(src, local_path)
                        img['src'] = f"{res_subdir_name}/{filename}"
            
            # 重写 CSS 链接
            for link in soup.find_all('link', rel='stylesheet'):
                href = link.get('href')
                if href:
                    if href.startswith('//'): href = 'https:' + href
                    if href.startswith('http'):
                        filename = safe_filename(os.path.basename(urlparse(href).path)) or "style.css"
                        local_path = os.path.join(res_dir, filename)
                        download_file(href, local_path)
                        link['href'] = f"{res_subdir_name}/{filename}"
                        
            # 重写 JS 链接
            for script in soup.find_all('script'):
                src = script.get('src')
                if src:
                    if src.startswith('//'): src = 'https:' + src
                    if src.startswith('http'):
                        filename = safe_filename(os.path.basename(urlparse(src).path)) or "script.js"
                        local_path = os.path.join(res_dir, filename)
                        download_file(src, local_path)
                        script['src'] = f"{res_subdir_name}/{filename}"

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
                
        except Exception as e:
            logging.error(f"快照失败 {url}: {e}")

    def _generate_json(self, messages, cov, cov_dir, safe_title):
        data = {
            "conversation": cov,
            "messages": messages
        }
        with open(os.path.join(cov_dir, f"{safe_title}.json"), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _generate_markdown(self, messages, cov, cov_dir, safe_title):
        path = os.path.join(cov_dir, f"{safe_title}.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# {cov.get('cov_title', '聊天记录')}\n\n")
            
            for msg in messages:
                sender_name = msg.get("sender", "未知")
                
                timestamp = msg.get("time", 0)
                time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                
                text = msg.get("text") or ""
                
                # 替换卡片链接
                if msg.get("local_card_path"):
                    # 替换 <a>...</a> 为 Markdown 链接
                    # 使用正则替换
                    card_link = f"[卡片: {msg.get('card_title')}]({msg.get('local_card_path')})"
                    if text:
                        text = re.sub(r'<a[^>]*>.*?</a>', card_link, text, flags=re.DOTALL)
                
                f.write(f"**{sender_name}** | {time_str}\n")
                f.write(f"> {text}\n\n")

    def _generate_html(self, messages, cov, cov_dir, safe_title):
        my_user_id = self.client.user_info.get("id")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8"/>
            <title>{cov.get('cov_title', '聊天记录')}</title>
            <style>
                body {{ background-color: #181818; color: #e0e0e0; font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }}
                .message-container {{ display: flex; flex-direction: column; gap: 20px; }}
                
                .message-row {{ display: flex; align_items: flex-start; gap: 10px; }}
                .message-row.me {{ flex-direction: row-reverse; }}
                .message-row.other {{ flex-direction: row; }}
                
                .avatar {{ width: 40px; height: 40px; border-radius: 5px; background-color: #333; flex-shrink: 0; overflow: hidden; }}
                .avatar img {{ width: 100%; height: 100%; object-fit: cover; }}
                
                .content-wrapper {{ display: flex; flex-direction: column; max-width: 70%; }}
                .message-row.me .content-wrapper {{ align_items: flex-end; }}
                .message-row.other .content-wrapper {{ align_items: flex-start; }}
                
                .sender-name {{ font-size: 0.8em; color: #888; margin-bottom: 4px; }}
                .sender-name.me {{ text-align: right; }}
                
                .bubble {{ padding: 10px 15px; border-radius: 8px; position: relative; word-wrap: break-word; display: inline-block; }}
                .message-row.me .bubble {{ background-color: #FFCA01; color: #000000; text-align: left; }}
                .message-row.other .bubble {{ background-color: #242424; color: #FFFFFF; text-align: left; }}
                
                .time {{ font-size: 0.7em; color: #666; margin-bottom: 5px; text-align: center; width: 100%; }}
                
                a {{ color: inherit; text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{cov.get('cov_title', '聊天记录')}</h1>
            </div>
            <div class="message-container">
        """
        
        for msg in messages:
            sender_id = msg.get("user_id", None)
            sender_name = msg.get("sender", "未知")
            
            timestamp = msg.get("time", 0)
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            text = msg.get("text") or ""
            local_avatar = msg.get("local_avatar")
            
            is_me = (sender_id == my_user_id)
            row_class = "me" if is_me else "other"
            
            # 替换卡片链接
            if msg.get("local_card_path"):
                card_link = f'<a href="{msg.get("local_card_path")}" target="_blank">卡片: {msg.get("card_title")}</a>'
                if text:
                    text = re.sub(r'<a[^>]*>.*?</a>', card_link, text, flags=re.DOTALL)
            
            # 简单的换行处理
            if text:
                text = text.replace('\n', '<br>')
            
            avatar_html = ""
            if local_avatar:
                avatar_html = f'<img src="{local_avatar}" alt="{sender_name}">'
            else:
                # 默认头像占位
                avatar_html = f'<div style="width:100%;height:100%;display:flex;align-items:center;justify_content:center;color:#666;">{sender_name[0] if sender_name else "?"}</div>'

            html += f"""
                <div class="time">{time_str}</div>
                <div class="message-row {row_class}">
                    <div class="avatar">
                        {avatar_html}
                    </div>
                    <div class="content-wrapper">
                        <div class="sender-name {row_class}">{sender_name}</div>
                        <div class="bubble">{text}</div>
                    </div>
                </div>
            """
            
        html += """
            </div>
        </body>
        </html>
        """
        
        path = os.path.join(cov_dir, f"{safe_title}.html")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
