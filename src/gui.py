import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import json
import logging
from PIL import Image, ImageTk
from .api_client import LLSpaceClient
from .exporter import Exporter
from .utils import download_file

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("llspace 导出工具")
        self.root.geometry("600x600")
        
        self.client = LLSpaceClient()
        self.packages = []
        self.package_vars = {}
        self.package_images = {}
        
        self.setup_ui()
        self.check_auto_login()
        
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
        
        # 顶部信息栏
        top_frame = ttk.Frame(self.main_frame)
        top_frame.pack(fill=tk.X, pady=10)
        
        self.user_info_label = ttk.Label(top_frame, text="欢迎")
        self.user_info_label.pack(side=tk.LEFT)
        
        ttk.Button(top_frame, text="退出登录", command=self.do_logout).pack(side=tk.RIGHT)
        
        ttk.Label(self.main_frame, text="选择要导出的卡包:").pack(anchor=tk.W)
        
        # 卡包列表容器
        self.list_container = ttk.Frame(self.main_frame)
        self.list_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 导出按钮
        ttk.Button(self.main_frame, text="导出选中项", command=self.start_export).pack(pady=10)
        
        # 进度框架 (初始隐藏)
        self.progress_frame = ttk.Frame(self.main_container)
        
        # 总进度 (卡包)
        ttk.Label(self.progress_frame, text="总进度 (卡包):").pack(anchor=tk.W, pady=(10, 0))
        self.pkg_progress_var = tk.DoubleVar()
        self.pkg_progress_bar = ttk.Progressbar(self.progress_frame, variable=self.pkg_progress_var, maximum=100)
        self.pkg_progress_bar.pack(fill=tk.X, pady=5)
        self.pkg_status_label = ttk.Label(self.progress_frame, text="")
        self.pkg_status_label.pack(pady=(0, 10))

        # 当前任务 (卡片)
        ttk.Label(self.progress_frame, text="当前任务 (卡片):").pack(anchor=tk.W)
        self.card_progress_var = tk.DoubleVar()
        self.card_progress_bar = ttk.Progressbar(self.progress_frame, variable=self.card_progress_var, maximum=100)
        self.card_progress_bar.pack(fill=tk.X, pady=5)
        self.card_status_label = ttk.Label(self.progress_frame, text="准备中...")
        self.card_status_label.pack(pady=5)
        
    def check_auto_login(self):
        session_file = "cache/session_data.json"
        if os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    user_info = data.get("user", {})
                    token = user_info.get("authentication_token")
                    
                    if token:
                        self.client.token = token
                        self.client.user_info = user_info
                        # 尝试获取卡包以验证 token
                        packages = self.client.get_packages()
                        if packages:
                            self.packages = packages
                            self.show_main_view(refresh_packages=False)
                            return
            except Exception as e:
                logging.error(f"Auto login failed: {e}")
                
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
            
    def do_logout(self):
        if messagebox.askyesno("确认", "确定要退出登录吗？"):
            # 清除会话文件
            session_file = "cache/session_data.json"
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except Exception as e:
                    logging.error(f"Failed to remove session file: {e}")
            
            # 清除客户端状态
            self.client.token = None
            self.client.user_info = {}
            self.packages = []
            
            # 切换回登录界面
            self.main_frame.pack_forget()
            self.login_frame.pack(fill=tk.BOTH, expand=True)
            self.username_var.set("")
            self.password_var.set("")
            
    def show_main_view(self, refresh_packages=True):
        self.login_frame.pack_forget()
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        user_name = self.client.user_info.get("name", "用户")
        self.user_info_label.config(text=f"欢迎, {user_name}")
        
        if refresh_packages:
            # 获取卡包
            self.packages = self.client.get_packages()
        
        # 缓存会话数据
        os.makedirs("cache", exist_ok=True)
        with open("cache/session_data.json", "w", encoding='utf-8') as f:
            json.dump({
                "user": self.client.user_info,
                "packages": self.packages
            }, f, ensure_ascii=False, indent=2)
            
        self.create_package_list()
        
    def create_package_list(self):
        # 清除旧内容
        for widget in self.list_container.winfo_children():
            widget.destroy()
            
        # Canvas and Scrollbar
        canvas = tk.Canvas(self.list_container)
        scrollbar = ttk.Scrollbar(self.list_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        self.package_vars = {}
        self.package_images = {}
        
        for pkg in self.packages:
            pg_id = pkg.get("pg_id")
            pg_name = pkg.get("pg_name", "未命名卡包")
            
            item_frame = ttk.Frame(self.scrollable_frame)
            item_frame.pack(fill="x", pady=5, padx=5)
            
            # Checkbox
            var = tk.BooleanVar()
            self.package_vars[pg_id] = var
            chk = ttk.Checkbutton(item_frame, variable=var)
            chk.pack(side="left")
            
            # Image Label (Placeholder)
            img_label = ttk.Label(item_frame, text="[加载中]", width=10, anchor="center", relief="solid")
            img_label.pack(side="left", padx=10)
            
            # Name Label
            ttk.Label(item_frame, text=pg_name, font=("Arial", 12)).pack(side="left", padx=5)
            
            # Store reference to update image later
            pkg['_ui_label'] = img_label
            
        # Start thread to load images
        threading.Thread(target=self.load_images, daemon=True).start()

    def load_images(self):
        cache_dir = "cache/covers"
        os.makedirs(cache_dir, exist_ok=True)
        
        for pkg in self.packages:
            cover_url = pkg.get("cover_url")
            pg_id = pkg.get("pg_id")
            if not cover_url:
                continue
                
            try:
                filename = f"{pg_id}.jpg"
                filepath = os.path.join(cache_dir, filename)
                
                if not os.path.exists(filepath):
                    download_file(cover_url, filepath)
                    
                # Update UI in main thread by passing filepath
                self.root.after(0, self.update_image_label, pkg, filepath)
                
            except Exception as e:
                logging.error(f"Failed to load cover for {pg_id}: {e}")
                self.root.after(0, self.update_image_label_error, pkg)

    def update_image_label(self, pkg, filepath):
        try:
            # Load and resize in main thread to avoid threading issues with PIL/Tkinter
            image = Image.open(filepath)
            aspect_ratio = image.width / image.height
            new_height = 60
            new_width = int(new_height * aspect_ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(image)
            label = pkg.get('_ui_label')
            if label and label.winfo_exists():
                label.configure(image=photo, text="", width=0, relief="flat")
                self.package_images[pkg['pg_id']] = photo
        except Exception as e:
            logging.error(f"Failed to create PhotoImage for {pkg.get('pg_id')}: {e}")
            self.update_image_label_error(pkg)

    def update_image_label_error(self, pkg):
        label = pkg.get('_ui_label')
        if label and label.winfo_exists():
            label.configure(text="[无封面]")

    def start_export(self):
        selected_packages = [p for p in self.packages if self.package_vars[p['pg_id']].get()]
        
        if not selected_packages:
            messagebox.showwarning("提示", "请至少选择一个卡包")
            return
            
        self.main_frame.pack_forget()
        self.progress_frame.pack(fill=tk.BOTH, expand=True)
        
        threading.Thread(target=self.run_export_task, args=(selected_packages,), daemon=True).start()

    def run_export_task(self, packages):
        total_pkgs = len(packages)
        success_count = 0
        
        for i, pkg in enumerate(packages):
            pg_name = pkg.get("pg_name")
            
            # Update package progress
            pkg_percent = (i / total_pkgs) * 100
            self.root.after(0, lambda p=pkg_percent, n=pg_name, i=i: self.update_pkg_progress(p, f"正在导出 ({i+1}/{total_pkgs}): {n}"))
            
            exporter = Exporter(self.client, self.update_progress)
            try:
                output_dir, count = exporter.run(pkg)
                logging.info(f"Exported {pg_name} to {output_dir}")
                success_count += 1
            except Exception as e:
                logging.error(f"Export failed for {pg_name}: {e}")
        
        # Final 100% for package progress
        self.root.after(0, lambda: self.update_pkg_progress(100, "所有任务完成"))
        self.root.after(0, lambda: self.export_finished(success_count, total_pkgs))

    def update_pkg_progress(self, percent, message):
        self.pkg_progress_var.set(percent)
        self.pkg_status_label.config(text=message)

    def update_progress(self, current, total, message, percent):
        # Use after to ensure thread safety, but pass values directly to avoid lambda capture issues (though here it's fine)
        # Update the variable instead of configure(value=...)
        self.root.after(0, lambda m=message, p=percent: self._update_card_ui(m, p))

    def _update_card_ui(self, message, percent):
        self.card_status_label.config(text=message)
        self.card_progress_var.set(percent)

    def export_finished(self, success_count, total):
        messagebox.showinfo("完成", f"导出完成！成功: {success_count}/{total}")
        self.progress_frame.pack_forget()
        self.main_frame.pack(fill=tk.BOTH, expand=True)
