# gui/main_window.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QTableWidget, QTableWidgetItem,
    QTreeWidget, QTreeWidgetItem, QTabWidget, QMessageBox,
    QSplitter, QDialog, QDialogButtonBox, QLineEdit, QComboBox,
    QInputDialog, QStackedWidget, QRadioButton, QButtonGroup,
    QScrollArea, QHBoxLayout, QGridLayout, QSizePolicy
)
from PyQt5.QtGui import QPalette, QColor, QFont, QBrush
from PyQt5.QtCore import Qt
from SRM_core.parser import parse_response
import os
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from obspy.signal.invsim import evalresp
import numpy as np
from obspy import read_inventory
import configparser
import copy
from obspy.clients.nrl import NRL


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax_amp = self.fig.add_subplot(211)
        self.ax_phase = self.fig.add_subplot(212, sharex=self.ax_amp)
        self.fig.tight_layout()
        super().__init__(self.fig)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Field", "Value"])
        self.setWindowTitle("Station Response Manager")
        self.resize(1280, 720)
        self.menu = self.menuBar()
        file_menu = self.menu.addMenu("File")

        new_action = file_menu.addAction("New")
        new_action.triggered.connect(self.new_project)

        open_action = file_menu.addAction("Open...")
        open_action.triggered.connect(self.open_file)

        save_action = file_menu.addAction("Save")
        save_action.triggered.connect(self.save_project)

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        self.tree.itemChanged.connect(self.handle_tree_edit)
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self.central)
        layout.addWidget(self.tree)
        layout.addWidget(self.tabs)
        self.viewer_tab = QWidget()
        self.info_label = QLabel("No file loaded.")
        layout.addWidget(self.info_label)
        self.viewer_layout = QVBoxLayout(self.viewer_tab)
        self.viewer_layout.addWidget(self.tree)
        self.viewer_layout.addWidget(self.info_label)
        self.tabs.addTab(self.viewer_tab, "Explorer")
        self.tree.setColumnWidth(0, int(self.tree.width() * 0.5))
        self.tree.setColumnWidth(1, int(self.tree.width() * 0.5))
        self.response_tab = QWidget()
        self.response_layout = QVBoxLayout(self.response_tab)
        self.response_label = QLabel("Select a channel's response to edit.")
        self.response_layout.addWidget(self.response_label)
        self.tabs.addTab(self.response_tab, "Response")
        self.tree.itemDoubleClicked.connect(self.handle_tree_double_click)

    def handle_tree_double_click(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data and isinstance(data, tuple) and data[0] == "response":
            response = data[1]
            self.load_response_editor(response)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Response File", "", "All Files (*.xml *.resp *.dless);;StationXML (*.xml);;RESP (*.resp);;Dataless SEED (*.dless *dataless)"
        )
        if path:
            try:
                inv = parse_response(path)
                self.info_label.setText(f"Loaded: {os.path.basename(path)}")
                self.populate_tree(inv)
            except Exception as e:
                self.info_label.setText(f"Error: {e}")
        self.current_inventory = inv

    def new_project(self):
        QMessageBox.information(
            self, "New", "New project not yet implemented.")

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save StationXML", "", "StationXML (*.xml)"
        )
        if not path:
            return

        try:
            if hasattr(self, 'current_inventory'):
                self.current_inventory.write(path, format="STATIONXML")
                QMessageBox.information(self, "Saved", f"Saved to {path}")
            else:
                QMessageBox.warning(self, "Error", "No inventory to save.")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Error: {e}")

    def populate_tree(self, inv):
        self.tree.clear()
        try:
            for net in inv.networks:
                net_item = QTreeWidgetItem([f"Network: {net.code}", ""])
                self.tree.addTopLevelItem(net_item)

                for field in dir(net):
                    if not field.startswith("_") and not callable(
                            getattr(net, field)):
                        value = getattr(net, field)
                        if isinstance(value, (str, float, int)):
                            item = QTreeWidgetItem(
                                net_item, [field, str(value)])
                            item.setFlags(item.flags() | Qt.ItemIsEditable)
                            item.setData(0, Qt.UserRole, (net, field))

                for sta in net.stations:
                    sta_item = QTreeWidgetItem([f"Station: {sta.code}", ""])
                    net_item.addChild(sta_item)

                    for field in dir(sta):
                        if not field.startswith("_") and not callable(
                                getattr(sta, field)):
                            value = getattr(sta, field)
                            if isinstance(value, (str, float, int)):
                                item = QTreeWidgetItem(
                                    sta_item, [field, str(value)])
                                item.setFlags(item.flags() | Qt.ItemIsEditable)
                                item.setData(0, Qt.UserRole, (sta, field))

                    for chan in sta.channels:
                        chan_item = QTreeWidgetItem(
                            [f"Channel: {chan.code}", ""])
                        sta_item.addChild(chan_item)
                        leaf_item = QTreeWidgetItem(
                            sta_item, [field, str(value)])
                        leaf_item.setFlags(
                            leaf_item.flags() | Qt.ItemIsEditable)
                        leaf_item.setData(0, Qt.UserRole, (chan, field))
                        for field in dir(chan):
                            if not field.startswith("_") and not callable(
                                    getattr(chan, field)):
                                value = getattr(chan, field)
                                if isinstance(value, (str, float, int)):
                                    item = QTreeWidgetItem(
                                        chan_item, [field, str(value)])
                                    item.setFlags(
                                        item.flags() | Qt.ItemIsEditable)
                                    item.setData(0, Qt.UserRole, (chan, field))
                        resp = chan.response
                        if resp:
                            resp_item = QTreeWidgetItem(["Response", ""])
                            chan_item.addChild(resp_item)
                            resp_item.setData(
                                0, Qt.UserRole, ("response", chan.response))
                            resp_item.setFlags(
                                resp_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                            if resp.instrument_sensitivity:
                                QTreeWidgetItem(
                                    resp_item, [
                                        "Sensitivity Value", str(
                                            resp.instrument_sensitivity.value)])
                                QTreeWidgetItem(
                                    resp_item, [
                                        "Sensitivity Frequency", str(
                                            resp.instrument_sensitivity.frequency)])

                            for i, stage in enumerate(resp.response_stages):
                                stage_item = QTreeWidgetItem(
                                    [f"Stage {i+1}", type(stage).__name__])
                                resp_item.addChild(stage_item)

                                if hasattr(stage, "stage_gain"):
                                    QTreeWidgetItem(
                                        stage_item, [
                                            "Stage Gain", str(
                                                stage.stage_gain)])

                                if hasattr(stage, "normalization_frequency"):
                                    QTreeWidgetItem(
                                        stage_item, [
                                            "Norm. Frequency", str(
                                                stage.normalization_frequency)])

                                if hasattr(stage, "poles"):
                                    poles_item = QTreeWidgetItem(
                                        stage_item, ["Poles", ""])
                                    for j, p in enumerate(stage.poles):
                                        QTreeWidgetItem(
                                            poles_item, [
                                                f"Pole {j}", f"{p.real} + {p.imag}j"])

                                if hasattr(stage, "zeros"):
                                    zeros_item = QTreeWidgetItem(
                                        stage_item, ["Zeros", ""])
                                    for j, z in enumerate(stage.zeros):
                                        QTreeWidgetItem(
                                            zeros_item, [
                                                f"Zero {j}", f"{z.real} + {z.imag}j"])
        except Exception as e:
            QTreeWidgetItem(self.tree, ["Error", str(e)])

    def handle_tree_edit(self, item, column):
        if column != 1:
            return

        ref = item.data(0, Qt.UserRole)
        if ref is None:
            return

        ref_object, attr = ref
        new_value = item.text(1)

        old_value = getattr(ref_object, attr, None)
        try:
            if isinstance(old_value, float):
                new_value = float(new_value)
            elif isinstance(old_value, int):
                new_value = int(new_value)
            setattr(ref_object, attr, new_value)

            font = QFont()
            font.setBold(True)
            item.setFont(1, font)
            item.setForeground(1, QBrush(QColor("royalblue")))

            item.setData(1, Qt.UserRole, "modified")

        except Exception as e:
            QMessageBox.warning(
                self, "Edit Error", f"Failed to update {attr}: {e}")
            item.setText(1, str(old_value))

    def load_response_editor(self, response):
        self.selected_response = response

        for i in reversed(range(self.response_layout.count())):
            item = self.response_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        if response.instrument_sensitivity:
            sens = response.instrument_sensitivity
            left_layout.addWidget(
                QLabel(f"<b>Sensitivity:</b> {sens.value} @ {sens.frequency} Hz"))

        self.stage_tree = QTreeWidget()
        self.stage_tree.setHeaderLabels(["Field", "Value"])
        self.stage_tree.setColumnWidth(0, 200)
        self.stage_tree.itemChanged.connect(self.handle_response_edit)
        self.stage_tree.itemDoubleClicked.connect(self.edit_complex_value)

        self.populate_stage_tree(response)
        left_layout.addWidget(self.stage_tree)

        replace_button = QPushButton("Replace Response")
        left_layout.addWidget(replace_button)
        replace_button.clicked.connect(self.replace_response)

        save_btn = QPushButton("Save Response")
        save_btn.clicked.connect(self.save_edited_response)
        left_layout.addWidget(save_btn)
        splitter.addWidget(left_widget)

        self.canvas = MplCanvas(self)
        splitter.addWidget(self.canvas)

        self.response_layout.addWidget(splitter)

        self.tabs.setCurrentWidget(self.response_tab)

        self.plot_response(response)

    def plot_response(self, response):
        self.canvas.ax_amp.clear()
        self.canvas.ax_phase.clear()
        try:
            freq = np.logspace(-2, 2, 1000)
            h = response.get_evalresp_response_for_frequencies(
                freq, output="DEF")

            amp = np.abs(h)
            phase = np.angle(h, deg=True)

            self.canvas.ax_amp.plot(
                freq, amp, color="royalblue", label="Amplitude")
            self.canvas.ax_amp.set_title("Amplitude Response")
            self.canvas.ax_amp.set_ylabel("Amplitude")
            self.canvas.ax_amp.set_xscale("log")
            self.canvas.ax_amp.set_yscale("log")
            self.canvas.ax_amp.legend()

            self.canvas.ax_phase.plot(
                freq, phase, color="seagreen", label="Phase")
            self.canvas.ax_phase.set_title("Phase Response")
            self.canvas.ax_phase.set_xlabel("Frequency [Hz]")
            self.canvas.ax_phase.set_ylabel("Phase [°]")
            self.canvas.ax_phase.set_xscale("log")
            self.canvas.ax_phase.legend()

        except Exception as e:
            self.canvas.ax_amp.text(
                0.5, 0.5, f"Error plotting: {e}", ha="center")
            self.canvas.ax_phase.text(
                0.5, 0.5, f"Error plotting: {e}", ha="center")
        self.canvas.draw()

    def save_edited_response(self):
        if not hasattr(self, "selected_response"):
            return

        updated = False
        for net in self.current_inventory.networks:
            for sta in net.stations:
                for chan in sta.channels:
                    if chan.response == self.selected_response:
                        chan.response = self.selected_response
                        updated = True

        if updated:
            QMessageBox.information(
                self, "Saved", "Response updated successfully.")
            self.populate_tree(self.current_inventory)
            self.plot_response(self.selected_response)

            self.load_response_editor(self.selected_response)
        else:
            QMessageBox.warning(self, "Error", "Could not apply changes.")

    def populate_stage_tree(self, response):
        self.stage_tree.clear()
        if response.instrument_sensitivity:
            sens = response.instrument_sensitivity
            sens_item = QTreeWidgetItem(
                self.stage_tree, [
                    "Instrument Sensitivity", ""])

            val_item = QTreeWidgetItem(sens_item, ["Value", str(sens.value)])
            val_item.setFlags(val_item.flags() | Qt.ItemIsEditable)
            val_item.setData(0, Qt.UserRole, (sens, "value"))

            freq_item = QTreeWidgetItem(
                sens_item, [
                    "Frequency", str(
                        sens.frequency)])
            freq_item.setFlags(freq_item.flags() | Qt.ItemIsEditable)
            freq_item.setData(0, Qt.UserRole, (sens, "frequency"))

        for i, stage in enumerate(response.response_stages):
            stage_item = QTreeWidgetItem(
                self.stage_tree, [
                    f"Stage {i+1}: {type(stage).__name__}", ""])
            if hasattr(stage, "stage_gain"):
                item = QTreeWidgetItem(
                    stage_item, [
                        "Stage Gain", str(
                            stage.stage_gain)])
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                item.setData(0, Qt.UserRole, (stage, "stage_gain"))
            if hasattr(stage, "normalization_frequency"):
                item = QTreeWidgetItem(
                    stage_item, [
                        "Normalization Freq", str(
                            stage.normalization_frequency)])
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                item.setData(
                    0, Qt.UserRole, (stage, "normalization_frequency"))

            if hasattr(stage, "poles"):
                poles_item = QTreeWidgetItem(stage_item, ["Poles", ""])
                for j, pole in enumerate(stage.poles):
                    pole_item = QTreeWidgetItem(
                        poles_item, [
                            f"Pole {j}", f"{pole.real} + {pole.imag}j"])

                    pole_item.setData(0, Qt.UserRole, ("pole", stage, j))

            if hasattr(stage, "zeros"):
                zeros_item = QTreeWidgetItem(stage_item, ["Zeros", ""])
                for j, zero in enumerate(stage.zeros):
                    zero_item = QTreeWidgetItem(
                        zeros_item, [
                            f"Zero {j}", f"{zero.real} + {zero.imag}j"])
                    zero_item.setData(0, Qt.UserRole, ("zero", stage, j))

    def handle_response_edit(self, item, column):
        if column != 1:
            return

        ref = item.data(0, Qt.UserRole)
        if not ref or not isinstance(ref, tuple):
            return

        if len(ref) != 2:
            return

        ref_object, attr = ref
        new_text = item.text(1)
        old_value = getattr(ref_object, attr)

        try:
            if isinstance(old_value, float):
                new_value = float(new_text)
            elif isinstance(old_value, int):
                new_value = int(new_text)
            else:
                new_value = new_text

            setattr(ref_object, attr, new_value)

            item.setForeground(1, QBrush(QColor("blue")))
            font = item.font(1)
            font.setBold(True)
            item.setFont(1, font)

        except Exception as e:
            QMessageBox.warning(
                self, "Edit Error", f"Failed to update {attr}: {e}")
            item.setText(1, str(old_value))

    def edit_complex_value(self, item, column):
        if column != 1:
            return

        ref = item.data(0, Qt.UserRole)
        if not ref or not isinstance(ref, tuple):
            return

        if len(ref) != 3:
            return

        ref_type, stage, index = ref
        if ref_type not in ("pole", "zero"):
            return

        value = stage.poles[index] if ref_type == "pole" else stage.zeros[index]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit {ref_type.title()} {index}")
        layout = QVBoxLayout(dialog)

        real_edit = QLineEdit(str(value.real))
        imag_edit = QLineEdit(str(value.imag))

        layout.addWidget(QLabel("Real:"))
        layout.addWidget(real_edit)
        layout.addWidget(QLabel("Imag:"))
        layout.addWidget(imag_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            try:
                real = float(real_edit.text())
                imag = float(imag_edit.text())
                new_val = complex(real, imag)
                if ref_type == "pole":
                    stage.poles[index] = new_val
                else:
                    stage.zeros[index] = new_val

                item.setText(1, f"{new_val.real} + {new_val.imag}j")
                item.setForeground(1, QBrush(QColor("blue")))
                font = item.font(1)
                font.setBold(True)
                item.setFont(1, font)

                self.plot_response(self.selected_response)

            except ValueError:
                QMessageBox.warning(
                    self, "Invalid Input", "Please enter valid float numbers.")

    def select_response_from_inventory(self, inventory):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Response to Import")
        layout = QVBoxLayout(dialog)

        combo = QComboBox()
        channel_map = {}

        for net in inventory.networks:
            for sta in net.stations:
                for chan in sta.channels:
                    label = f"{net.code}.{sta.code}.{chan.location_code}.{chan.code}"
                    combo.addItem(label)
                    channel_map[label] = chan

        layout.addWidget(QLabel("Select Channel Response:"))
        layout.addWidget(combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            selected = combo.currentText()
            chan_to_copy = channel_map[selected]

            if hasattr(self, "selected_response") and self.selected_response:
                new_response = chan_to_copy.response
                if new_response:
                    self.selected_response.response_stages = copy.deepcopy(
                        new_response.response_stages)
                    self.selected_response.instrument_sensitivity = copy.deepcopy(
                        new_response.instrument_sensitivity)

                    QMessageBox.information(
                        self, "Success", "Response replaced successfully.")
                    self.load_response_editor(
                        self.selected_response)
                    self.plot_response(self.selected_response)
                else:
                    QMessageBox.warning(
                        self, "No Response", "Selected channel has no response.")

    def replace_response(self):
        choice, ok = QInputDialog.getItem(
            self, "Replace Response",
            "Choose source of replacement response:",
            ["Open from file", "Select from opened", "Load from local NRL folder"],
            0, False
        )

        if not ok:
            return

        if choice == "Open from file":
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Response File",
                "", "StationXML (*.xml);;RESP (*.resp);;Dataless SEED (*.dless *.seed);;All Files (*)"
            )
            if not path:
                return
            try:
                inv = read_inventory(path)
                self.select_response_from_inventory(inv)
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to read file:\n{e}")

        elif choice == "Select from opened":
            if not hasattr(
                    self, "loaded_inventories") or not self.loaded_inventories:
                QMessageBox.information(
                    self, "No inventories", "No other inventories are loaded.")
                return
            all_inv = Inventory(networks=[], source="merged")
            for inv in self.loaded_inventories:
                all_inv.networks.extend(inv.networks)
            self.select_response_from_inventory(all_inv)

        elif choice == "Load from local NRL folder":
            folder = QFileDialog.getExistingDirectory(
                self, "Select NRL Folder")
            if not folder:
                return
            dlg = NRLDialog(folder, self)
            dlg.exec_()

            new_resp = dlg.get_response()
            if new_resp and hasattr(
                    self, "selected_response") and self.selected_response:
                self.selected_response.response_stages = copy.deepcopy(
                    new_resp.response_stages)
                self.selected_response.instrument_sensitivity = copy.deepcopy(
                    new_resp.instrument_sensitivity)

                self.load_response_editor(self.selected_response)
                self.plot_response(self.selected_response)
                QMessageBox.information(
                    self, "Success", "Response loaded from local NRL.")


class NRLDialog(QDialog):
    def __init__(self, nrl_root, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(600)
        self.nrl_root = nrl_root
        self.nrl = NRL(root=nrl_root)
        self.stage = "sensor"
        self.sensor_path_stack = [os.path.join(nrl_root, "sensor")]
        self.datalogger_path_stack = [os.path.join(nrl_root, "datalogger")]
        self.selected_keys = {"sensor": [], "datalogger": []}
        self.response = None
        self.in_summary = False

        self._sensor_xml = None
        self._sensor_description = ""
        self._datalogger_xml = None
        self._datalogger_description = ""
        self._final_xml_config = None
        self.selected_option = None

        self.layout = QVBoxLayout(self)
        self.question_label = QLabel("Loading...")
        self.layout.addWidget(self.question_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll)

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignRight)
        button_layout.setSpacing(5)
        button_layout.addStretch()
        self.back_btn = QPushButton("Back")
        self.next_btn = QPushButton("Next")
        self.cancel_btn = QPushButton("Cancel")
        for btn in (self.back_btn, self.next_btn, self.cancel_btn):
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button_layout.addWidget(self.back_btn)
        button_layout.addWidget(self.next_btn)
        button_layout.addWidget(self.cancel_btn)
        self.layout.addLayout(button_layout)

        self.back_btn.clicked.connect(self.go_back)
        self.next_btn.clicked.connect(self.next_step)
        self.cancel_btn.clicked.connect(self.reject)

        self.option_buttons = {}
        self.load_step()

    def current_path_stack(self):
        return self.sensor_path_stack if self.stage == "sensor" else self.datalogger_path_stack

    def load_step(self):
        path_stack = self.current_path_stack()
        current_path = path_stack[-1]
        self.clear_layout(self.scroll_layout)
        self.selected_option = None
        self._final_xml_config = None
        self.next_btn.setText("Next")
        self._disconnect_next()
        self.next_btn.clicked.connect(self.next_step)

        index_path = os.path.join(current_path, "index.txt") if os.path.isdir(
            current_path) else current_path
        if not os.path.isfile(index_path):
            QMessageBox.warning(
                self, "Error", f"Missing index.txt in {index_path}")
            return

        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(index_path)

        self.question_label.setText(
            config.get(
                "Main",
                "question",
                fallback="Make a selection"))
        self.option_buttons = {}
        base_dir = os.path.dirname(index_path)
        for section in sorted(config.sections(), key=str.lower):
            if section == "Main":
                continue
            raw_path = config.get(
                section, "path", fallback="").strip().strip('"')
            btn = QRadioButton(wrap_text(section))
            btn.toggled.connect(
                lambda checked,
                s=section: self.set_selection(s))
            self.scroll_layout.addWidget(btn)
            resolved_path = os.path.join(base_dir, raw_path)
            self.option_buttons[section] = (btn, resolved_path)

        self.back_btn.setEnabled(
            len(path_stack) > 1 or self.stage == "datalogger")

    def load_final_xml_choices(self, config):
        self._final_xml_config = config
        self._at_final_xml_selection = True
        self.selected_option = None
        self.clear_layout(self.scroll_layout)
        self._disconnect_next()
        self.next_btn.setText("Finish" if self.stage ==
                              "datalogger" else "Next")
        self.next_btn.clicked.connect(self.next_step)

        question = config.get(
            "Main",
            "question",
            fallback="Select configuration")
        self.question_label.setText(question)

        self.option_buttons = {}
        for section in config.sections():
            if section == "Main":
                continue
            desc = config.get(
                section,
                "description",
                fallback="").strip().strip('"')
            xml = config.get(section, "xml", fallback="").strip().strip('"')

            label = f"{section}: {desc}"
            wrapped_label = wrap_text(label)
            btn = QRadioButton(wrapped_label)
            btn.toggled.connect(
                lambda checked,
                s=section: self.set_selection(s))
            self.scroll_layout.addWidget(btn)
            self.option_buttons[section] = (btn, xml)

    def next_step(self):
        if not self.selected_option:
            QMessageBox.warning(self, "Selection Required",
                                "Please select an option.")
            return

        _, next_path = self.option_buttons[self.selected_option]

        if not self.selected_keys[self.stage] or self.selected_keys[self.stage][-1] != self.selected_option:
            self.selected_keys[self.stage].append(self.selected_option)

        if self._final_xml_config:
            xml_filename = self.option_buttons[self.selected_option][1]
            description = self.option_buttons[self.selected_option][0].text()

            if self.stage == "sensor":
                self._sensor_xml = xml_filename
                self._sensor_description = description
                self.stage = "datalogger"
                self.selected_option = None
                self._final_xml_config = None
                self.load_step()
            else:
                self._datalogger_xml = xml_filename
                self._datalogger_description = description
                self.show_summary()
            return

        config = configparser.ConfigParser()
        config.optionxform = str

        if os.path.isfile(next_path) and next_path.endswith(".txt"):
            config.read(next_path)
            if "Main" in config:
                sections = [s for s in config.sections() if s != "Main"]
                if all(config.has_option(s, "xml") and config.has_option(
                        s, "description") for s in sections):
                    self._final_xml_config = config
                    self.current_path_stack().append(next_path)
                    self.load_final_xml_choices(config)
                    return
                elif all(config.has_option(s, "path") for s in sections):
                    self.current_path_stack().append(next_path)
                    self.load_step()
                    return

        elif os.path.isdir(next_path):
            self.current_path_stack().append(next_path)
            self.load_step()
            return

        QMessageBox.warning(
            self,
            "NRL Error",
            f"Unrecognized path:\n{next_path}")

    def go_back(self):
        if self.in_summary:
            # From summary, go back to final XML config screen
            self.in_summary = False
            self.stage = "datalogger"
            self.selected_option = None
            if self.selected_keys["datalogger"]:
                self.selected_keys["datalogger"].pop()
            self._at_final_xml_selection = True
            self.selected_option = None
            self._disconnect_next()
            self.next_btn.setText("Finish")
            self.next_btn.clicked.connect(self.next_step)
            self.load_final_xml_choices(self._final_xml_config)
            return

        if getattr(self, "_at_final_xml_selection", False):
            # If we're coming back from XML config screen, go back one step
            self._at_final_xml_selection = False
            path_stack = self.current_path_stack()
            if len(path_stack) > 1:
                path_stack.pop()
            if self.selected_keys[self.stage]:
                self.selected_keys[self.stage].pop()
            self.selected_option = None
            self._final_xml_config = None
            self.load_step()
            return

        path_stack = self.current_path_stack()
        if len(path_stack) > 1:
            path_stack.pop()
            if self.selected_keys[self.stage]:
                self.selected_keys[self.stage].pop()
            self.selected_option = None
            self._final_xml_config = None
            self.load_step()
        elif self.stage == "datalogger":
            self.stage = "sensor"
            self.selected_option = None
            self._final_xml_config = None
            self.load_step()

    def show_summary(self):
        self.in_summary = True
        self.clear_layout(self.scroll_layout)
        self.question_label.setText("Review your selections and confirm:")

        summary_text = (
            "<b>Sensor Selection:</b><br>"
            + "<br>".join(self.selected_keys["sensor"])
            + f"<br><i>{self._sensor_description}</i><br><br>"
            + "<b>Datalogger Selection:</b><br>"
            + "<br>".join(self.selected_keys["datalogger"])
            + f"<br><i>{self._datalogger_description}</i>"
        )

        label = QLabel(summary_text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.scroll_layout.addWidget(label)

        self.next_btn.setText("Finish")
        self._disconnect_next()
        self.next_btn.clicked.connect(self.finalize_response)

    def finalize_response(self):
        try:
            self.response = self.nrl.get_response(
                sensor_keys=self.selected_keys["sensor"],
                datalogger_keys=self.selected_keys["datalogger"],
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "NRL Error", f"Failed to generate response:\n{e}")

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def set_selection(self, section):
        if self.option_buttons[section][0].isChecked():
            self.selected_option = section

    def _disconnect_next(self):
        try:
            self.next_btn.clicked.disconnect()
        except Exception:
            pass

    def get_response(self):
        return self.nrl.get_response(
            sensor_keys=self.selected_keys["sensor"],
            datalogger_keys=self.selected_keys["datalogger"]
        )


def wrap_text(text, max_len=75):
    lines = []
    while len(text) > max_len:
        semi_idx = text.rfind(";", 0, max_len)
        space_idx = text.rfind(" ", 0, max_len)
        break_idx = -1

        if semi_idx != -1:
            break_idx = semi_idx + 1
        elif space_idx != -1:
            break_idx = space_idx
        else:
            break_idx = max_len

        lines.append(text[:break_idx].strip())
        text = text[break_idx:].strip()

    lines.append(text)
    return "\n".join(lines)
