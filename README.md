# TGSift - Telegram 聊天记录本地搜索工具

TGSift 是一款专为海量（百万级）Telegram 聊天记录导出文件（HTML格式）设计的本地全文搜索引擎。它解决了原生 `Ctrl+F` 在处理大量数据时卡顿、崩溃的问题，提供了一个高性能、功能丰富的桌面搜索体验。

![App Screenshot](https://i.imgur.com/g8Y2gqg.png) 
*(请将此处的图片链接替换为您自己截取的最终版软件截图)*

## ✨ 核心功能

*   **高性能全文索引**: 首次导入时自动为您的聊天记录建立本地索引，后续所有搜索都在毫秒级完成。
*   **源文件安全**: 您的原始聊天记录文件夹（证据文件）**不会被做任何修改**。所有索引数据都安全地存储在独立的应用程序目录中。
*   **高级搜索语法**:
    *   **多关键词**: `苹果 香蕉` (查找同时包含“苹果”和“香蕉”的消息)。
    *   **指定发送人**: `from:张三`
    *   **过滤含链接的消息**: `has:link`
*   **图形化日期过滤**: 通过简单易用的日历控件，精确筛选特定日期范围内的消息。
*   **高保真上下文预览**:
    *   通过**双击**搜索结果，可以弹出一个独立的对话框。
    *   该对话框会**100%还原**原始网页的样式，显示被选中消息及其前后的对话，完美还原语境。
*   **一键追溯源文件**: 在上下文预览窗口中，可以一键在您的默认浏览器中打开原始的 `messages.html` 文件，并自动跳转到该消息的位置。

## 🚀 技术栈

*   **后端**: Python 3
*   **GUI 框架**: PyQt6
*   **全文搜索引擎**: Whoosh
*   **HTML 解析**: BeautifulSoup4
*   **中文分词**: Jieba

## 🛠️ 如何使用

#### 对于开发者

1.  **克隆仓库**:
    ```bash
    git clone https://github.com/your-username/TGSift.git
    cd TGSift
    ```

2.  **安装依赖**:
    建议在虚拟环境中进行。
    ```bash
    pip install -r requirements.txt
    ```

3.  **运行程序**:
    ```bash
    python main.py
    ```

#### 对于普通用户

1.  从 `Release` 页面下载最新的 `TGSift.exe` 文件。
2.  双击运行程序，无需安装。
3.  点击“选择导出文件夹”按钮，选择您从Telegram导出的聊天记录根目录（例如 `ChatExport_2025-07-24`）。
4.  程序会提示您建立索引，点击“是”并等待完成。
5.  开始使用强大的搜索功能！

## 📦 打包为可执行文件

本项目使用 **PyInstaller** 进行打包。

1.  **安装 PyInstaller**:
    ```bash
    pip install pyinstaller
    ```

2.  **生成 `.spec` 文件**:
    此步骤是为了确保 `jieba` 的词典数据能被正确打包。
    ```bash
    pyi-makespec --name TGSift --windowed --onefile main.py
    ```

3.  **修改 `.spec` 文件**:
    打开生成的 `TGSift.spec` 文件，找到 `Analysis` 部分，在 `datas=[]` 中添加 `jieba` 的数据文件。
    ```python
    # ...
    from PyInstaller.utils.hooks import collect_data_files

    a = Analysis(
        # ...
        datas=collect_data_files('jieba'),
        # ...
    )
    # ...
    ```

4.  **执行打包**:
    ```bash
    pyinstaller TGSift.spec
    ```

5.  **获取成品**:
    打包完成后，最终的可执行文件位于 `dist/TGSift.exe`。

## 📜 许可

本项目采用 [MIT License](LICENSE)。