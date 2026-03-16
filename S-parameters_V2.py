import sys
import os
import numpy as np
import skrf as rf
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QFileDialog, QLabel, QLineEdit, QListWidget, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QListWidgetItem, QComboBox, QColorDialog, QSizePolicy,
    QAction, QStyledItemDelegate, QFrame, QAbstractItemView
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPainter, QPen
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# ── Global stylesheet ────────────────────────────────────────────────────────
APP_STYLE = """
QMainWindow, QWidget {
    background-color: #F5F7FA;
    color: #2C3E50;
    font-family: "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 13px;
}
QPushButton {
    background-color: #4A90D9;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover { background-color: #357ABD; }
QPushButton:pressed { background-color: #2868A9; }
QPushButton#danger { background-color: #E74C3C; }
QPushButton#danger:hover { background-color: #C0392B; }
QLineEdit {
    border: 1.5px solid #D5DCE8;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #FFFFFF;
    color: #2C3E50;
}
QLineEdit:focus { border-color: #4A90D9; }
QListWidget {
    border: 1.5px solid #D5DCE8;
    border-radius: 6px;
    background-color: #FFFFFF;
    padding: 4px;
}
QListWidget::item { padding: 4px 6px; border-radius: 4px; }
QListWidget::item:selected { background-color: #D6E8FA; color: #1A5FA8; }
QListWidget::item:hover { background-color: #EBF3FC; }
QTableWidget {
    border: 1.5px solid #D5DCE8;
    border-radius: 6px;
    background-color: #FFFFFF;
    gridline-color: #EDF0F5;
}
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background-color: #D6E8FA; color: #1A5FA8; }
QHeaderView::section {
    background-color: #EDF0F5;
    color: #5A6A7E;
    border: none;
    border-right: 1px solid #D5DCE8;
    border-bottom: 1px solid #D5DCE8;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
}
QComboBox {
    border: 1.5px solid #D5DCE8;
    border-radius: 6px;
    padding: 4px 8px;
    background-color: #FFFFFF;
}
QComboBox:focus { border-color: #4A90D9; }
QFrame#divider { background-color: #D5DCE8; max-height: 1px; }
"""

CURVE_COLORS = [
    '#4A90D9', '#E74C3C', '#27AE60', '#F39C12',
    '#8E44AD', '#16A085', '#2C3E50', '#D35400'
]


# ── Line style delegate ──────────────────────────────────────────────────────
class LineStyleDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        mapping = {'-': Qt.SolidLine, '--': Qt.DashLine, '-.': Qt.DashDotLine, ':': Qt.DotLine}
        pen = QPen(Qt.black, 2, mapping.get(index.data(Qt.DisplayRole), Qt.SolidLine))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(pen)
        mid_y = option.rect.center().y()
        painter.drawLine(option.rect.left() + 8, mid_y, option.rect.right() - 8, mid_y)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(super().sizeHint(option, index).width(), 28)


# ── Plot Window ──────────────────────────────────────────────────────────────
class PlotWindow(QMainWindow):
    def __init__(self, file_paths, selected_s_params=None,
                 start_freq=None, stop_freq=None, s_min=None, s_max=None, mark_freqs=None):
        super().__init__()
        self.setWindowTitle('S-Parameter Analyzer — Plot')
        self.setGeometry(120, 80, 1280, 780)
        self.setStyleSheet(APP_STYLE)

        self.file_paths = file_paths
        self.selected_s_params = selected_s_params or ["S11"]
        self.user_start_freq = start_freq
        self.user_stop_freq = stop_freq
        self.user_s_min = s_min
        self.user_s_max = s_max
        self.mark_freqs = mark_freqs
        self.curve_data = []
        self.curve_config = {}

        # ── Menu bar
        self.menuBar().setNativeMenuBar(True)
        pref = self.menuBar().addMenu("Preferences")

        self.action_db = QAction("Show dB Plot", self, checkable=True)
        self.action_db.setChecked(True)
        self.action_db.setMenuRole(QAction.NoRole)
        self.action_db.triggered.connect(lambda c: self.canvas_db.setVisible(c))
        pref.addAction(self.action_db)

        self.action_smith = QAction("Show Smith Chart", self, checkable=True)
        self.action_smith.setChecked(True)
        self.action_smith.setMenuRole(QAction.NoRole)
        self.action_smith.triggered.connect(lambda c: self.canvas_smith.setVisible(c))
        pref.addAction(self.action_smith)

        pref.addSeparator()
        act_save = QAction("Save Image", self)
        act_save.setMenuRole(QAction.NoRole)
        act_save.triggered.connect(self.save_image)
        pref.addAction(act_save)

        # ── Layout
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        self.title_edit = QLineEdit("S-Parameter Analyzer")
        self.title_edit.setAlignment(Qt.AlignCenter)
        self.title_edit.setStyleSheet(
            "font-size: 17pt; font-weight: 600; border: none; "
            "background: transparent; color: #2C3E50;"
        )
        root.addWidget(self.title_edit)

        charts = QHBoxLayout()
        charts.setSpacing(10)
        self.canvas_db = FigureCanvas(plt.figure(figsize=(6, 5)))
        self.canvas_db.setMinimumHeight(340)
        charts.addWidget(self.canvas_db)
        self.canvas_smith = FigureCanvas(plt.figure(figsize=(6, 5)))
        self.canvas_smith.setMinimumHeight(340)
        charts.addWidget(self.canvas_smith)
        root.addLayout(charts)

        self.table_widget = QTableWidget()
        self.table_widget.setMaximumHeight(200)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setStyleSheet(
            "QTableWidget { alternate-background-color: #F8FAFC; }"
        )
        root.addWidget(self.table_widget)

        self._apply_mpl_style()
        self.plot_s_parameter()
        self.init_table()

    # ── Matplotlib style
    def _apply_mpl_style(self):
        plt.rcParams.update({
            'axes.facecolor': '#FFFFFF',
            'figure.facecolor': '#F5F7FA',
            'axes.edgecolor': '#D5DCE8',
            'axes.labelcolor': '#5A6A7E',
            'xtick.color': '#8A9BB0',
            'ytick.color': '#8A9BB0',
            'grid.color': '#EDF0F5',
            'grid.linewidth': 0.8,
            'font.size': 10,
        })

    # ── Core plot
    def plot_s_parameter(self):
        try:
            self.curve_data = []
            all_freqs, all_db_vals = [], []

            self.canvas_db.figure.clear()
            self.ax_db = self.canvas_db.figure.add_subplot(111)
            self.canvas_db.figure.patch.set_facecolor('#F5F7FA')

            self.canvas_smith.figure.clear()
            self.ax_smith = self.canvas_smith.figure.add_subplot(111)
            self.canvas_smith.figure.patch.set_facecolor('#F5F7FA')

            idx = 0
            for i, fp in enumerate(self.file_paths):
                net = rf.Network(fp)
                f = net.f / 1e6
                for j, sp in enumerate(self.selected_s_params):
                    try:
                        m, n = int(sp[1]) - 1, int(sp[2]) - 1
                    except Exception:
                        raise ValueError(f"Invalid S-parameter: {sp}")
                    if net.number_of_ports <= max(m, n):
                        raise ValueError(
                            f"{os.path.basename(fp)} has insufficient ports for {sp}")

                    s_val = net.s[:, m, n]
                    s_db = 20 * np.log10(np.abs(s_val) + 1e-30)

                    if self.user_start_freq is not None and self.user_stop_freq is not None:
                        mask = (f >= self.user_start_freq) & (f <= self.user_stop_freq)
                    else:
                        mask = np.ones(f.shape, dtype=bool)

                    f_f = f[mask]
                    s_f = s_db[mask]

                    self.curve_data.append({
                        'file_path': fp, 's_param': sp,
                        'f': f, 'f_filtered': f_f,
                        's_db_filtered': s_f, 's_val': s_val,
                        'network': net, 'm': m, 'n': n
                    })
                    self.curve_config[idx] = {
                        'color': CURVE_COLORS[(i * len(self.selected_s_params) + j) % len(CURVE_COLORS)],
                        'linestyle': '-'
                    }
                    all_freqs.extend(f_f)
                    all_db_vals.extend(s_f)
                    idx += 1

            self._draw_curves(all_freqs, all_db_vals)
            self.canvas_db.draw()
            self.canvas_smith.draw()

        except Exception as e:
            QMessageBox.critical(self, 'Plot Error', f"An error occurred while plotting:\n{e}")

    def _filtered_network(self, curve):
        f = curve['f']
        lo = self.user_start_freq if self.user_start_freq is not None else f.min()
        hi = self.user_stop_freq if self.user_stop_freq is not None else f.max()
        return curve['network'][(f >= lo) & (f <= hi)]

    def _draw_curves(self, all_freqs, all_db_vals):
        for idx, curve in enumerate(self.curve_data):
            cfg = self.curve_config.get(idx, {'color': '#4A90D9', 'linestyle': '-'})
            label = f"{os.path.splitext(os.path.basename(curve['file_path']))[0]}  {curve['s_param']}"

            self.ax_db.plot(curve['f_filtered'], curve['s_db_filtered'],
                            color=cfg['color'], linestyle=cfg['linestyle'],
                            linewidth=1.5, label=label)

            self._filtered_network(curve).plot_s_smith(
                ax=self.ax_smith, m=curve['m'], n=curve['n'],
                linewidth=1.5, draw_labels=False,
                color=cfg['color'], linestyle=cfg['linestyle'])

            if self.mark_freqs:
                for freq in self.mark_freqs:
                    ci = np.argmin(np.abs(curve['f'] - freq))
                    self.ax_smith.plot(
                        np.real(curve['s_val'][ci]), np.imag(curve['s_val'][ci]),
                        'o', markersize=5, color=cfg['color'],
                        markeredgecolor='white', markeredgewidth=0.8)
                    self.ax_db.axvline(x=freq, linestyle='--', color='#AABDD0', linewidth=0.9)

        # dB axes
        self.ax_db.set_xlabel('Frequency (MHz)', fontsize=10, color='#5A6A7E')
        self.ax_db.set_ylabel('Magnitude (dB)', fontsize=10, color='#5A6A7E')
        self.ax_db.grid(True, linestyle='--', alpha=0.6)
        self.ax_db.set_facecolor('#FFFFFF')
        for sp in self.ax_db.spines.values():
            sp.set_edgecolor('#D5DCE8')

        if all_freqs and all_db_vals:
            flo, fhi = min(all_freqs), max(all_freqs)
            dlo, dhi = min(all_db_vals), max(all_db_vals)
            pf = 0.03 * (fhi - flo) if fhi != flo else 1
            pd = 0.05 * (dhi - dlo) if dhi != dlo else 1
            self.ax_db.set_xlim(
                self.user_start_freq if self.user_start_freq is not None else flo - pf,
                self.user_stop_freq if self.user_stop_freq is not None else fhi + pf)
            self.ax_db.set_ylim(
                self.user_s_min if self.user_s_min is not None else dlo - pd,
                self.user_s_max if self.user_s_max is not None else dhi + pd)

        handles, labels = self.ax_db.get_legend_handles_labels()
        if handles:
            self.ax_db.legend(handles, labels, fontsize=9,
                              framealpha=0.85, edgecolor='#D5DCE8', loc='best', handlelength=2)

        leg = self.ax_smith.get_legend()
        if leg:
            leg.remove()

        self.canvas_db.figure.tight_layout(pad=1.5)
        self.canvas_smith.figure.tight_layout(pad=1.5)

    # ── Table
    def init_table(self):
        n_mark = len(self.mark_freqs) if self.mark_freqs else 0
        self.table_widget.blockSignals(True)
        self.table_widget.setRowCount(len(self.curve_data))
        self.table_widget.setColumnCount(3 + n_mark)
        headers = ["Color", "Line Style", "File · S-Param"]
        if self.mark_freqs:
            headers += [f"{int(f)} MHz" for f in self.mark_freqs]
        self.table_widget.setHorizontalHeaderLabels(headers)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)

        for idx, curve in enumerate(self.curve_data):
            self.table_widget.setRowHeight(idx, 36)

            # Color swatch button
            btn = QPushButton()
            btn.setStyleSheet(
                f"background-color: {self.curve_config[idx]['color']};"
                "border-radius: 4px; border: none;")
            btn.setFixedSize(36, 26)
            btn.clicked.connect(lambda _, r=idx, b=btn: self.on_color_button_clicked(r, b))
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(6, 4, 6, 4)
            wl.addWidget(btn)
            self.table_widget.setCellWidget(idx, 0, wrap)

            # Line style
            combo = QComboBox()
            for s in ['-', '--', '-.', ':']:
                combo.addItem(s)
            combo.setCurrentText(self.curve_config[idx]['linestyle'])
            combo.setItemDelegate(LineStyleDelegate(combo))
            combo.setFixedHeight(28)
            combo.currentTextChanged.connect(lambda s, r=idx: self.on_line_style_changed(r, s))
            self.table_widget.setCellWidget(idx, 1, combo)

            # Label
            fname = os.path.splitext(os.path.basename(curve['file_path']))[0]
            item = QTableWidgetItem(f"{fname}  ·  {curve['s_param']}")
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.table_widget.setItem(idx, 2, item)

            # Marker values
            if self.mark_freqs:
                for col, freq in enumerate(self.mark_freqs, start=3):
                    if len(curve['f_filtered']) > 0:
                        ci = np.argmin(np.abs(curve['f_filtered'] - freq))
                        amp = curve['s_db_filtered'][ci]
                        txt = f"{amp:.2f} dB"
                    else:
                        txt = "—"
                    mi = QTableWidgetItem(txt)
                    mi.setTextAlignment(Qt.AlignCenter)
                    self.table_widget.setItem(idx, col, mi)

        self.table_widget.blockSignals(False)
        hdr = self.table_widget.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        self.table_widget.setColumnWidth(0, 70)
        self.table_widget.setColumnWidth(1, 120)
        self.table_widget.setColumnWidth(2, 260)
        for c in range(3, 3 + n_mark):
            self.table_widget.setColumnWidth(c, 110)

    def on_color_button_clicked(self, row, button):
        color = QColorDialog.getColor(QColor(self.curve_config[row]['color']), self, "Select Color")
        if color.isValid():
            self.curve_config[row]['color'] = color.name()
            button.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 4px; border: none;")
            self.update_plots()

    def on_line_style_changed(self, row, style):
        self.curve_config[row]['linestyle'] = style
        self.update_plots()

    def update_plots(self):
        self.ax_db.clear()
        self.ax_smith.clear()
        all_freqs = [v for c in self.curve_data for v in c['f_filtered']]
        all_db = [v for c in self.curve_data for v in c['s_db_filtered']]
        self._draw_curves(all_freqs, all_db)
        self.canvas_db.draw()
        self.canvas_smith.draw()

    def save_image(self):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        title = self.title_edit.text().strip() or "S-Parameter-Analyzer"
        fp = os.path.join(desktop, f"{title}.png")
        pixmap = self.centralWidget().grab()
        if pixmap.save(fp, "PNG"):
            QMessageBox.information(self, "Image Saved", f"Saved to:\n{fp}")
        else:
            QMessageBox.warning(self, "Save Failed", "Could not save image.")


# ── Main Window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('S-Analyzer')
        self.setFixedWidth(380)
        self.setMinimumHeight(680)
        self.setStyleSheet(APP_STYLE)
        self.file_paths = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        tl = QLabel("S-Analyzer")
        tl.setStyleSheet("font-size: 16pt; font-weight: 700; color: #2C3E50;")
        hdr.addWidget(tl)
        hdr.addStretch()
        el = QLabel("foy.fan@outlook.com")
        el.setStyleSheet("color: #8A9BB0; font-size: 11px;")
        hdr.addWidget(el)
        root.addLayout(hdr)

        self._divider(root)

        # Files
        self._sec(root, "FILES")
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(110)
        self.file_list.setMaximumHeight(140)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        root.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_add = QPushButton("＋  Add Files")
        btn_add.clicked.connect(self.select_files)
        btn_row.addWidget(btn_add)
        btn_del = QPushButton("✕  Remove")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self.delete_selected_files)
        btn_row.addWidget(btn_del)
        root.addLayout(btn_row)

        self._divider(root)

        # Freq & axis
        self._sec(root, "FREQUENCY RANGE & AXIS")
        grid = QGridLayout()
        grid.setSpacing(8)
        self.start_freq_input = QLineEdit()
        self.start_freq_input.setPlaceholderText("Start (MHz)  — auto")
        self.stop_freq_input = QLineEdit()
        self.stop_freq_input.setPlaceholderText("Stop (MHz)  — auto")
        self.s_max_input = QLineEdit()
        self.s_max_input.setPlaceholderText("Y Max (dB)  — auto")
        self.s_min_input = QLineEdit()
        self.s_min_input.setPlaceholderText("Y Min (dB)  — auto")
        self.mark_freq_input = QLineEdit()
        self.mark_freq_input.setPlaceholderText("Markers (MHz): 1000, 2000, …")
        grid.addWidget(self.start_freq_input, 0, 0)
        grid.addWidget(self.stop_freq_input, 0, 1)
        grid.addWidget(self.s_max_input, 1, 0)
        grid.addWidget(self.s_min_input, 1, 1)
        grid.addWidget(self.mark_freq_input, 2, 0, 1, 2)
        root.addLayout(grid)

        self._divider(root)

        # S-params
        self._sec(root, "S-PARAMETERS")
        self.s_param_list = QListWidget()
        self.s_param_list.setSelectionMode(QListWidget.MultiSelection)
        self.s_param_list.setMaximumHeight(150)
        for sp in [f'S{i}{j}' for i in range(1, 5) for j in range(1, 5)]:
            item = QListWidgetItem(sp)
            if sp == 'S11':
                item.setSelected(True)
            self.s_param_list.addItem(item)
        root.addWidget(self.s_param_list)

        root.addStretch()

        # Plot button
        btn_plot = QPushButton("▶   Plot")
        btn_plot.setStyleSheet(
            "QPushButton { background-color: #27AE60; font-size: 14px; font-weight: 600; "
            "padding: 10px; border-radius: 8px; }"
            "QPushButton:hover { background-color: #1E8449; }"
            "QPushButton:pressed { background-color: #196F3D; }"
        )
        btn_plot.clicked.connect(self.open_plot_window)
        root.addWidget(btn_plot)

        self.setAcceptDrops(True)

    def _divider(self, layout):
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        layout.addWidget(line)

    def _sec(self, layout, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #8A9BB0; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(lbl)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            if fp.lower().endswith(('.s1p', '.s2p', '.s3p', '.s4p')) and fp not in self.file_paths:
                self.file_paths.append(fp)
                self.file_list.addItem(os.path.basename(fp))

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Select S-Parameter Files', '',
            'Touchstone Files (*.s1p *.s2p *.s3p *.s4p);;All Files (*)')
        for fp in files:
            if fp not in self.file_paths:
                self.file_paths.append(fp)
                self.file_list.addItem(os.path.basename(fp))

    def delete_selected_files(self):
        for item in self.file_list.selectedItems():
            idx = self.file_list.row(item)
            if idx < len(self.file_paths):
                self.file_paths.pop(idx)
            self.file_list.takeItem(idx)

    def _parse_float(self, w):
        t = w.text().strip()
        if not t:
            return None
        try:
            return float(t)
        except ValueError:
            raise ValueError(f"Invalid number: '{t}'")

    def _parse_mark_freqs(self, txt):
        txt = txt.replace('，', ',').strip()
        if not txt:
            return None
        result = []
        for part in txt.split(','):
            part = part.strip()
            if part:
                try:
                    result.append(float(part))
                except ValueError:
                    raise ValueError(f"Invalid marker frequency: '{part}'")
        return result or None

    def open_plot_window(self):
        try:
            start = self._parse_float(self.start_freq_input)
            stop = self._parse_float(self.stop_freq_input)
            s_min = self._parse_float(self.s_min_input)
            s_max = self._parse_float(self.s_max_input)
            marks = self._parse_mark_freqs(self.mark_freq_input.text())
        except ValueError as ve:
            QMessageBox.warning(self, 'Invalid Input', str(ve))
            return

        if not self.file_paths:
            QMessageBox.warning(self, 'No Files', 'Please add at least one S-parameter file.')
            return
        selected = self.s_param_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, 'No S-Parameters', 'Please select at least one S-parameter.')
            return

        self.plot_window = PlotWindow(
            self.file_paths,
            selected_s_params=[i.text() for i in selected],
            start_freq=start, stop_freq=stop,
            s_min=s_min, s_max=s_max, mark_freqs=marks
        )
        self.plot_window.show()


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = QApplication(sys.argv)
    if sys.platform == 'darwin':
        app.setAttribute(Qt.AA_DontUseNativeMenuBar, False)
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())