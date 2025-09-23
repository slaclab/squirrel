"""
Top-level window widget that contains other widgets
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Optional

import qtawesome as qta
from epicscorelibs.ca.cadef import CAException
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QCloseEvent

from squirrel.client import Client
from squirrel.model import PV, EpicsData, Snapshot
from squirrel.permission_manager import PermissionManager
from squirrel.widgets.core import NameDescTagsWidget, QtSingleton
from squirrel.widgets.date_range import DateRangeWidget
from squirrel.widgets.filter_bar import FilterBar
from squirrel.widgets.page.page import Page
from squirrel.widgets.page.pv_browser import PVBrowserPage
from squirrel.widgets.page.snapshot_comparison import SnapshotComparisonPage
from squirrel.widgets.page.snapshot_details import SnapshotDetailsPage
from squirrel.widgets.page.tag import TagPage
from squirrel.widgets.pv_details_components import (PVDetails, PVDetailsPopup,
                                                    PVDetailsPopupEditable)
from squirrel.widgets.tables import (PVTableModel, SnapshotFilterModel,
                                     SnapshotTableModel, SquirrelTableView)
from squirrel.widgets.views import DiffDispatcher

logger = logging.getLogger(__name__)


class Window(QtWidgets.QMainWindow, metaclass=QtSingleton):
    """Main squirrel window"""

    # Diff dispatcher singleton, used to notify when diffs are ready
    diff_dispatcher: DiffDispatcher = DiffDispatcher()

    def __init__(self, *args, client: Optional[Client] = None, **kwargs):
        super().__init__(*args, **kwargs)
        if client:
            self.client = client
        else:
            self.client = Client.from_config()
        self.pages: set[Page] = set()
        self.setup_ui()

        self.permission_manager = PermissionManager.get_instance()

    def setup_ui(self) -> None:
        self.navigation_panel = self.init_nav_panel()

        # Initialize content pages and add to stack
        self.view_snapshot_page = self.init_view_snapshot_page()
        self.snapshot_details_page = self.init_snapshot_details_page()
        self.comparison_page = self.init_comparison_page()
        self.pv_browser_page = self.init_pv_browser_page()
        self.configure_page = self.init_configure_page()

        self.pages.add(self.view_snapshot_page)
        self.pages.add(self.snapshot_details_page)
        self.pages.add(self.comparison_page)
        self.pages.add(self.pv_browser_page)
        self.pages.add(self.configure_page)

        self.main_content_stack = QtWidgets.QStackedLayout()
        for page in self.pages:
            self.main_content_stack.addWidget(page)
        self.main_content_stack.setCurrentWidget(self.view_snapshot_page)

        self.main_content_container = QtWidgets.QWidget()
        self.main_content_container.setContentsMargins(0, 0, 0, 0)
        self.main_content_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.main_content_container.setLayout(self.main_content_stack)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(QtWidgets.QHBoxLayout())
        central_widget.layout().addWidget(self.navigation_panel)
        central_widget.layout().addWidget(self.main_content_container)
        central_widget.layout().setSpacing(0)
        central_widget.layout().setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)

    def init_nav_panel(self) -> NavigationPanel:
        navigation_panel = NavigationPanel()
        navigation_panel.sigViewSnapshots.connect(self.open_view_snapshot_page)
        navigation_panel.sigBrowsePVs.connect(self.open_pv_browser_page)
        navigation_panel.sigSave.connect(self.take_snapshot)
        navigation_panel.sigConfigureTags.connect(self.open_configure_page)
        navigation_panel.set_nav_button_selected(navigation_panel.view_snapshots_button)
        navigation_panel.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        return navigation_panel

    def init_view_snapshot_page(self) -> QtWidgets.QWidget:
        """Initialize the snapshot page"""
        view_snapshot_page = QtWidgets.QWidget()
        view_snapshot_layout = QtWidgets.QVBoxLayout()
        view_snapshot_layout.setContentsMargins(0, 11, 0, 0)
        view_snapshot_page.setLayout(view_snapshot_layout)

        filters_layout = QtWidgets.QHBoxLayout()

        date_range = DateRangeWidget()
        date_range.setRange(
            QtCore.QDate.currentDate().addYears(-1),
            QtCore.QDate.currentDate(),
        )
        filters_layout.addWidget(date_range)

        search_bar = QtWidgets.QLineEdit()
        search_bar.setClearButtonEnabled(True)
        search_bar.addAction(
            qta.icon("fa5s.search"),
            QtWidgets.QLineEdit.TrailingPosition,
        )
        search_bar.setPlaceholderText("Search title...")
        filters_layout.addWidget(search_bar)

        filter_toggle_button = QtWidgets.QPushButton(qta.icon("fa5s.filter"), "Filter  ")
        filter_toggle_button.setLayoutDirection(QtCore.Qt.RightToLeft)  # Put the filter icon after the button text
        filter_toggle_button.setToolTip("Show/hide meta pv filters")
        filter_toggle_button.clicked.connect(self.toggle_filter_popup)
        filters_layout.addWidget(filter_toggle_button)

        spacer = QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        filters_layout.addSpacerItem(spacer)

        view_snapshot_layout.addLayout(filters_layout)

        self.snapshot_table = SquirrelTableView()
        snapshot_model = SnapshotTableModel(self.client)
        proxy_model = SnapshotFilterModel()
        proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        proxy_model.setSourceModel(snapshot_model)
        self.snapshot_table.setModel(proxy_model)
        self.snapshot_table.doubleClicked.connect(self.open_snapshot_index)
        self.snapshot_table.setShowGrid(False)
        self.snapshot_table.setStyleSheet(
            "QTableView::item {"
            "    padding: 5px;"
            "}"
        )
        self.snapshot_table.setSelectionBehavior(self.snapshot_table.SelectionBehavior.SelectRows)
        self.snapshot_table.verticalHeader().hide()
        header_view = self.snapshot_table.horizontalHeader()
        header_view.setSectionResizeMode(header_view.ResizeMode.Fixed)
        header_view.setSectionResizeMode(1, header_view.ResizeMode.Stretch)
        self.snapshot_table.resizeColumnsToContents()
        view_snapshot_layout.addWidget(self.snapshot_table)

        search_bar.textEdited.connect(proxy_model.setFilterFixedString)
        date_range.rangeChanged.connect(proxy_model.setDateRange)

        # Set up the filters for the meta pv columns
        meta_columns = [pv.description for pv in self.client.backend.get_meta_pvs()]
        self.meta_pv_filter_popup = QtWidgets.QFrame(self)
        self.meta_pv_filter_popup.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.meta_pv_filter_popup.setWindowFlags(QtCore.Qt.Popup)
        filter_popup_layout = QtWidgets.QVBoxLayout(self.meta_pv_filter_popup)
        filter_popup_layout.setContentsMargins(10, 10, 10, 10)

        self.meta_pv_filter_bar = FilterBar(meta_columns)
        filter_popup_layout.addWidget(self.meta_pv_filter_bar)

        self.meta_pv_filter_bar.filters_updated.connect(
            lambda: proxy_model.setMetaPVFilters(self.meta_pv_filter_bar.get_filters())
        )

        self.meta_pv_filter_popup.installEventFilter(self)

        return view_snapshot_page

    def init_snapshot_details_page(self) -> SnapshotDetailsPage:
        """Initialize the snapshot details page with the first snapshot in the snapshot_model."""
        temp_index = self.snapshot_table.model().sourceModel().index(0, 0)
        first_snapshot = self.snapshot_table.model().sourceModel().index_to_snapshot(temp_index)
        snapshot_details_page = SnapshotDetailsPage(self, self.client, first_snapshot)
        snapshot_details_page.snapshot_details_table.doubleClicked.connect(
            lambda index: self.open_pv_details(index, snapshot_details_page.snapshot_details_table)
        )
        snapshot_details_page.back_to_main_signal.connect(self.open_view_snapshot_page)
        snapshot_details_page.comparison_signal.connect(self.open_comparison_page)

        return snapshot_details_page

    def init_comparison_page(self) -> SnapshotComparisonPage:
        """Initialize the snapshot comparison page so it can be opened later."""
        comparison_page = SnapshotComparisonPage(self.client, self)
        comparison_page.remove_comparison_signal.connect(self.open_snapshot)

        return comparison_page

    def init_pv_browser_page(self) -> PVBrowserPage:
        """Initialize the PV browser page with the PV browser table."""
        pv_browser_page = PVBrowserPage(self.client, self)
        pv_browser_page.sigOpenPVDetails.connect(self.open_pv_editor)
        pv_browser_page.sigAddPV.connect(self.open_new_pv_dialog)
        return pv_browser_page

    def init_configure_page(self) -> QtWidgets.QWidget:
        """Initialize the configure page with the tag groups window."""
        configure_page = QtWidgets.QWidget()
        configure_layout = QtWidgets.QVBoxLayout()
        configure_layout.setContentsMargins(0, 11, 0, 0)
        configure_page.setLayout(configure_layout)

        self.tag_groups_window = TagPage(self.client)
        self.tag_groups_window.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        configure_layout.addWidget(self.tag_groups_window)

        return configure_page

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Event filter for the window for responding to events as needed."""
        # If the filter popup is open and the user clicks out of it, close it for them
        if watched is self.meta_pv_filter_popup and event.type() == QtCore.QEvent.MouseButtonPress:
            if not self.meta_pv_filter_popup.rect().contains(event.pos()):
                self.meta_pv_filter_popup.hide()
        return super().eventFilter(watched, event)

    @QtCore.Slot()
    def open_pv_browser_page(self) -> None:
        """Open the PV Browser Page if it is not already open."""
        if self.main_content_stack.currentWidget() != self.pv_browser_page:
            self.main_content_stack.setCurrentWidget(self.pv_browser_page)
            self.navigation_panel.set_nav_button_selected(self.navigation_panel.browse_pvs_button)

            # Fixes TagWidget vertical size allocation
            self.pv_browser_page.pv_browser_table.resizeRowsToContents()

    @QtCore.Slot()
    def open_view_snapshot_page(self) -> None:
        """Open the snapshot page if it is not already open."""
        if self.main_content_stack.currentWidget() != self.view_snapshot_page:
            self.main_content_stack.setCurrentWidget(self.view_snapshot_page)
            self.navigation_panel.set_nav_button_selected(self.navigation_panel.view_snapshots_button)

    @QtCore.Slot()
    def open_configure_page(self) -> None:
        """Open the configure page if it is not already open."""
        if self.main_content_stack.currentWidget() != self.configure_page:
            self.main_content_stack.setCurrentWidget(self.configure_page)
            self.navigation_panel.set_nav_button_selected(self.navigation_panel.configure_tags_button)

    @QtCore.Slot(QtCore.QModelIndex)
    def open_snapshot_index(self, proxy_index: QtCore.QModelIndex) -> None:
        """
        Opens the snapshot stored at the selected index. A widget representing the
        snapshot is created if necessary and set as the current view in the stack.

        Args:
            index (QtCore.Qt.QModelIndex): table index of the snapshot to open
        """
        if not proxy_index.isValid():
            logger.warning("Invalid index passed to open_snapshot_details")
            return

        # Set new_snapshot in the details page
        source_index = self.snapshot_table.model().mapToSource(proxy_index)
        to_open = self.snapshot_table.model().sourceModel().index_to_snapshot(source_index)
        self.open_snapshot(to_open)

    def toggle_filter_popup(self) -> None:
        """Show or hide the popup that includes the meta pv filters."""
        if self.meta_pv_filter_popup.isVisible():
            self.meta_pv_filter_popup.hide()
        else:
            button = self.sender()
            pos = button.mapToGlobal(QtCore.QPoint(0, button.height()))
            self.meta_pv_filter_popup.move(pos)
            self.meta_pv_filter_popup.show()

    @QtCore.Slot()
    @QtCore.Slot(Snapshot)
    def open_snapshot(self, snapshot: Snapshot = None) -> None:
        if isinstance(snapshot, Snapshot):
            self.snapshot_details_page.set_snapshot(snapshot)
        self.main_content_stack.setCurrentWidget(self.snapshot_details_page)

    def take_snapshot(self) -> Optional[Snapshot]:
        """
        Save a new snapshot for the entry connected to this page. Also opens the
        new snapshot.
        """
        dest_snapshot = Snapshot()
        dialog = self.metadata_dialog(dest_snapshot)
        dialog.accepted.connect(partial(self.client.snap, dest=dest_snapshot))
        dialog.accepted.connect(partial(self.client.backend.add_snapshot, dest_snapshot))
        dialog.accepted.connect(partial(self.open_snapshot, dest_snapshot))
        dialog.accepted.connect(self.snapshot_table.model().sourceModel().fetch)

        dialog.open()
        return dest_snapshot

    def metadata_dialog(self, dest: Snapshot) -> QtWidgets.QDialog:
        """Construct dialog prompting the user to enter metadata for the given entry"""
        metadata_dialog = QtWidgets.QDialog(parent=self)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(NameDescTagsWidget(data=dest, tag_options=self.client.backend.get_tags()))
        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(buttonBox)
        buttonBox.accepted.connect(metadata_dialog.accept)
        buttonBox.rejected.connect(metadata_dialog.reject)
        metadata_dialog.setLayout(layout)
        metadata_dialog.resize(558, 254)
        return metadata_dialog

    @QtCore.Slot(Snapshot, Snapshot)
    def open_comparison_page(self, main_snapshot: Snapshot, comp_snapshot: Snapshot) -> None:
        """Open the comparison page with the given snapshots."""
        self.comparison_page.set_main_snapshot(main_snapshot)
        self.comparison_page.set_comparison_snapshot(comp_snapshot)

        self.main_content_stack.setCurrentWidget(self.comparison_page)

    @QtCore.Slot(QtCore.QModelIndex, QtWidgets.QAbstractItemView)
    def open_pv_editor(self, index: QtCore.QModelIndex, view: QtWidgets.QAbstractItemView):
        self.open_pv_details(index, view, editable=self.permission_manager.is_admin())

    @QtCore.Slot(QtCore.QModelIndex, QtWidgets.QAbstractItemView)
    def open_pv_details(
        self,
        index: QtCore.QModelIndex,
        view: QtWidgets.QAbstractItemView,
        editable=False,
    ) -> None:
        if not index.isValid():
            logger.warning("Invalid index passed to open_pv_details")
            return
        data: PV
        if isinstance(index.model(), QtCore.QSortFilterProxyModel):
            source_model = index.model().sourceModel()
            source_index = index.model().mapToSource(index)
            data = source_model._data[source_index.row()]
        elif isinstance(index.model(), PVTableModel):
            data = index.model()._data[index.row()]
        else:
            raise TypeError("Invalid model type passed to open_pv_details")

        # Get data via the client for alarm limits
        epics_data: EpicsData = None
        try:
            epics_data = self.client.cl.get(data.readback or data.setpoint)
        except CAException as e:
            logging.exception(e)

        pv_details = PVDetails(
            pv_name=data.setpoint,
            readback_name=data.readback,
            description=data.description,
            tolerance_abs=data.abs_tolerance,
            tolerance_rel=data.rel_tolerance,
            lolo=epics_data.lower_alarm_limit if isinstance(epics_data, EpicsData) else None,
            low=epics_data.lower_warning_limit if isinstance(epics_data, EpicsData) else None,
            high=epics_data.upper_warning_limit if isinstance(epics_data, EpicsData) else None,
            hihi=epics_data.upper_alarm_limit if isinstance(epics_data, EpicsData) else None,
            tags=data.tags,
        )
        popup_class = PVDetailsPopupEditable if editable else PVDetailsPopup
        self.popup = popup_class(
            tag_groups=self.client.backend.get_tags(),
            pv_details=pv_details,
            pv_id=data.uuid
        )
        if editable:
            self.popup.accepted.connect(self.update_pv)
            self.popup.accepted.connect(lambda: view.model().sourceModel().refetch_row(index.row()))
        self.popup.adjustSize()

        table_top_right = view.mapToGlobal(view.rect().topRight())
        x = table_top_right.x() - self.popup.width()
        y = table_top_right.y()
        self.popup.move(x, y)

        self.popup.show()

    @QtCore.Slot()
    def update_pv(self):
        pv_id = self.sender().pv_id
        pv_details = self.sender().pv_details
        self.client.backend.update_pv(
            pv_id,
            pv_name=pv_details.pv_name,
            description=pv_details.description,
            tags=pv_details.tags,
            abs_tolerance=pv_details.tolerance_abs,
            rel_tolerance=pv_details.tolerance_rel,
        )

    @QtCore.Slot()
    def open_new_pv_dialog(self) -> None:
        self.popup = PVDetailsPopupEditable(
            tag_groups=self.client.backend.get_tags(),
        )
        self.popup.adjustSize()

        def add_pv():
            try:
                pv = self.client.backend.add_pv(
                    self.popup.pv_details.pv_name or None,
                    self.popup.pv_details.readback_name or None,
                    self.popup.pv_details.description,
                    abs_tolerance=self.popup.pv_details.tolerance_abs,
                    rel_tolerance=self.popup.pv_details.tolerance_rel,
                    tags=self.popup.pv_details.tags,
                )
            except Exception as e:
                logger.exception(e)
            else:
                self.pv_browser_page.pv_browser_table.model().sourceModel().add_pv(pv)

        self.popup.accepted.connect(add_pv)
        self.popup.show()

    def closeEvent(self, a0: QCloseEvent) -> None:
        for page in self.pages:
            try:
                page.close()
            except AttributeError:
                logger.warning("Error closing page: %s", page)
        super().closeEvent(a0)


class NavigationPanel(QtWidgets.QWidget):

    sigViewSnapshots = QtCore.Signal()
    sigBrowsePVs = QtCore.Signal()
    sigConfigureTags = QtCore.Signal()
    sigSave = QtCore.Signal()
    sigExpandedChanged = QtCore.Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setLayout(QtWidgets.QVBoxLayout())

        self.setStyleSheet(
            """
            QPushButton {
                padding: 8px;
                border-radius: 4px;
                text-align: left;
                border: none;
            }
            QPushButton:hover {
                background-color: lightgray;
            }
            QPushButton#save-snapshot-btn {
                border: 1px solid #555555;
                background-color: white;
            }
            QPushButton#save-snapshot-btn:hover {
                background-color: lightgray;
            }
            QPushButton[selected="true"] {
                background-color: white;
            }
            QPushButton[icon-only="true"] {
                text-align: center;
            }
            """
        )

        self.expanded = True

        self.view_snapshots_button = QtWidgets.QPushButton()
        self.view_snapshots_button.setIcon(qta.icon("ph.stack"))
        self.view_snapshots_button.setIconSize(QtCore.QSize(24, 24))
        self.view_snapshots_button.setText("View Snapshots")
        self.view_snapshots_button.setFlat(True)
        self.view_snapshots_button.setToolTip("View Snapshots")
        self.view_snapshots_button.setProperty("icon-only", False)
        self.view_snapshots_button.setProperty("selected", False)
        self.view_snapshots_button.clicked.connect(self.sigViewSnapshots.emit)
        self.layout().addWidget(self.view_snapshots_button)

        self.browse_pvs_button = QtWidgets.QPushButton()
        self.browse_pvs_button.setIcon(qta.icon("ph.database"))
        self.browse_pvs_button.setIconSize(QtCore.QSize(24, 24))
        self.browse_pvs_button.setText("Browse PVs")
        self.browse_pvs_button.setFlat(True)
        self.browse_pvs_button.setToolTip("Browse PVs")
        self.browse_pvs_button.setProperty("icon-only", False)
        self.browse_pvs_button.setProperty("selected", False)
        self.browse_pvs_button.clicked.connect(self.sigBrowsePVs.emit)
        self.layout().addWidget(self.browse_pvs_button)

        self.configure_tags_button = QtWidgets.QPushButton()
        self.configure_tags_button.setIcon(qta.icon("ph.tag"))
        self.configure_tags_button.setIconSize(QtCore.QSize(24, 24))
        self.configure_tags_button.setText("Configure Tags")
        self.configure_tags_button.setFlat(True)
        self.configure_tags_button.setToolTip("Configure Tags")
        self.configure_tags_button.setProperty("icon-only", False)
        self.configure_tags_button.setProperty("selected", False)
        self.configure_tags_button.clicked.connect(self.sigConfigureTags.emit)
        self.layout().addWidget(self.configure_tags_button)

        self.nav_buttons = [self.view_snapshots_button, self.browse_pvs_button, self.configure_tags_button]

        self.layout().addStretch()

        toggle_expand_layout = QtWidgets.QHBoxLayout()
        self.toggle_expand_button = QtWidgets.QPushButton()
        self.toggle_expand_button.setIcon(qta.icon("ph.arrow-line-left"))
        self.toggle_expand_button.setIconSize(QtCore.QSize(24, 24))
        self.toggle_expand_button.setFlat(True)
        self.toggle_expand_button.setProperty("icon-only", False)
        self.toggle_expand_button.clicked.connect(self.toggle_expanded)
        toggle_expand_layout.addWidget(self.toggle_expand_button)
        toggle_expand_layout.addStretch()
        self.layout().addLayout(toggle_expand_layout)

        self.save_button = QtWidgets.QPushButton()
        self.save_button.setIcon(qta.icon("ph.instagram-logo"))
        self.save_button.setIconSize(QtCore.QSize(24, 24))
        self.save_button.setText("Save Snapshot")
        self.save_button.setProperty("icon-only", False)
        self.save_button.clicked.connect(self.sigSave.emit)
        self.save_button.setObjectName("save-snapshot-btn")
        self.layout().addWidget(self.save_button)

    def set_nav_button_selected(self, nav_button: QtWidgets.QPushButton) -> None:
        """Sets a nav button as selected and deselects the others.

        Args:
            nav_button (QtWidgets.QPushButton): The button to set as selected.
        """
        for button in self.nav_buttons:
            button.setProperty("selected", True if button == nav_button else False)
        self.reset_stylesheet()

    def toggle_expanded(self) -> None:
        """Toggles the expanded state of the nav panel"""
        self.set_expanded(not self.expanded)

    def set_expanded(self, value: bool) -> None:
        """Sets the expanded state of the nav panel and redraws the buttons appropriately"""
        if self.expanded != value:
            self.expanded = value
            if self.expanded:
                self.toggle_expand_button.setIcon(qta.icon("ph.arrow-line-left"))
                self.view_snapshots_button.setText("View Snapshots")
                self.browse_pvs_button.setText("Browse PVs")
                self.configure_tags_button.setText("Configure Tags")
                self.save_button.setText("Save Snapshot")
                for button in self.nav_buttons:
                    button.setProperty("icon-only", False)
                self.save_button.setProperty("icon-only", False)
            else:
                self.toggle_expand_button.setIcon(qta.icon("ph.arrow-line-right"))
                for button in self.nav_buttons:
                    button.setText("")
                    button.setProperty("icon-only", True)
                self.save_button.setText("")
                self.save_button.setProperty("icon-only", True)

            self.sigExpandedChanged.emit(self.expanded)
            self.reset_stylesheet()

    def reset_stylesheet(self) -> None:
        """Clears then resets stylesheet to force recomputation. Needed when property
        or object name driven styles should change."""
        stylesheet = self.styleSheet()
        self.setStyleSheet("")
        self.setStyleSheet(stylesheet)
