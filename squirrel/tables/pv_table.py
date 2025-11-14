from enum import Enum, auto
from typing import Iterable, Optional, Union
from uuid import UUID

from qtpy import QtCore, QtGui

import squirrel.color
from squirrel.model import PV, Severity, Snapshot
from squirrel.widgets import SEVERITY_ICONS
from squirrel.widgets.views import LivePVTableModel

NO_DATA = "--"


class PV_HEADER(Enum):
    CHECKBOX = 0
    SEVERITY = auto()
    DEVICE = auto()
    PV = auto()
    SETPOINT = auto()
    LIVE_SETPOINT = auto()
    READBACK = auto()
    LIVE_READBACK = auto()
    CONFIG = auto()

    def display_string(self) -> str:
        return self._strings[self]


# Must be added outside class def to avoid processing as an enum member
PV_HEADER._strings = {
    PV_HEADER.CHECKBOX: "",
    PV_HEADER.SEVERITY: "",
    PV_HEADER.DEVICE: "Device",
    PV_HEADER.PV: "PV Name",
    PV_HEADER.SETPOINT: "Saved Value",
    PV_HEADER.LIVE_SETPOINT: "Live Value",
    PV_HEADER.READBACK: "Saved Readback",
    PV_HEADER.LIVE_READBACK: "Live Readback",
    PV_HEADER.CONFIG: "CON",
}


class PVTableModel(LivePVTableModel):
    """
    A table model for representing PV data within a Snapshot. Includes live data and checkboxes
    for selecting rows.
    """

    def __init__(
        self,
        client,
        snapshot: Optional[Union[UUID, Snapshot]],
        parent=None,
    ):
        super().__init__(client=client, entries=[], parent=parent)
        if snapshot:
            self.set_snapshot(snapshot)
        else:
            self._data = []
            self._checked = set()

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(PV_HEADER)

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ):
        if orientation == QtCore.Qt.Horizontal:
            if role == QtCore.Qt.DisplayRole:
                return PV_HEADER(section).display_string()

    def flags(self, index) -> QtCore.Qt.ItemFlags:
        if not index.isValid():
            return

        column = PV_HEADER(index.column())
        if column == PV_HEADER.CHECKBOX:
            return (
                QtCore.Qt.ItemIsUserCheckable
                | QtCore.Qt.ItemIsEnabled
                | QtCore.Qt.ItemIsSelectable
            )
        else:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def data(
        self,
        index: QtCore.QModelIndex,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ):
        entry = self._data[index.row()]
        column = PV_HEADER(index.column())
        if role == QtCore.Qt.DisplayRole:
            if column == PV_HEADER.CHECKBOX:
                pass
            elif column == PV_HEADER.SEVERITY:
                return None
            elif column == PV_HEADER.DEVICE:
                return entry.device or NO_DATA
            elif column == PV_HEADER.PV:
                return entry.setpoint
            elif column == PV_HEADER.SETPOINT:
                return getattr(entry.setpoint_data, "data", "")
            elif column == PV_HEADER.LIVE_SETPOINT:
                # return self._get_live_data_field(entry, 'data')
                return NO_DATA
            elif column == PV_HEADER.READBACK:
                return getattr(entry.readback_data, "data", "")
            elif column == PV_HEADER.LIVE_READBACK:
                # return self._get_live_data_field(entry.readback, 'data') if entry.readback else None
                return NO_DATA
            elif column == PV_HEADER.CONFIG:
                return None
            else:
                return None
        elif role == QtCore.Qt.ToolTipRole:
            if column == PV_HEADER.SEVERITY:
                return entry.setpoint + ".SEVR"
            elif column in (PV_HEADER.PV, PV_HEADER.SETPOINT, PV_HEADER.LIVE_SETPOINT):
                return entry.setpoint
            elif column in (PV_HEADER.READBACK, PV_HEADER.LIVE_READBACK) and entry.readback:
                return entry.readback
            elif column == PV_HEADER.CONFIG:
                return None
        elif role == QtCore.Qt.CheckStateRole and column == PV_HEADER.CHECKBOX:
            return index.row() in self._checked
        elif role == QtCore.Qt.DecorationRole and column == PV_HEADER.SEVERITY:
            severity = Severity.INVALID
            try:
                severity = entry.setpoint_data.severity
            except AttributeError:
                pass
            icon = SEVERITY_ICONS[severity]
            if icon is None:
                icon = SEVERITY_ICONS[entry.setpoint_data.status]
            return icon
        elif role == QtCore.Qt.ForegroundRole and column in [PV_HEADER.LIVE_SETPOINT, PV_HEADER.LIVE_READBACK]:
            return QtGui.QColor(squirrel.color.BLUE)
        elif role in [QtCore.Qt.BackgroundRole, QtCore.Qt.FontRole] and column == PV_HEADER.LIVE_SETPOINT:
            stored_data = getattr(entry, 'data', None)
            is_close = self.is_close(entry, stored_data)
            if stored_data is not None and not is_close:
                if role == QtCore.Qt.BackgroundRole:
                    return QtGui.QColor(squirrel.color.LIVE_SETPOINT_HIGHLIGHT)
                elif role == QtCore.Qt.FontRole:
                    font = QtGui.QFont()
                    font.setBold(True)
                    return font
            return None
        elif role == QtCore.Qt.TextAlignmentRole:
            if column not in [PV_HEADER.PV]:
                return QtCore.Qt.AlignCenter
        elif role == QtCore.Qt.UserRole:
            return entry
        return None

    def setData(self, index, value, role) -> bool:
        if role == QtCore.Qt.CheckStateRole and PV_HEADER(index.column()) == PV_HEADER.CHECKBOX:
            try:
                self._checked.remove(index.row())
            except KeyError:
                self._checked.add(index.row())
            self.dataChanged.emit(index, index)
        return True

    def set_snapshot(self, snapshot: Union[UUID, Snapshot]) -> None:
        """
        Uses the provided snapshot as the model's data source. If the snapshot
        is a Snapshot instance, then its data is used directly. If the arg is
        an ID, then the data is fetched from the backend.

        Parameters
        ----------
        snapshot: Union[UUID, Snapshot]
            The model's new data source; either a Snapshot instance or the ID of
            a snapshot
        """
        try:
            entries = snapshot.pvs
        except AttributeError:
            entries = list(self.client.search(
                ("ancestor", "eq", snapshot),
                ("entry_type", "eq", PV),
            ))
        finally:
            self._data = [
                entry if isinstance(entry, PV) else list(
                    self.client.search(
                        ("uuid", "eq", entry)
                    )
                )[0] for entry in entries
            ]
        self._checked = set()
        self.set_entries(self._data)

    def get_selected_pvs(self) -> Iterable[PV]:
        """Return the Setpoints corresponding to checked rows in the table"""
        return [self._data[i] for i in self._checked]


class PVTableFilterProxyModel(QtCore.QSortFilterProxyModel):
    """
    A filter proxy model for filtering PVTableModel entries based on a search
    string. The search string is matched against the device and setpoint
    fields of each entry.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_string = ""

    @property
    def search_string(self) -> str:
        """Get the current search string for filtering."""
        return self._search_string

    @search_string.setter
    def search_string(self, value: str) -> None:
        """Set the search string for filtering. Apply filter to model
        immediately. The value is converted to lowercase for case-insensitive
        matching.

        Parameters
        ----------
        value : str
            The string to filter entries by.
        """
        self._search_string = value.lower()
        self.invalidateFilter()

    def search_accepts_entry(self, entry: PV) -> bool:
        """Check if the entry matches the current search string. Searches
        the device and setpoint fields.

        Parameters
        ----------
        entry : PV
            Entry to be searched

        Returns
        -------
        bool
            True if the entry matches the search string, False otherwise
        """
        if not self.search_string:
            return True

        search_device = self.search_string in (entry.device or NO_DATA).lower()
        search_setpoint = self.search_string in (entry.setpoint or "").lower()

        return search_device or search_setpoint

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        row_index = self.sourceModel().index(source_row, 0, source_parent)
        entry = self.sourceModel().data(row_index, QtCore.Qt.UserRole)
        if not entry:
            return False

        return self.search_accepts_entry(entry)
