import sys
import csv
import os
import time
import datetime
from collections import deque
import applog

applog.setup_logging()
from applog import log

try:
    log.info("Import PyQt5.QtWidgets...")
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                 QHBoxLayout, QGroupBox, QLabel, QComboBox,
                                 QPushButton, QFrame, QMessageBox, QProgressBar,
                                 QColorDialog, QFileDialog, QAction, QActionGroup,
                                 QTabWidget, QCheckBox, QSpinBox, QFormLayout,
                                 QDoubleSpinBox, QScrollArea, QGridLayout)
    log.info("Import PyQt5.QtCore...")
    from PyQt5.QtCore import Qt, QTimer, QTime, QSettings, QUrl
    log.info("Import PyQt5.QtGui...")
    from PyQt5.QtGui import QFont, QColor, QDesktopServices
    log.info("Import PyQt5.QtSerialPort...")
    from PyQt5.QtSerialPort import QSerialPortInfo
    log.info("Import vc99_parser...")
    from vc99_parser import VC99Parser, VC99Reading
    log.info("Import serial_device...")
    from serial_device import SerialDevice
    log.info("Import widgets...")
    from widgets import BarGraphWidget, TrendPlot, BgaProfileChart, BatteryCurveWidget
    log.info("Import buzzer...")
    from buzzer import Buzzer
    log.info("Wszystkie importy OK")
except Exception:
    import traceback
    log.error("Blad importu:\n%s", traceback.format_exc())
    raise

class MainWindow(QMainWindow):
    FULL_SCALE_COUNTS = 6000
    BGA_DEFAULTS = [
        ("Preheat", 90, 150, "#4aa3ff"),
        ("Soak", 60, 180, "#ffd24a"),
        ("Reflow", 45, 235, "#ff5a4a"),
        ("Cool", 90, 50, "#4affa3"),
    ]
    # (nazwa, [ (etap, sekundy, temp_C) x4 ], liquidus_C, opis)
    BGA_PRESETS = [
        ("SAC305 (Pb-free) – standard", [
            ("Preheat", 60, 150), ("Soak", 90, 180),
            ("Reflow", 40, 245), ("Cool", 90, 100),
        ], 217, "Bezolowiowe SAC305: topienie 217-218°C, szczyt 240-250°C "
                "(~245), TAL>217 ok. 45-75 s, ramp <2.5°C/s, chlodzenie <4°C/s."),
        ("SAC305 – BGA hot-air rework", [
            ("Preheat", 45, 150), ("Soak", 60, 180),
            ("Reflow", 30, 235), ("Cool", 60, 80),
        ], 217, "Rework BGA na stacji hot-air (mniejsza masa): krotszy profil, "
                "szczyt ~235°C, TAL>217 ok. 30-45 s."),
        ("Sn63Pb37 (olowiowe 183°C)", [
            ("Preheat", 60, 120), ("Soak", 60, 150),
            ("Reflow", 40, 210), ("Cool", 60, 90),
        ], 183, "Eutektyk SnPb: topienie 183°C, szczyt ~205-215°C, "
                "TAL>183 ok. 60-90 s. Dobrze zwilza, nizsza temperatura."),
        ("Sn42Bi58 (bizmut 138°C)", [
            ("Preheat", 60, 100), ("Soak", 60, 125),
            ("Reflow", 40, 175), ("Cool", 60, 60),
        ], 138, "Niskotemperaturowy SnBi: topienie 138°C, szczyt 170-185°C, "
                "chlodzenie <4°C/s. Do elementow wrazliwych termicznie."),
    ]
    # Krzywe rozładowania ogniw: [(napiecie V, SoC %)]
    CURVE_LIION = [(3.00, 0), (3.45, 5), (3.68, 10), (3.74, 20), (3.77, 30),
                   (3.79, 40), (3.82, 50), (3.87, 60), (3.92, 70),
                   (3.98, 80), (4.06, 90), (4.20, 100)]
    CURVE_LIHV = [(3.00, 0), (3.45, 5), (3.70, 10), (3.78, 20), (3.83, 30),
                  (3.88, 40), (3.93, 50), (4.00, 60), (4.08, 70),
                  (4.15, 80), (4.25, 90), (4.35, 100)]
    CURVE_LIFEPO4 = [(2.50, 0), (3.00, 5), (3.20, 10), (3.27, 30), (3.30, 50),
                     (3.33, 70), (3.40, 90), (3.65, 100)]
    CURVE_NIMH = [(1.00, 0), (1.10, 10), (1.15, 20), (1.20, 40),
                  (1.25, 60), (1.30, 80), (1.40, 100)]
    CURVE_NIZN = [(1.20, 0), (1.30, 10), (1.40, 30), (1.50, 50),
                  (1.60, 70), (1.75, 90), (1.85, 100)]
    CURVE_ALKALINE = [(0.90, 0), (1.10, 10), (1.20, 20), (1.28, 40),
                      (1.35, 60), (1.45, 80), (1.60, 100)]
    CURVE_ZNC = [(0.90, 0), (1.10, 10), (1.20, 25), (1.30, 50),
                 (1.40, 75), (1.55, 100)]
    CURVE_LIFES2 = [(0.90, 0), (1.20, 10), (1.35, 30), (1.45, 50),
                    (1.55, 70), (1.70, 90), (1.80, 100)]
    CURVE_SILVER = [(1.20, 0), (1.30, 10), (1.40, 30), (1.50, 60),
                    (1.58, 85), (1.62, 100)]
    CURVE_ZINC_AIR = [(1.00, 0), (1.10, 10), (1.20, 30), (1.30, 60),
                      (1.38, 85), (1.45, 100)]
    CURVE_PB = [(1.75, 0), (1.90, 10), (1.95, 25), (2.00, 50),
                (2.05, 75), (2.10, 100)]
    CURVE_LIMNO2 = [(2.00, 0), (2.40, 5), (2.60, 20), (2.75, 50),
                    (2.85, 75), (3.00, 100)]

    # (nazwa, pelne /ogn., puste /ogn., domyslna liczba ogniw, opis, krzywa)
    BATTERY_TYPES = [
        {"name": "Li-ion / LiPo (3,7 V)", "full": 4.20, "empty": 3.00,
         "cells": 1,
         "note": "Ogniwo 3,6-3,7 V. Pełne 4,20 V, puste ~3,00 V. "
                 "Nie rozładowuj poniżej ~2,5 V.",
         "curve": CURVE_LIION},
        {"name": "LiHV / Li-ion 4,35 V (RC, smartfon)", "full": 4.35,
         "empty": 3.00, "cells": 1,
         "note": "Ogniwo wysokonapięciowe 4,35 V (LiHV, telefony). "
                 "Pełne 4,35 V, puste ~3,00 V.",
         "curve": CURVE_LIHV},
        {"name": "LiFePO4 (3,2 V)", "full": 3.65, "empty": 2.50,
         "cells": 1,
         "note": "Ogniwo 3,2 V, bardzo płaska charakterystyka 3,2-3,3 V. "
                 "Pełne 3,65 V, puste ~2,50 V.",
         "curve": CURVE_LIFEPO4},
        {"name": "NiMH (1,2 V)", "full": 1.40, "empty": 1.00,
         "cells": 1,
         "note": "Ogniwo 1,2 V. Świeżo naładowane może mieć 1,45 V; "
                 "nominalne 1,20 V.",
         "curve": CURVE_NIMH},
        {"name": "NiCd (1,2 V)", "full": 1.40, "empty": 1.00,
         "cells": 1,
         "note": "Ogniwo 1,2 V, charakterystyka zbliżona do NiMH.",
         "curve": CURVE_NIMH},
        {"name": "NiZn (1,6 V)", "full": 1.85, "empty": 1.20,
         "cells": 1,
         "note": "Akumulator niklowo-cynkowy 1,6 V (zamiennik AA). "
                 "Pełny ~1,85 V, pusty ~1,20 V.",
         "curve": CURVE_NIZN},
        {"name": "Alkaliczna (1,5 V)", "full": 1.60, "empty": 0.90,
         "cells": 1,
         "note": "Bateria alkaliczna AA/AAA/C/D. Pełna 1,60 V, pusta ~0,90 V.",
         "curve": CURVE_ALKALINE},
        {"name": "Cynkowo-węglowa (1,5 V)", "full": 1.55, "empty": 0.90,
         "cells": 1,
         "note": "Bateria Zn-C: mniejsza pojemność i szybszy spadek napięcia.",
         "curve": CURVE_ZNC},
        {"name": "Li-FeS2 / litowa AA (1,5 V)", "full": 1.80, "empty": 0.90,
         "cells": 1,
         "note": "Energizer Ultimate Lithium (Li-FeS2). Pełna ~1,80 V, "
                 "bardzo płaska charakterystyka.",
         "curve": CURVE_LIFES2},
        {"name": "Srebrowo-tlenkowa SR (1,55 V)", "full": 1.62, "empty": 1.20,
         "cells": 1,
         "note": "Bateria srebrowa SR44/377. Pełna ~1,62 V, pusta ~1,20 V.",
         "curve": CURVE_SILVER},
        {"name": "Cynkowo-powietrzna (1,4 V)", "full": 1.45, "empty": 1.00,
         "cells": 1,
         "note": "Bateria cynkowo-powietrzna do aparatów słuchowych. "
                 "Pełna ~1,45 V, pusta ~1,00 V.",
         "curve": CURVE_ZINC_AIR},
        {"name": "CR2032 / LiMnO2 (3,0 V)", "full": 3.00, "empty": 2.00,
         "cells": 1,
         "note": "Bateria pastylkowa litowa. Pełna ~3,0 V, pusta ~2,0 V.",
         "curve": CURVE_LIMNO2},
        {"name": "CR2016 (3,0 V)", "full": 3.00, "empty": 2.00,
         "cells": 1,
         "note": "Cienka pastylka litowa (zegarki, piloty). "
                 "Pełna ~3,0 V, pusta ~2,0 V.",
         "curve": CURVE_LIMNO2},
        {"name": "CR123A (3,0 V)", "full": 3.00, "empty": 2.00,
         "cells": 1,
         "note": "Bateria litowa CR123A/CR2 (latarki). Pełna ~3,0 V, "
                 "pusta ~2,0 V.",
         "curve": CURVE_LIMNO2},
        {"name": "LR44 / AG13 (1,5 V)", "full": 1.60, "empty": 0.90,
         "cells": 1,
         "note": "Pastylka alkaliczna LR44/AG13. Pełna ~1,60 V, pusta ~0,90 V.",
         "curve": CURVE_ALKALINE},
        {"name": "9 V alkaliczna (6×1,5 V)", "full": 1.60, "empty": 0.90,
         "cells": 6,
         "note": "Bateria 9 V zbudowana z 6 ogniw alkalicznych 1,5 V. "
                 "Pełna ~9,6 V, pusta ~5,4 V (realnie ~6 V).",
         "curve": CURVE_ALKALINE},
        {"name": "9 V NiMH (7×1,2 V)", "full": 1.40, "empty": 1.00,
         "cells": 7,
         "note": "Akumulator 9 V NiMH z 7 ogniw 1,2 V. "
                 "Pełny ~9,8 V, pusty ~7,0 V.",
         "curve": CURVE_NIMH},
        {"name": "9 V litowa (3×3,0 V)", "full": 3.00, "empty": 2.00,
         "cells": 3,
         "note": "Bateria 9 V litowa (3 ogniwa LiMnO2). "
                 "Pełna ~9,0 V, pusta ~6,0 V.",
         "curve": CURVE_LIMNO2},
        {"name": "Narzędzia 12 V Li-ion (3S)", "full": 4.20, "empty": 3.00,
         "cells": 3,
         "note": "Pakiet wkrętarki 12 V: 3 ogniwa 18650/21700 w szeregu "
                 "(9,0-12,6 V).",
         "curve": CURVE_LIION},
        {"name": "Narzędzia 18/20 V Li-ion (5S)", "full": 4.20, "empty": 3.00,
         "cells": 5,
         "note": "Typowy pakiet 18 V / 20 V Max (DeWalt, Makita, Bosch, "
                 "Milwaukee, Ryobi): 5S, 15,0-21,0 V.",
         "curve": CURVE_LIION},
        {"name": "Narzędzia 36 V Li-ion (10S)", "full": 4.20, "empty": 3.00,
         "cells": 10,
         "note": "Pakiet 36 V (10S, 30-42 V) – mocniejsze wkrętarki, "
                 "pilarki, kosiarki.",
         "curve": CURVE_LIION},
        {"name": "Narzędzia 60 V FlexVolt (15S)", "full": 4.20, "empty": 3.00,
         "cells": 15,
         "note": "DeWalt FlexVolt w trybie 60 V: 15S, 45-63 V "
                 "(w trybie 20 V pracuje jako 5S3P).",
         "curve": CURVE_LIION},
        {"name": "Narzędzia 12 V NiCd/NiMH (10S)", "full": 1.40, "empty": 1.00,
         "cells": 10,
         "note": "Stary pakiet 12 V NiCd/NiMH: 10 ogniw 1,2 V "
                 "(10-14 V).",
         "curve": CURVE_NIMH},
        {"name": "Narzędzia 14,4 V NiCd/NiMH (12S)", "full": 1.40,
         "empty": 1.00, "cells": 12,
         "note": "Pakiet 14,4 V NiCd/NiMH: 12 ogniw 1,2 V (12-16,8 V).",
         "curve": CURVE_NIMH},
        {"name": "Narzędzia 18 V NiCd/NiMH (15S)", "full": 1.40, "empty": 1.00,
         "cells": 15,
         "note": "Pakiet 18 V NiCd/NiMH: 15 ogniw 1,2 V (15-21 V).",
         "curve": CURVE_NIMH},
        {"name": "LiPo RC 2S (7,4 V)", "full": 4.20, "empty": 3.00,
         "cells": 2,
         "note": "Pakiet LiPo 2S do modeli (6,0-8,4 V). "
                 "Przechowuj na ~3,8 V/ogn.",
         "curve": CURVE_LIION},
        {"name": "LiPo RC 3S (11,1 V)", "full": 4.20, "empty": 3.00,
         "cells": 3,
         "note": "Pakiet LiPo 3S do modeli (9,0-12,6 V). "
                 "Przechowuj na ~3,8 V/ogn.",
         "curve": CURVE_LIION},
        {"name": "LiPo RC 6S (22,2 V)", "full": 4.20, "empty": 3.00,
         "cells": 6,
         "note": "Pakiet LiPo 6S do dronów/helikopterów (18-25,2 V). "
                 "Przechowuj na ~3,8 V/ogn.",
         "curve": CURVE_LIION},
        {"name": "Ołowiowa 6 V (3 ogniwa)", "full": 2.10, "empty": 1.75,
         "cells": 3,
         "note": "Akumulator 6 V (latarka, UPS): 3 ogniwa, "
                 "5,25-6,30 V.",
         "curve": CURVE_PB},
        {"name": "Ołowiowa 12 V (6 ogniw)", "full": 2.10, "empty": 1.75,
         "cells": 6,
         "note": "Akumulator 12 V (samochód, UPS, AGM): 6 ogniw, "
                 "10,5-12,6 V.",
         "curve": CURVE_PB},
        {"name": "Ołowiowa 24 V (12 ogniw)", "full": 2.10, "empty": 1.75,
         "cells": 12,
         "note": "Akumulator 24 V (ciężarówki, wózki): 12 ogniw, "
                 "21,0-25,2 V.",
         "curve": CURVE_PB},
        {"name": "LiFePO4 12 V (4S)", "full": 3.65, "empty": 2.50,
         "cells": 4,
         "note": "Pakiet LiFePO4 12 V (4S): 10,0-14,6 V. "
                 "Popularny w kamperach i magazynach energii.",
         "curve": CURVE_LIFEPO4},
        {"name": "LiFePO4 48 V (16S)", "full": 3.65, "empty": 2.50,
         "cells": 16,
         "note": "Pakiet LiFePO4 48 V (16S): 40-58,4 V. "
                 "Magazyny energii, rowery elektryczne.",
         "curve": CURVE_LIFEPO4},
    ]
    APP_NAME = "VICI VC99 PC App"
    APP_VERSION = "1.0"
    AUTHOR = "Krzysztof Nowacki"
    GITHUB_URL = "https://github.com/pmbb81-wq"

    DARK_QSS = """
        QWidget { background-color: #202225; color: #e6e6e6; }
        QGroupBox { border: 1px solid #3a3d42; border-radius: 4px; margin-top: 8px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; color: #b9bdc4; }
        QPushButton { background-color: #2f3136; border: 1px solid #3a3d42;
                      border-radius: 4px; padding: 4px 10px; color: #e6e6e6; }
        QPushButton:hover { background-color: #3a3d42; }
        QPushButton:disabled { color: #777; }
        QComboBox { background-color: #2f3136; border: 1px solid #3a3d42;
                    border-radius: 4px; padding: 2px 6px; color: #e6e6e6; }
        QComboBox QAbstractItemView { background-color: #2f3136; color: #e6e6e6;
                   selection-background-color: #3a3d42; }
        QSpinBox, QDoubleSpinBox { background-color: #2f3136; border: 1px solid #3a3d42;
                   border-radius: 4px; padding: 2px 6px; color: #e6e6e6; }
        QSpinBox:disabled, QDoubleSpinBox:disabled { color: #777; }
        QMenuBar { background-color: #202225; color: #e6e6e6; }
        QMenuBar::item { background: transparent; }
        QMenuBar::item:selected { background: #3a3d42; }
        QMenu { background-color: #2f3136; color: #e6e6e6; border: 1px solid #3a3d42; }
        QMenu::item:selected { background: #3a3d42; }
        QTabWidget::pane { border: 1px solid #3a3d42; background: #202225; }
        QTabBar { background: #202225; }
        QTabBar::tab { background: #2f3136; color: #e6e6e6;
                       padding: 6px 16px; margin-right: 2px;
                       border: 1px solid #3a3d42; border-bottom: none;
                       border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:!selected { color: #b9bdc4; }
        QTabBar::tab:hover { background: #3a3d42; color: #ffffff; }
        QTabBar::tab:selected { background: #4a4d52; color: #ffffff; font-weight: bold; }
        QCheckBox { color: #e6e6e6; }
        QLabel { background: transparent; }
        QMessageBox { background-color: #202225; }
    """

    def __init__(self):
        super().__init__()
        self.serial = SerialDevice(self)
        self.buzzer = Buzzer()
        self.ports_timer = QTimer(self)
        self.display_color = QColor("#000000")
        self.color_customized = False
        self.theme = "light"
        self.settings = QSettings("VICI", "VC99")
        self.saved_port = self.settings.value("last_port", "", type=str)

        self.csv_file = None
        self.csv_writer = None
        self.csv_path = ""
        self.recording = False
        self.blink_state = False
        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(500)
        self.blink_timer.timeout.connect(self.on_blink)

        self.stat_count = 0
        self.stat_min = None
        self.stat_max = None
        self.stat_sum = 0.0

        self._frame_stamps = deque(maxlen=400)
        self._last_frame_time = None

        self.init_ui()
        self.refresh_ports()
        
        self.serial.frameReceived.connect(self.on_frame_received)
        self.serial.connectedChanged.connect(self.on_connected_changed)
        self.serial.errorOccurred.connect(self.on_error)
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.connect_btn.clicked.connect(self.toggle_connect)
        self.port_combo.currentIndexChanged.connect(self.on_port_changed)
        
        self.ports_timer.setInterval(1500)
        self.ports_timer.timeout.connect(self.on_auto_refresh_ports)
        self.ports_timer.start()

        self.status_message = ""
        self.status_error = False
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(250)
        self.clock_timer.timeout.connect(self.refresh_status_clock)
        self.clock_timer.start()
        
        self.setWindowTitle("VICI VC99 - UART Reader")
        self.setMinimumSize(460, 480)
        self.resize(520, 540)
        self.apply_theme(self.settings.value("theme", "light", type=str))
        self.set_status("Gotowy", False)
    
    def init_ui(self):
        self.build_menu()
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        tab_font = self.tabs.tabBar().font()
        tab_font.setBold(True)
        self.tabs.tabBar().setFont(tab_font)
        outer.addWidget(self.tabs)

        meas_tab = QWidget()
        main_layout = QVBoxLayout(meas_tab)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)
        self.tabs.addTab(meas_tab, "Pomiary")
        
        port_box = QGroupBox("Port szeregowy (2400 8N1)")
        port_layout = QHBoxLayout(port_box)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        self.refresh_btn = QPushButton("Odśwież")
        self.connect_btn = QPushButton("Połącz")
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_btn)
        port_layout.addStretch()
        port_layout.addWidget(self.connect_btn)
        main_layout.addWidget(port_box)
        
        display_frame = QFrame()
        display_frame.setFrameShape(QFrame.StyledPanel)
        display_frame.setFrameShadow(QFrame.Raised)
        disp_layout = QVBoxLayout(display_frame)
        disp_layout.setSpacing(6)
        
        val_row = QHBoxLayout()
        val_row.setSpacing(8)
        
        self.value_label = QLabel("0.000")
        vf = self.value_label.font()
        vf.setPointSize(48)
        vf.setBold(True)
        self.value_label.setFont(vf)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.suffix_label = QLabel("V")
        sf = self.suffix_label.font()
        sf.setPointSize(36)
        self.suffix_label.setFont(sf)
        self.suffix_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.suffix_label.setContentsMargins(0, 0, 0, 8)

        val_row.addStretch(1)
        val_row.addWidget(self.value_label, 0)
        val_row.addWidget(self.suffix_label, 0)
        disp_layout.addLayout(val_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.FULL_SCALE_COUNTS)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / 6000 counts")
        self.progress_bar.setFixedHeight(22)
        disp_layout.addWidget(self.progress_bar)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(8)
        self.bar_caption = QLabel("BAR")
        bcf = self.bar_caption.font()
        bcf.setPointSize(10)
        bcf.setBold(True)
        self.bar_caption.setFont(bcf)
        self.bar_caption.setFixedWidth(34)
        self.bargraph = BarGraphWidget(segments=61)
        self.bar_value_label = QLabel("--/61")
        self.bar_value_label.setMinimumWidth(64)
        self.bar_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bar_row.addWidget(self.bar_caption, 0)
        bar_row.addWidget(self.bargraph, 1)
        bar_row.addWidget(self.bar_value_label, 0)
        disp_layout.addLayout(bar_row)

        self.stats_label = QLabel("Min: --   Max: --   AVG: --")
        self.stats_label.setStyleSheet("color: #555;")
        disp_layout.addWidget(self.stats_label)

        self.trend_plot = TrendPlot(max_points=300, scale_max=61)
        disp_layout.addWidget(self.trend_plot)

        mode_row = QHBoxLayout()
        self.mode_label = QLabel("DC AUTO")
        mf = self.mode_label.font()
        mf.setPointSize(14)
        self.mode_label.setFont(mf)
        self.mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.color_btn = QPushButton("Kolor")
        self.color_btn.setToolTip("Zmień kolor czcionki wyniku")
        self.color_btn.clicked.connect(self.choose_color)

        self.csv_btn = QPushButton("Zapis CSV")
        self.csv_btn.setToolTip("Zapisuj pomiary do pliku CSV")
        self.csv_btn.clicked.connect(self.toggle_csv)

        self.extra_label = QLabel()
        self.extra_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.extra_label.setStyleSheet("color: gray;")

        mode_row.addWidget(self.mode_label, 0)
        mode_row.addStretch()
        mode_row.addWidget(self.extra_label, 0)
        mode_row.addWidget(self.csv_btn, 0)
        mode_row.addWidget(self.color_btn, 0)
        disp_layout.addLayout(mode_row)
        main_layout.addWidget(display_frame, 1)
        
        self.raw_label = QLabel("RAW: --")
        self.raw_label.setStyleSheet("color: #666; font-family: Consolas, 'Courier New', monospace; font-size: 9pt;")
        self.raw_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.raw_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        main_layout.addWidget(self.raw_label)
        
        self.status_label = QLabel("Status")
        main_layout.addWidget(self.status_label)

        self.build_options_tab()
        self.build_bga_tab()
        self.build_battery_tab()

    def _tune_form(self, form):
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)

    def build_options_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setMinimumWidth(440)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        grp = QGroupBox("Brzęczyk – tryb ciągłości")
        form = QFormLayout(grp)
        self._tune_form(form)

        self.buzzer_cb = QCheckBox("Dźwięk przy zwarciu")
        self.buzzer_cb.setChecked(self.settings.value("buzzer_enabled", False, type=bool))

        self.freq_spin = QSpinBox()
        self.freq_spin.setRange(100, 15000)
        self.freq_spin.setSingleStep(100)
        self.freq_spin.setSuffix(" Hz")
        self.freq_spin.setMinimumWidth(120)
        self.freq_spin.setValue(self.settings.value("buzzer_freq", 2700, type=int))

        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(0, 100)
        self.vol_spin.setSuffix(" %")
        self.vol_spin.setMinimumWidth(80)
        self.vol_spin.setValue(self.settings.value("buzzer_volume", 60, type=int))

        self.thr_spin = QSpinBox()
        self.thr_spin.setRange(1, 600)
        self.thr_spin.setSuffix(" \u03a9")
        self.thr_spin.setMinimumWidth(100)
        self.thr_spin.setValue(self.settings.value("buzzer_threshold", 30, type=int))

        self.test_btn = QPushButton("Test dźwięku")
        self.test_btn.clicked.connect(self.test_buzzer)

        form.addRow(self.buzzer_cb)
        form.addRow("Częstotliwość:", self.freq_spin)
        form.addRow("Głośność:", self.vol_spin)
        form.addRow("Próg zwarcia:", self.thr_spin)
        form.addRow("", self.test_btn)
        layout.addWidget(grp)

        dgrp = QGroupBox("Tryb diody (jak ZOYI 706S)")
        dform = QFormLayout(dgrp)
        self._tune_form(dform)

        self.diode_cb = QCheckBox("Dźwięk w trybie diody")
        self.diode_cb.setChecked(self.settings.value("diode_enabled", False, type=bool))

        self.diode_freq_spin = QSpinBox()
        self.diode_freq_spin.setRange(100, 15000)
        self.diode_freq_spin.setSingleStep(100)
        self.diode_freq_spin.setSuffix(" Hz")
        self.diode_freq_spin.setMinimumWidth(120)
        self.diode_freq_spin.setValue(self.settings.value("diode_freq", 2700, type=int))

        self.diode_vol_spin = QSpinBox()
        self.diode_vol_spin.setRange(0, 100)
        self.diode_vol_spin.setSuffix(" %")
        self.diode_vol_spin.setMinimumWidth(80)
        self.diode_vol_spin.setValue(self.settings.value("diode_volume", 60, type=int))

        self.diode_beep_spin = QSpinBox()
        self.diode_beep_spin.setRange(10, 1000)
        self.diode_beep_spin.setSingleStep(10)
        self.diode_beep_spin.setSuffix(" ms")
        self.diode_beep_spin.setMinimumWidth(110)
        self.diode_beep_spin.setValue(self.settings.value("diode_beep_ms", 60, type=int))

        self.diode_gap_spin = QSpinBox()
        self.diode_gap_spin.setRange(20, 2000)
        self.diode_gap_spin.setSingleStep(10)
        self.diode_gap_spin.setSuffix(" ms")
        self.diode_gap_spin.setMinimumWidth(110)
        self.diode_gap_spin.setValue(self.settings.value("diode_gap_ms", 120, type=int))

        self.diode_repeat_spin = QSpinBox()
        self.diode_repeat_spin.setRange(200, 10000)
        self.diode_repeat_spin.setSingleStep(100)
        self.diode_repeat_spin.setSuffix(" ms")
        self.diode_repeat_spin.setMinimumWidth(120)
        self.diode_repeat_spin.setValue(
            self.settings.value("diode_repeat_ms", 1500, type=int))

        self.diode_thr_spin = QDoubleSpinBox()
        self.diode_thr_spin.setRange(0.05, 1.5)
        self.diode_thr_spin.setSingleStep(0.05)
        self.diode_thr_spin.setDecimals(2)
        self.diode_thr_spin.setSuffix(" V")
        self.diode_thr_spin.setMinimumWidth(100)
        self.diode_thr_spin.setValue(
            self.settings.value("diode_schottky_v", 0.40, type=float))

        self.diode_min_spin = QDoubleSpinBox()
        self.diode_min_spin.setRange(0.01, 1.0)
        self.diode_min_spin.setSingleStep(0.01)
        self.diode_min_spin.setDecimals(2)
        self.diode_min_spin.setSuffix(" V")
        self.diode_min_spin.setMinimumWidth(100)
        self.diode_min_spin.setValue(
            self.settings.value("diode_min_v", 0.10, type=float))

        self.diode_test_btn = QPushButton("Test wzoru (1/2 piski)")
        self.diode_test_btn.clicked.connect(self.test_diode_buzzer)

        self.diode_short_cb = QCheckBox("Piszcz przy zwarciu (0.000 V)")
        self.diode_short_cb.setChecked(
            self.settings.value("diode_short_enabled", True, type=bool))

        self.diode_short_spin = QDoubleSpinBox()
        self.diode_short_spin.setRange(0.001, 0.100)
        self.diode_short_spin.setSingleStep(0.005)
        self.diode_short_spin.setDecimals(3)
        self.diode_short_spin.setSuffix(" V")
        self.diode_short_spin.setMinimumWidth(100)
        self.diode_short_spin.setValue(
            self.settings.value("diode_short_v", 0.020, type=float))

        dform.addRow(self.diode_cb)
        dform.addRow(self.diode_short_cb)
        dform.addRow("Próg zwarcia:", self.diode_short_spin)
        dform.addRow("Częstotliwość piknięcia:", self.diode_freq_spin)
        dform.addRow("Głośność:", self.diode_vol_spin)
        dform.addRow("Czas piknięcia:", self.diode_beep_spin)
        dform.addRow("Odstęp przy 2 piskach:", self.diode_gap_spin)
        dform.addRow("Powtarzaj co:", self.diode_repeat_spin)
        dform.addRow("Próg Schottky'ego:", self.diode_thr_spin)
        dform.addRow("Min. napięcie diody:", self.diode_min_spin)
        dform.addRow("", self.diode_test_btn)
        layout.addWidget(dgrp)

        tts_grp = QGroupBox("Mowa (TTS) – wkrótce")
        tts_form = QFormLayout(tts_grp)
        self._tune_form(tts_form)
        self.tts_cb = QCheckBox("Czytaj wynik głosem")
        self.tts_cb.setEnabled(False)
        self.tts_lang = QComboBox()
        self.tts_lang.addItems(["Polski", "English"])
        self.tts_lang.setMinimumWidth(140)
        self.tts_lang.setEnabled(False)
        tts_form.addRow(self.tts_cb)
        tts_form.addRow("Język:", self.tts_lang)
        layout.addWidget(tts_grp)

        layout.addStretch()

        # zapamietywanie ustawien
        self.buzzer_cb.stateChanged.connect(self.save_options)
        self.freq_spin.valueChanged.connect(self.save_options)
        self.vol_spin.valueChanged.connect(self.save_options)
        self.thr_spin.valueChanged.connect(self.save_options)
        self.buzzer_cb.stateChanged.connect(self.on_buzzer_toggle)

        self.diode_cb.stateChanged.connect(self.save_options)
        self.diode_freq_spin.valueChanged.connect(self.save_options)
        self.diode_vol_spin.valueChanged.connect(self.save_options)
        self.diode_beep_spin.valueChanged.connect(self.save_options)
        self.diode_gap_spin.valueChanged.connect(self.save_options)
        self.diode_repeat_spin.valueChanged.connect(self.save_options)
        self.diode_thr_spin.valueChanged.connect(self.save_options)
        self.diode_min_spin.valueChanged.connect(self.save_options)
        self.diode_short_cb.stateChanged.connect(self.save_options)
        self.diode_short_spin.valueChanged.connect(self.save_options)
        self.diode_cb.stateChanged.connect(self.on_buzzer_toggle)

        self.options_tab = tab
        self.tabs.addTab(tab, "Opcje")

    def build_bga_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setMinimumWidth(460)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.bga_chart = BgaProfileChart()
        layout.addWidget(self.bga_chart, 1)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Profil spoiwa:"))
        self.bga_preset_combo = QComboBox()
        self.bga_preset_combo.addItem("Własny profil")
        for name, _stages, _liq, _note in self.BGA_PRESETS:
            self.bga_preset_combo.addItem(name)
        self.bga_preset_combo.setMinimumWidth(240)
        self.bga_preset_combo.currentIndexChanged.connect(self.load_bga_preset)
        preset_row.addWidget(self.bga_preset_combo, 1)
        layout.addLayout(preset_row)

        self.bga_note_lbl = QLabel()
        self.bga_note_lbl.setWordWrap(True)
        self.bga_note_lbl.setStyleSheet("color: #9aa4ae; font-size: 9pt;")
        layout.addWidget(self.bga_note_lbl)

        grid_grp = QGroupBox("Etapy profilu")
        grid = QGridLayout(grid_grp)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for c, hdr in enumerate(("Etap", "Czas [s]", "Temp. [\u00b0C]")):
            hl = QLabel(hdr)
            hf = hl.font()
            hf.setBold(True)
            hl.setFont(hf)
            grid.addWidget(hl, 0, c)

        self.bga_rows = []
        for i, (name, dur, temp, color) in enumerate(self.BGA_DEFAULTS):
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

            dur_spin = QSpinBox()
            dur_spin.setRange(1, 600)
            dur_spin.setSuffix(" s")
            dur_spin.setMinimumWidth(90)
            dur_spin.setValue(self.settings.value(f"bga_dur_{i}", dur, type=int))

            temp_spin = QSpinBox()
            temp_spin.setRange(20, 300)
            temp_spin.setSuffix(" \u00b0C")
            temp_spin.setMinimumWidth(90)
            temp_spin.setValue(self.settings.value(f"bga_temp_{i}", temp, type=int))

            grid.addWidget(lbl, i + 1, 0)
            grid.addWidget(dur_spin, i + 1, 1)
            grid.addWidget(temp_spin, i + 1, 2)
            dur_spin.valueChanged.connect(self.update_bga_profile)
            temp_spin.valueChanged.connect(self.update_bga_profile)
            self.bga_rows.append((dur_spin, temp_spin))
        layout.addWidget(grid_grp)

        status_row = QHBoxLayout()
        self.bga_stage_lbl = QLabel("Etap: --")
        self.bga_temp_lbl = QLabel("Temp.: -- \u00b0C")
        self.bga_live_lbl = QLabel("Pomiar: --")
        self.bga_live_lbl.setStyleSheet("color: #25d0ff; font-weight: bold;")
        self.bga_elapsed_lbl = QLabel("Czas: 00:00 / 00:00")
        status_row.addWidget(self.bga_stage_lbl)
        status_row.addWidget(self.bga_temp_lbl)
        status_row.addWidget(self.bga_live_lbl)
        status_row.addStretch()
        status_row.addWidget(self.bga_elapsed_lbl)
        layout.addLayout(status_row)

        self.bga_hint_lbl = QLabel("Podłącz miernik (tryb temperatury) i uruchom profil.")
        self.bga_hint_lbl.setWordWrap(True)
        self.bga_hint_lbl.setStyleSheet("color: #b9bdc4; font-weight: bold;")
        layout.addWidget(self.bga_hint_lbl)

        self.bga_progress = QProgressBar()
        self.bga_progress.setRange(0, 1000)
        self.bga_progress.setValue(0)
        self.bga_progress.setFixedHeight(20)
        layout.addWidget(self.bga_progress)

        btn_row = QHBoxLayout()
        self.bga_start_btn = QPushButton("Start")
        self.bga_start_btn.clicked.connect(self.bga_start)
        self.bga_stop_btn = QPushButton("Stop")
        self.bga_stop_btn.setEnabled(False)
        self.bga_stop_btn.clicked.connect(self.bga_stop)
        self.bga_reset_btn = QPushButton("Reset")
        self.bga_reset_btn.clicked.connect(self.bga_reset)
        self.bga_csv_btn = QPushButton("Zapis CSV")
        self.bga_csv_btn.setCheckable(True)
        self.bga_csv_btn.clicked.connect(self.toggle_bga_csv)
        self.bga_sound_cb = QCheckBox("Dźwięk na zmianę etapu")
        self.bga_sound_cb.setChecked(self.settings.value("bga_sound", True, type=bool))
        self.bga_sound_cb.stateChanged.connect(
            lambda *a: self.settings.setValue("bga_sound", self.bga_sound_cb.isChecked()))

        btn_row.addWidget(self.bga_start_btn)
        btn_row.addWidget(self.bga_stop_btn)
        btn_row.addWidget(self.bga_reset_btn)
        btn_row.addWidget(self.bga_csv_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.bga_sound_cb)
        layout.addLayout(btn_row)
        layout.addStretch()

        self.bga_timer = QTimer(self)
        self.bga_timer.setInterval(200)
        self.bga_timer.timeout.connect(self.bga_tick)
        self.bga_running = False
        self.bga_elapsed = 0.0
        self.bga_last_stage = -1
        self.bga_real_t = None
        self._bga_loading = False
        self.bga_csv_file = None

        self.bga_tab = tab
        self.tabs.addTab(tab, "BGA HOT-AIR")

        saved_idx = self.settings.value("bga_preset", 1, type=int)
        self.bga_preset_combo.blockSignals(True)
        self.bga_preset_combo.setCurrentIndex(saved_idx)
        self.bga_preset_combo.blockSignals(False)
        self.load_bga_preset(saved_idx)

    def bga_stages(self):
        stages = []
        for (name, dur, temp, color), (ds, ts) in zip(self.BGA_DEFAULTS, self.bga_rows):
            stages.append({
                "name": name,
                "dur": float(ds.value()),
                "end": float(ts.value()),
                "color": color,
            })
        return stages

    @staticmethod
    def _fmt_time(sec):
        sec = int(round(sec))
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def bga_liquidus(self):
        idx = self.bga_preset_combo.currentIndex()
        if 1 <= idx <= len(self.BGA_PRESETS):
            return self.BGA_PRESETS[idx - 1][2]
        return None

    def load_bga_preset(self, idx):
        self.settings.setValue("bga_preset", idx)
        if idx <= 0:
            self.bga_note_lbl.setText(
                "Własny profil – ustaw czasy i temperatury etapów ręcznie.")
            self.update_bga_profile()
            return
        _name, stages, _liquidus, note = self.BGA_PRESETS[idx - 1]
        self._bga_loading = True
        for (_sname, dur, temp), (ds, ts) in zip(stages, self.bga_rows):
            ds.setValue(dur)
            ts.setValue(temp)
        self.bga_note_lbl.setText(note)
        self.update_bga_profile()
        self._bga_loading = False

    def update_bga_profile(self, *args):
        stages = self.bga_stages()
        total = sum(s["dur"] for s in stages)
        self.bga_chart.set_profile(stages, 25.0, self.bga_liquidus())
        if not self._bga_loading and self.bga_preset_combo.currentIndex() != 0:
            self.bga_preset_combo.blockSignals(True)
            self.bga_preset_combo.setCurrentIndex(0)
            self.bga_preset_combo.blockSignals(False)
            self.bga_note_lbl.setText("Własny profil – zmodyfikowany ręcznie.")
            self.settings.setValue("bga_preset", 0)
        if not self.bga_running:
            self.bga_chart.set_elapsed(0.0)
            self.bga_elapsed_lbl.setText(
                f"Czas: {self._fmt_time(0)} / {self._fmt_time(total)}")
        for i, (ds, ts) in enumerate(self.bga_rows):
            self.settings.setValue(f"bga_dur_{i}", ds.value())
            self.settings.setValue(f"bga_temp_{i}", ts.value())

    def bga_state_at(self, t, stages):
        temp = 25.0
        acc = 0.0
        for i, s in enumerate(stages):
            if t <= acc + s["dur"]:
                f = (t - acc) / s["dur"] if s["dur"] > 0 else 0.0
                return temp + (s["end"] - temp) * f, i
            temp = s["end"]
            acc += s["dur"]
        return (stages[-1]["end"] if stages else 25.0), max(0, len(stages) - 1)

    def bga_start(self):
        stages = self.bga_stages()
        total = sum(s["dur"] for s in stages)
        if total <= 0:
            return
        self.bga_elapsed = 0.0
        self.bga_last_stage = -1
        self.bga_running = True
        self.bga_real_t = None
        self.bga_chart.set_profile(stages, 25.0, self.bga_liquidus())
        self.bga_chart.clear_real()
        if self.bga_csv_btn.isChecked():
            self.start_bga_csv()
        self.bga_timer.start()
        self.bga_start_btn.setEnabled(False)
        self.bga_stop_btn.setEnabled(True)
        for ds, ts in self.bga_rows:
            ds.setEnabled(False)
            ts.setEnabled(False)
        self.bga_tick()

    def bga_stop(self):
        self.bga_timer.stop()
        self.bga_running = False
        self.bga_start_btn.setEnabled(True)
        self.bga_stop_btn.setEnabled(False)
        for ds, ts in self.bga_rows:
            ds.setEnabled(True)
            ts.setEnabled(True)

    def bga_reset(self):
        self.bga_stop()
        self.bga_elapsed = 0.0
        self.bga_last_stage = -1
        self.bga_real_t = None
        self.bga_chart.clear_real()
        self.bga_chart.set_elapsed(0.0)
        self.bga_progress.setValue(0)
        self.bga_stage_lbl.setText("Etap: --")
        self.bga_temp_lbl.setText("Temp.: -- \u00b0C")
        self.bga_hint_lbl.setText("Podłącz miernik (tryb temperatury) i uruchom profil.")
        total = sum(s["dur"] for s in self.bga_stages())
        self.bga_elapsed_lbl.setText(
            f"Czas: {self._fmt_time(0)} / {self._fmt_time(total)}")
        self.stop_bga_csv()

    def bga_tick(self):
        stages = self.bga_stages()
        total = sum(s["dur"] for s in stages)
        if total <= 0:
            self.bga_stop()
            return
        self.bga_elapsed += self.bga_timer.interval() / 1000.0
        finished = self.bga_elapsed >= total
        if finished:
            self.bga_elapsed = total

        temp, stage_idx = self.bga_state_at(self.bga_elapsed, stages)
        if (not finished and self.bga_running
                and self.bga_last_stage >= 0
                and stage_idx != self.bga_last_stage):
            self.bga_beep(1)
        self.bga_last_stage = stage_idx

        self.bga_chart.set_elapsed(self.bga_elapsed)
        self.bga_progress.setValue(int(1000 * self.bga_elapsed / total))
        self.bga_elapsed_lbl.setText(
            f"Czas: {self._fmt_time(self.bga_elapsed)} / {self._fmt_time(total)}")
        self.bga_temp_lbl.setText(f"Temp.: {temp:.0f} \u00b0C")
        if finished:
            self.bga_stage_lbl.setText("Etap: Koniec")
            self.bga_beep(3)
            self.bga_stop()
        elif self.bga_running:
            self.bga_stage_lbl.setText(f"Etap: {stages[stage_idx]['name']}")

    def bga_beep(self, count=1):
        if not self.bga_sound_cb.isChecked():
            return
        beep_ms, gap_ms = 110, 80
        period = count * (beep_ms + gap_ms)
        self.buzzer.play_pattern(2400, 0.6, count, beep_ms, gap_ms, period)
        QTimer.singleShot(period + 60, self.buzzer.stop)

    def on_temperature(self, reading):
        if not hasattr(self, "bga_chart"):
            return
        if not (reading.celsius or reading.fahrenheit):
            return
        if not reading.has_value:
            self.bga_live_lbl.setText("Pomiar: O.L")
            return
        temp_c = reading.value if reading.celsius else (reading.value - 32.0) * 5.0 / 9.0
        self.bga_live_lbl.setText(f"Pomiar: {temp_c:.1f} \u00b0C")
        if not self.bga_running:
            return
        if self.bga_real_t is None or (self.bga_elapsed - self.bga_real_t) >= 0.2:
            self.bga_real_t = self.bga_elapsed
            self.bga_chart.add_real_point(self.bga_elapsed, temp_c)
            self._bga_log_row(self.bga_elapsed, temp_c)
        self._bga_guidance(temp_c)

    def _bga_guidance(self, real_c):
        stages = self.bga_stages()
        total = sum(s["dur"] for s in stages)
        if total <= 0:
            return
        if self.bga_elapsed >= total:
            self.bga_hint_lbl.setText(
                "Koniec profilu – chłodzenie zakończone. Zdejmij płytę.")
            return
        plan, idx = self.bga_state_at(self.bga_elapsed, stages)
        delta = real_c - plan
        stage = stages[idx]["name"]
        base = {
            "Preheat": "Podgrzewanie – równomiernie nagrzewaj płytę",
            "Soak": "Aktywacja topnika – ustabilizuj temperaturę",
            "Reflow": "Reflow – doprowadź do szczytu",
            "Cool": "Chłodzenie – nie przyspieszaj",
        }.get(stage, stage)
        if abs(delta) <= 10:
            tip = "OK"
        elif delta < -20:
            tip = "ZA ZIMNO: zwiększ moc / dmuch"
        elif delta > 20:
            tip = "ZA GORĄCO: zmniejsz moc / dmuch"
        elif delta < 0:
            tip = "trochę za zimno"
        else:
            tip = "trochę za gorąco"
        self.bga_hint_lbl.setText(
            f"{base} | plan {plan:.0f}\u00b0C, jest {real_c:.0f}\u00b0C "
            f"(\u0394{delta:+.0f}) – {tip}")

    def toggle_bga_csv(self):
        if self.bga_csv_btn.isChecked():
            self.start_bga_csv()
        else:
            self.stop_bga_csv()

    def start_bga_csv(self):
        default = "vici_bga_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
        path = os.path.join(os.path.expanduser("~"), "Desktop", default)
        try:
            self.bga_csv_file = open(path, "w", encoding="utf-8", newline="")
            self.bga_csv_file.write("czas_s,zadana_C,rzeczywista_C\n")
            self.bga_csv_btn.setChecked(True)
            self.bga_csv_btn.setText("Zapis CSV \u25cf")
            self.set_status("Zapis profilu BGA: " + path, False)
        except Exception as e:
            self.bga_csv_btn.setChecked(False)
            self.bga_csv_btn.setText("Zapis CSV")
            self.bga_csv_file = None
            QMessageBox.warning(self, "Błąd", f"Nie można zapisać CSV:\n{e}")

    def stop_bga_csv(self):
        if self.bga_csv_file:
            try:
                self.bga_csv_file.close()
            except Exception:
                pass
        self.bga_csv_file = None
        self.bga_csv_btn.setChecked(False)
        self.bga_csv_btn.setText("Zapis CSV")

    def _bga_log_row(self, elapsed, real_c):
        if not self.bga_csv_file:
            return
        try:
            plan, _ = self.bga_state_at(elapsed, self.bga_stages())
            self.bga_csv_file.write(f"{elapsed:.1f},{plan:.1f},{real_c:.1f}\n")
            self.bga_csv_file.flush()
        except Exception:
            pass

    def build_battery_tab(self):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setMinimumWidth(460)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        cfg = QGroupBox("Bateria")
        form = QFormLayout(cfg)
        self._tune_form(form)

        self.bat_type_combo = QComboBox()
        for t in self.BATTERY_TYPES:
            self.bat_type_combo.addItem(t["name"])
        self.bat_type_combo.addItem("Własny (liniowy)")
        self.bat_type_combo.setMinimumWidth(240)

        self.bat_cells_spin = QSpinBox()
        self.bat_cells_spin.setRange(1, 24)
        self.bat_cells_spin.setSuffix(" ogniw")
        self.bat_cells_spin.setMinimumWidth(110)

        self.bat_full_spin = QDoubleSpinBox()
        self.bat_full_spin.setRange(0.5, 60.0)
        self.bat_full_spin.setDecimals(2)
        self.bat_full_spin.setSingleStep(0.05)
        self.bat_full_spin.setSuffix(" V")
        self.bat_full_spin.setMinimumWidth(110)

        self.bat_empty_spin = QDoubleSpinBox()
        self.bat_empty_spin.setRange(0.1, 50.0)
        self.bat_empty_spin.setDecimals(2)
        self.bat_empty_spin.setSingleStep(0.05)
        self.bat_empty_spin.setSuffix(" V")
        self.bat_empty_spin.setMinimumWidth(110)

        form.addRow("Typ baterii:", self.bat_type_combo)
        form.addRow("Liczba ogniw (szeregowo):", self.bat_cells_spin)
        form.addRow("Napięcie pełne /ogn.:", self.bat_full_spin)
        form.addRow("Napięcie puste /ogn.:", self.bat_empty_spin)
        layout.addWidget(cfg)

        self.bat_curve = BatteryCurveWidget()
        layout.addWidget(self.bat_curve, 1)

        self.bat_soc_lbl = QLabel("SoC: --%")
        sf = self.bat_soc_lbl.font()
        sf.setPointSize(28)
        sf.setBold(True)
        self.bat_soc_lbl.setFont(sf)
        self.bat_volt_lbl = QLabel("Napięcie: --")
        self.bat_status_lbl = QLabel("Status: --")
        layout.addWidget(self.bat_soc_lbl)
        layout.addWidget(self.bat_volt_lbl)
        layout.addWidget(self.bat_status_lbl)

        self.bat_progress = QProgressBar()
        self.bat_progress.setRange(0, 100)
        self.bat_progress.setValue(0)
        self.bat_progress.setFixedHeight(22)
        layout.addWidget(self.bat_progress)

        self.bat_note_lbl = QLabel()
        self.bat_note_lbl.setWordWrap(True)
        self.bat_note_lbl.setStyleSheet("color: #9aa4ae; font-size: 9pt;")
        layout.addWidget(self.bat_note_lbl)
        layout.addStretch()

        self._bat_last_v = None

        idx = self.settings.value("bat_type", 0, type=int)
        self.bat_cells_spin.setValue(self.settings.value("bat_cells", 1, type=int))
        self.bat_full_spin.setValue(self.settings.value("bat_full", 4.20, type=float))
        self.bat_empty_spin.setValue(self.settings.value("bat_empty", 3.00, type=float))
        self.bat_type_combo.blockSignals(True)
        self.bat_type_combo.setCurrentIndex(
            max(0, min(idx, self.bat_type_combo.count() - 1)))
        self.bat_type_combo.blockSignals(False)

        self.bat_type_combo.currentIndexChanged.connect(self.on_bat_type_changed)
        self.bat_cells_spin.valueChanged.connect(self.on_bat_cells)
        self.bat_full_spin.valueChanged.connect(self.apply_battery_type)
        self.bat_empty_spin.valueChanged.connect(self.apply_battery_type)

        self.apply_battery_type()

        self.battery_tab = tab
        self.tabs.addTab(tab, "Battery SoC")

    def battery_current_curve(self):
        idx = self.bat_type_combo.currentIndex()
        if 0 <= idx < len(self.BATTERY_TYPES):
            t = self.BATTERY_TYPES[idx]
            return t["curve"], t["full"], t["empty"], t["note"]
        full = self.bat_full_spin.value()
        empty = self.bat_empty_spin.value()
        return ([(empty, 0), (full, 100)], full, empty,
                "Własny profil – liniowa estymacja między napięciem pustym "
                "i pełnym.")

    @staticmethod
    def soc_from_voltage(v, curve):
        pts = sorted(curve)
        if not pts:
            return 0.0
        if v <= pts[0][0]:
            return 0.0
        if v >= pts[-1][0]:
            return 100.0
        for i in range(1, len(pts)):
            v0, s0 = pts[i - 1]
            v1, s1 = pts[i]
            if v0 <= v <= v1:
                if v1 == v0:
                    return float(s1)
                return s0 + (s1 - s0) * (v - v0) / (v1 - v0)
        return 0.0

    def on_bat_type_changed(self, *args):
        self.apply_battery_type()
        idx = self.bat_type_combo.currentIndex()
        if not (0 <= idx < len(self.BATTERY_TYPES)):
            return
        cells = self.BATTERY_TYPES[idx].get("cells", 1)
        self.bat_cells_spin.blockSignals(True)
        self.bat_cells_spin.setValue(cells)
        self.bat_cells_spin.blockSignals(False)
        self.settings.setValue("bat_cells", cells)
        if self._bat_last_v is not None:
            self._bat_recalc(self._bat_last_v)

    def apply_battery_type(self, *args):
        if not hasattr(self, "bat_curve"):
            return
        idx = self.bat_type_combo.currentIndex()
        custom = idx >= len(self.BATTERY_TYPES)
        self.bat_full_spin.setEnabled(custom)
        self.bat_empty_spin.setEnabled(custom)
        if not custom:
            t = self.BATTERY_TYPES[idx]
            self.bat_full_spin.blockSignals(True)
            self.bat_empty_spin.blockSignals(True)
            self.bat_full_spin.setValue(t["full"])
            self.bat_empty_spin.setValue(t["empty"])
            self.bat_full_spin.blockSignals(False)
            self.bat_empty_spin.blockSignals(False)

        curve, full, empty, note = self.battery_current_curve()
        self.bat_note_lbl.setText(note)
        self.settings.setValue("bat_type", idx)
        self.settings.setValue("bat_cells", self.bat_cells_spin.value())
        self.settings.setValue("bat_full", self.bat_full_spin.value())
        self.settings.setValue("bat_empty", self.bat_empty_spin.value())
        if self._bat_last_v is not None:
            self._bat_recalc(self._bat_last_v)
        else:
            self.bat_curve.set_data(curve, full, empty, None, None)

    def on_bat_cells(self, *args):
        self.settings.setValue("bat_cells", self.bat_cells_spin.value())
        if self._bat_last_v is not None:
            self._bat_recalc(self._bat_last_v)

    def update_battery(self, r):
        if not hasattr(self, "bat_curve"):
            return
        if not (r.volt and not r.diode and r.has_value):
            return
        scale = {"n": 1e-9, "\u00b5": 1e-6, "m": 1e-3,
                 "k": 1e3, "M": 1e6}.get(r.prefix, 1.0)
        v_total = abs(r.value) * scale
        self._bat_last_v = v_total
        self._bat_recalc(v_total)

    def _bat_recalc(self, v_total):
        cells = max(1, self.bat_cells_spin.value())
        v_cell = v_total / cells
        curve, full, empty, _note = self.battery_current_curve()
        soc = self.soc_from_voltage(v_cell, curve)
        self.bat_volt_lbl.setText(
            f"Napięcie: {v_total:.3f} V  ({v_cell:.3f} V/ogn., {cells} ogniw)")
        self.bat_soc_lbl.setText(f"SoC: {soc:.0f}%")
        self.bat_progress.setValue(int(round(soc)))
        if soc >= 80:
            status, color = "Pełna / Dobra", "#43d17a"
        elif soc >= 40:
            status, color = "OK", "#8ed17a"
        elif soc >= 15:
            status, color = "Niska", "#e0c85a"
        else:
            status, color = "Krytyczna", "#ff5a4a"
        self.bat_status_lbl.setText(f"Status: {status}")
        self.bat_status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.bat_curve.set_data(curve, full, empty, v_cell, soc)

    def save_options(self, *args):
        self.settings.setValue("buzzer_enabled", self.buzzer_cb.isChecked())
        self.settings.setValue("buzzer_freq", self.freq_spin.value())
        self.settings.setValue("buzzer_volume", self.vol_spin.value())
        self.settings.setValue("buzzer_threshold", self.thr_spin.value())
        self.settings.setValue("diode_enabled", self.diode_cb.isChecked())
        self.settings.setValue("diode_freq", self.diode_freq_spin.value())
        self.settings.setValue("diode_volume", self.diode_vol_spin.value())
        self.settings.setValue("diode_beep_ms", self.diode_beep_spin.value())
        self.settings.setValue("diode_gap_ms", self.diode_gap_spin.value())
        self.settings.setValue("diode_repeat_ms", self.diode_repeat_spin.value())
        self.settings.setValue("diode_schottky_v", self.diode_thr_spin.value())
        self.settings.setValue("diode_min_v", self.diode_min_spin.value())
        self.settings.setValue("diode_short_enabled", self.diode_short_cb.isChecked())
        self.settings.setValue("diode_short_v", self.diode_short_spin.value())

    def on_buzzer_toggle(self, *args):
        if not self.buzzer_cb.isChecked() and not self.diode_cb.isChecked():
            self.buzzer.stop()

    def test_buzzer(self):
        self.buzzer.play_tone(self.freq_spin.value(), self.vol_spin.value() / 100.0)
        QTimer.singleShot(1200, self._stop_test_buzzer)

    def diode_pattern(self, beeps):
        return (self.diode_freq_spin.value(), self.diode_vol_spin.value() / 100.0,
                beeps, self.diode_beep_spin.value(), self.diode_gap_spin.value(),
                self.diode_repeat_spin.value())

    def test_diode_buzzer(self):
        period = self.diode_repeat_spin.value()
        self.buzzer.play_pattern(*self.diode_pattern(1))
        QTimer.singleShot(period, lambda: self.buzzer.play_pattern(*self.diode_pattern(2)))
        QTimer.singleShot(period * 2, self._stop_test_buzzer)

    def _stop_test_buzzer(self):
        self.buzzer.stop()

    def build_menu(self):
        menubar = self.menuBar()

        theme_menu = menubar.addMenu("&Theme")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self.act_light = QAction("Light", self, checkable=True)
        self.act_dark = QAction("Dark", self, checkable=True)
        theme_group.addAction(self.act_light)
        theme_group.addAction(self.act_dark)
        theme_menu.addAction(self.act_light)
        theme_menu.addAction(self.act_dark)
        self.act_light.triggered.connect(lambda: self.apply_theme("light"))
        self.act_dark.triggered.connect(lambda: self.apply_theme("dark"))

        help_menu = menubar.addMenu("&Help")

        act_about = QAction("About", self)
        act_about.triggered.connect(self.show_about)
        act_github = QAction("Github", self)
        act_github.triggered.connect(self.open_github)
        act_authors = QAction("Authors", self)
        act_authors.triggered.connect(self.show_authors)

        help_menu.addAction(act_about)
        help_menu.addAction(act_github)
        help_menu.addAction(act_authors)

    def show_about(self):
        QMessageBox.about(
            self,
            "About",
            f"<h3>{self.APP_NAME}</h3>"
            f"<p>Wersja: {self.APP_VERSION}</p>"
            "<p>Czytnik multimetru VICI VC99 (FS9922-DMM4) przez UART.</p>"
            "<p>Port: 2400 8N1, ramki 14-bajtowe.</p>"
            f"<p>Autor: {self.AUTHOR}</p>",
        )

    def open_github(self):
        QDesktopServices.openUrl(QUrl(self.GITHUB_URL))
        self.set_status("Otwarto: " + self.GITHUB_URL)

    def show_authors(self):
        QMessageBox.information(
            self,
            "Authors",
            f"<h3>Authors</h3><p>{self.AUTHOR}</p>"
            f"<p>GitHub: <a href=\"{self.GITHUB_URL}\">{self.GITHUB_URL}</a></p>",
        )
    
    def refresh_ports(self):
        current = self.port_combo.currentData()

        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        ports = QSerialPortInfo.availablePorts()
        for p in ports:
            name = p.portName()
            desc = p.description()
            text = name
            if desc:
                text += " - " + desc
            self.port_combo.addItem(text, name)

        target = current or self.saved_port
        idx = self.find_port_index(target)
        if idx < 0 and self.port_combo.count() > 0:
            idx = 0
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)
        self.port_combo.blockSignals(False)

    def find_port_index(self, port_name):
        if not port_name:
            return -1
        for i in range(self.port_combo.count()):
            if self.port_combo.itemData(i) == port_name:
                return i
        return -1

    def on_port_changed(self, index):
        data = self.port_combo.itemData(index)
        if data:
            self.saved_port = data
            self.settings.setValue("last_port", data)
            log.info("Zapamietano port: %s", data)
    
    def on_auto_refresh_ports(self):
        if not self.serial.is_open():
            self.refresh_ports()
    
    def toggle_connect(self):
        if self.serial.is_open():
            self.serial.close()
            return
        if self.port_combo.count() == 0:
            QMessageBox.warning(self, "Brak portu", "Nie znaleziono portu COM/tty.")
            return
        data = self.port_combo.currentData()
        if data:
            port_name = data
        else:
            port_name = self.port_combo.currentText().split()[0]
        if self.serial.open(port_name, 2400):
            self.set_status(f"Połączono: {port_name} @2400")
        else:
            self.set_status(f"Błąd połączenia: {self.serial.error_string()}", True)
    
    def on_connected_changed(self, connected):
        self.connect_btn.setText("Rozłącz" if connected else "Połącz")
        self.port_combo.setEnabled(not connected)
        self.refresh_btn.setEnabled(not connected)
        self.reset_stats()
        self._frame_stamps.clear()
        self._last_frame_time = None
        if not connected:
            self.buzzer.stop()
            self.update_display(VC99Reading())
            self.raw_label.setText("RAW: --")
    
    def on_error(self, msg):
        self.set_status(msg, True)
    
    def update_display(self, r):
        if not r.valid:
            self.value_label.setText("--.--")
            self.suffix_label.clear()
            self.mode_label.clear()
            self.extra_label.clear()
            self.progress_bar.setValue(0)
            self.update_analysis(r)
            return
        if r.overload:
            self.value_label.setText("O.L")
            self.suffix_label.setText(r.prefix + r.unit)
            self.progress_bar.setValue(self.FULL_SCALE_COUNTS)
            modes = []
            if r.dc: modes.append("DC")
            if r.ac: modes.append("AC")
            if r.auto_mode: modes.append("AUTO")
            self.mode_label.setText(' '.join(modes))
            extra = []
            if r.hold: extra.append("HOLD")
            if r.rel: extra.append("REL")
            if r.max_flag: extra.append("MAX")
            if r.min_flag: extra.append("MIN")
            if r.bat_low: extra.append("BAT")
            self.extra_label.setText(' '.join(extra))
            self.update_analysis(r)
            return
        if r.has_value:
            v = r.value
            if abs(v) >= 1000.0 or abs(v) < 0.001:
                num_str = f"{v:g}"
            else:
                num_str = f"{v:.4f}"
                while num_str.endswith('0') and '.' in num_str:
                    num_str = num_str[:-1]
                if num_str.endswith('.'):
                    num_str = num_str[:-1]
            self.value_label.setText(num_str)
            self.progress_bar.setValue(min(abs(r.counts), self.FULL_SCALE_COUNTS))
        else:
            self.value_label.setText("----")
            self.progress_bar.setValue(0)
        self.suffix_label.setText(r.prefix + r.unit)
        modes = []
        if r.dc: modes.append("DC")
        if r.ac: modes.append("AC")
        if r.auto_mode: modes.append("AUTO")
        self.mode_label.setText(' '.join(modes))
        extra = []
        if r.hold: extra.append("HOLD")
        if r.rel: extra.append("REL")
        if r.max_flag: extra.append("MAX")
        if r.min_flag: extra.append("MIN")
        if r.diode or r.z1: extra.append("DIODE")
        if r.beep: extra.append("CONT")
        if r.bat_low: extra.append("BAT")
        if r.apo: extra.append("APO")
        self.extra_label.setText(' '.join(extra))
        self.update_analysis(r)

    def update_analysis(self, r):
        if r.has_value:
            self.update_stats(r.value)

        if r.overload:
            self.bargraph.set_value(61, r.negative, True)
            self.bar_value_label.setText("O.L")
            self.trend_plot.add_value(61)
        elif r.bpn:
            value = abs(r.bargraph)
            self.bargraph.set_value(value, r.negative, True)
            self.bar_value_label.setText(f"{r.bargraph}/61")
            self.trend_plot.add_value(value)
        else:
            self.bargraph.clear()
            self.bar_value_label.setText("--/61")

        value_txt = (self.value_label.text() + " " + self.suffix_label.text()).strip()
        self.trend_plot.set_info(
            value_txt, self.mode_label.text(), self.extra_label.text()
        )
        self.update_buzzer(r)
        self.on_temperature(r)
        self.update_battery(r)

    def update_buzzer(self, r):
        if not hasattr(self, "diode_cb"):
            return
        if self.diode_cb.isChecked() and r.diode and r.has_value:
            v = abs(r.value)
            if (self.diode_short_cb.isChecked()
                    and v <= self.diode_short_spin.value()):
                self.buzzer.play_tone(self.diode_freq_spin.value(),
                                      self.diode_vol_spin.value() / 100.0)
                return
            if v >= self.diode_min_spin.value():
                beeps = 2 if v < self.diode_thr_spin.value() else 1
                self.buzzer.play_pattern(*self.diode_pattern(beeps))
                return
        if (self.buzzer_cb.isChecked() and r.beep and r.has_value
                and 0 < abs(r.value) <= self.thr_spin.value()):
            self.buzzer.play_tone(self.freq_spin.value(),
                                  self.vol_spin.value() / 100.0)
            return
        self.buzzer.stop()

    def update_stats(self, v):
        if self.stat_min is None or v < self.stat_min:
            self.stat_min = v
        if self.stat_max is None or v > self.stat_max:
            self.stat_max = v
        self.stat_sum += v
        self.stat_count += 1
        self.stats_label.setText(
            f"Min: {self.stat_min:g}   Max: {self.stat_max:g}   "
            f"AVG: {self.stat_sum / self.stat_count:g}   (n={self.stat_count})"
        )

    def reset_stats(self):
        self.stat_count = 0
        self.stat_min = None
        self.stat_max = None
        self.stat_sum = 0.0
        self.stats_label.setText("Min: --   Max: --   AVG: --")
        self.trend_plot.clear()
        self.bargraph.clear()
        self.bar_value_label.setText("--/61")
    
    def on_frame_received(self, frame_bytes):
        now = time.monotonic()
        self._last_frame_time = now
        self._frame_stamps.append(now)
        r = VC99Parser.parse(frame_bytes)
        self.update_display(r)
        self.raw_label.setText("RAW: " + r.raw_hex)
        if self.recording:
            self.write_csv_row(r)

    def toggle_csv(self):
        if self.recording:
            self.stop_recording()
            return

        default_name = "vici_vc99_pomiary_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
        start_dir = os.path.join(os.path.expanduser("~"), "Desktop", default_name)
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz pomiary do CSV", start_dir, "Pliki CSV (*.csv)"
        )
        if not path:
            return

        try:
            self.csv_file = open(path, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                "timestamp", "value", "prefix", "unit", "counts",
                "dc", "ac", "auto", "rel", "hold", "max", "min",
                "diode", "cont", "bat", "apo", "bargraph", "raw_hex",
            ])
            self.csv_file.flush()
        except Exception as e:
            log.error("Nie mozna otworzyc pliku CSV: %s", e)
            QMessageBox.critical(self, "Blad", "Nie można otworzyć pliku:\n" + str(e))
            self.csv_file = None
            self.csv_writer = None
            return

        self.csv_path = path
        self.recording = True
        self.csv_btn.setText("Stop zapisu")
        self.blink_timer.start()
        self.set_status("Zapis do: " + path)
        log.info("Rozpoczeto zapis CSV: %s", path)

    def stop_recording(self):
        self.recording = False
        self.blink_timer.stop()
        self.blink_state = False
        self.csv_btn.setStyleSheet("")
        self.csv_btn.setText("Zapis CSV")
        if self.csv_file:
            try:
                self.csv_file.flush()
                self.csv_file.close()
            except Exception:
                pass
        self.csv_file = None
        self.csv_writer = None
        self.set_status("Zapis zakonczony" + (": " + self.csv_path if self.csv_path else ""))
        log.info("Zakonczono zapis CSV: %s", self.csv_path)

    def write_csv_row(self, r):
        if not self.csv_writer:
            return
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            value = "" if r.overload else f"{r.value:g}"
            self.csv_writer.writerow([
                ts, value, r.prefix,
                (r.unit.encode("unicode_escape").decode() if r.unit else ""),
                r.counts,
                int(r.dc), int(r.ac), int(r.auto_mode), int(r.rel),
                int(r.hold), int(r.max_flag), int(r.min_flag),
                int(r.diode or r.z1), int(r.beep), int(r.bat_low),
                int(r.apo), r.bargraph, r.raw_hex,
            ])
            self.csv_file.flush()
        except Exception as e:
            log.error("Blad zapisu wiersza CSV: %s", e)

    def on_blink(self):
        self.blink_state = not self.blink_state
        if self.blink_state:
            self.csv_btn.setStyleSheet(
                "color: white; background-color: green; font-weight: bold;"
            )
        else:
            self.csv_btn.setStyleSheet(
                "color: green; background-color: #f0f0f0; font-weight: bold;"
            )

    def closeEvent(self, event):
        self.buzzer.stop()
        if self.recording:
            self.stop_recording()
        super().closeEvent(event)

    def choose_color(self):
        color = QColorDialog.getColor(self.display_color, self, "Kolor czcionki wyniku")
        if color.isValid():
            self.display_color = color
            self.color_customized = True
            self.apply_display_color()
            log.info("Zmieniono kolor czcionki na %s", color.name())

    def apply_theme(self, name):
        name = "dark" if str(name).lower() == "dark" else "light"
        self.theme = name
        self.setStyleSheet(self.DARK_QSS if name == "dark" else "")

        if hasattr(self, "act_light"):
            self.act_light.setChecked(name == "light")
            self.act_dark.setChecked(name == "dark")

        if not self.color_customized:
            self.display_color = QColor("#e6e6e6") if name == "dark" else QColor("#000000")

        stats_color = "#b9bdc4" if name == "dark" else "#555555"
        self.stats_label.setStyleSheet(f"color: {stats_color};")

        self.apply_display_color()
        self.settings.setValue("theme", name)
        log.info("Ustawiono motyw: %s", name)

    def apply_display_color(self):
        c = self.display_color.name()
        self.value_label.setStyleSheet(f"color: {c};")
        self.suffix_label.setStyleSheet(f"color: {c};")
        bg = "#2a2c30" if self.theme == "dark" else "#eeeeee"
        border = "#3a3d42" if self.theme == "dark" else "#999999"
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid {border}; border-radius: 3px; "
            f"text-align: center; background: {bg}; }} "
            f"QProgressBar::chunk {{ background-color: {c}; }}"
        )
    
    def set_status(self, s, error=False):
        self.status_message = s
        self.status_error = error
        self.status_label.setStyleSheet("color: red;" if error else "")
        self.refresh_status_clock()

    def refresh_status_clock(self):
        metrics = ""
        if self.serial.is_open():
            now = time.monotonic()
            fps = 0.0
            if len(self._frame_stamps) >= 2:
                recent = [t for t in self._frame_stamps if now - t <= 1.0]
                if len(recent) >= 2:
                    span = recent[-1] - recent[0]
                    if span > 0:
                        fps = (len(recent) - 1) / span
            if self._last_frame_time is not None:
                delta_ms = (now - self._last_frame_time) * 1000.0
                delta_txt = f"{delta_ms:.0f} ms"
            else:
                delta_txt = "--"
            metrics = f"   |   FPS: {fps:.1f}   |   od ostatniej ramki: {delta_txt}"
        self.status_label.setText(
            QTime.currentTime().toString("HH:mm:ss") + "  "
            + self.status_message + metrics
        )


def main():
    try:
        log.info("Tworzenie QApplication...")
        app = QApplication(sys.argv)
        log.info("Tworzenie MainWindow...")
        w = MainWindow()
        log.info("Pokazywanie okna...")
        w.show()
        log.info("Wejscie do petli zdarzen")
        rc = app.exec_()
        log.info("Wyjscie z petli zdarzen, kod=%s", rc)
        return rc
    except Exception:
        import traceback
        log.error("Blad krytyczny:\n%s", traceback.format_exc())
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                None,
                "Blad",
                "Aplikacja napotkala blad.\n\nSzczegoly w pliku:\n" + applog.LOG_FILE,
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
