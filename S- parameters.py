import sys
import os
import numpy as np
import skrf as rf
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QLineEdit, QListWidget, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QListWidgetItem, QComboBox, QColorDialog, QSizePolicy, QAction, QStyledItemDelegate
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd


# 自定义委托：用于绘制下拉框中显示的线型效果
class LineStyleDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        style_str = index.data(Qt.DisplayRole)
        mapping = {'-': Qt.SolidLine, '--': Qt.DashLine, '-.': Qt.DashDotLine, ':': Qt.DotLine}
        pen_style = mapping.get(style_str, Qt.SolidLine)
        pen = QPen(Qt.black, 2, pen_style)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(pen)
        midY = option.rect.center().y()
        painter.drawLine(option.rect.left() + 5, midY, option.rect.right() - 5, midY)
        painter.restore()

    def sizeHint(self, option, index):
        return super().sizeHint(option, index)


class PlotWindow(QMainWindow):
    def __init__(self, file_paths, selected_s_params=None,
                 start_freq=None, stop_freq=None, s_min=None, s_max=None, mark_freqs=None):
        super().__init__()
        self.setWindowTitle('S-Parameter Analyzer')
        self.setGeometry(100, 100, 1200, 700)
        self.file_paths = file_paths
        self.selected_s_params = selected_s_params if selected_s_params else ["S11"]
        self.user_start_freq = start_freq
        self.user_stop_freq = stop_freq
        self.user_s_min = s_min
        self.user_s_max = s_max
        self.mark_freqs = mark_freqs

        # 保存曲线数据和配置（颜色、线型）
        self.curve_data = []
        self.curve_config = {}

        # 设置原生菜单栏（macOS 下菜单会显示在左上角的系统菜单栏中）
        self.menuBar().setNativeMenuBar(True)
        menubar = self.menuBar()
        preferences_menu = menubar.addMenu("Preferences")

        self.action_show_db = QAction("Show dB Plot", self, checkable=True)
        self.action_show_db.setChecked(True)
        self.action_show_db.setMenuRole(QAction.NoRole)
        self.action_show_db.triggered.connect(self.toggle_db_chart)
        preferences_menu.addAction(self.action_show_db)

        self.action_show_smith = QAction("Show Smith Chart", self, checkable=True)
        self.action_show_smith.setChecked(True)
        self.action_show_smith.setMenuRole(QAction.NoRole)
        self.action_show_smith.triggered.connect(self.toggle_smith_chart)
        preferences_menu.addAction(self.action_show_smith)

        # 添加 Save Image 菜单项
        self.action_save = QAction("Save Image", self)
        self.action_save.setMenuRole(QAction.NoRole)
        self.action_save.triggered.connect(self.save_image)
        preferences_menu.addAction(self.action_save)

        # 主体布局（放在 central widget 中）
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        # 标题
        self.title_edit = QLineEdit("S-Parameter Analyzer")
        self.title_edit.setAlignment(Qt.AlignCenter)
        self.title_edit.setStyleSheet("font-size: 18pt; font-weight: bold;")
        self.layout.addWidget(self.title_edit)

        # 上部：两个图表（dB plot 和 Smith chart）
        upper_layout = QHBoxLayout()
        self.canvas_db = FigureCanvas(plt.figure(figsize=(6, 6)))
        upper_layout.addWidget(self.canvas_db)
        self.canvas_smith = FigureCanvas(plt.figure(figsize=(6, 6)))
        upper_layout.addWidget(self.canvas_smith)
        self.layout.addLayout(upper_layout)

        # 下部：表格控件
        self.table_widget = QTableWidget()
        self.layout.addWidget(self.table_widget)

        # 绘制初始图形和初始化表格
        self.plot_s_parameter()
        self.init_table()

    def toggle_db_chart(self, checked):
        self.canvas_db.setVisible(checked)

    def toggle_smith_chart(self, checked):
        self.canvas_smith.setVisible(checked)

    def plot_s_parameter(self):
        try:
            self.curve_data = []
            colors_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
            all_freqs = []
            all_db_vals = []
            self.canvas_db.figure.clear()
            self.ax_db = self.canvas_db.figure.add_subplot(111)
            self.canvas_smith.figure.clear()
            self.ax_smith = self.canvas_smith.figure.add_subplot(111)

            curve_index = 0
            for i, file_path in enumerate(self.file_paths):
                network = rf.Network(file_path)
                f = network.f / 1e6  # MHz
                for j, s_param in enumerate(self.selected_s_params):
                    try:
                        m = int(s_param[1]) - 1
                        n = int(s_param[2]) - 1
                    except Exception:
                        raise ValueError(f"无效的 S 参数: {s_param}")
                    if network.number_of_ports <= max(m, n):
                        raise ValueError(f"文件 {os.path.basename(file_path)} 端口数不足，无法获取 {s_param}")

                    s_val = network.s[:, m, n]
                    s_db = 20 * np.log10(np.abs(s_val))
                    if self.user_start_freq is not None and self.user_stop_freq is not None:
                        freq_mask = (f >= self.user_start_freq) & (f <= self.user_stop_freq)
                    else:
                        freq_mask = np.full(f.shape, True)
                    f_filtered = f[freq_mask]
                    s_db_filtered = s_db[freq_mask]
                    self.curve_data.append({
                        'file_path': file_path,
                        's_param': s_param,
                        'f': f,
                        'f_filtered': f_filtered,
                        's_db_filtered': s_db_filtered,
                        's_val': s_val,
                        'network': network,
                        'm': m,
                        'n': n
                    })
                    default_color = colors_cycle[(i * len(self.selected_s_params) + j) % len(colors_cycle)]
                    self.curve_config[curve_index] = {'color': default_color, 'linestyle': '-'}
                    all_freqs.extend(f_filtered)
                    all_db_vals.extend(s_db_filtered)
                    curve_index += 1

            for idx, curve in enumerate(self.curve_data):
                config = self.curve_config.get(idx, {'color': 'blue', 'linestyle': '-'})
                self.ax_db.plot(curve['f_filtered'], curve['s_db_filtered'],
                                color=config['color'], linestyle=config['linestyle'], linewidth=1.2)
                network_filtered = curve['network'][
                    (curve['f'] >= (self.user_start_freq if self.user_start_freq else min(curve['f']))) &
                    (curve['f'] <= (self.user_stop_freq if self.user_stop_freq else max(curve['f'])))]
                network_filtered.plot_s_smith(ax=self.ax_smith, m=curve['m'], n=curve['n'],
                                              linewidth=1.2, draw_labels=False,
                                              color=config['color'], linestyle=config['linestyle'])
                if self.mark_freqs:
                    for freq in self.mark_freqs:
                        closest_index = np.argmin(np.abs(curve['f'] - freq))
                        self.ax_smith.plot(np.real(curve['s_val'][closest_index]),
                                           np.imag(curve['s_val'][closest_index]),
                                           'o', markersize=4, color=config['color'])
                        self.ax_db.axvline(x=freq, linestyle='--', color='gray', linewidth=1)

            self.ax_db.set_xlabel('Frequency (MHz)')
            self.ax_db.set_ylabel('Magnitude (dB)')
            self.ax_db.grid(True)
            if all_freqs and all_db_vals:
                f_min = min(all_freqs)
                f_max = max(all_freqs)
                db_min = min(all_db_vals)
                db_max = max(all_db_vals)
                x_min = self.user_start_freq if self.user_start_freq is not None else f_min - 0.05 * (f_max - f_min)
                x_max = self.user_stop_freq if self.user_stop_freq is not None else f_max + 0.05 * (f_max - f_min)
                y_min = self.user_s_min if self.user_s_min is not None else db_min - 0.05 * (db_max - db_min)
                y_max = self.user_s_max if self.user_s_max is not None else db_max + 0.05 * (db_max - db_min)
                self.ax_db.set_xlim(x_min, x_max)
                self.ax_db.set_ylim(y_min, y_max)

            # 删除 smith chart 中可能存在的 legend
            leg = self.ax_smith.get_legend()
            if leg is not None:
                leg.remove()

            self.canvas_db.draw()
            self.canvas_smith.draw()
        except Exception as e:
            QMessageBox.critical(self, 'Plot Error', f"An error occurred while plotting: {str(e)}")

    # 表格使用 header 显示标题，保留第0列（颜色列）
    def init_table(self):
        # 列定义：["颜色", "线型", "File - S Param"] + 标记频率列（如果有）
        num_cols = 3 + (len(self.mark_freqs) if self.mark_freqs else 0)
        num_rows = len(self.curve_data)
        self.table_widget.blockSignals(True)
        self.table_widget.setRowCount(num_rows)
        self.table_widget.setColumnCount(num_cols)
        headers = ["color", "linestyle", "File S-Param"]
        if self.mark_freqs:
            headers.extend([str(int(freq)) for freq in self.mark_freqs])
        self.table_widget.setHorizontalHeaderLabels(headers)

        # 填充数据
        for idx, curve in enumerate(self.curve_data):
            row = idx
            # 第0列：颜色按钮（不可直接编辑，通过点击弹出 QColorDialog）
            color_btn = QPushButton("")
            color = self.curve_config[idx]['color']
            color_btn.setStyleSheet(f"background-color: {color};")
            color_btn.setFixedSize(30, 30)
            color_btn.clicked.connect(lambda _, r=idx, btn=color_btn: self.on_color_button_clicked(r, btn))
            self.table_widget.setCellWidget(row, 0, color_btn)
            # 第1列：线型，使用 QComboBox 显示
            combo = QComboBox()
            line_styles = ['-', '--', '-.', ':']
            for style in line_styles:
                combo.addItem(style)
            current_style = self.curve_config[idx]['linestyle']
            combo.setCurrentText(current_style)
            combo.setItemDelegate(LineStyleDelegate(combo))
            combo.currentTextChanged.connect(lambda style, r=idx: self.on_line_style_changed(r, style))
            self.table_widget.setCellWidget(row, 1, combo)
            # 第2列：File - S Param（允许编辑）
            filename = os.path.splitext(os.path.basename(curve['file_path']))[0]
            file_text = f"{filename} - {curve['s_param']}"
            file_item = QTableWidgetItem(file_text)
            file_item.setFlags(file_item.flags() | Qt.ItemIsEditable)
            self.table_widget.setItem(row, 2, file_item)
            # 标记频率列（允许编辑）
            if self.mark_freqs:
                for col, freq in enumerate(self.mark_freqs, start=3):
                    closest_index = np.argmin(np.abs(curve['f_filtered'] - freq))
                    amplitude = curve['s_db_filtered'][closest_index]
                    amp_item = QTableWidgetItem(f"{amplitude:.2f}")
                    amp_item.setFlags(amp_item.flags() | Qt.ItemIsEditable)
                    self.table_widget.setItem(row, col, amp_item)

        self.table_widget.blockSignals(False)
        # 允许用户手动调整列宽
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        # 设置第一列（颜色列）和第二列（线型列）的初始宽度
        self.table_widget.setColumnWidth(0, 100)
        self.table_widget.setColumnWidth(1, 150)
        # 根据内容初始调整其他列宽
        self.table_widget.resizeColumnsToContents()
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def on_color_button_clicked(self, row_index, button):
        initial = QColor(self.curve_config[row_index]['color'])
        color = QColorDialog.getColor(initial, self, "Select Color")
        if color.isValid():
            new_color = color.name()
            self.curve_config[row_index]['color'] = new_color
            button.setStyleSheet(f"background-color: {new_color};")
            self.update_plots()

    def on_line_style_changed(self, row_index, style):
        self.curve_config[row_index]['linestyle'] = style
        self.update_plots()

    def update_plots(self):
        self.ax_db.clear()
        self.ax_smith.clear()
        all_freqs = []
        all_db_vals = []
        for idx, curve in enumerate(self.curve_data):
            config = self.curve_config.get(idx, {'color': 'blue', 'linestyle': '-'})
            self.ax_db.plot(curve['f_filtered'], curve['s_db_filtered'],
                            color=config['color'], linestyle=config['linestyle'], linewidth=1.2)
            network_filtered = curve['network'][
                (curve['f'] >= (self.user_start_freq if self.user_start_freq else min(curve['f']))) &
                (curve['f'] <= (self.user_stop_freq if self.user_stop_freq else max(curve['f'])))]
            network_filtered.plot_s_smith(ax=self.ax_smith, m=curve['m'], n=curve['n'],
                                          linewidth=1.2, draw_labels=False,
                                          color=config['color'], linestyle=config['linestyle'])
            all_freqs.extend(curve['f_filtered'])
            all_db_vals.extend(curve['s_db_filtered'])
            if self.mark_freqs:
                for freq in self.mark_freqs:
                    closest_index = np.argmin(np.abs(curve['f'] - freq))
                    self.ax_smith.plot(np.real(curve['s_val'][closest_index]),
                                       np.imag(curve['s_val'][closest_index]),
                                       'o', markersize=4, color=config['color'])
                    self.ax_db.axvline(x=freq, linestyle='--', color='gray', linewidth=1)
        self.ax_db.set_xlabel('Frequency (MHz)')
        self.ax_db.set_ylabel('Magnitude (dB)')
        self.ax_db.grid(True)
        if all_freqs and all_db_vals:
            f_min = min(all_freqs)
            f_max = max(all_freqs)
            db_min = min(all_db_vals)
            db_max = max(all_db_vals)
            x_min = self.user_start_freq if self.user_start_freq is not None else f_min - 0.05 * (f_max - f_min)
            x_max = self.user_stop_freq if self.user_stop_freq is not None else f_max + 0.05 * (f_max - f_min)
            y_min = self.user_s_min if self.user_s_min is not None else db_min - 0.05 * (db_max - db_min)
            y_max = self.user_s_max if self.user_s_max is not None else db_max + 0.05 * (db_max - db_min)
            self.ax_db.set_xlim(x_min, x_max)
            self.ax_db.set_ylim(y_min, y_max)
        # 删除 smith chart 中可能存在的 legend
        leg = self.ax_smith.get_legend()
        if leg is not None:
            leg.remove()
        self.canvas_db.draw()
        self.canvas_smith.draw()

    def save_image(self):
        # 获取桌面路径
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        # 以标题作为文件名
        filename = f"{self.title_edit.text()}.png"
        filepath = os.path.join(desktop, filename)
        # 截取 central widget 的图像（不包含窗口装饰）
        pixmap = self.centralWidget().grab()
        if pixmap.save(filepath, "PNG"):
            QMessageBox.information(self, "Save Image", f"Image saved to {filepath}")
        else:
            QMessageBox.warning(self, "Save Image", "Failed to save image.")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('S-Analyzer')
        self.setGeometry(0, 20, 400, 700)
        self.file_paths = []
        self.file_names = []
        self.layout = QVBoxLayout()
        self.label = QLabel('Mail: foy.fan@goertek.com')
        self.layout.addWidget(self.label)

        self.file_list = QListWidget()
        self.layout.addWidget(self.file_list)

        self.button_select = QPushButton('Select Files')
        self.button_select.clicked.connect(self.select_files)
        self.layout.addWidget(self.button_select)

        self.button_delete = QPushButton('Delete Selected Files')
        self.button_delete.clicked.connect(self.delete_selected_files)
        self.layout.addWidget(self.button_delete)

        self.start_freq_input = QLineEdit(self)
        self.start_freq_input.setPlaceholderText('Start Frequency (MHz) - Auto')
        self.layout.addWidget(self.start_freq_input)

        self.stop_freq_input = QLineEdit(self)
        self.stop_freq_input.setPlaceholderText('Stop Frequency (MHz) - Auto')
        self.layout.addWidget(self.stop_freq_input)

        self.s11_max_input = QLineEdit(self)
        self.s11_max_input.setPlaceholderText('S11 Max (dB) - Auto')
        self.layout.addWidget(self.s11_max_input)

        self.s11_min_input = QLineEdit(self)
        self.s11_min_input.setPlaceholderText('S11 Min (dB) - Auto')
        self.layout.addWidget(self.s11_min_input)

        self.mark_freq_input = QLineEdit(self)
        self.mark_freq_input.setPlaceholderText('Mark Frequencies (e.g., 1000,2000)')
        self.layout.addWidget(self.mark_freq_input)

        self.s_param_list = QListWidget()
        self.s_param_list.setSelectionMode(QListWidget.MultiSelection)
        s_params = [f'S{i}{j}' for i in range(1, 5) for j in range(1, 5)]
        for param in s_params:
            item = QListWidgetItem(param)
            if param == 'S11':
                item.setSelected(True)
            self.s_param_list.addItem(item)
        self.layout.addWidget(QLabel('Select S-Parameters'))
        self.layout.addWidget(self.s_param_list)

        self.button_plot = QPushButton('Plot 右上角perfermance save')
        self.button_plot.clicked.connect(self.open_plot_window)
        self.layout.addWidget(self.button_plot)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith(('.s1p', '.s2p', '.s3p', '.s4p')) and file_path not in self.file_paths:
                self.file_paths.append(file_path)
                self.file_names.append(os.path.basename(file_path))
                self.file_list.addItem(os.path.basename(file_path))

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Select S-Parameter Files', '',
                                                'Touchstone Files (*.s1p *.s2p *.s3p *.s4p);;All Files (*)')
        if files:
            for file_path in files:
                if file_path not in self.file_paths:
                    self.file_paths.append(file_path)
                    self.file_names.append(os.path.basename(file_path))
                    self.file_list.addItem(os.path.basename(file_path))

    def delete_selected_files(self):
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            index = self.file_list.row(item)
            if index < len(self.file_paths):
                self.file_paths.pop(index)
                self.file_names.pop(index)
                self.file_list.takeItem(index)

    def open_plot_window(self):
        try:
            start_freq = float(self.start_freq_input.text()) if self.start_freq_input.text() else None
            stop_freq = float(self.stop_freq_input.text()) if self.stop_freq_input.text() else None
            s_min = float(self.s11_min_input.text()) if self.s11_min_input.text() else None
            s_max = float(self.s11_max_input.text()) if self.s11_max_input.text() else None
            mark_freqs_text = self.mark_freq_input.text()
            if mark_freqs_text:
                mark_freqs_text = mark_freqs_text.replace('，', ',')
                mark_freqs = [float(f) for f in mark_freqs_text.split(',') if f.strip().isdigit()]
            else:
                mark_freqs = None
        except ValueError as ve:
            QMessageBox.warning(self, 'Invalid Input', str(ve))
            return

        if not self.file_paths:
            QMessageBox.warning(self, 'No Files', 'Please select at least one S-Parameter file to plot.')
            return

        selected_items = self.s_param_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, 'No S Parameters', 'Please select at least one S Parameter.')
            return
        selected_s_params = [item.text() for item in selected_items]

        self.plot_window = PlotWindow(
            self.file_paths, selected_s_params=selected_s_params,
            start_freq=start_freq, stop_freq=stop_freq,
            s_min=s_min, s_max=s_max, mark_freqs=mark_freqs
        )
        self.plot_window.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    if sys.platform == 'darwin':
        app.setAttribute(Qt.AA_DontUseNativeMenuBar, False)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())