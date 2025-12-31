# llspace 导出工具 (llspace Exporter)

这是一个用于从 llspace 平台导出用户卡片内容的桌面 GUI 工具。它可以帮助你将卡包中的内容备份到本地，支持导出为 Markdown 格式，并自动下载相关图片和网页快照。

## 系统要求

*   Python 3.9 或更高版本
*   推荐使用 `uv` 包管理器进行依赖管理和运行

## 安装与运行

### 方式一：下载可执行文件 (推荐)

1.  访问本仓库的 [Releases 页面](https://github.com/pvz122/llspace_export/releases)。
2.  根据你的操作系统下载对应的可执行文件：
    *   **Windows**: 下载 `_win.exe` 文件。
    *   **macOS**: 下载`_mac`二进制文件。

### 方式二：直接运行源码

1.  **克隆或下载代码**到本地。

2.  **初始化环境**：
    确保已安装 `uv`，然后在项目根目录下运行：
    ```bash
    uv sync
    ```

3.  **运行程序**：
    ```bash
    uv run main.py
    ```

### 方式三：自行打包可执行文件

如果你想生成一个独立的可执行文件（如 `.exe` 或 `.app`），可以使用内置的构建脚本。

1.  **安装依赖**：
    ```bash
    uv sync
    ```

2.  **运行构建脚本**：
    ```bash
    uv run build.py
    ```

3.  **查找程序**：
    构建完成后，可执行文件将生成在 `dist` 目录下。
    *   **Windows**: `dist/llspace-exporter.exe`
    *   **macOS**: `dist/llspace-exporter.app` (或二进制文件)
    *   **Linux**: `dist/llspace-exporter`

## 使用指南

1.  **登录**：
    *   启动程序后，输入你的 llspace 用户名和密码。
    *   点击“登录”按钮。
    *   登录成功后，Token 会被保存在本地 `cache/session_data.json` 中，下次启动将自动登录。

2.  **选择卡包**：
    *   登录后，主界面会显示你账号下的所有卡包列表。
    *   勾选你想要导出的一个或多个卡包。

3.  **开始导出**：
    *   点击底部的“导出选中项”按钮。
    *   程序将开始下载并处理数据。界面上会显示当前的导出进度。

4.  **查看结果**：
    *   导出完成后，会弹窗提示。
    *   导出的文件保存在程序运行目录下的 `{卡包名}_{时间戳}` 文件夹中。
    *   文件夹结构如下：
        ```
        卡包名_1735647600/
        ├── images/          # 封面图片
        ├── web/             # 网页快照
        ├── 卡包名.md         # Markdown 内容文件
        └── index.html       # 浏览器索引文件
        ```

5.  **退出登录**：
    *   如果需要切换账号，点击主界面右上角的“退出登录”按钮即可清除本地缓存并返回登录界面。

## 常见问题

*   **macOS 上运行报错 `ModuleNotFoundError: No module named 'tkinter'`**：
    *   这是由于 Python 环境配置问题。请尝试使用 `uv run main.py` 运行，或者使用 `uv run build.py` 重新打包，构建脚本已包含针对 macOS 的修复。
*   **导出速度慢**：
    *   导出速度取决于网络状况和卡包内包含的图片/网页数量。程序需要逐个下载资源，请耐心等待。

## 开发说明

*   `main.py`: 程序入口。
*   `build.py`: PyInstaller 打包脚本。
*   `src/gui.py`: 图形界面实现 (Tkinter)。
*   `src/api_client.py`: llspace API 客户端。
*   `src/exporter.py`: 导出逻辑核心。
*   `src/utils.py`: 通用工具函数。
*   `src/config.py`: 配置文件。

## 免责声明

1.  本工具仅供学习和个人备份使用，请勿用于任何商业用途或非法用途。
2.  本仓库与 **llspace 平行世界** 官方无关。
3.  本工具**不存储**任何用户的账号、密码或隐私数据。所有数据仅保存在用户本地计算机上。
4.  使用本工具产生的任何后果由用户自行承担。

## 许可证

MIT License
