import sys
import os
import re
import hashlib
import webbrowser
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QLineEdit, QTextEdit, 
                             QListWidget, QListWidgetItem, QLabel, QProgressDialog, 
                             QMessageBox, QDialog, QDateEdit,
                             QCheckBox, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate, QUrl
from bs4 import BeautifulSoup
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, BOOLEAN
from whoosh.qparser import QueryParser, MultifieldParser, OrGroup
from whoosh.query import Term, And, TermRange, Every
from whoosh.analysis import Tokenizer, Token
import jieba

# --- 此处省略了所有与之前版本相同的辅助函数和类 ---
# --- (get_app_data_dir, get_index_dir_for_path, Chinese*, IndexerThread) ---
# --- 请确保它们存在于您的最终代码中 ---
APP_NAME = "TGSift"
def get_app_data_dir():
    path = os.path.join(os.path.expanduser('~'), f".{APP_NAME}")
    os.makedirs(path, exist_ok=True)
    return path
def get_index_dir_for_path(export_path):
    path_hash = hashlib.md5(os.path.abspath(export_path).encode()).hexdigest()
    indexes_base_dir = os.path.join(get_app_data_dir(), "indexes")
    os.makedirs(indexes_base_dir, exist_ok=True)
    return os.path.join(indexes_base_dir, path_hash)
class ChineseTokenizer(Tokenizer):
    def __call__(self, value, positions=False, chars=False, keeporiginal=False, removestops=True, start_pos=0, start_char=0, mode='', **kwargs):
        words = jieba.cut_for_search(value)
        token = Token()
        for w in words:
            token.original = token.text = w
            token.pos = start_pos + value.find(w)
            token.startchar = start_char + value.find(w)
            token.endchar = start_char + value.find(w) + len(w)
            yield token
def ChineseAnalyzer():
    return ChineseTokenizer()
class IndexerThread(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str, int)
    def __init__(self, export_path, index_dir):
        super().__init__()
        self.export_path = export_path
        self.index_dir = index_dir
    def run(self):
        schema = Schema(message_id=ID(stored=True, unique=True), from_user=TEXT(stored=True, analyzer=ChineseAnalyzer()), content=TEXT(stored=True, analyzer=ChineseAnalyzer()), date=TEXT(stored=True, sortable=True), original_date=TEXT(stored=True), has_link=BOOLEAN(stored=True), raw_content=TEXT(stored=True))
        if not os.path.exists(self.index_dir): os.makedirs(self.index_dir)
        ix = create_in(self.index_dir, schema)
        writer = ix.writer(procs=4, multisegment=True, limitmb=256)
        html_files = [os.path.join(self.export_path, f) for f in os.listdir(self.export_path) if f.startswith('messages') and f.endswith('.html')]
        all_messages = []
        for html_file in html_files:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'lxml')
                all_messages.extend(soup.find_all('div', class_=re.compile(r'\bmessage\b.*\bdefault\b')))
        total_messages = len(all_messages)
        self.progress.emit(0, total_messages)
        for i, msg in enumerate(all_messages):
            msg_id = msg.get('id', '')
            from_user_div = msg.find('div', class_='from_name')
            content_div = msg.find('div', class_='text')
            date_div = msg.find('div', class_='date')
            from_user = from_user_div.text.strip() if from_user_div else "Unknown User"
            content_text = content_div.text.strip() if content_div else ""
            raw_content_html = content_div.prettify() if content_div else ""
            original_date = date_div.get('title', '').strip() if date_div else ""
            formatted_date = ""
            if original_date:
                date_part = original_date.split(' ')[0]
                parts = date_part.split('.')
                if len(parts) == 3: formatted_date = f"{parts[2]}.{parts[1]}.{parts[0]}"
            has_link = 'href=' in raw_content_html
            if content_text:
                writer.add_document(message_id=msg_id, from_user=from_user, content=content_text, date=formatted_date, original_date=original_date, has_link=has_link, raw_content=raw_content_html)
            if (i + 1) % 100 == 0: self.progress.emit(i + 1, total_messages)
        writer.commit()
        self.finished.emit(self.index_dir, total_messages)

# -----------------------------------------------------------------------------
# 4. 上下文预览对话框 (已修复)
# -----------------------------------------------------------------------------
class ContextDialog(QDialog):
    def __init__(self, export_path, message_id, parent=None):
        super().__init__(parent)
        self.export_path = export_path
        self.message_id = message_id
        
        self.setWindowTitle("消息上下文预览")
        self.setGeometry(200, 200, 750, 600)
        
        layout = QVBoxLayout(self)
        
        self.context_view = QTextEdit()
        self.context_view.setReadOnly(True)
        layout.addWidget(self.context_view)
        
        button_layout = QHBoxLayout()
        self.open_in_browser_btn = QPushButton("在浏览器中打开")
        self.open_in_browser_btn.clicked.connect(self.open_in_browser)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)

        button_layout.addStretch()
        button_layout.addWidget(self.open_in_browser_btn)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        self.load_context()

    def load_context(self):
        all_html_files = sorted([os.path.join(self.export_path, f) for f in os.listdir(self.export_path) if f.startswith('messages') and f.endswith('.html')])
        target_msg_div = None
        for html_file in all_html_files:
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'lxml')
                target_msg_div = soup.find('div', id=self.message_id)
                if target_msg_div: break
        if not target_msg_div:
            self.context_view.setText("错误：在源文件中找不到此消息。")
            return
        context_divs = []
        prev_sibs = target_msg_div.find_previous_siblings('div', class_=re.compile(r'\bmessage\b'), limit=10)
        context_divs.extend(reversed(list(prev_sibs)))
        context_divs.append(target_msg_div)
        next_sibs = target_msg_div.find_next_siblings('div', class_=re.compile(r'\bmessage\b'), limit=10)
        context_divs.extend(list(next_sibs))
        
        # --- 关键修复点 ---
        # 1. 读取CSS样式
        css_path = os.path.join(self.export_path, "css", "common.css")
        css_content = ""
        try:
            with open(css_path, 'r', encoding='utf-8') as f: css_content = f.read()
        except FileNotFoundError: print("警告: 未找到 common.css 文件。")
        
        # 2. 构建HTML片段
        html_body = ""
        for div in context_divs:
            div_html = div.prettify()
            if div.get('id') == self.message_id:
                div_html = div_html.replace(f'id="{self.message_id}"', f'id="{self.message_id}" style="border: 2px solid #D35400; background-color: #FEF9E7; border-radius: 5px;"', 1)
            html_body += div_html
            
        # 3. 组合成完整的HTML，并注入CSS
        full_html = f"""<html><head><style>{css_content}</style></head><body><div class="page_body chat_page"><div class="history">{html_body}</div></div></body></html>"""
        
        # 4. 设置文档的根路径，以便正确加载CSS中的相对路径资源（如背景图）
        self.context_view.document().setBaseUrl(QUrl.fromLocalFile(self.export_path + os.path.sep))
        
        # 5. 设置HTML内容并滚动
        self.context_view.setHtml(full_html)
        self.context_view.scrollToAnchor(self.message_id)

    def open_in_browser(self):
        # ... (此方法逻辑与之前版本完全相同) ...
        all_html_files = sorted([os.path.join(self.export_path, f) for f in os.listdir(self.export_path) if f.startswith('messages') and f.endswith('.html')])
        target_html_file = None
        for html_file in all_html_files:
            with open(html_file, 'r', encoding='utf-8') as f:
                if self.message_id in f.read():
                    target_html_file = html_file
                    break
        if target_html_file:
            url = QUrl.fromLocalFile(target_html_file).toString() + f"#{self.message_id}"
            webbrowser.open(url)
        else:
            QMessageBox.critical(self, "错误", "无法定位到包含该消息的原始HTML文件。")

# -----------------------------------------------------------------------------
# 5. 主窗口 GUI (纯净功能版)
# -----------------------------------------------------------------------------
class SearchApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Telegram 聊天记录本地搜索工具')
        self.setGeometry(100, 100, 800, 700)
        
        self.ix = None
        self.export_path = None
        
        self.main_layout = QVBoxLayout(self)
        
        top_controls_frame = QFrame()
        top_controls_layout = QVBoxLayout(top_controls_frame)
        top_layout = QHBoxLayout()
        self.import_btn = QPushButton("选择导出文件夹")
        self.status_label = QLabel('请先选择一个作为证据的文件夹...')
        top_layout.addWidget(self.import_btn)
        top_layout.addWidget(self.status_label, 1)
        top_controls_layout.addLayout(top_layout)
        filter_layout = QHBoxLayout()
        self.date_filter_checkbox = QCheckBox("按日期过滤")
        self.start_date_edit = QDateEdit(calendarPopup=True)
        self.end_date_edit = QDateEdit(calendarPopup=True)
        self.reset_date_btn = QPushButton("重置")
        self.start_date_edit.setDisplayFormat("yyyy.MM.dd")
        self.end_date_edit.setDisplayFormat("yyyy.MM.dd")
        filter_layout.addWidget(self.date_filter_checkbox)
        filter_layout.addWidget(QLabel("从:"))
        filter_layout.addWidget(self.start_date_edit)
        filter_layout.addWidget(QLabel("到:"))
        filter_layout.addWidget(self.end_date_edit)
        filter_layout.addWidget(self.reset_date_btn)
        filter_layout.addStretch()
        top_controls_layout.addLayout(filter_layout)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('输入关键词，或使用高级语法: from:用户名 has:link')
        self.search_btn = QPushButton("搜索")
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_btn)
        top_controls_layout.addLayout(search_layout)
        self.main_layout.addWidget(top_controls_frame)

        self.results_count_label = QLabel("搜索结果")
        self.results_list = QListWidget()
        self.main_layout.addWidget(self.results_count_label)
        self.main_layout.addWidget(self.results_list, 1)

        self.set_controls_enabled(False)
        self.import_btn.clicked.connect(self.select_folder)
        self.search_btn.clicked.connect(self.execute_search)
        self.search_input.returnPressed.connect(self.execute_search)
        self.reset_date_btn.clicked.connect(self.set_date_range_from_index)
        self.results_list.itemDoubleClicked.connect(self.show_context_view)
        
    def show_context_view(self, item):
        hit = item.data(Qt.ItemDataRole.UserRole)
        if hit and self.export_path:
            message_id = hit['message_id']
            dialog = ContextDialog(self.export_path, message_id, self)
            dialog.exec()

    # --- 后续所有方法 (set_controls_enabled, select_folder, start_indexing, on_indexing_finished,
    # --- load_index, execute_search, set_date_range_from_index)
    # --- 都与上一个版本完全相同，为节省篇幅不重复粘贴。请直接复用。---
    def set_controls_enabled(self, enabled):
        self.date_filter_checkbox.setEnabled(enabled)
        self.start_date_edit.setEnabled(enabled)
        self.end_date_edit.setEnabled(enabled)
        self.reset_date_btn.setEnabled(enabled)
        self.search_input.setEnabled(enabled)
        self.search_btn.setEnabled(enabled)
    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择 ChatExport 文件夹 (此文件夹不会被修改)")
        if folder_path:
            if not os.path.exists(os.path.join(folder_path, 'messages.html')):
                QMessageBox.warning(self, "文件夹错误", "选择的文件夹中未找到 'messages.html' 文件。")
                return
            self.export_path = folder_path
            self.status_label.setText(f"源文件: {folder_path}")
            index_dir = get_index_dir_for_path(folder_path)
            if os.path.exists(index_dir) and os.path.exists(os.path.join(index_dir, "_MAIN_1.toc")):
                self.load_index(index_dir)
            else:
                reply = QMessageBox.question(self, "需要建立索引", "需要为此文件夹建立搜索索引。\n\n索引将保存在应用数据目录，不会修改您的源文件夹。\n\n根据消息数量可能需要几分钟时间。是否现在开始？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes: self.start_indexing(folder_path, index_dir)
    def start_indexing(self, folder_path, index_dir):
        self.progress_dialog = QProgressDialog("正在建立索引...", "取消", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.indexer_thread = IndexerThread(folder_path, index_dir)
        self.indexer_thread.progress.connect(lambda val, max_val: self.progress_dialog.setMaximum(max_val) or self.progress_dialog.setValue(val))
        self.indexer_thread.finished.connect(self.on_indexing_finished)
        self.progress_dialog.canceled.connect(self.indexer_thread.terminate)
        self.indexer_thread.start()
        self.progress_dialog.exec()
    def on_indexing_finished(self, index_dir, total_messages):
        self.progress_dialog.close()
        if self.indexer_thread.isFinished():
            QMessageBox.information(self, "完成", f"索引建立完毕！共处理了 {total_messages} 条消息。\n源文件夹未做任何改动。")
            self.load_index(index_dir)
    def load_index(self, index_dir):
        try:
            self.ix = open_dir(index_dir)
            self.status_label.setText(f"索引已加载，共 {self.ix.doc_count()} 条记录。可以开始搜索了！")
            self.set_controls_enabled(True)
            self.set_date_range_from_index()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载索引失败: {e}")
            self.status_label.setText("加载索引失败，请重新选择文件夹。")
    def set_date_range_from_index(self):
        if not self.ix: return
        try:
            with self.ix.searcher() as searcher:
                if searcher.doc_count() == 0:
                    self.start_date_edit.setDate(QDate.currentDate()); self.end_date_edit.setDate(QDate.currentDate())
                    return
                first_hit = searcher.search(Every(), sortedby="date", limit=1)
                start_date_str = first_hit[0]['date'] if first_hit else "2000.01.01"
                last_hit = searcher.search(Every(), sortedby="date", reverse=True, limit=1)
                end_date_str = last_hit[0]['date'] if last_hit else "2099.12.31"
                start_date = QDate.fromString(start_date_str, "yyyy.MM.dd"); end_date = QDate.fromString(end_date_str, "yyyy.MM.dd")
                self.start_date_edit.setMinimumDate(start_date); self.start_date_edit.setMaximumDate(end_date); self.start_date_edit.setDate(start_date)
                self.end_date_edit.setMinimumDate(start_date); self.end_date_edit.setMaximumDate(end_date); self.end_date_edit.setDate(end_date)
        except Exception as e: print(f"设置日期范围时出错: {e}")
    def execute_search(self):
        if not self.ix: return
        query_str = self.search_input.text().strip()
        must_queries = []
        from_terms = re.findall(r'from:(\S+)', query_str)
        for term in from_terms: must_queries.append(Term("from_user", term))
        query_str = re.sub(r'from:\S+', '', query_str).strip()
        if 'has:link' in query_str:
            must_queries.append(Term("has_link", True))
            query_str = query_str.replace('has:link', '').strip()
        if self.date_filter_checkbox.isChecked():
            start_date = self.start_date_edit.date().toString("yyyy.MM.dd"); end_date = self.end_date_edit.date().toString("yyyy.MM.dd")
            must_queries.append(TermRange("date", start_date, end_date))
        if query_str:
            parser = MultifieldParser(["from_user", "content"], schema=self.ix.schema, group=OrGroup)
            must_queries.append(parser.parse(query_str))
        if not must_queries:
            self.results_list.clear(); self.results_count_label.setText("搜索结果: 请输入关键词或选择过滤条件。")
            return
        final_query = And(must_queries)
        self.results_list.clear()
        with self.ix.searcher() as searcher:
            results = searcher.search(final_query, limit=500)
            self.results_count_label.setText(f"搜索结果: 找到约 {len(results)} 条")
            if not results: self.results_list.addItem("没有找到匹配的结果。")
            else:
                for hit in results:
                    item_widget = QWidget()
                    item_layout = QVBoxLayout(item_widget); item_layout.setContentsMargins(5, 5, 5, 5)
                    content_html = hit.highlights("content", top=5) or (hit['content'][:200] + '...')
                    header = f"<b>{hit['from_user']}</b> <font color='gray'>({hit['original_date']})</font>"
                    header_label = QLabel(header); content_label = QLabel(content_html); content_label.setWordWrap(True)
                    item_layout.addWidget(header_label); item_layout.addWidget(content_label)
                    list_item = QListWidgetItem(self.results_list)
                    list_item.setData(Qt.ItemDataRole.UserRole, hit); list_item.setSizeHint(item_widget.sizeHint())
                    self.results_list.addItem(list_item); self.results_list.setItemWidget(list_item, item_widget)

# -----------------------------------------------------------------------------
# 6. 程序入口
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 移除了所有加载样式的代码
    jieba.initialize()
    ex = SearchApp()
    ex.show()
    sys.exit(app.exec())