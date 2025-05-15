"""
Top-level window widget that contains other widgets
"""
from __future__ import annotations

import logging
from typing import Optional

import qtawesome as qta
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QCloseEvent

from superscore.client import Client
from superscore.widgets.core import QtSingleton
from superscore.widgets.pv_browser_table import (PVBrowserFilterProxyModel,
                                                 PVBrowserTableModel)
from superscore.widgets.pv_table import PV_HEADER, PVTableModel
from superscore.widgets.snapshot_table import SnapshotTableModel
from superscore.widgets.views import DiffDispatcher

logger = logging.getLogger(__name__)


class Window(QtWidgets.QMainWindow, metaclass=QtSingleton):
    """Main superscore window"""

    # Diff dispatcher singleton, used to notify when diffs are ready
    diff_dispatcher: DiffDispatcher = DiffDispatcher()

    def __init__(self, *args, client: Optional[Client] = None, **kwargs):
        super().__init__(*args, **kwargs)
        if client:
            self.client = client
        else:
            self.client = Client.from_config()
        self.live_models: set[PVTableModel] = set()
        self.setup_ui()

    def setup_ui(self) -> None:
        self.init_view_snapshot_page()
        self.init_pv_browser_page()

        navigation_panel = NavigationPanel()
        navigation_panel.sigViewSnapshots.connect(lambda: self.open_page(self.view_snapshot_page))
        navigation_panel.sigBrowsePVs.connect(lambda: self.open_page(self.pv_browser_page))

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(navigation_panel)
        self.splitter.addWidget(self.view_snapshot_page)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        self.setWindowTitle("Superscore")
        self.setCentralWidget(self.splitter)

    def init_view_snapshot_page(self) -> None:
        self.view_snapshot_page = QtWidgets.QWidget()
        view_snapshot_layout = QtWidgets.QVBoxLayout()
        view_snapshot_layout.setContentsMargins(0, 11, 0, 0)
        self.view_snapshot_page.setLayout(view_snapshot_layout)

        self.snapshot_model = SnapshotTableModel(self.client)
        snapshot_table = QtWidgets.QTableView()
        snapshot_table.setModel(self.snapshot_model)
        snapshot_table.doubleClicked.connect(self.open_snapshot_details)
        snapshot_table.setStyleSheet(
            "QTableView::item {"
            "    border: 0px;"  # required to enforce padding on left side of cell
            "    padding: 5px;"
            "}"
        )
        snapshot_table.verticalHeader().hide()
        header_view = snapshot_table.horizontalHeader()
        header_view.setSectionResizeMode(header_view.ResizeToContents)
        header_view.setSectionResizeMode(1, header_view.Stretch)
        view_snapshot_layout.addWidget(snapshot_table)

    def init_pv_browser_page(self) -> None:
        """Initialize the PV browser page with the PV browser table."""
        pv_browser_model = PVBrowserTableModel(self.client)
        pv_browser_filter = PVBrowserFilterProxyModel()
        pv_browser_filter.setSourceModel(pv_browser_model)

        self.pv_browser_page = QtWidgets.QWidget()
        pv_browser_layout = QtWidgets.QVBoxLayout()
        pv_browser_layout.setContentsMargins(0, 11, 0, 0)
        self.pv_browser_page.setLayout(pv_browser_layout)

        search_bar = QtWidgets.QLineEdit(self.pv_browser_page)
        search_bar.setClearButtonEnabled(True)
        search_bar.addAction(
            qta.icon("fa5s.search"),
            QtWidgets.QLineEdit.LeadingPosition,
        )
        search_bar.textChanged.connect(pv_browser_filter.setFilterFixedString)
        search_bar_lyt = QtWidgets.QHBoxLayout()
        spacer = QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        search_bar_lyt.addWidget(search_bar)
        search_bar_lyt.addSpacerItem(spacer)
        pv_browser_layout.addLayout(search_bar_lyt)

        self.pv_browser_table = QtWidgets.QTableView(self.pv_browser_page)
        self.pv_browser_table.setModel(pv_browser_filter)
        self.pv_browser_table.verticalHeader().hide()
        header_view = self.pv_browser_table.horizontalHeader()
        header_view.setSectionResizeMode(header_view.ResizeToContents)
        header_view.setStretchLastSection(True)
        pv_browser_layout.addWidget(self.pv_browser_table)

    def open_snapshot_details(self, index: QtCore.QModelIndex) -> None:
        snapshot = self.snapshot_model.index_to_snapshot(index)
        snapshot_details_model = PVTableModel(snapshot.uuid, self.client)
        self.live_models.add(snapshot_details_model)

        snapshot_details_table = QtWidgets.QTableView()
        snapshot_details_table.setModel(snapshot_details_model)
        snapshot_details_table.destroyed.connect(snapshot_details_model.close)
        snapshot_details_table.setShowGrid(False)
        snapshot_details_table.verticalHeader().hide()
        header_view = snapshot_details_table.horizontalHeader()
        header_view.setSectionResizeMode(header_view.Stretch)
        header_view.setSectionResizeMode(PV_HEADER.CHECKBOX.value, header_view.ResizeToContents)
        header_view.setSectionResizeMode(PV_HEADER.SEVERITY.value, header_view.ResizeToContents)
        header_view.setSectionResizeMode(PV_HEADER.DEVICE.value, header_view.ResizeToContents)
        header_view.setSectionResizeMode(PV_HEADER.PV.value, header_view.ResizeToContents)

        self.open_page(snapshot_details_table)

    def open_page(self, page: QtWidgets.QWidget) -> None:
        """Open a page in the main window."""
        curr_widget = self.splitter.widget(1)
        if curr_widget is page:
            return
        self.splitter.replaceWidget(1, page)
        self.splitter.setStretchFactor(1, 1)

    def closeEvent(self, a0: QCloseEvent) -> None:
        for model in self.live_models:
            model.close()
        super().closeEvent(a0)


class NavigationPanel(QtWidgets.QWidget):

    sigViewSnapshots = QtCore.Signal()
    sigBrowsePVs = QtCore.Signal()
    sigConfigureTags = QtCore.Signal()
    sigSave = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setLayout(QtWidgets.QVBoxLayout())

        view_snapshots_button = QtWidgets.QPushButton()
        view_snapshots_button.setIcon(qta.icon("ph.stack"))
        view_snapshots_button.setText("View Snapshots")
        view_snapshots_button.setFlat(True)
        view_snapshots_button.clicked.connect(self.sigViewSnapshots.emit)
        self.layout().addWidget(view_snapshots_button)

        browse_pvs_button = QtWidgets.QPushButton()
        browse_pvs_button.setIcon(qta.icon("ph.database"))
        browse_pvs_button.setText("Browse PVs")
        browse_pvs_button.setFlat(True)
        browse_pvs_button.clicked.connect(self.sigBrowsePVs.emit)
        self.layout().addWidget(browse_pvs_button)

        configure_tags_button = QtWidgets.QPushButton()
        configure_tags_button.setIcon(qta.icon("ph.tag"))
        configure_tags_button.setText("Configure Tags")
        configure_tags_button.setFlat(True)
        configure_tags_button.clicked.connect(self.sigConfigureTags.emit)
        self.layout().addWidget(configure_tags_button)

        self.layout().addStretch()

        save_button = QtWidgets.QPushButton()
        save_button.setIcon(qta.icon("ph.instagram-logo"))
        save_button.setText("Save Snapshot")
        save_button.clicked.connect(self.sigSave.emit)
        self.layout().addWidget(save_button)
