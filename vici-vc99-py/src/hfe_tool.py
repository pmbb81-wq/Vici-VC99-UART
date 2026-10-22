from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HfeTool(QWidget):
    GOOD = "#2e8b57"
    WARN = "#b8860b"
    BAD = "#c62828"
    NEUTRAL = "#888888"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = None
        self._can_save = False
        self._npn = None
        self._pnp = None
        self._build_ui()
        self._update_buttons()
        self._update_pair()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title = QLabel("hFE — diagnostyka tranzystora")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setWordWrap(True)

        hint = QLabel(
            "Ustaw multimetr w tryb hFE i umieść tranzystor w gniazdku "
            "E-B-C / C-B-E."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")

        outer.addWidget(title)
        outer.addWidget(hint)

        read_box = QGroupBox("Aktualny pomiar")
        read_layout = QVBoxLayout(read_box)
        read_layout.setSpacing(6)

        value_row = QHBoxLayout()
        value_row.setSpacing(8)
        self.value_label = QLabel("---")
        self.value_label.setFont(QFont("Consolas", 40, QFont.Bold))
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setMinimumWidth(140)
        self.unit_label = QLabel("hFE")
        unit_font = self.unit_label.font()
        unit_font.setPointSize(20)
        unit_font.setBold(True)
        self.unit_label.setFont(unit_font)
        self.unit_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.unit_label.setContentsMargins(0, 0, 0, 8)
        value_row.addStretch(1)
        value_row.addWidget(self.value_label)
        value_row.addWidget(self.unit_label)
        value_row.addStretch(1)
        read_layout.addLayout(value_row)

        self.status_label = QLabel("Oczekiwanie na ramkę hFE...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"color: {self.NEUTRAL}; font-weight: bold;")
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.class_label = QLabel(
            "BC547: grupa A 110–220 | B 200–450 | C 420–800")
        self.class_label.setWordWrap(True)
        self.class_label.setStyleSheet("color: #888;")
        read_layout.addWidget(self.status_label)
        read_layout.addWidget(self.detail_label)
        read_layout.addWidget(self.class_label)
        outer.addWidget(read_box)

        pair_box = QGroupBox("Parowanie tranzystorów (match-pairing)")
        pair_layout = QVBoxLayout(pair_box)
        pair_layout.setSpacing(6)

        saved_row = QHBoxLayout()
        self.npn_label = QLabel("NPN: —")
        self.pnp_label = QLabel("PNP: —")
        for label in (self.npn_label, self.pnp_label):
            label_font = label.font()
            label_font.setPointSize(12)
            label_font.setBold(True)
            label.setFont(label_font)
            label.setMinimumWidth(110)
        saved_row.addWidget(self.npn_label)
        saved_row.addSpacing(18)
        saved_row.addWidget(self.pnp_label)
        saved_row.addStretch(1)
        pair_layout.addLayout(saved_row)

        button_row = QHBoxLayout()
        self.save_npn_btn = QPushButton("Zapisz NPN")
        self.save_npn_btn.setToolTip(
            "Zapisz bieżący pomiar hFE jako wartość tranzystora NPN.")
        self.save_pnp_btn = QPushButton("Zapisz PNP")
        self.save_pnp_btn.setToolTip(
            "Zapisz bieżący pomiar hFE jako wartość tranzystora PNP.")
        self.clear_pair_btn = QPushButton("Wyczyść parę")
        self.clear_pair_btn.setMinimumWidth(120)
        self.clear_pair_btn.setToolTip(
            "Usuń zapisane wartości NPN i PNP oraz wynik parowania.")
        self.save_npn_btn.clicked.connect(self._save_npn)
        self.save_pnp_btn.clicked.connect(self._save_pnp)
        self.clear_pair_btn.clicked.connect(self._clear_pair)
        button_row.addWidget(self.save_npn_btn)
        button_row.addWidget(self.save_pnp_btn)
        button_row.addWidget(self.clear_pair_btn)
        button_row.addStretch(1)
        pair_layout.addLayout(button_row)

        self.delta_label = QLabel("Δ = —")
        self.delta_label.setToolTip(
            "Różnica względna hFE: |NPN - PNP| / średnia × 100%. "
            "Poniżej 5% to idealna para, 5-10% jest akceptowalne.")
        delta_font = self.delta_label.font()
        delta_font.setPointSize(13)
        delta_font.setBold(True)
        self.delta_label.setFont(delta_font)
        self.verdict_label = QLabel("")
        self.verdict_label.setWordWrap(True)
        pair_layout.addWidget(self.delta_label)
        pair_layout.addWidget(self.verdict_label)
        outer.addWidget(pair_box)
        outer.addStretch(1)

    def update_reading(self, reading):
        if not getattr(reading, "valid", False):
            self._set_unavailable("Brak ramki z miernika.")
            return
        if not getattr(reading, "hfe", False):
            self._set_unavailable("Ustaw multimetr w tryb hFE.")
            return
        if getattr(reading, "overload", False):
            self._current = None
            self._can_save = False
            self.value_label.setText("O.L")
            self._set_status(
                "Zwarcie złącza lub przepełnienie pomiaru.", self.BAD)
            self.detail_label.setText(
                "Tranzystor uszkodzony? Sprawdź złącze kolektor-emiter.")
            self._update_buttons()
            return
        if not getattr(reading, "has_value", False):
            self._current = None
            self._can_save = False
            self.value_label.setText("---")
            self._set_status("Brak poprawnej wartości hFE.", self.WARN)
            self.detail_label.setText(
                "Sprawdź ustawienie miernika i osadzenie tranzystora.")
            self._update_buttons()
            return

        value = int(reading.counts)
        self._current = value
        self.value_label.setText(str(value))
        self._can_save = 10 <= value <= 900

        if value <= 5:
            self._set_status(
                "Brak tranzystora lub obwód rozwarty (Open Circuit).",
                self.NEUTRAL,
            )
            self.detail_label.setText(
                "Włóż tranzystor do gniazda E-B-C / C-B-E.")
        elif value < 10:
            self._set_status("Bardzo niska wartość hFE.", self.WARN)
            self.detail_label.setText(
                "Sprawdź osadzenie tranzystora i styki gniazda.")
        elif value <= 800:
            self._set_status("Tranzystor sprawny.", self.GOOD)
            self.detail_label.setText(self._bc547_group(value))
        elif value <= 900:
            self._set_status(
                "Wysoka wartość hFE — sprawdź pomiar.", self.WARN)
            self.detail_label.setText(
                "BC547: powyżej typowego zakresu grupy C (420–800).")
        else:
            self._set_status(
                "Tranzystor uszkodzony — zwarcie złącza C-E.", self.BAD)
            self.detail_label.setText(
                "Zwarcie złącza (Short Circuit) lub przebicie C-E.")
        self._update_buttons()

    def _set_unavailable(self, status):
        self._current = None
        self._can_save = False
        self.value_label.setText("---")
        self._set_status(status, self.NEUTRAL)
        self.detail_label.setText(
            "Narzędzie odczyta wartość, gdy miernik wyśle ramkę hFE.")
        self._update_buttons()

    def _set_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; font-weight: bold;")
        self.value_label.setStyleSheet(f"color: {color};")

    def _bc547_group(self, value):
        groups = []
        if 110 <= value <= 220:
            groups.append("A (110–220)")
        if 200 <= value <= 450:
            groups.append("B (200–450)")
        if 420 <= value <= 800:
            groups.append("C (420–800)")
        if groups:
            return "BC547: grupa " + " / ".join(groups) + "."
        if value < 110:
            return "BC547: poniżej grupy A (110–220)."
        return "BC547: poza zakresem grup A/B/C."

    def _save_npn(self):
        if self._current is None or not self._can_save:
            return
        self._npn = self._current
        self.npn_label.setText(f"NPN: {self._npn}")
        self._update_pair()

    def _save_pnp(self):
        if self._current is None or not self._can_save:
            return
        self._pnp = self._current
        self.pnp_label.setText(f"PNP: {self._pnp}")
        self._update_pair()

    def _clear_pair(self):
        self._npn = None
        self._pnp = None
        self.npn_label.setText("NPN: —")
        self.pnp_label.setText("PNP: —")
        self._update_pair()

    def _update_pair(self):
        if self._npn is None or self._pnp is None:
            self.delta_label.setText("Δ = —")
            self.delta_label.setStyleSheet("")
            if self._npn is None and self._pnp is None:
                self.verdict_label.setText(
                    "Zapisz wartości NPN i PNP, aby obliczyć różnicę.")
            else:
                missing = "NPN" if self._npn is None else "PNP"
                self.verdict_label.setText(
                    f"Zapisz jeszcze wartość {missing}.")
            self.verdict_label.setStyleSheet(f"color: {self.NEUTRAL};")
        else:
            average = (self._npn + self._pnp) / 2.0
            delta = abs(self._npn - self._pnp) / average * 100.0
            self.delta_label.setText(f"Δ = {delta:.2f}%")
            if delta < 5:
                color = self.GOOD
                verdict = "Idealna para do audio (Hi-Fi)."
            elif delta <= 10:
                color = self.WARN
                verdict = "Para akceptowalna."
            else:
                color = self.BAD
                verdict = "Duża rozbieżność — dobierz inną parę."
            self.delta_label.setStyleSheet(
                f"color: {color}; font-weight: bold;")
            self.verdict_label.setText(verdict)
            self.verdict_label.setStyleSheet(f"color: {color};")
        self._update_buttons()

    def _update_buttons(self):
        self.save_npn_btn.setEnabled(self._can_save)
        self.save_pnp_btn.setEnabled(self._can_save)
        self.clear_pair_btn.setEnabled(
            self._npn is not None or self._pnp is not None)
