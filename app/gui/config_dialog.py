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
        self.folder_widgets = []

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
        api_row.addWidget(self.radio_production)
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
        layout.addRow(QLabel("Authentication"))

        # Auth Method
        self.auth_method = QComboBox()
        self.auth_method.addItems(["API Key", "Username / Password"])
        if self.config.qualer_auth_mode == "credentials":
            self.auth_method.setCurrentIndex(1)
        else:
            self.auth_method.setCurrentIndex(0)
        layout.addRow("Auth Method:", self.auth_method)

        # -- API Key group --
        self.api_key_group = QWidget()
        api_key_layout = QFormLayout(self.api_key_group)
        api_key_layout.setContentsMargins(0, 0, 0, 0)

        # Qualer API Key — never pre-populated; user types a new value to replace
        self.qualer_key = QLineEdit()
        self.qualer_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.qualer_key.setPlaceholderText(
            "(saved — type to replace)" if self.config.qualer_api_key else "(not set)"
        )
        api_key_layout.addRow("Qualer API Key:", self.qualer_key)
        layout.addRow(self.api_key_group)

        # -- Credentials group --
        self.credentials_group = QWidget()
        cred_layout = QFormLayout(self.credentials_group)
        cred_layout.setContentsMargins(0, 0, 0, 0)

        self.username_edit = QLineEdit(self.config.qualer_username)
        cred_layout.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit(self.config.qualer_password)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        pwd_row = QHBoxLayout()
        pwd_row.addWidget(self.password_edit)
        show_pwd = QPushButton("Show")
        show_pwd.setFixedWidth(50)
        show_pwd.setCheckable(True)
        show_pwd.toggled.connect(
            lambda checked: self.password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        pwd_row.addWidget(show_pwd)
        cred_layout.addRow("Password:", pwd_row)

        self.test_login_btn = QPushButton("Test Login")
        self.test_login_btn.clicked.connect(self._test_login)
        cred_layout.addRow("", self.test_login_btn)

        layout.addRow(self.credentials_group)

        # Toggle visibility based on current auth method
        self._on_auth_method_changed(self.auth_method.currentIndex())
        self.auth_method.currentIndexChanged.connect(self._on_auth_method_changed)

        # Gemini API Key (always visible, independent of auth method)
        layout.addRow(QLabel(""))
        # Gemini API Key — never pre-populated; user types a new value to replace
        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.setPlaceholderText(
            "(saved — type to replace)" if self.config.gemini_api_key else "(not set)"
        )
        layout.addRow("Gemini API Key:", self.gemini_key)

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

    def _on_auth_method_changed(self, index: int):
        is_credentials = index == 1
        self.api_key_group.setVisible(not is_credentials)
        self.credentials_group.setVisible(is_credentials)

    def _test_login(self):
        from app.auth import AuthenticationError, qualer_login

        username = self.username_edit.text()
        password = self.password_edit.text()
        if not username or not password:
            QMessageBox.warning(self, "Validation", "Enter username and password.")
            return
        base_url = (self.config.qualer_endpoint).removesuffix("/api")
        try:
            token = qualer_login(username, password, base_url)
            QMessageBox.information(
                self,
                "Success",
                "Login successful! Token will be saved when you click Save.",
            )
            self.qualer_key.setText(token)
        except AuthenticationError as e:
            QMessageBox.critical(self, "Login Failed", str(e))

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

        auth_mode = "credentials" if self.auth_method.currentIndex() == 1 else "api_key"

        # Build new config — keep existing key when the field is left blank
        qualer_text = self.qualer_key.text().strip()
        gemini_text = self.gemini_key.text().strip()
        new_config = AppConfig(
            max_runtime=max_runtime,
            debug=self.debug_check.isChecked(),
            delete_mode=self.delete_check.isChecked(),
            tesseract_cmd_path=self.tesseract_path.text(),
            sharepoint_path=self.sharepoint_path.text(),
            log_file=self.config.log_file,
            po_dict_file=self.config.po_dict_file,
            qualer_endpoint=self.config.qualer_endpoint,
            watched_folders=folders,
            qualer_api_key=qualer_text or self.config.qualer_api_key,
            gemini_api_key=gemini_text or self.config.gemini_api_key,
            qualer_auth_mode=auth_mode,
            qualer_username=(
                self.username_edit.text() if auth_mode == "credentials" else ""
            ),
            qualer_password=(
                self.password_edit.text() if auth_mode == "credentials" else ""
            ),
        )

        # Save config.yaml
        save_config(new_config)

        # Persist secrets
        save_env(
            qualer_api_key=new_config.qualer_api_key,
            gemini_api_key=new_config.gemini_api_key,
            qualer_auth_mode=new_config.qualer_auth_mode,
            qualer_username=new_config.qualer_username,
            qualer_password=new_config.qualer_password,
        )

        # Invalidate cached client so next API call uses new credentials
        from app.qualer_client import reset_qualer_client

        reset_qualer_client()

        self.accept()
