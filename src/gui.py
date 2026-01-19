import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import json
import logging
import math
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from .api_client import LLSpaceClient
from .cards_exporter import CardsExporter
from .chat_exporter import ChatExporter
from .utils import format_timestamp
from .config import MAX_WORKERS

PKG_PER_PAGE = 19
CHAT_PER_PAGE = 23

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("llspace 导出工具")
        
        self.client = LLSpaceClient()
        self.packages = []
        self.selected_pkg_ids = set()
        self.pkg_page = 1

        self.conversations = []
        self.filtered_conversations = []
        self.selected_chat_ids = set()
        self.chat_page = 1
        
        self.ui_queue = queue.Queue()
        self.setup_ui()
        self.check_auto_login()
        self.process_ui_queue()
        
        # 聊天列表相关的UI应用缓存引用
        self.chat_row_widgets = {} # cov_id -> {label references}
        
    def process_ui_queue(self):
        try:
            while True:
                task = self.ui_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        self.root.after(100, self.process_ui_queue)

    def setup_ui(self):
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # --- 登录框架 ---
        self.login_frame = ttk.Frame(self.main_container)
        
        ttk.Label(self.login_frame, text="用户名:").pack(pady=5)
        self.username_var = tk.StringVar()
        username_entry = ttk.Entry(self.login_frame, textvariable=self.username_var)
        username_entry.pack(pady=5)
        username_entry.bind("<Return>", lambda event: self.do_login())
        
        ttk.Label(self.login_frame, text="密码:").pack(pady=5)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(self.login_frame, textvariable=self.password_var, show="*")
        password_entry.pack(pady=5)
        password_entry.bind("<Return>", lambda event: self.do_login())
        
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
        
        # 分页控件 (卡包)
        self.pkg_pagination_frame = ttk.Frame(self.pkg_export_frame)
        self.pkg_pagination_frame.pack(fill=tk.X, pady=2)

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
        ttk.Button(top_chat_frame, text="刷新列表", command=self.refresh_conversations).pack(side=tk.RIGHT)
        
        # 工具栏 (全选 + 筛选)
        tools_frame = ttk.Frame(self.chat_export_frame)
        tools_frame.pack(fill=tk.X, pady=5)
        
        # 全选
        self.chat_select_all_var = tk.BooleanVar()
        ttk.Checkbutton(tools_frame, text="全选", variable=self.chat_select_all_var, command=self.toggle_chat_select_all).pack(side=tk.LEFT)
        
        # 分隔
        ttk.Separator(tools_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 筛选
        self.filter_only_follow = tk.BooleanVar(value=False)
        self.filter_only_resident = tk.BooleanVar(value=False)
        
        ttk.Label(tools_frame, text="筛选:").pack(side=tk.LEFT)
        ttk.Checkbutton(tools_frame, text="仅显示已关注", variable=self.filter_only_follow, command=self.apply_chat_filters).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(tools_frame, text="仅显示居民", variable=self.filter_only_resident, command=self.apply_chat_filters).pack(side=tk.LEFT, padx=5)
        
        # 分页控件 (聊天)
        self.chat_pagination_frame = ttk.Frame(self.chat_export_frame)
        self.chat_pagination_frame.pack(fill=tk.X, pady=2)

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
            
            self.filtered_conversations = []
            self.selected_pkg_ids.clear()
            self.selected_chat_ids.clear()
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
        # Pagination slicing
        start_idx = (self.pkg_page - 1) * PKG_PER_PAGE
        end_idx = start_idx + PKG_PER_PAGE
        page_items = self.packages[start_idx:end_idx]
        
        self._render_list_items(
            self.pkg_list_container, 
            page_items, 
            "pg_id", 
            "pg_name", 
            self.selected_pkg_ids,
            lambda item_id, val: self._on_selection_change(self.selected_pkg_ids, item_id, val)
        )
        
        self.render_pagination(
            self.pkg_pagination_frame, 
            self.pkg_page, 
            len(self.packages), 
            lambda p: self._change_pkg_page(p),
            PKG_PER_PAGE
        )

    def _change_pkg_page(self, p):
        self.pkg_page = p
        self.create_package_list()

    def toggle_pkg_select_all(self):
        if self.pkg_select_all_var.get():
            for p in self.packages:
                self.selected_pkg_ids.add(p['pg_id'])
        else:
            self.selected_pkg_ids.clear()
        self.create_package_list()

    def start_pkg_export(self):
        selected_packages = [p for p in self.packages if p['pg_id'] in self.selected_pkg_ids]
        
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
        self.root.geometry("470x810")
        
        if not self.conversations:
            self.load_conversations()
        else:
            self.apply_chat_filters() # Initialize view with filters

    def load_conversations(self):
        # 尝试从缓存加载
        cache_file = "cache/conversations.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding='utf-8') as f:
                    self.conversations = json.load(f)
                self.apply_chat_filters()
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
        self._save_conversations_cache()
            
        self.root.after(0, lambda: self.root.title("llspace 导出工具"))
        self.root.after(0, self.apply_chat_filters)
        
        # 启动后台丰富信息线程
        threading.Thread(target=self._background_enrich_task, daemon=True).start()

    def _save_conversations_cache(self):
        os.makedirs("cache", exist_ok=True)
        with open("cache/conversations.json", "w", encoding='utf-8') as f:
            json.dump(self.conversations, f, ensure_ascii=False, indent=2)

    def _background_enrich_task(self):
        """后台线程：逐个获取好友详细信息并更新UI"""
        updated_any = False

        def fetch_info(cov):
            # 如果已经由于之前的操作有了信息，跳过
            if "friend_info" in cov:
                # 即使有缓存，也要更新UI显示状态（从加载中->显示），防止UI重绘后状态丢失
                self.ui_queue.put(lambda c=cov: self.update_chat_row_info(c))
                return False
                
            user_id = cov.get("extras", {}).get("user_id")
            if user_id:
                u_info = self.client.get_friend_info(user_id)
                if u_info:
                    cov["friend_info"] = u_info
                    # 更新UI
                    self.ui_queue.put(lambda c=cov: self.update_chat_row_info(c))
                    return True
            return False
            
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(fetch_info, cov) for cov in self.conversations]
            
            for future in as_completed(futures):
                try:
                    if future.result():
                        updated_any = True
                except Exception as e:
                    logging.error(f"Failed to fetch friend info: {e}")
        
        if updated_any:
            self._save_conversations_cache()


    def apply_chat_filters(self):
        filtered = []
        only_follow = self.filter_only_follow.get()
        only_resident = self.filter_only_resident.get()
        
        for item in self.conversations:
            has_friend_info = "friend_info" in item
            friend_info = item.get("friend_info", {})
            
            is_followed = friend_info.get("hasFollow", False) if has_friend_info else False
            is_resident = (friend_info.get("premium", {}).get("premium_status", 0) == 1) if has_friend_info else False
            
            if only_follow and not is_followed:
                continue
            if only_resident and not is_resident:
                continue
            filtered.append(item)
            
        self.filtered_conversations = filtered
        self.chat_page = 1
        self.create_chat_list()

    def create_chat_list(self):
        container = self.chat_list_container
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
        
        self.chat_row_widgets.clear()
        
        # 表头
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill="x", pady=2)
        
        header_configs = [
            (0, "", 3, "w"),
            (1, "对话名称", 20, "w"), # 名字靠左
            (2, "最后时间", 16, "center"), # 时间居中
            (3, "关注状态", 10, "center"), # 状态居中
            (4, "居民状态", 10, "center")  # 状态居中
        ]
        
        for col, text, width, anchor in header_configs:
            lbl = ttk.Label(header_frame, text=text, width=width, font=("Arial", 12, "bold"), anchor=anchor)
            lbl.grid(row=0, column=col, sticky="ew") # 使用 ew 填充并配合 anchor

        ttk.Separator(scrollable_frame, orient='horizontal').pack(fill='x', pady=5)
        
        # Pagination Slice
        start_idx = (self.chat_page - 1) * CHAT_PER_PAGE
        end_idx = start_idx + CHAT_PER_PAGE
        page_items = self.filtered_conversations[start_idx:end_idx]

        for item in page_items:
            item_id = item.get("cov_id")
            cov_title = item.get("cov_title", "未命名")
            ts = item.get("last_date_at")
            time_str = format_timestamp(ts) if ts else ""
            
            has_friend_info = "friend_info" in item
            friend_info = item.get("friend_info", {})
            is_followed = friend_info.get("hasFollow", False) if has_friend_info else False
            resident_status = (friend_info.get("premium", {}).get("premium_status", 0)) if has_friend_info else False

            item_frame = ttk.Frame(scrollable_frame)
            item_frame.pack(fill="x", pady=2)
            
            # Checkbox
            var = tk.BooleanVar(value=item_id in self.selected_chat_ids)
            def _cb(v=var, i=item_id):
                self._on_selection_change(self.selected_chat_ids, i, v.get())
            
            chk = ttk.Checkbutton(item_frame, variable=var, command=_cb)
            chk.grid(row=0, column=0, padx=(0, 5))
            
            # Name
            ttk.Label(item_frame, text=cov_title, width=20, font=("Arial", 12), anchor="w").grid(row=0, column=1, sticky="w")
            
            # Time
            ttk.Label(item_frame, text=time_str, width=16, font=("Arial", 11), anchor="center").grid(row=0, column=2, sticky="ew")
            
            # Status Widgets
            follow_text = "已关注" if is_followed else ""
            if not has_friend_info:
                follow_text = "..."
                
            follow_lbl = ttk.Label(item_frame, text=follow_text, width=10, font=("Arial", 10), anchor="center")
            follow_lbl.grid(row=0, column=3, sticky="ew")
            
            if not has_friend_info:
                resident_text = "..."
            elif resident_status == 0:
                resident_text = "已注销"
            elif resident_status == 1:
                resident_text = "居民"
            elif resident_status == 2:
                resident_text = "非居民"
            else:
                logging.warning(f"Unknown resident status: {resident_status} for cov_id: {item_id}")
                resident_text = ""
                
            res_lbl = ttk.Label(item_frame, text=resident_text, width=10, font=("Arial", 10), anchor="center")
            res_lbl.grid(row=0, column=4, sticky="ew")
            
            self.chat_row_widgets[item_id] = {
                "follow_label": follow_lbl,
                "resident_label": res_lbl
            }

        self.render_pagination(
            self.chat_pagination_frame, 
            self.chat_page, 
            len(self.filtered_conversations), 
            lambda p: self._change_chat_page(p),
            CHAT_PER_PAGE
        )

    def _change_chat_page(self, p):
        self.chat_page = p
        self.create_chat_list()

    def update_chat_row_info(self, item):
        item_id = item.get("cov_id")
        if item_id not in self.chat_row_widgets:
            return
            
        widgets = self.chat_row_widgets[item_id]
        friend_info = item.get("friend_info", {})
        
        is_followed = friend_info.get("hasFollow", False)
        resident_status = friend_info.get("premium", {}).get("premium_status", 0)
        
        widgets["follow_label"].config(text="已关注" if is_followed else "")
        if resident_status == 0:
            res_text = "已注销"
        elif resident_status == 1:
            res_text = "居民"
        elif resident_status == 2:
            res_text = "非居民"
        else:
            res_text = ""
        widgets["resident_label"].config(text=res_text)

    def toggle_chat_select_all(self):
        target_ids = {c['cov_id'] for c in self.filtered_conversations}
        if self.chat_select_all_var.get():
            self.selected_chat_ids.update(target_ids)
        else:
            self.selected_chat_ids.difference_update(target_ids)
        self.create_chat_list()

    def start_chat_export(self):
        selected_covs = [c for c in self.conversations if c['cov_id'] in self.selected_chat_ids]
        
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

    def _render_list_items(self, container, items, id_key, name_key_or_func, selection_set, on_toggle):
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
        
        for item in items:
            item_id = item.get(id_key)
            if callable(name_key_or_func):
                item_name = name_key_or_func(item)
            else:
                item_name = item.get(name_key_or_func, f"未命名 ({item_id})")
            
            item_frame = ttk.Frame(scrollable_frame)
            item_frame.pack(fill="x", pady=5, padx=5)
            
            # Checkbox
            var = tk.BooleanVar(value=item_id in selection_set)
            def _cb(v=var, i=item_id):
                on_toggle(i, v.get())
            
            chk = ttk.Checkbutton(item_frame, variable=var, command=_cb)
            chk.pack(side="left")
            
            # Name Label
            ttk.Label(item_frame, text=item_name, font=("Arial", 12)).pack(side="left", padx=5)

    def _on_selection_change(self, s_set, item_id, is_selected):
        if is_selected:
            s_set.add(item_id)
        else:
            s_set.discard(item_id)

    def render_pagination(self, parent, current_page, total_items, page_callback, ITEMS_PER_PAGE):
        for w in parent.winfo_children():
            w.destroy()
            
        if total_items == 0:
            return

        total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
        if total_pages <= 1:
            return

        frame = ttk.Frame(parent)
        frame.pack(anchor=tk.CENTER)

        def go_page(p):
            if 1 <= p <= total_pages:
                page_callback(p)

        ttk.Button(frame, text="<<", width=3, command=lambda: go_page(1), state=tk.NORMAL if current_page > 1 else tk.DISABLED).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame, text="<", width=3, command=lambda: go_page(current_page - 1), state=tk.NORMAL if current_page > 1 else tk.DISABLED).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(frame, text=f"第 {current_page} / {total_pages} 页").pack(side=tk.LEFT, padx=10)
        
        ttk.Button(frame, text=">", width=3, command=lambda: go_page(current_page + 1), state=tk.NORMAL if current_page < total_pages else tk.DISABLED).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame, text=">>", width=3, command=lambda: go_page(total_pages), state=tk.NORMAL if current_page < total_pages else tk.DISABLED).pack(side=tk.LEFT, padx=2)

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
