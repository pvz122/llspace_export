import os
import sys
import subprocess
import platform
import shutil

def build():
    system = platform.system()
    print(f"正在为 {system} 平台构建...")

    # 基础命令
    args = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "llspace-exporter",
        "--clean",
        "--paths", ".",
        "main.py"
    ]

    # 平台特定配置
    if system == "Windows":
        # Windows 特定配置
        pass
    elif system == "Darwin": # macOS
        # macOS 特定配置
        # 关键修复：设置 TCL_LIBRARY 和 TK_LIBRARY 环境变量，
        # 否则 PyInstaller 会认为 tkinter 安装损坏并排除它。
        base_prefix = sys.base_prefix
        tcl_lib = os.path.join(base_prefix, 'lib', 'tcl8.6')
        tk_lib = os.path.join(base_prefix, 'lib', 'tk8.6')
        
        if os.path.exists(tcl_lib) and os.path.exists(tk_lib):
            print(f"Setting TCL_LIBRARY={tcl_lib}")
            print(f"Setting TK_LIBRARY={tk_lib}")
            os.environ['TCL_LIBRARY'] = tcl_lib
            os.environ['TK_LIBRARY'] = tk_lib
        else:
            print("Warning: Could not find Tcl/Tk libraries in base_prefix")

        # 解决 macOS 上可能的 tkinter 问题
        args.extend([
            "--hidden-import", "PIL._tkinter_finder",
            "--hidden-import", "_tkinter",
        ])
        
        # 显式添加数据文件
        if os.path.exists(tcl_lib):
            args.extend(["--add-data", f"{tcl_lib}:lib/tcl8.6"])
        if os.path.exists(tk_lib):
            args.extend(["--add-data", f"{tk_lib}:lib/tk8.6"])

    elif system == "Linux":
        # Linux 特定配置
        pass

    try:
        # 运行构建命令
        print(f"执行命令: {' '.join(args)}")
        subprocess.check_call(args)
        
        print("\n" + "="*30)
        print("构建成功！")
        
        dist_dir = os.path.join(os.getcwd(), "dist")
        if system == "Windows":
            exe_path = os.path.join(dist_dir, "llspace-exporter.exe")
        elif system == "Darwin":
            # macOS .app bundle is in dist, but onefile produces a binary too?
            # With --onefile on macOS, it produces a binary in dist/
            # With --windowed, it ALSO produces an .app bundle.
            exe_path = os.path.join(dist_dir, "llspace-exporter.app")
        else:
            exe_path = os.path.join(dist_dir, "llspace-exporter")
            
        print(f"可执行文件位于: {dist_dir}")
        print("="*30 + "\n")
        
    except subprocess.CalledProcessError as e:
        print(f"\n构建失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # 确保在虚拟环境中运行或已安装 pyinstaller
    try:
        import PyInstaller
    except ImportError:
        print("错误: 未找到 PyInstaller。请先运行 'uv sync' 安装依赖。")
        sys.exit(1)
        
    build()
