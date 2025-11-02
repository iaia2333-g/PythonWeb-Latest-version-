import sys, os, json, requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QToolBar, QAction,
    QLineEdit, QFileDialog, QMessageBox, QListWidget, QDialog, QLabel, QPushButton,
    QComboBox, QInputDialog, QTextEdit, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtCore import QUrl, Qt, QStandardPaths

CONFIG_DIR = os.path.join(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation), "PyBrowserPro")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# =====================================================
# ブラウザタブ
# =====================================================
class BrowserTab(QWidget):
    def __init__(self, url):
        super().__init__()
        layout = QVBoxLayout(self)
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(url))
        layout.addWidget(self.browser)
        self.setLayout(layout)

        # ネットワーク監視用
        self.requests = []

        profile = self.browser.page().profile()
        interceptor = RequestInterceptor(self)
        profile.setRequestInterceptor(interceptor)

# =====================================================
# リクエストインターセプタ
# =====================================================
class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, tab):
        super().__init__()
        self.tab = tab

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        method = info.requestMethod().data().decode()
        self.tab.requests.append(f"{method} - {url}")

# =====================================================
# 開発者コンソール
# =====================================================
class DevConsole(QDialog):
    def __init__(self, parent, tab):
        super().__init__(parent)
        self.setWindowTitle("Developer Console")
        self.resize(800, 500)
        self.tab = tab
        self.js_history = []

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左側：JS入力と履歴
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.js_input = QLineEdit()
        run_btn = QPushButton("Run JS")
        run_btn.clicked.connect(self.run_js)
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.js_input)
        hlayout.addWidget(run_btn)
        left_layout.addLayout(hlayout)
        self.js_output = QTextEdit()
        self.js_output.setReadOnly(True)
        left_layout.addWidget(QLabel("JS Console Output / History:"))
        left_layout.addWidget(self.js_output)
        splitter.addWidget(left_widget)

        # 右側：DOM & Network
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.dom_input = QLineEdit()
        self.dom_input.setPlaceholderText("Enter CSS Selector (e.g., body > div)")
        dom_btn = QPushButton("Highlight DOM")
        dom_btn.clicked.connect(self.highlight_dom)
        dom_layout = QHBoxLayout()
        dom_layout.addWidget(self.dom_input)
        dom_layout.addWidget(dom_btn)
        right_layout.addLayout(dom_layout)
        self.dom_output = QTextEdit()
        self.dom_output.setReadOnly(True)
        right_layout.addWidget(QLabel("DOM Elements / Attributes:"))
        right_layout.addWidget(self.dom_output)
        self.net_output = QTreeWidget()
        self.net_output.setHeaderLabels(["Method - URL"])
        right_layout.addWidget(QLabel("Network Requests:"))
        right_layout.addWidget(self.net_output)
        net_refresh = QPushButton("Refresh Network Log")
        net_refresh.clicked.connect(self.refresh_network)
        right_layout.addWidget(net_refresh)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 400])

    def run_js(self):
        code = self.js_input.text()
        if code:
            self.js_history.append(code)
            self.tab.browser.page().runJavaScript(code, self.handle_js_result)
            self.js_input.clear()
            self.js_output.append(f">>> {code}")

    def handle_js_result(self, result):
        self.js_output.append(f"<< {result}")

    def highlight_dom(self):
        selector = self.dom_input.text()
        if selector:
            js_code = f"""
            let el=document.querySelectorAll("{selector}");
            el.forEach(e => e.style.outline='3px solid red');
            Array.from(el).map(e=>e.outerHTML);
            """
            self.tab.browser.page().runJavaScript(js_code, self.show_dom_result)

    def show_dom_result(self, result):
        if result:
            if isinstance(result, list):
                for r in result:
                    self.dom_output.append(r)
            else:
                self.dom_output.append(str(result))

    def refresh_network(self):
        self.net_output.clear()
        for req in self.tab.requests:
            QTreeWidgetItem(self.net_output, [req])

# =====================================================
# メインブラウザ
# =====================================================
class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PythonWeb DevFull Browser")
        self.resize(1300, 850)

        # 設定
        self.config = self.load_config()
        self.home = self.config.get("home", "https://www.google.com")
        self.theme = self.config.get("theme", "light")
        self.history = self.config.get("history", [])
        self.bookmarks = self.config.get("bookmarks", [])
        self.browser_type = self.config.get("browser_type", "PyQt5")

        # タブ
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        # URLバー
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)

        # ツールバー
        self.create_toolbar()
        self.add_tab(self.home)
        self.apply_theme(self.theme)

    # =====================================================
    # ツールバー作成
    # =====================================================
    def create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        for text, func in [
            ("←", lambda: self.current_browser().back()),
            ("→", lambda: self.current_browser().forward()),
            ("🔄", lambda: self.current_browser().reload()),
            ("🏠", self.navigate_home),
            ("＋", lambda: self.add_tab())
        ]:
            a = QAction(text, self)
            a.triggered.connect(func)
            toolbar.addAction(a)

        toolbar.addWidget(self.url_bar)
        toolbar.addAction(QAction("🕘", self, triggered=self.show_history))
        toolbar.addAction(QAction("📚", self, triggered=self.show_bookmarks))
        toolbar.addAction(QAction("⭐", self, triggered=self.add_bookmark))
        toolbar.addAction(QAction("🎨", self, triggered=self.change_theme))
        toolbar.addAction(QAction("⚙️", self, triggered=self.select_browser_type))
        toolbar.addAction(QAction("📂", self, triggered=self.open_html_file))
        toolbar.addAction(QAction("⬇️", self, triggered=self.download_file))
        toolbar.addAction(QAction("💻", self, triggered=self.open_dev_console))
        toolbar.addAction(QAction("⏳", self, triggered=self.view_past_snapshot))  # 過去スナップショット
        toolbar.addAction(QAction("❕", self, triggered=self.show_help))

    # =====================================================
    # タブ操作
    # =====================================================
    def add_tab(self, url=None):
        url = url or self.home
        tab = BrowserTab(url if isinstance(url, str) else url.toString())
        self.tabs.addTab(tab, "Tab")
        self.tabs.setCurrentWidget(tab)
        tab.browser.urlChanged.connect(lambda qurl: self.update_url(qurl, tab))
        tab.browser.loadFinished.connect(lambda: self.add_history(tab.browser.url().toString()))

    def close_tab(self, idx):
        if self.tabs.count() > 1:
            self.tabs.removeTab(idx)

    def current_browser(self):
        tab = self.tabs.currentWidget()
        return tab.browser if tab else None

    def navigate_home(self):
        self.current_browser().setUrl(QUrl(self.home))

    def navigate_to_url(self):
        url = self.url_bar.text()
        if not url.startswith("http"):
            url = "https://" + url
        self.current_browser().setUrl(QUrl(url))

    def update_url(self, qurl, tab):
        self.url_bar.setText(qurl.toString())
        self.tabs.setTabText(self.tabs.indexOf(tab), tab.browser.title())

    # =====================================================
    # 履歴
    # =====================================================
    def add_history(self, url):
        self.history.append({"url": url, "time": datetime.now().strftime("%H:%M:%S")})
        self.save_config()

    def show_history(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("History")
        layout = QVBoxLayout(dlg)
        lw = QListWidget()
        for h in self.history:
            lw.addItem(f"[{h['time']}] {h['url']}")
        layout.addWidget(lw)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(lambda: self.open_history_item(lw))
        layout.addWidget(open_btn)
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(lambda: self.clear_history(lw))
        layout.addWidget(clear_btn)
        dlg.exec_()

    def open_history_item(self, lw):
        if lw.selectedItems():
            url = lw.selectedItems()[0].text().split("] ", 1)[1]
            self.current_browser().setUrl(QUrl(url))

    def clear_history(self, lw):
        self.history.clear()
        lw.clear()
        self.save_config()

    # =====================================================
    # ブックマーク
    # =====================================================
    def add_bookmark(self):
        url = self.current_browser().url().toString()
        if url not in self.bookmarks:
            self.bookmarks.append(url)
            self.save_config()
            QMessageBox.information(self, "Bookmark Added", f"{url} added to bookmarks.")

    def show_bookmarks(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Bookmarks")
        layout = QVBoxLayout(dlg)
        lw = QListWidget()
        lw.addItems(self.bookmarks)
        layout.addWidget(lw)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(lambda: self.open_bookmark_item(lw))
        layout.addWidget(open_btn)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_bookmark_item(lw))
        layout.addWidget(delete_btn)
        dlg.exec_()

    def open_bookmark_item(self, lw):
        if lw.selectedItems():
            self.current_browser().setUrl(QUrl(lw.selectedItems()[0].text()))

    def delete_bookmark_item(self, lw):
        for item in lw.selectedItems():
            if item.text() in self.bookmarks:
                self.bookmarks.remove(item.text())
        lw.clear()
        lw.addItems(self.bookmarks)
        self.save_config()

    # =====================================================
    # 開発者コンソール
    # =====================================================
    def open_dev_console(self):
        tab = self.tabs.currentWidget()
        if tab:
            dlg = DevConsole(self, tab)
            dlg.exec_()

    # =====================================================
    # 過去スナップショット機能（Wayback Machine）
    # =====================================================
    def view_past_snapshot(self):
        url, ok = QInputDialog.getText(self, "View Past Snapshot", "Enter URL:")
        if ok and url:
            api_url = f"https://archive.org/wayback/available?url={url}"
            try:
                resp = requests.get(api_url)
                data = resp.json()
                if "archived_snapshots" in data and "closest" in data["archived_snapshots"]:
                    snapshot_url = data["archived_snapshots"]["closest"]["url"]
                    self.add_tab(snapshot_url)
                    QMessageBox.information(self, "Snapshot Loaded", f"Loaded snapshot: {snapshot_url}")
                else:
                    QMessageBox.information(self, "No Archive", "No past snapshot found for this URL.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to fetch snapshot: {e}")

    # =====================================================
    # テーマ
    # =====================================================
    def change_theme(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Theme Settings")
        layout = QVBoxLayout(dlg)
        combo = QComboBox()
        combo.addItems(["light", "dark", "solarized", "amoled"])
        combo.setCurrentText(self.theme)
        layout.addWidget(combo)
        ok = QPushButton("Apply")
        ok.clicked.connect(lambda: self.apply_theme(combo.currentText(), dlg))
        layout.addWidget(ok)
        dlg.exec_()

    def apply_theme(self, theme, dlg=None):
        self.theme = theme
        styles = {
            "light": "",
            "dark": "QMainWindow{background:#222;color:#ddd;} QLineEdit{background:#333;color:#fff;}",
            "solarized": "QMainWindow{background:#fdf6e3;color:#586e75;} QLineEdit{background:#eee8d5;color:#657b83;}",
            "amoled": "QMainWindow{background:#000;color:#fff;} QLineEdit{background:#111;color:#fff;}"
        }
        self.setStyleSheet(styles.get(theme, ""))
        self.save_config()
        if dlg: dlg.close()

    # =====================================================
    # ブラウザ種類選択
    # =====================================================
    def select_browser_type(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Select Browser Type")
        layout = QVBoxLayout(dlg)
        combo = QComboBox()
        combo.addItems(["PyQt5"])
        combo.setCurrentText(self.browser_type)
        layout.addWidget(combo)
        ok = QPushButton("Apply")
        ok.clicked.connect(lambda: self.set_browser_type(combo.currentText(), dlg))
        layout.addWidget(ok)
        dlg.exec_()

    def set_browser_type(self, value, dlg=None):
        self.browser_type = value
        self.save_config()
        if dlg: dlg.close()
        QMessageBox.information(self, "Browser Type", f"Browser type set to {value}")

    # =====================================================
    # HTML / ダウンロード / Help
    # =====================================================
    def open_html_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open HTML File", "", "HTML Files (*.html *.htm)")
        if file:
            self.add_tab(QUrl.fromLocalFile(file).toString())

    def download_file(self):
        url, ok = QInputDialog.getText(self, "Download File", "Enter URL:")
        if ok and url:
            save_path, _ = QFileDialog.getSaveFileName(self, "Save File")
            if save_path:
                try:
                    import urllib.request
                    urllib.request.urlretrieve(url, save_path)
                    QMessageBox.information(self, "Download Complete", "File downloaded successfully.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Download failed: {e}")

    def show_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Help / About")
        layout = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "PythonWeb DevFull Browser\n"
            "Features:\n"
            "- Multiple tabs\n"
            "- Bookmarks & History\n"
            "- Developer Console with JS, DOM & Network\n"
            "- Themes: Light / Dark / Solarized / AMOLED\n"
            "- View past snapshots (Wayback Machine)\n"
        )
        layout.addWidget(text)
        dlg.exec_()

    # =====================================================
    # 設定保存・読み込み
    # =====================================================
    def save_config(self):
        try:
            data = {
                "home": self.home,
                "theme": self.theme,
                "history": self.history,
                "bookmarks": self.bookmarks,
                "browser_type": self.browser_type
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot save config: {e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

# =====================================================
# メイン起動
# =====================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PythonWeb DevFull Browser")
    win = Browser()
    win.show()
    sys.exit(app.exec_())
