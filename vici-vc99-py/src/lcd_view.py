import json
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl, QPoint, QSettings, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings


HTML_REL = Path("html") / "gemini-code-lcd 2.html"


def _html_path():
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / HTML_REL)
    candidates.append(Path(__file__).resolve().parents[2] / HTML_REL)
    candidates.append(Path.cwd() / HTML_REL)
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


BRIDGE_JS = r"""
(function () {
  window.appSetLive = function (live, port) {
    var status = document.getElementById('status-text');
    if (status) {
      status.innerText = live
        ? ('Połączono: ' + (port || 'UART') + ' (dane z aplikacji)')
        : 'Stan: Rozłączony';
    }
  };
  window.appSetTheme = function (theme) {
    var select = document.getElementById('themeSelect');
    if (select) select.value = theme;
    if (window.changeTheme) window.changeTheme(theme);
  };
})();
"""


class LcdView(QWebEngineView):
    THEME_KEY = "lcd_theme"
    DEFAULT_THEME = "green"
    THEMES = {
        "green", "amber", "cyan", "white", "red",
        "purple", "yellow", "gameboy", "blue", "emerald",
    }
    menuRequested = pyqtSignal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._pending = None
        self._pending_live = None
        self._live = False
        self._html_file = _html_path()
        self._settings = QSettings("VICI", "VC99")

        s = self.settings()
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._emit_menu)
        self.page().setBackgroundColor(QColor("#0b0f12"))
        self.page().titleChanged.connect(self._on_title_changed)
        self.loadFinished.connect(self._on_load)
        self.setUrl(QUrl.fromLocalFile(str(self._html_file)))

    def _emit_menu(self, pos):
        self.menuRequested.emit(pos)

    def _on_title_changed(self, title):
        prefix = "vici-lcd-theme:"
        if not title.startswith(prefix):
            return
        theme = title[len(prefix):].strip()
        if theme not in self.THEMES:
            return
        if self._settings.value(self.THEME_KEY, "", type=str) != theme:
            self._settings.setValue(self.THEME_KEY, theme)
            self._settings.sync()

    def _send_theme(self, theme):
        if theme not in self.THEMES:
            theme = self.DEFAULT_THEME
        self.page().runJavaScript(
            "if (window.appSetTheme) { window.appSetTheme(%s); }"
            % json.dumps(theme))

    def _on_load(self, ok):
        self._ready = bool(ok)
        if not self._ready:
            return
        self.page().runJavaScript(BRIDGE_JS)
        self._send_theme(self._settings.value(
            self.THEME_KEY, self.DEFAULT_THEME, type=str))
        if self._pending_live is not None:
            live, port = self._pending_live
            self._pending_live = None
            self._send_live(live, port)
        if self._pending is not None:
            frame, self._pending = self._pending, None
            self._send_frame(frame)

    def _send_live(self, live, port):
        self.page().runJavaScript(
            "if (window.appSetLive) { window.appSetLive(%s, %s); }"
            % ("true" if live else "false", json.dumps(str(port))))

    def _send_frame(self, frame):
        payload = ",".join(str(int(b)) for b in frame)
        self.page().runJavaScript(
            "if (window.parseRS232Frame) { "
            "window.parseRS232Frame(new Uint8Array([%s])); }" % payload)

    def update_frame(self, frame):
        frame = bytes(frame)
        if not self._ready:
            self._pending = frame
            return
        self._send_frame(frame)

    def set_live(self, live, port=""):
        self._live = bool(live)
        if not self._ready:
            self._pending_live = (self._live, port)
            return
        self._send_live(self._live, port)
