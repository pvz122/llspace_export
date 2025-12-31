import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import json
import logging
from .api_client import LLSpaceClient
from .exporter import Exporter

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("llspace 导出工具")
        self.root.geometry("600x500")
        
        self.client = LLSpaceClient()
        self.packages = []
        
        self.setup_ui()
        
    def setup_ui(self):
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # 登录框架
        self.login_frame = ttk.Frame(self.main_container)
        
        ttk.Label(self.login_frame, text="用户名:").pack(pady=5)
        self.username_var = tk.StringVar()
        ttk.Entry(self.login_frame, textvariable=self.username_var).pack(pady=5)
        
        ttk.Label(self.login_frame, text="密码:").pack(pady=5)
        self.password_var = tk.StringVar()
        ttk.Entry(self.login_frame, textvariable=self.password_var, show="*").pack(pady=5)
        
        ttk.Button(self.login_frame, text="登录", command=self.do_login).pack(pady=20)
        
        self.login_frame.pack(fill=tk.BOTH, expand=True)
        
        # 主框架 (初始隐藏)
        self.main_frame = ttk.Frame(self.main_container)
        
        self.user_info_label = ttk.Label(self.main_frame, text="欢迎")
        self.user_info_label.pack(pady=10)
        
        ttk.Label(self.main_frame, text="选择要导出的卡包:").pack(anchor=tk.W)
        
        self.pkg_listbox = tk.Listbox(self.main_frame, height=15)
        self.pkg_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Button(self.main_frame, text="导出选中项", command=self.start_export).pack(pady=10)
        
        # 进度框架 (初始隐藏)
        self.progress_frame = ttk.Frame(self.main_container)
        
        self.progress_label = ttk.Label(self.progress_frame, text="准备中...")
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
            messagebox.showerror("错误", "请输入用户名和密码")
            return
            
        success, msg = self.client.login(username, password)
        if success:
            self.show_main_view()
        else:
            messagebox.showerror("登录失败", msg)
            
    def show_main_view(self):
        self.login_frame.pack_forget()
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        user_name = self.client.user_info.get("name", "用户")
        self.user_info_label.config(text=f"欢迎, {user_name}")
        
        # 获取卡包
        self.packages = self.client.get_packages()
        
        # 缓存会话数据
        os.makedirs("cache", exist_ok=True)
        with open("cache/session_data.json", "w", encoding='utf-8') as f:
            json.dump({
                "user": self.client.user_info,
                "packages": self.packages
            }, f, ensure_ascii=False, indent=2)
            
        for pkg in self.packages:
            self.pkg_listbox.insert(tk.END, pkg.get("pg_name", "未命名卡包"))
            
    def start_export(self):
        selection = self.pkg_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请选择一个卡包")
            return
            
        pkg_index = selection[0]
        package = self.packages[pkg_index]
        
        self.main_frame.pack_forget()
        self.progress_frame.pack(fill=tk.BOTH, expand=True)
        
        # 启动导出线程
        self.export_thread = threading.Thread(target=self.run_export, args=(package,))
        self.export_thread.start()
        
    def run_export(self, package):
        exporter = Exporter(self.client, self.update_progress_safe)
        try:
            base_dir, count = exporter.run(package)
            self.root.after(0, lambda: self.export_finished(base_dir, count))
        except Exception as e:
            logging.error(f"导出失败: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"导出失败: {e}"))
            self.root.after(0, self.reset_ui)

    def update_progress_safe(self, current, total, message, percent):
        self.root.after(0, lambda: self.update_progress_ui(current, total, message, percent))
        
    def update_progress_ui(self, current, total, message, percent):
        self.progress_var.set(percent)
        self.progress_label.config(text=f"{message}")
        if total > 0:
            self.status_label.config(text=f"{current}/{total}")
            
    def export_finished(self, base_dir, count):
        msg = f"导出完成!\n\n已导出 {count} 张卡片。\n位置: {os.path.abspath(base_dir)}"
        if messagebox.askyesno("成功", msg + "\n\n打开文件夹?"):
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
