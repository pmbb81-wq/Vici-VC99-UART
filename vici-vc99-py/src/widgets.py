from collections import deque
import datetime
import os

from PyQt5.QtWidgets import QWidget, QSizePolicy, QMenu, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor


class BarGraphWidget(QWidget):
    """Wizualny bargraf miernika: N segmentow, znak, przekroczenie zakresu."""

    def __init__(self, segments=61, parent=None):
        super().__init__(parent)
        self.segments = segments
        self.value = 0
        self.negative = False
        self.visible = False
        self.setMinimumHeight(26)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value, negative=False, visible=True):
        self.value = value
        self.negative = negative
        self.visible = visible
        self.update()

    def clear(self):
        self.value = 0
        self.negative = False
        self.visible = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        w = self.width()
        h = self.height()
        seg = self.segments

        if not self.visible:
            painter.fillRect(0, 0, w, h, QColor("#f5f5f5"))
            painter.setPen(QColor("#aaa"))
            painter.drawText(self.rect(), Qt.AlignCenter, "bargraf nieaktywny")
            return

        gap = 1.0
        seg_w = (w - (seg - 1) * gap) / seg
        overflow = self.value >= seg
        lit = min(max(self.value, 0), seg)

        if overflow:
            lit_color = QColor("#d32f2f")
        elif self.negative:
            lit_color = QColor("#1565c0")
        else:
            lit_color = QColor("#2e7d32")
        off_color = QColor("#e6e6e6")

        for i in range(seg):
            x = i * (seg_w + gap)
            rect = QRectF(x, 0, seg_w, h)
            painter.fillRect(rect, lit_color if i < lit else off_color)

        painter.setPen(QColor("#888"))
        painter.drawRect(0, 0, w - 1, h - 1)


class TrendPlot(QWidget):
    """Mini-wykres trendu wartosci bargrafu w czasie (0..segments)."""

    def __init__(self, max_points=300, scale_max=61, parent=None):
        super().__init__(parent)
        self.data = deque(maxlen=max_points)
        self.scale_max = scale_max
        self.info_text = ""
        self.mode_text = ""
        self.flags_text = ""
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        act_png = menu.addAction("Zapisz wykres jako PNG...")
        act_jpg = menu.addAction("Zapisz wykres jako JPG...")
        menu.addSeparator()
        act_clear = menu.addAction("Wyczyść wykres")
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen == act_png:
            self.save_image("PNG")
        elif chosen == act_jpg:
            self.save_image("JPG")
        elif chosen == act_clear:
            self.clear()

    def save_image(self, fmt):
        default = "vici_vc99_trend_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        start_dir = os.path.join(os.path.expanduser("~"), "Desktop", default + "." + fmt.lower())
        if fmt == "PNG":
            file_filter = "Obraz PNG (*.png)"
        else:
            file_filter = "Obraz JPG (*.jpg *.jpeg)"
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz wykres", start_dir, file_filter)
        if not path:
            return

        pixmap = self.grab()
        save_fmt = "PNG" if fmt == "PNG" else "JPEG"
        ok = pixmap.save(path, save_fmt, 92 if save_fmt == "JPEG" else -1)
        if ok:
            QMessageBox.information(self, "Zapisano", "Wykres zapisano:\n" + path)
        else:
            QMessageBox.critical(self, "Błąd", "Nie udało się zapisać pliku:\n" + path)

    def add_value(self, v):
        self.data.append(v)
        self.update()

    def set_info(self, info="", mode="", flags=""):
        self.info_text = info
        self.mode_text = mode
        self.flags_text = flags
        self.update()

    def clear(self):
        self.data.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#0f1a12"))

        # siatka
        painter.setPen(QColor("#22392a"))
        for frac in (0.25, 0.5, 0.75):
            y = int(h * frac)
            painter.drawLine(0, y, w, y)

        if len(self.data) < 2:
            painter.setPen(QColor("#5a7a63"))
            painter.drawText(self.rect(), Qt.AlignCenter, "trend...")
        else:
            n = len(self.data)
            step = w / max(1, n - 1)
            scale = max(1, self.scale_max)

            painter.setPen(QColor("#43d17a"))
            prev = None
            for i, v in enumerate(self.data):
                x = i * step
                y = h - (min(max(v, 0), scale) / scale) * (h - 4) - 2
                if prev is not None:
                    painter.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
                prev = (x, y)

        # czytelne nakladki tekstowe
        if self.info_text:
            f = painter.font()
            f.setBold(True)
            f.setPointSize(11)
            painter.setFont(f)
            painter.setPen(QColor("#eaffea"))
            painter.drawText(8, 18, self.info_text)

        if self.mode_text:
            f = painter.font()
            f.setBold(True)
            f.setPointSize(9)
            painter.setFont(f)
            painter.setPen(QColor("#9ff0b5"))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.mode_text)
            painter.drawText(w - tw - 8, 17, self.mode_text)

        if self.flags_text:
            f = painter.font()
            f.setBold(False)
            f.setPointSize(8)
            painter.setFont(f)
            painter.setPen(QColor("#e0c85a"))
            painter.drawText(8, h - 6, self.flags_text)

        painter.setPen(QColor("#888"))
        painter.drawRect(0, 0, w - 1, h - 1)


class BgaProfileChart(QWidget):
    """Wykres profilu temperaturowego BGA: plan etapow + wskaznik czasu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stages = []
        self.start_temp = 25.0
        self.elapsed = 0.0
        self.liquidus = None
        self.real = []
        self.real_current = None
        self.real_max = None
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_profile(self, stages, start_temp=25.0, liquidus=None):
        self.stages = list(stages)
        self.start_temp = float(start_temp)
        self.liquidus = float(liquidus) if liquidus else None
        self.update()

    def set_elapsed(self, seconds):
        self.elapsed = max(0.0, float(seconds))
        self.update()

    def add_real_point(self, t, temp):
        self.real.append((float(t), float(temp)))
        self.real_current = float(temp)
        if self.real_max is None or temp > self.real_max:
            self.real_max = float(temp)
        self.update()

    def clear_real(self):
        self.real = []
        self.real_current = None
        self.real_max = None
        self.update()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        act_png = menu.addAction("Zapisz przebieg jako PNG...")
        act_jpg = menu.addAction("Zapisz przebieg jako JPG...")
        menu.addSeparator()
        act_clear = menu.addAction("Wyczyść pomiar (zostaw plan)")
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen == act_png:
            self.save_image("PNG")
        elif chosen == act_jpg:
            self.save_image("JPG")
        elif chosen == act_clear:
            self.clear_real()

    def save_image(self, fmt):
        default = "vici_bga_profil_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        start_dir = os.path.join(os.path.expanduser("~"), "Desktop", default + "." + fmt.lower())
        if fmt == "PNG":
            file_filter = "Obraz PNG (*.png)"
        else:
            file_filter = "Obraz JPG (*.jpg *.jpeg)"
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz przebieg BGA", start_dir, file_filter)
        if not path:
            return
        pixmap = self.grab()
        save_fmt = "PNG" if fmt == "PNG" else "JPEG"
        ok = pixmap.save(path, save_fmt, 92 if save_fmt == "JPEG" else -1)
        if ok:
            QMessageBox.information(self, "Zapisano", "Przebieg zapisano:\n" + path)
        else:
            QMessageBox.critical(self, "Błąd", "Nie udało się zapisać pliku:\n" + path)

    def reset(self):
        self.elapsed = 0.0
        self.update()

    def _total(self):
        return sum(s["dur"] for s in self.stages) or 1.0

    def _temp_max(self):
        vals = [self.start_temp] + [s["end"] for s in self.stages]
        if self.real_max is not None:
            vals.append(self.real_max)
        m = max(vals) if vals else 50.0
        return max(50.0, (int(m / 50.0) + 1) * 50.0)

    def _points(self):
        pts = [(0.0, self.start_temp)]
        t = 0.0
        temp = self.start_temp
        for s in self.stages:
            t += s["dur"]
            temp = s["end"]
            pts.append((t, temp))
        return pts

    def _temp_at(self, t):
        acc = 0.0
        temp = self.start_temp
        for s in self.stages:
            if t <= acc + s["dur"]:
                f = (t - acc) / s["dur"] if s["dur"] > 0 else 0.0
                return temp + (s["end"] - temp) * f
            temp = s["end"]
            acc += s["dur"]
        return temp

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#0f141a"))

        ml, mr, mt, mb = 46, 12, 12, 24
        pw = max(1, w - ml - mr)
        ph = max(1, h - mt - mb)
        total = self._total()
        tmax = self._temp_max()

        def mx(t):
            return ml + (t / total) * pw

        def my(temp):
            return mt + ph - (temp / tmax) * ph

        # tlo etapow
        acc = 0.0
        for s in self.stages:
            x1 = mx(acc)
            x2 = mx(acc + s["dur"])
            c = QColor(s.get("color", "#4aa3ff"))
            c.setAlpha(28)
            painter.fillRect(QRectF(x1, mt, max(1.0, x2 - x1), ph), c)
            acc += s["dur"]

        # siatka temperatura
        painter.setPen(QColor("#26303a"))
        step = 50
        v = 0
        while v <= tmax:
            y = my(v)
            painter.drawLine(ml, int(y), ml + pw, int(y))
            painter.setPen(QColor("#7a8794"))
            painter.drawText(4, int(y) + 4, f"{v}")
            painter.setPen(QColor("#26303a"))
            v += step

        # siatka czas
        for k in range(5):
            t = total * k / 4.0
            x = mx(t)
            painter.setPen(QColor("#26303a"))
            painter.drawLine(int(x), mt, int(x), mt + ph)
            painter.setPen(QColor("#7a8794"))
            sec = int(round(t))
            painter.drawText(int(x) - 14, h - 6, f"{sec // 60}:{sec % 60:02d}")

        # plan
        pts = self._points()
        for i, s in enumerate(self.stages):
            x1, y1 = mx(pts[i][0]), my(pts[i][1])
            x2, y2 = mx(pts[i + 1][0]), my(pts[i + 1][1])
            painter.setPen(QColor(s.get("color", "#4aa3ff")))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            painter.drawText(int((x1 + x2) / 2) - 18, mt + ph - 6, s.get("name", ""))

        # linia liquidus
        if self.liquidus:
            y = my(self.liquidus)
            pen = painter.pen()
            pen.setColor(QColor("#ff9f43"))
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(ml, int(y), ml + pw, int(y))
            pen.setStyle(Qt.SolidLine)
            painter.setPen(QColor("#ffb066"))
            painter.drawText(ml + 4, int(y) - 4, f"liquidus {self.liquidus:.0f} C")

        # rzeczywista temperatura z miernika
        if len(self.real) >= 1:
            painter.setPen(QColor("#e8e8e8"))
            prev = None
            for (t, temp) in self.real:
                x = int(mx(t))
                y = int(my(temp))
                if prev is not None:
                    painter.drawLine(prev[0], prev[1], x, y)
                prev = (x, y)
            if self.real_current is not None:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#25d0ff"))
                painter.drawEllipse(
                    QRectF(mx(self.real[-1][0]) - 4, my(self.real_current) - 4, 8, 8))
                painter.setBrush(Qt.NoBrush)

        # wskaznik
        if self.elapsed > 0:
            x = mx(min(self.elapsed, total))
            temp = self._temp_at(self.elapsed)
            y = my(temp)
            pen = painter.pen()
            pen.setColor(QColor("#ffffff"))
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(int(x), mt, int(x), mt + ph)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QRectF(x - 4, y - 4, 8, 8))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(x) + 6, int(y) - 6, f"{temp:.0f} C")

        painter.setPen(QColor("#3a4652"))
        painter.drawRect(ml, mt, pw, ph)


class BatteryCurveWidget(QWidget):
    """Charakterystyka rozladowania: SoC [%] vs napiecie ogniwa [V]."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.curve = []
        self.full = 4.2
        self.empty = 3.0
        self.v_cell = None
        self.soc = None
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, curve, full, empty, v_cell=None, soc=None):
        self.curve = list(curve)
        self.full = float(full)
        self.empty = float(empty)
        self.v_cell = v_cell
        self.soc = soc
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#0f141a"))

        ml, mr, mt, mb = 48, 14, 14, 26
        pw = max(1, w - ml - mr)
        ph = max(1, h - mt - mb)
        vmin = self.empty
        vmax = self.full
        if vmax <= vmin:
            vmax = vmin + 0.1

        def mx(v):
            return ml + ((v - vmin) / (vmax - vmin)) * pw

        def my(s):
            return mt + ph - (s / 100.0) * ph

        painter.setPen(QColor("#26303a"))
        for s in (0, 25, 50, 75, 100):
            y = my(s)
            painter.drawLine(ml, int(y), ml + pw, int(y))
            painter.setPen(QColor("#7a8794"))
            painter.drawText(4, int(y) + 4, f"{s}%")
            painter.setPen(QColor("#26303a"))

        for k in range(5):
            v = vmin + (vmax - vmin) * k / 4.0
            x = mx(v)
            painter.drawLine(int(x), mt, int(x), mt + ph)
            painter.setPen(QColor("#7a8794"))
            painter.drawText(int(x) - 12, h - 8, f"{v:.2f}")
            painter.setPen(QColor("#26303a"))

        if len(self.curve) >= 2:
            painter.setPen(QColor("#4aa3ff"))
            prev = None
            for (v, s) in sorted(self.curve):
                x = int(mx(v))
                y = int(my(s))
                if prev is not None:
                    painter.drawLine(prev[0], prev[1], x, y)
                prev = (x, y)

        if self.v_cell is not None and self.soc is not None:
            vv = min(max(self.v_cell, vmin), vmax)
            ss = min(max(self.soc, 0.0), 100.0)
            x = mx(vv)
            y = my(ss)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#25d0ff"))
            painter.drawEllipse(QRectF(x - 5, y - 5, 10, 10))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(x) + 8, int(y) - 6, f"{ss:.0f}% @ {vv:.2f}V")

        painter.setPen(QColor("#3a4652"))
        painter.drawRect(ml, mt, pw, ph)


