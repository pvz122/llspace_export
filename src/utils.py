import hashlib
import time
import re
import requests
import logging
import os
from .config import SECRET_KEY, CLIENT_VERSION, PLATFORM

def md5(s: str) -> str:
    """计算字符串的 MD5 哈希值。"""
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def generate_headers(token: str = None) -> dict:
    """根据规范生成 API 请求头。"""
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
        "User-Agent": "llspace-exporter/1.0"
    }
    
    if token and token.strip():
        headers["Authorization"] = token
        
    return headers

def safe_filename(s: str) -> str:
    """清理字符串以用作安全的文件名。"""
    return re.sub(r'[\\/*?:"<>|]', "_", s)

def download_file(url: str, dest_path: str):
    """从 URL 下载文件到目标路径。"""
    try:
        resp = requests.get(url, stream=True, timeout=10)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        logging.error(f"下载失败 {url}: {e}")
