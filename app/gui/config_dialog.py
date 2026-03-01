"""Configuration dialog for editing settings and watched folders."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config_manager import (
    AppConfig,
    WatchedFolder,
    get_config,
    save_config,
    save_env,
)

QUALER_DOCUMENT_TYPES = [
    "general",
    "assetsummary",
    "assetlabel",
    "assetdetail",
    "assetcertificate",
    "ordersummary",
    "orderinvoice",
    "orderestimate",
    "dashboard",
    "orderdetail",
    "ordercertificate",
]


class FolderConfigWidget(QGroupBox):
    """Editable widget for a single watched folder configuration."""

    def __init__(self, folder: WatchedFolder, index: int, parent=None):
        super().__init__(f"Folder {index + 1}", parent)
        self.index = index

        layout = QFormLayout(self)

        # Input dir
        self.input_dir = QLineEdit(folder.input_dir)
        input_row = QHBoxLayout()
        input_row.addWidget(self.input_dir)
        input_browse = QPushButton("...")
        input_browse.setFixedWidth(30)
        input_browse.clicked.connect(lambda: self._browse(self.input_dir))
        input_row.addWidget(input_browse)
        layout.addRow("Input Dir:", input_row)

        # Archive dir
        self.output_dir = QLineEdit(folder.output_dir)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir)
        output_browse = QPushButton("...")
        output_browse.setFixedWidth(30)
        output_browse.clicked.connect(lambda: self._browse(self.output_dir))
        output_row.addWidget(output_browse)
        layout.addRow("Archive Dir:", output_row)

        # Reject dir
        self.reject_dir = QLineEdit(folder.reject_dir)
        reject_row = QHBoxLayout()
        reject_row.addWidget(self.reject_dir)
        reject_browse = QPushButton("...")
        reject_browse.setFixedWidth(30)
        reject_browse.clicked.connect(lambda: self._browse(self.reject_dir))
        reject_row.addWidget(reject_browse)
        layout.addRow("Reject Dir:", reject_row)

        # Document type
        self.doc_type = QComboBox()
        self.doc_type.addItems(QUALER_DOCUMENT_TYPES)
        current_idx = 0
        for i, dt in enumerate(QUALER_DOCUMENT_TYPES):
            if dt.lower() == folder.qualer_document_type.lower():
                current_idx = i
                break
        self.doc_type.setCurrentIndex(current_idx)
        layout.addRow("Document Type:", self.doc_type)

        # Validate PO
        self.validate_po = QCheckBox("Validate PO prices")
        self.validate_po.setChecked(folder.validate_po)
        layout.addRow("", self.validate_po)

        # Remove button
        self.remove_btn = QPushButton("Remove Folder")
        self.remove_btn.setStyleSheet("color: red;")
        layout.addRow("", self.remove_btn)

    def _browse(self, line_edit):
        path = QFileDialog.getExistingDirectory(
            self, "Select Directory", line_edit.text()
        )
        if path:
            line_edit.setText(path)

    def to_watched_folder(self) -> WatchedFolder:
        """Read current form values into a WatchedFolder."""
        return WatchedFolder(
            input_dir=self.input_dir.text(),
            output_dir=self.output_dir.text(),
            reject_dir=self.reject_dir.text(),
            qualer_document_type=self.doc_type.currentText(),
            validate_po=self.validate_po.isChecked(),
        )


class ConfigDialog(QDialog):
    """Settings dialog with General and Watched Folders tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(650, 550)
        self.config = get_config()
        self.folder_widgets: list[FolderConfigWidget] = []

        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self._build_general_tab()
        self._build_folders_tab()
        main_layout.addWidget(self.tabs)

        # Button box
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _build_general_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        # API Mode
        api_row = QHBoxLayout()
        self.radio_production = QRadioButton("Production")
        self.radio_staging = QRadioButton("Staging")
        if self.config.live_api:
            self.radio_production.setChecked(True)
        else:
            self.radio_staging.setChecked(True)
        api_row.addWidget(self.radio_production)
        api_row.addWidget(self.radio_staging)
        api_row.addStretch()
        layout.addRow("API Mode:", api_row)

        # Debug mode
        self.debug_check = QCheckBox("Skip uploads (debug)")
        self.debug_check.setChecked(self.config.debug)
        layout.addRow("Debug Mode:", self.debug_check)

        # Delete mode
        self.delete_check = QCheckBox("Delete old PDFs (vs archive)")
        self.delete_check.setChecked(self.config.delete_mode)
        layout.addRow("Delete Mode:", self.delete_check)

        # Max runtime
        self.max_runtime = QLineEdit(
            str(self.config.max_runtime) if self.config.max_runtime else ""
        )
        self.max_runtime.setPlaceholderText("blank = unlimited")
        layout.addRow("Max Runtime (s):", self.max_runtime)

        # Tesseract path
        tess_row = QHBoxLayout()
        self.tesseract_path = QLineEdit(self.config.tesseract_cmd_path)
        tess_row.addWidget(self.tesseract_path)
        tess_browse = QPushButton("...")
        tess_browse.setFixedWidth(30)
        tess_browse.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(tess_browse)
        layout.addRow("Tesseract Path:", tess_row)

        # SharePoint path
        sp_row = QHBoxLayout()
        self.sharepoint_path = QLineEdit(self.config.sharepoint_path)
        sp_row.addWidget(self.sharepoint_path)
        sp_browse = QPushButton("...")
        sp_browse.setFixedWidth(30)
        sp_browse.clicked.connect(self._browse_sharepoint)
        sp_row.addWidget(sp_browse)
        layout.addRow("SharePoint Path:", sp_row)

        # Separator
        layout.addRow(QLabel(""))
        layout.addRow(QLabel("API Keys (stored in .env)"))

        # Qualer API Key
        self.qualer_key = QLineEdit(self.config.qualer_api_key)
        self.qualer_key.setEchoMode(QLineEdit.EchoMode.Password)
        key_row = QHBoxLayout()
        key_row.addWidget(self.qualer_key)
        show_qualer = QPushButton("Show")
        show_qualer.setFixedWidth(50)
        show_qualer.setCheckable(True)
        show_qualer.toggled.connect(
            lambda checked: self.qualer_key.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        key_row.addWidget(show_qualer)
        layout.addRow("Qualer API Key:", key_row)

        # Gemini API Key
        self.gemini_key = QLineEdit(self.config.gemini_api_key)
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        gkey_row = QHBoxLayout()
        gkey_row.addWidget(self.gemini_key)
        show_gemini = QPushButton("Show")
        show_gemini.setFixedWidth(50)
        show_gemini.setCheckable(True)
        show_gemini.toggled.connect(
            lambda checked: self.gemini_key.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        gkey_row.addWidget(show_gemini)
        layout.addRow("Gemini API Key:", gkey_row)

        self.tabs.addTab(tab, "General")

    def _build_folders_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        # Scroll area for folder widgets
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.folders_layout = QVBoxLayout(scroll_widget)
        self.folders_layout.addStretch()
        scroll.setWidget(scroll_widget)
        tab_layout.addWidget(scroll)

        # Add existing folders
        for i, wf in enumerate(self.config.watched_folders):
            self._add_folder_widget(wf, i)

        # Add folder button
        add_btn = QPushButton("+ Add Folder")
        add_btn.clicked.connect(self._add_empty_folder)
        tab_layout.addWidget(add_btn)

        self.tabs.addTab(tab, "Watched Folders")

    def _add_folder_widget(self, folder: WatchedFolder, index: int):
        widget = FolderConfigWidget(folder, index)
        widget.remove_btn.clicked.connect(lambda: self._remove_folder(widget))
        # Insert before the stretch
        self.folders_layout.insertWidget(self.folders_layout.count() - 1, widget)
        self.folder_widgets.append(widget)

    def _add_empty_folder(self):
        empty = WatchedFolder(input_dir="", output_dir="", reject_dir="")
        idx = len(self.folder_widgets)
        self._add_folder_widget(empty, idx)

    def _remove_folder(self, widget):
        self.folders_layout.removeWidget(widget)
        self.folder_widgets.remove(widget)
        widget.deleteLater()
        # Re-index remaining widgets
        for i, fw in enumerate(self.folder_widgets):
            fw.setTitle(f"Folder {i + 1}")

    def _browse_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Tesseract Executable",
            self.tesseract_path.text(),
            "Executables (*.exe);;All Files (*)",
        )
        if path:
            self.tesseract_path.setText(path)

    def _browse_sharepoint(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select SharePoint Directory", self.sharepoint_path.text()
        )
        if path:
            self.sharepoint_path.setText(path)

    def _save(self):
        # Validate
        folders = [fw.to_watched_folder() for fw in self.folder_widgets]
        for i, f in enumerate(folders):
            if not f.input_dir:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Folder {i + 1}: Input directory is required.",
                )
                return

        # Parse max runtime
        max_runtime = None
        rt_text = self.max_runtime.text().strip()
        if rt_text:
            try:
                max_runtime = int(rt_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Validation Error", "Max Runtime must be a number or blank."
                )
                return

        # Build new config
        new_config = AppConfig(
            max_runtime=max_runtime,
            live_api=self.radio_production.isChecked(),
            debug=self.debug_check.isChecked(),
            delete_mode=self.delete_check.isChecked(),
            tesseract_cmd_path=self.tesseract_path.text(),
            sharepoint_path=self.sharepoint_path.text(),
            log_file=self.config.log_file,
            po_dict_file=self.config.po_dict_file,
            qualer_endpoint=self.config.qualer_endpoint,
            qualer_staging_endpoint=self.config.qualer_staging_endpoint,
            watched_folders=folders,
            qualer_api_key=self.qualer_key.text(),
            gemini_api_key=self.gemini_key.text(),
        )

        # Save config.yaml
        save_config(new_config)

        # Save .env if keys changed
        if (
            new_config.qualer_api_key != self.config.qualer_api_key
            or new_config.gemini_api_key != self.config.gemini_api_key
        ):
            save_env(new_config.qualer_api_key, new_config.gemini_api_key)

        self.accept()
