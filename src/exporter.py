import os
import time
import threading
import logging
from datetime import datetime
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from .utils import safe_filename, download_file
from .api_client import LLSpaceClient

class Exporter:
    def __init__(self, client: LLSpaceClient, update_callback):
        self.client = client
        self.update_callback = update_callback
        self.stop_event = threading.Event()

    def run(self, package):
        pg_name = package.get("pg_name", "未知")
        pg_id = package.get("pg_id")
        safe_pg_name = safe_filename(pg_name)
        timestamp = int(time.time())
        base_dir = f"{safe_pg_name}_{timestamp}"
        
        os.makedirs(base_dir, exist_ok=True)
        images_dir = os.path.join(base_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        web_dir = os.path.join(base_dir, "web")
        os.makedirs(web_dir, exist_ok=True)

        # 获取目录
        self.update_callback(0, 0, f"正在获取 {pg_name} 的目录...", 0)
        cards_list = self.client.get_directory(pg_id)
        total_cards = len(cards_list)
        
        exported_cards = []
        
        for idx, card_entry in enumerate(cards_list):
            if self.stop_event.is_set():
                break
                
            card_id = card_entry.get("id")
            # 优先使用目录列表中的标题，稍后用详情更新
            title = card_entry.get("data", {}).get("title", f"卡片 {card_id}")
            
            self.update_callback(idx + 1, total_cards, f"正在处理: {title}", (idx / total_cards) * 100)
            
            detail = self.client.get_card_detail(card_id, pg_id)
            if not detail:
                logging.warning(f"由于缺少详情，跳过卡片 {card_id}。")
                continue
                
            # 处理卡片数据
            card_data = {
                "title": detail.get("title", title),
                "created_date": detail.get("created_date", ""),
                "description": detail.get("description", ""),
                "cover_url": detail.get("cover_url", ""),
                "url": detail.get("url", ""),
                "id": card_id
            }
            
            # 下载封面
            if card_data["cover_url"]:
                ext = os.path.splitext(urlparse(card_data["cover_url"]).path)[1] or ".jpg"
                cover_filename = f"cover_{card_id}{ext}"
                cover_path = os.path.join(images_dir, cover_filename)
                download_file(card_data["cover_url"], cover_path)
                card_data["local_cover"] = f"images/{cover_filename}"
            else:
                card_data["local_cover"] = None

            # 处理网页快照
            if card_data["url"]:
                self._process_web_snapshot(card_data["url"], web_dir, card_id)
                card_data["local_web"] = f"web/{card_id}.html"
            else:
                card_data["local_web"] = None

            exported_cards.append(card_data)
            
        # 按创建日期排序 (格式为 YYYY.MM.DD)
        try:
            exported_cards.sort(key=lambda x: datetime.strptime(x["created_date"], "%Y.%m.%d"), reverse=True)
        except ValueError:
            # 如果日期格式解析失败，回退到字符串排序
            logging.warning("Date parsing failed, falling back to string sort")
            # 倒序排列：最新的在最前面
        exported_cards.sort(key=lambda x: x["created_date"], reverse=True)
        
        # 生成 Markdown
        md_path = os.path.join(base_dir, f"{safe_pg_name}.md")
        self._generate_markdown(exported_cards, md_path, pg_name)
        
        # 生成索引 HTML
        self._generate_index_html(exported_cards, base_dir, pg_name)
        
        return base_dir, len(exported_cards)

    def _process_web_snapshot(self, url, web_dir, card_id):
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
                        # 避免文件名过长
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

            with open(os.path.join(web_dir, f"{card_id}.html"), 'w', encoding='utf-8') as f:
                f.write(str(soup))
                
        except Exception as e:
            logging.error(f"快照失败 {url}: {e}")

    def _generate_markdown(self, cards, path, pg_name):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# {pg_name}\n\n")
            for card in cards:
                f.write(f"## {card['title']}\n\n")
                f.write(f"**日期:** {card['created_date']}\n\n")
                if card['local_cover']:
                    f.write(f"![封面]({card['local_cover']})\n\n")
                f.write(f"{card['description']}\n\n")
                if card['local_web']:
                    f.write(f"[查看快照]({card['local_web']})\n\n")
                f.write("---\n\n")

    def _generate_index_html(self, cards, base_dir, pg_name):
        html = f"""
        <!DOCTYPE html>
        <html>
        <meta charset="utf-8"/>
        <head><title>{pg_name} 索引</title>
        <style>
            body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .card {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; }}
            .card img {{ max-width: 200px; display: block; margin-bottom: 10px; }}
            .meta {{ color: #666; font-size: 0.9em; }}
        </style>
        </head>
        <body>
        <h1>{pg_name}</h1>
        """
        for card in cards:
            html += f'<div class="card">'
            html += f'<h3>{card["title"]}</h3>'
            html += f'<div class="meta">{card["created_date"]}</div>'
            if card['local_cover']:
                html += f'<img src="{card["local_cover"]}">'
            html += f'<p>{card["description"].replace(chr(10), "<br>")}</p>'
            if card['local_web']:
                html += f'<a href="{card["local_web"]}" target="_blank">查看快照</a>'
            html += '</div>'
            
        html += "</body></html>"
        
        with open(os.path.join(base_dir, "index.html"), 'w', encoding='utf-8') as f:
            f.write(html)
