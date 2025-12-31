import sys
import os
import tkinter as tk
import logging
from src.config import LOG_FILE
from src.gui import App

def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding='utf-8'
    )

def fix_macos_tk():
    # 修复 macOS 上 uv/standalone python 的 Tcl/Tk 问题
    if sys.platform == 'darwin':
        try:
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的路径
                base_lib = os.path.join(sys._MEIPASS, 'lib')
            else:
                # 开发环境路径
                base_lib = os.path.join(sys.base_prefix, 'lib')
                
            tcl_path = os.path.join(base_lib, 'tcl8.6')
            tk_path = os.path.join(base_lib, 'tk8.6')
            
            if os.path.exists(tcl_path) and os.path.exists(tk_path):
                os.environ.setdefault('TCL_LIBRARY', tcl_path)
                os.environ.setdefault('TK_LIBRARY', tk_path)
                print(f"已设置 Tcl/Tk 路径: {tcl_path}")
        except Exception as e:
            print(f"警告: 设置 Tcl/Tk 路径失败: {e}")

def main():
    setup_logging()
    fix_macos_tk()
    
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
