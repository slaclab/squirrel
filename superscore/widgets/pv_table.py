from enum import Enum, auto
from typing import Iterable, Union
from uuid import UUID

from qtpy import QtCore, QtGui

import superscore.color
from superscore.model import Readback, Setpoint, Snapshot
from superscore.widgets import SEVERITY_ICONS
from superscore.widgets.views import LivePVTableModel


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

    def __init__(self, snapshot: Union[UUID, Snapshot], client, parent=None):
        super().__init__(client=client, entries=[], parent=parent)
        self.set_snapshot(snapshot)

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
            if isinstance(entry, Setpoint):
                if column == PV_HEADER.CHECKBOX:
                    pass
                elif column == PV_HEADER.SEVERITY:
                    return None
                elif column == PV_HEADER.DEVICE:
                    return None
                elif column == PV_HEADER.PV:
                    return entry.pv_name
                elif column == PV_HEADER.SETPOINT:
                    return entry.data
                elif column == PV_HEADER.LIVE_SETPOINT:
                    return self._get_live_data_field(entry, 'data')
                elif column == PV_HEADER.READBACK:
                    return entry.readback.data if entry.readback else None
                elif column == PV_HEADER.LIVE_READBACK:
                    return self._get_live_data_field(entry.readback, 'data') if entry.readback else None
                elif column == PV_HEADER.CONFIG:
                    return None
                else:
                    return None
            else:
                if column == PV_HEADER.SEVERITY:
                    return None
                elif column == PV_HEADER.DEVICE:
                    return None
                elif column == PV_HEADER.PV:
                    return entry.pv_name
                elif column == PV_HEADER.SETPOINT:
                    return None
                elif column == PV_HEADER.LIVE_SETPOINT:
                    return None
                elif column == PV_HEADER.READBACK:
                    return entry.data
                elif column == PV_HEADER.LIVE_READBACK:
                    return self._get_live_data_field(entry, 'data')
                elif column == PV_HEADER.CONFIG:
                    return None
                else:
                    return None
        elif role == QtCore.Qt.ToolTipRole:
            if isinstance(entry, Setpoint):
                if column == PV_HEADER.SEVERITY:
                    return entry.pv_name + ".SEVR"
                elif column in (PV_HEADER.PV, PV_HEADER.SETPOINT, PV_HEADER.LIVE_SETPOINT):
                    return entry.pv_name
                elif column in (PV_HEADER.READBACK, PV_HEADER.LIVE_READBACK) and entry.readback is not None:
                    return entry.readback.pv_name
                elif column == PV_HEADER.CONFIG:
                    return None
            else:
                if column == PV_HEADER.SEVERITY:
                    return entry.pv_name + ".SEVR"
                elif column in (PV_HEADER.READBACK, PV_HEADER.LIVE_READBACK):
                    return entry.pv_name
                elif column == PV_HEADER.CONFIG:
                    return None
        elif role == QtCore.Qt.CheckStateRole and column == PV_HEADER.CHECKBOX:
            return index.row() in self._checked
        elif role == QtCore.Qt.DecorationRole and column == PV_HEADER.SEVERITY:
            icon = SEVERITY_ICONS[entry.severity]
            if icon is None:
                icon = SEVERITY_ICONS[entry.status]
            return icon
        elif role == QtCore.Qt.ForegroundRole and column in [PV_HEADER.LIVE_SETPOINT, PV_HEADER.LIVE_READBACK]:
            return QtGui.QColor(superscore.color.BLUE)
        elif role in [QtCore.Qt.BackgroundRole, QtCore.Qt.FontRole] and column == PV_HEADER.LIVE_SETPOINT:
            stored_data = getattr(entry, 'data', None)
            is_close = self.is_close(entry, stored_data)
            if stored_data is not None and not is_close:
                if role == QtCore.Qt.BackgroundRole:
                    return QtGui.QColor(superscore.color.LIVE_SETPOINT_HIGHLIGHT)
                elif role == QtCore.Qt.FontRole:
                    font = QtGui.QFont()
                    font.setBold(True)
                    return font
            return None
        elif role == QtCore.Qt.TextAlignmentRole and column not in [PV_HEADER.DEVICE, PV_HEADER.PV]:
            return QtCore.Qt.AlignCenter
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
            entries = snapshot.children
        except AttributeError:
            entries = list(self.client.search(
                ("ancestor", "eq", snapshot),
                ("entry_type", "eq", (Setpoint, Readback)),
            ))
        finally:
            self._data = [
                entry if isinstance(entry, (Setpoint, Readback)) else list(
                    self.client.search(
                        ("uuid", "eq", entry)
                    )
                )[0] for entry in entries
            ]
        self._checked = set()
        self.set_entries(self._data)

    def get_selected_pvs(self) -> Iterable[Setpoint]:
        """Return the Setpoints corresponding to checked rows in the table"""
        return [self._data[i] for i in self._checked]
