import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import json
import logging
from .api_client import LLSpaceClient
from .cards_exporter import CardsExporter
from .chat_exporter import ChatExporter

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("llspace 导出工具")
        
        self.client = LLSpaceClient()
        self.packages = []
        self.package_vars = {}
        self.conversations = []
        self.conversation_vars = {}
        
        self.setup_ui()
        self.check_auto_login()
        
    def setup_ui(self):
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # --- 登录框架 ---
        self.login_frame = ttk.Frame(self.main_container)
        
        ttk.Label(self.login_frame, text="用户名:").pack(pady=5)
        self.username_var = tk.StringVar()
        ttk.Entry(self.login_frame, textvariable=self.username_var).pack(pady=5)
        
        ttk.Label(self.login_frame, text="密码:").pack(pady=5)
        self.password_var = tk.StringVar()
        ttk.Entry(self.login_frame, textvariable=self.password_var, show="*").pack(pady=5)
        
        ttk.Button(self.login_frame, text="登录", command=self.do_login).pack(pady=20)
        
        self.login_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- 主页框架 (Home) ---
        self.home_frame = ttk.Frame(self.main_container)
        
        self.home_user_label = ttk.Label(self.home_frame, text="欢迎", font=("Arial", 14))
        self.home_user_label.pack(pady=20)
        
        btn_frame = ttk.Frame(self.home_frame)
        btn_frame.pack(expand=True)
        
        ttk.Button(btn_frame, text="导出卡包", command=self.show_package_export_view, width=20).pack(pady=10)
        ttk.Button(btn_frame, text="导出聊天记录", command=self.show_chat_export_view, width=20).pack(pady=10)
        
        ttk.Button(self.home_frame, text="退出登录", command=self.do_logout).pack(side=tk.BOTTOM, pady=20)

        # --- 卡包导出框架 ---
        self.pkg_export_frame = ttk.Frame(self.main_container)
        
        top_pkg_frame = ttk.Frame(self.pkg_export_frame)
        top_pkg_frame.pack(fill=tk.X, pady=5)
        ttk.Button(top_pkg_frame, text="< 返回主页", command=self.show_home_view).pack(side=tk.LEFT)
        ttk.Label(top_pkg_frame, text="选择要导出的卡包").pack(side=tk.LEFT, padx=20)
        ttk.Button(top_pkg_frame, text="刷新列表", command=self.refresh_packages).pack(side=tk.RIGHT)
        
        # 全选复选框 (卡包)
        self.pkg_select_all_var = tk.BooleanVar()
        pkg_select_all_frame = ttk.Frame(self.pkg_export_frame)
        pkg_select_all_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(pkg_select_all_frame, text="全选", variable=self.pkg_select_all_var, command=self.toggle_pkg_select_all).pack(side=tk.LEFT)
        
        # 卡包列表容器
        self.pkg_list_container = ttk.Frame(self.pkg_export_frame)
        self.pkg_list_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 导出路径选择 (卡包)
        pkg_path_frame = ttk.Frame(self.pkg_export_frame)
        pkg_path_frame.pack(fill=tk.X, pady=5)
        ttk.Label(pkg_path_frame, text="导出路径:").pack(side=tk.LEFT)
        self.pkg_path_var = tk.StringVar(value=os.getcwd())
        ttk.Entry(pkg_path_frame, textvariable=self.pkg_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(pkg_path_frame, text="选择...", command=lambda: self.select_path(self.pkg_path_var)).pack(side=tk.LEFT)

        ttk.Button(self.pkg_export_frame, text="导出选中卡包", command=self.start_pkg_export).pack(pady=10)

        # --- 聊天导出框架 ---
        self.chat_export_frame = ttk.Frame(self.main_container)
        
        top_chat_frame = ttk.Frame(self.chat_export_frame)
        top_chat_frame.pack(fill=tk.X, pady=5)
        ttk.Button(top_chat_frame, text="< 返回主页", command=self.show_home_view).pack(side=tk.LEFT)
        ttk.Label(top_chat_frame, text="选择要导出的对话").pack(side=tk.LEFT, padx=20)
        ttk.Button(top_chat_frame, text="刷新列表", command=self.refresh_conversations).pack(side=tk.RIGHT)
        
        # 全选复选框 (聊天)
        self.chat_select_all_var = tk.BooleanVar()
        chat_select_all_frame = ttk.Frame(self.chat_export_frame)
        chat_select_all_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(chat_select_all_frame, text="全选", variable=self.chat_select_all_var, command=self.toggle_chat_select_all).pack(side=tk.LEFT)
        
        # 聊天列表容器
        self.chat_list_container = ttk.Frame(self.chat_export_frame)
        self.chat_list_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 导出路径选择 (聊天)
        chat_path_frame = ttk.Frame(self.chat_export_frame)
        chat_path_frame.pack(fill=tk.X, pady=5)
        ttk.Label(chat_path_frame, text="导出路径:").pack(side=tk.LEFT)
        self.chat_path_var = tk.StringVar(value=os.getcwd())
        ttk.Entry(chat_path_frame, textvariable=self.chat_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(chat_path_frame, text="选择...", command=lambda: self.select_path(self.chat_path_var)).pack(side=tk.LEFT)

        ttk.Button(self.chat_export_frame, text="导出选中对话", command=self.start_chat_export).pack(pady=10)
        
        # --- 进度框架 (通用) ---
        self.progress_frame = ttk.Frame(self.main_container)
        
        # 总进度
        ttk.Label(self.progress_frame, text="总进度:").pack(anchor=tk.W, pady=(10, 0))
        self.main_progress_var = tk.DoubleVar()
        self.main_progress_bar = ttk.Progressbar(self.progress_frame, variable=self.main_progress_var, maximum=100)
        self.main_progress_bar.pack(fill=tk.X, pady=5)
        self.main_status_label = ttk.Label(self.progress_frame, text="")
        self.main_status_label.pack(pady=(0, 10))

        # 子任务进度
        ttk.Label(self.progress_frame, text="当前任务:").pack(anchor=tk.W)
        self.sub_progress_var = tk.DoubleVar()
        self.sub_progress_bar = ttk.Progressbar(self.progress_frame, variable=self.sub_progress_var, maximum=100)
        self.sub_progress_bar.pack(fill=tk.X, pady=5)
        self.sub_status_label = ttk.Label(self.progress_frame, text="准备中...")
        self.sub_status_label.pack(pady=5)
        
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
                        # 验证 token 有效性 (简单请求)
                        # 这里我们假设如果能拿到包列表或者其他信息就算有效
                        # 为了不阻塞启动，我们先进入主页，如果后续请求失败再处理
                        self.show_home_view()
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
            self.save_session()
            self.show_home_view()
        else:
            messagebox.showerror("登录失败", msg)
            
    def do_logout(self):
        if messagebox.askyesno("确认", "确定要退出登录吗？"):
            session_file = "cache/session_data.json"
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except Exception as e:
                    logging.error(f"Failed to remove session file: {e}")
            
            self.client.token = None
            self.client.user_info = {}
            self.packages = []
            self.conversations = []
            
            self.hide_all_frames()
            self.login_frame.pack(fill=tk.BOTH, expand=True)
            self.username_var.set("")
            self.password_var.set("")
            self.root.geometry("")
            
    def save_session(self):
        os.makedirs("cache", exist_ok=True)
        with open("cache/session_data.json", "w", encoding='utf-8') as f:
            json.dump({
                "user": self.client.user_info
            }, f, ensure_ascii=False, indent=2)

    def hide_all_frames(self):
        self.login_frame.pack_forget()
        self.home_frame.pack_forget()
        self.pkg_export_frame.pack_forget()
        self.chat_export_frame.pack_forget()
        self.progress_frame.pack_forget()

    def show_home_view(self):
        self.hide_all_frames()
        self.home_frame.pack(fill=tk.BOTH, expand=True)
        self.root.geometry("400x400")
        
        user_name = self.client.user_info.get("name", "用户")
        self.home_user_label.config(text=f"欢迎, {user_name}")

    # --- 卡包导出逻辑 ---

    def show_package_export_view(self):
        self.hide_all_frames()
        self.pkg_export_frame.pack(fill=tk.BOTH, expand=True)
        self.root.geometry("400x800")
        
        if not self.packages:
            self.load_packages()
        else:
            # 如果已有数据，也刷新一下列表UI以防万一
            self.create_package_list()

    def load_packages(self):
        # 尝试从缓存加载
        cache_file = "cache/packages.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding='utf-8') as f:
                    self.packages = json.load(f)
                self.create_package_list()
                return
            except Exception as e:
                logging.error(f"Failed to load cached packages: {e}")
        
        # 如果没有缓存，刷新
        self.refresh_packages()

    def refresh_packages(self):
        threading.Thread(target=self._fetch_packages_thread, daemon=True).start()

    def _fetch_packages_thread(self):
        self.root.after(0, lambda: self.root.title("正在获取卡包列表..."))
        
        pkgs = self.client.get_packages()
        if pkgs:
            self.packages = pkgs
            # 缓存
            os.makedirs("cache", exist_ok=True)
            with open("cache/packages.json", "w", encoding='utf-8') as f:
                json.dump(self.packages, f, ensure_ascii=False, indent=2)
        
        self.root.after(0, lambda: self.root.title("llspace 导出工具"))
        self.root.after(0, self.create_package_list)

    def create_package_list(self):
        self._create_list_ui(self.pkg_list_container, self.packages, self.package_vars, "pg_id", "pg_name")

    def toggle_pkg_select_all(self):
        self._toggle_select_all(self.pkg_select_all_var, self.package_vars)

    def start_pkg_export(self):
        selected_packages = [p for p in self.packages if self.package_vars[p['pg_id']].get()]
        
        if not selected_packages:
            messagebox.showwarning("提示", "请至少选择一个卡包")
            return
            
        export_path = self.pkg_path_var.get()
        if not export_path:
            messagebox.showwarning("提示", "请选择导出路径")
            return

        self.hide_all_frames()
        self.progress_frame.pack(fill=tk.BOTH, expand=True)
        self.root.geometry("600x200")
        
        threading.Thread(target=self.run_pkg_export_task, args=(selected_packages, export_path), daemon=True).start()

    def run_pkg_export_task(self, packages, export_path):
        total_pkgs = len(packages)
        success_count = 0
        
        for i, pkg in enumerate(packages):
            pg_name = pkg.get("pg_name")
            
            percent = (i / total_pkgs) * 100
            self.root.after(0, lambda p=percent, n=pg_name, i=i: self.update_main_progress(p, f"正在导出 ({i+1}/{total_pkgs}): {n}"))
            
            exporter = CardsExporter(self.client, self.update_sub_progress)
            try:
                output_dir, count = exporter.run(pkg, export_path)
                logging.info(f"Exported {pg_name} to {output_dir}")
                success_count += 1
            except Exception as e:
                logging.error(f"Export failed for {pg_name}: {e}")
        
        self.root.after(0, lambda: self.update_main_progress(100, "所有任务完成"))
        self.root.after(0, lambda: self.export_finished(success_count, total_pkgs, export_path))

    # --- 聊天导出逻辑 ---

    def show_chat_export_view(self):
        self.hide_all_frames()
        self.chat_export_frame.pack(fill=tk.BOTH, expand=True)
        self.root.geometry("400x800")
        
        if not self.conversations:
            self.load_conversations()
        else:
            self.create_chat_list()

    def load_conversations(self):
        # 尝试从缓存加载
        cache_file = "cache/conversations.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding='utf-8') as f:
                    self.conversations = json.load(f)
                self.create_chat_list()
                return
            except Exception as e:
                logging.error(f"Failed to load cached conversations: {e}")
        
        # 如果没有缓存，刷新
        self.refresh_conversations()

    def refresh_conversations(self):
        # 在后台线程获取，避免卡顿
        threading.Thread(target=self._fetch_conversations_thread, daemon=True).start()

    def _fetch_conversations_thread(self):
        self.root.after(0, lambda: self.root.title("正在获取会话列表..."))
        
        all_covs = []
        divide_id = None
        
        while True:
            resp = self.client.get_conversations(divide_id)
            if not resp or not resp.get("conversations"):
                break
                
            batch = resp.get("conversations", [])
            all_covs.extend(batch)
            
            if not resp.get("hasnext"):
                break
                
            divide_id = batch[-1].get("cov_id")
            
        self.conversations = all_covs
        
        # 缓存
        os.makedirs("cache", exist_ok=True)
        with open("cache/conversations.json", "w", encoding='utf-8') as f:
            json.dump(self.conversations, f, ensure_ascii=False, indent=2)
            
        self.root.after(0, lambda: self.root.title("llspace 导出工具"))
        self.root.after(0, self.create_chat_list)

    def create_chat_list(self):
        self._create_list_ui(self.chat_list_container, self.conversations, self.conversation_vars, "cov_id", "cov_title")

    def toggle_chat_select_all(self):
        self._toggle_select_all(self.chat_select_all_var, self.conversation_vars)

    def start_chat_export(self):
        selected_covs = [c for c in self.conversations if self.conversation_vars[c['cov_id']].get()]
        
        if not selected_covs:
            messagebox.showwarning("提示", "请至少选择一个对话")
            return
            
        export_path = self.chat_path_var.get()
        if not export_path:
            messagebox.showwarning("提示", "请选择导出路径")
            return

        self.hide_all_frames()
        self.progress_frame.pack(fill=tk.BOTH, expand=True)
        self.root.geometry("600x200")
        
        threading.Thread(target=self.run_chat_export_task, args=(selected_covs, export_path), daemon=True).start()

    def run_chat_export_task(self, conversations, export_path):
        exporter = ChatExporter(self.client, self.update_chat_progress)
        output_dir, success_count = exporter.run(conversations, export_path)
        
        self.root.after(0, lambda: self.update_main_progress(100, "所有任务完成"))
        self.root.after(0, lambda: self.export_finished(success_count, len(conversations), output_dir))

    def update_chat_progress(self, current_idx, total_count, message, percent):
        # ChatExporter callback signature: (idx, total, message, percent)
        # If idx is -1, it means sub-task update
        
        if current_idx == -1:
            # Sub-task update (e.g. messages within a conversation)
            self.root.after(0, lambda m=message: self.sub_status_label.config(text=m))
        else:
            # Main task update (conversations)
            self.root.after(0, lambda p=percent, m=message: self._update_main_ui(p, m))

    def _update_main_ui(self, percent, message):
        self.main_progress_var.set(percent)
        self.main_status_label.config(text=message)

    # --- 通用辅助方法 ---

    def select_path(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def _create_list_ui(self, container, items, vars_dict, id_key, name_key):
        # 清除旧内容
        for widget in container.winfo_children():
            widget.destroy()
            
        # Canvas and Scrollbar
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        vars_dict.clear()
        
        for item in items:
            item_id = item.get(id_key)
            item_name = item.get(name_key, f"未命名 ({item_id})")
            
            item_frame = ttk.Frame(scrollable_frame)
            item_frame.pack(fill="x", pady=5, padx=5)
            
            # Checkbox
            var = tk.BooleanVar()
            vars_dict[item_id] = var
            chk = ttk.Checkbutton(item_frame, variable=var)
            chk.pack(side="left")
            
            # Name Label
            ttk.Label(item_frame, text=item_name, font=("Arial", 12)).pack(side="left", padx=5)

    def _toggle_select_all(self, master_var, vars_dict):
        select_all = master_var.get()
        for var in vars_dict.values():
            var.set(select_all)

    def update_main_progress(self, percent, message):
        self.main_progress_var.set(percent)
        self.main_status_label.config(text=message)

    def update_sub_progress(self, current, total, message, percent):
        self.root.after(0, lambda m=message, p=percent: self._update_sub_ui(m, p))

    def _update_sub_ui(self, message, percent):
        self.sub_status_label.config(text=message)
        self.sub_progress_var.set(percent)

    def export_finished(self, success_count, total, path):
        messagebox.showinfo("完成", f"导出完成！成功: {success_count}/{total}\n保存路径: {path}")
        self.show_home_view()
