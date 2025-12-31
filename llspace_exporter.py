import os
import sys

# Fix for Tcl/Tk on macOS with uv/standalone python
if sys.platform == 'darwin':
    try:
        base_lib = os.path.join(sys.base_prefix, 'lib')
        tcl_path = os.path.join(base_lib, 'tcl8.6')
        tk_path = os.path.join(base_lib, 'tk8.6')
        if os.path.exists(tcl_path) and os.path.exists(tk_path):
            os.environ.setdefault('TCL_LIBRARY', tcl_path)
            os.environ.setdefault('TK_LIBRARY', tk_path)
            print(f"Set Tcl/Tk paths: {tcl_path}")
    except Exception as e:
        print(f"Warning: Failed to set Tcl/Tk paths: {e}")

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import threading
import json
import time
import hashlib
import logging
import queue
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re

# --- Configuration & Constants ---
API_BASE_URL = "https://api.llspace.com"
SECRET_KEY = "C6DAA093BF4C08B46F01FAE4F09B797A"
CLIENT_VERSION = "1222"
PLATFORM = "ard"
LOG_FILE = "export.log"

# Setup Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)

# --- Utility Functions ---

def md5(s: str) -> str:
    """Calculate MD5 hash of a string."""
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def generate_headers(token: str = None) -> dict:
    """Generate API headers based on specs."""
    timestamp_ms = str(int(time.time() * 1000))
    salt = md5(timestamp_ms)
    
    if token and token.strip():
        base_str = SECRET_KEY + token + salt
    else:
        base_str = SECRET_KEY + salt
    
    sign = md5(base_str).upper()
    
    headers = {
        "salt": salt,
        "sign": sign,
        "CLIENT-VERSION": CLIENT_VERSION,
        "PLATFORM": PLATFORM,
        "User-Agent": "llspace-exporter/1.0" # Good practice
    }
    
    if token and token.strip():
        headers["Authorization"] = token
        
    return headers

def safe_filename(s: str) -> str:
    """Sanitize string to be safe for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "_", s)

def download_file(url: str, dest_path: str):
    """Download a file from URL to destination path."""
    try:
        resp = requests.get(url, stream=True, timeout=10)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        logging.error(f"Failed to download {url}: {e}")

# --- API Client ---

class LLSpaceClient:
    def __init__(self):
        self.token = None
        self.user_info = {}

    def login(self, account, password):
        url = f"{API_BASE_URL}/api/1/users/sign_in"
        headers = generate_headers()
        data = {
            "account": account,
            "password": password
        }
        
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                self.token = result["user"]["authentication_token"]
                self.user_info = result["user"]
                return True, None
            else:
                return False, result.get("message", "Unknown error")
        except Exception as e:
            logging.error(f"Login error: {e}")
            return False, str(e)

    def get_packages(self):
        url = f"{API_BASE_URL}/api/1/pg/list"
        headers = generate_headers(self.token)
        
        try:
            resp = requests.post(url, headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("pg", [])
            else:
                logging.error(f"Get packages error: {result.get('message')}")
                return []
        except Exception as e:
            logging.error(f"Get packages exception: {e}")
            return []

    def get_directory(self, pg_id):
        url = f"{API_BASE_URL}/api/1/pg/directoryList"
        headers = generate_headers(self.token)
        data = {"pg_id": pg_id}
        
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("cards", [])
            else:
                logging.error(f"Get directory error: {result.get('message')}")
                return []
        except Exception as e:
            logging.error(f"Get directory exception: {e}")
            return []

    def get_card_detail(self, card_id, pg_id):
        url = f"{API_BASE_URL}/api/1/cards/detail"
        headers = generate_headers(self.token)
        data = {"card_id": card_id, "from_pg_id": pg_id}
        
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("card", {})
            else:
                logging.error(f"Get card detail error: {result.get('message')}")
                return None
        except Exception as e:
            logging.error(f"Get card detail exception: {e}")
            return None

# --- Exporter Logic ---

class Exporter:
    def __init__(self, client: LLSpaceClient, update_callback):
        self.client = client
        self.update_callback = update_callback
        self.stop_event = threading.Event()

    def run(self, package):
        pg_name = package.get("pg_name", "Unknown")
        pg_id = package.get("pg_id")
        safe_pg_name = safe_filename(pg_name)
        timestamp = int(time.time())
        base_dir = f"{safe_pg_name}_{timestamp}"
        
        os.makedirs(base_dir, exist_ok=True)
        images_dir = os.path.join(base_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        web_dir = os.path.join(base_dir, "web")
        os.makedirs(web_dir, exist_ok=True)

        # Get Directory
        self.update_callback(0, 0, f"Fetching directory for {pg_name}...", 0)
        cards_list = self.client.get_directory(pg_id)
        total_cards = len(cards_list)
        
        exported_cards = []
        
        for idx, card_entry in enumerate(cards_list):
            if self.stop_event.is_set():
                break
                
            card_id = card_entry.get("id")
            # Use title from directory list first, will update with detail
            title = card_entry.get("data", {}).get("title", f"Card {card_id}")
            
            self.update_callback(idx + 1, total_cards, f"Processing: {title}", (idx / total_cards) * 100)
            
            detail = self.client.get_card_detail(card_id, pg_id)
            if not detail:
                logging.warning(f"Skipping card {card_id} due to missing details.")
                continue
                
            # Process Card
            card_data = {
                "title": detail.get("title", title),
                "created_date": detail.get("created_date", ""),
                "description": detail.get("description", ""),
                "cover_url": detail.get("cover_url", ""),
                "url": detail.get("url", ""),
                "id": card_id
            }
            
            # Download Cover
            if card_data["cover_url"]:
                ext = os.path.splitext(urlparse(card_data["cover_url"]).path)[1] or ".jpg"
                cover_filename = f"cover_{card_id}{ext}"
                cover_path = os.path.join(images_dir, cover_filename)
                download_file(card_data["cover_url"], cover_path)
                card_data["local_cover"] = f"images/{cover_filename}"
            else:
                card_data["local_cover"] = None

            # Process Web Snapshot
            if card_data["url"]:
                self._process_web_snapshot(card_data["url"], web_dir, card_id)
                card_data["local_web"] = f"web/{card_id}.html"
            else:
                card_data["local_web"] = None

            exported_cards.append(card_data)
            
        # Sort by created_date (This is a string in format YYYY.MM.DD, so string sort works mostly, 
        # but better to parse if format varies. Assuming YYYY.MM.DD based on specs)
        exported_cards.sort(key=lambda x: x["created_date"])
        
        # Generate Markdown
        md_path = os.path.join(base_dir, f"{safe_pg_name}.md")
        self._generate_markdown(exported_cards, md_path, pg_name)
        
        # Generate Index HTML
        self._generate_index_html(exported_cards, base_dir, pg_name)
        
        return base_dir, len(exported_cards)

    def _process_web_snapshot(self, url, web_dir, card_id):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Resource directory for this page
            res_subdir_name = f"{card_id}_files"
            res_dir = os.path.join(web_dir, res_subdir_name)
            os.makedirs(res_dir, exist_ok=True)
            
            # Rewrite images
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    if src.startswith('//'): src = 'https:' + src
                    if src.startswith('http'):
                        filename = safe_filename(os.path.basename(urlparse(src).path)) or "image.jpg"
                        # Avoid too long filenames
                        if len(filename) > 50: filename = filename[-50:]
                        local_path = os.path.join(res_dir, filename)
                        download_file(src, local_path)
                        img['src'] = f"{res_subdir_name}/{filename}"
            
            # Rewrite CSS
            for link in soup.find_all('link', rel='stylesheet'):
                href = link.get('href')
                if href:
                    if href.startswith('//'): href = 'https:' + href
                    if href.startswith('http'):
                        filename = safe_filename(os.path.basename(urlparse(href).path)) or "style.css"
                        local_path = os.path.join(res_dir, filename)
                        download_file(href, local_path)
                        link['href'] = f"{res_subdir_name}/{filename}"
                        
            # Rewrite JS
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
            logging.error(f"Snapshot failed for {url}: {e}")

    def _generate_markdown(self, cards, path, pg_name):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# {pg_name}\n\n")
            for card in cards:
                f.write(f"## {card['title']}\n\n")
                f.write(f"**Date:** {card['created_date']}\n\n")
                if card['local_cover']:
                    f.write(f"![Cover]({card['local_cover']})\n\n")
                f.write(f"{card['description']}\n\n")
                if card['local_web']:
                    f.write(f"[View Snapshot]({card['local_web']})\n\n")
                f.write("---\n\n")

    def _generate_index_html(self, cards, base_dir, pg_name):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>{pg_name} Index</title>
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
                html += f'<a href="{card["local_web"]}" target="_blank">View Snapshot</a>'
            html += '</div>'
            
        html += "</body></html>"
        
        with open(os.path.join(base_dir, "index.html"), 'w', encoding='utf-8') as f:
            f.write(html)

# --- GUI Application ---

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("llspace Exporter")
        self.root.geometry("600x500")
        
        self.client = LLSpaceClient()
        self.packages = []
        
        self.setup_ui()
        
    def setup_ui(self):
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Login Frame
        self.login_frame = ttk.Frame(self.main_container)
        
        ttk.Label(self.login_frame, text="Username:").pack(pady=5)
        self.username_var = tk.StringVar()
        ttk.Entry(self.login_frame, textvariable=self.username_var).pack(pady=5)
        
        ttk.Label(self.login_frame, text="Password:").pack(pady=5)
        self.password_var = tk.StringVar()
        ttk.Entry(self.login_frame, textvariable=self.password_var, show="*").pack(pady=5)
        
        ttk.Button(self.login_frame, text="Login", command=self.do_login).pack(pady=20)
        
        self.login_frame.pack(fill=tk.BOTH, expand=True)
        
        # Main Frame (Hidden initially)
        self.main_frame = ttk.Frame(self.main_container)
        
        self.user_info_label = ttk.Label(self.main_frame, text="Welcome")
        self.user_info_label.pack(pady=10)
        
        ttk.Label(self.main_frame, text="Select Package to Export:").pack(anchor=tk.W)
        
        self.pkg_listbox = tk.Listbox(self.main_frame, height=15)
        self.pkg_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Button(self.main_frame, text="Export Selected", command=self.start_export).pack(pady=10)
        
        # Progress Frame (Hidden initially)
        self.progress_frame = ttk.Frame(self.main_container)
        
        self.progress_label = ttk.Label(self.progress_frame, text="Preparing...")
        self.progress_label.pack(pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=10)
        
        self.status_label = ttk.Label(self.progress_frame, text="")
        self.status_label.pack(pady=5)
        
    def do_login(self):
        username = self.username_var.get()
        password = self.password_var.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter username and password")
            return
            
        success, msg = self.client.login(username, password)
        if success:
            self.show_main_view()
        else:
            messagebox.showerror("Login Failed", msg)
            
    def show_main_view(self):
        self.login_frame.pack_forget()
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        user_name = self.client.user_info.get("name", "User")
        self.user_info_label.config(text=f"Welcome, {user_name}")
        
        # Fetch packages
        self.packages = self.client.get_packages()
        
        # Cache session data
        os.makedirs("cache", exist_ok=True)
        with open("cache/session_data.json", "w", encoding='utf-8') as f:
            json.dump({
                "user": self.client.user_info,
                "packages": self.packages
            }, f, ensure_ascii=False, indent=2)
            
        for pkg in self.packages:
            self.pkg_listbox.insert(tk.END, pkg.get("pg_name", "Unnamed Package"))
            
    def start_export(self):
        selection = self.pkg_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a package")
            return
            
        pkg_index = selection[0]
        package = self.packages[pkg_index]
        
        self.main_frame.pack_forget()
        self.progress_frame.pack(fill=tk.BOTH, expand=True)
        
        # Start export thread
        self.export_thread = threading.Thread(target=self.run_export, args=(package,))
        self.export_thread.start()
        
    def run_export(self, package):
        exporter = Exporter(self.client, self.update_progress_safe)
        try:
            base_dir, count = exporter.run(package)
            self.root.after(0, lambda: self.export_finished(base_dir, count))
        except Exception as e:
            logging.error(f"Export failed: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Export failed: {e}"))
            self.root.after(0, self.reset_ui)

    def update_progress_safe(self, current, total, message, percent):
        self.root.after(0, lambda: self.update_progress_ui(current, total, message, percent))
        
    def update_progress_ui(self, current, total, message, percent):
        self.progress_var.set(percent)
        self.progress_label.config(text=f"{message}")
        if total > 0:
            self.status_label.config(text=f"{current}/{total}")
            
    def export_finished(self, base_dir, count):
        msg = f"Export Complete!\n\nExported {count} cards.\nLocation: {os.path.abspath(base_dir)}"
        if messagebox.askyesno("Success", msg + "\n\nOpen folder?"):
            if os.name == 'nt':
                os.startfile(os.path.abspath(base_dir))
            elif os.name == 'posix':
                # macOS
                os.system(f"open '{os.path.abspath(base_dir)}'")
            else:
                # Linux
                os.system(f"xdg-open '{os.path.abspath(base_dir)}'")
        self.reset_ui()
        
    def reset_ui(self):
        self.progress_frame.pack_forget()
        self.main_frame.pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
