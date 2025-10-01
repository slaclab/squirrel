from datetime import datetime
from unittest.mock import Mock

from qtpy import QtCore

from squirrel.model import PV, EpicsData
from squirrel.tables import SnapshotFilterModel


def test_meta_pv_numeric_filter():
    """Verify that the logic around filtering meta pvs works as expected"""
    # Set up a mock snapshot model with two snapshots, each containing the same two meta PV names
    snapshot1 = Mock()
    snapshot1.creation_time = datetime(2025, 8, 4)
    snapshot1.meta_pvs = [
        PV(description="HXR Pulse Intensity", readback_data=EpicsData(data="7.5")),
        PV(description="SXR Pulse Intensity", readback_data=EpicsData(data="10.25")),
    ]

    snapshot2 = Mock()
    snapshot2.creation_time = datetime(2025, 8, 4)
    snapshot2.meta_pvs = [
        PV(description="HXR Pulse Intensity", readback_data=EpicsData(data="7.5")),
        PV(description="SXR Pulse Intensity", readback_data=EpicsData(data="15.0")),
    ]

    source_model = Mock()
    source_model._data = [snapshot1, snapshot2]

    filter_model = SnapshotFilterModel()
    filter_model.sourceModel = lambda: source_model

    # Always allow both snapshots based on creation dates
    filter_model.setDateRange(
        QtCore.QDate(2024, 1, 1),
        QtCore.QDate(2025, 12, 31)
    )

    # Matches both since HXR Pulse Intensity is 7.5 for each
    filter_model.setMetaPVFilters([
        {"column": "HXR Pulse Intensity", "operator": ">", "value": "7"}
    ])
    assert filter_model.filterAcceptsRow(0, QtCore.QModelIndex())
    assert filter_model.filterAcceptsRow(1, QtCore.QModelIndex())

    # And so the opposite should not match either one
    filter_model.setMetaPVFilters([
        {"column": "HXR Pulse Intensity", "operator": "<", "value": "7"}
    ])
    assert not filter_model.filterAcceptsRow(0, QtCore.QModelIndex())
    assert not filter_model.filterAcceptsRow(1, QtCore.QModelIndex())

    # Check that applying two separate filters to the same meta pv works
    filter_model.setMetaPVFilters([
        {"column": "SXR Pulse Intensity", "operator": ">", "value": "10.0"},
        {"column": "SXR Pulse Intensity", "operator": "<=", "value": "13.0"}
    ])
    assert filter_model.filterAcceptsRow(0, QtCore.QModelIndex())
    assert not filter_model.filterAcceptsRow(1, QtCore.QModelIndex())

    # And filter on both meta PVs at the same time
    filter_model.setMetaPVFilters([
        {"column": "HXR Pulse Intensity", "operator": "=", "value": "7.5"},
        {"column": "SXR Pulse Intensity", "operator": "!=", "value": "13.0"}
    ])
    assert filter_model.filterAcceptsRow(0, QtCore.QModelIndex())
    assert filter_model.filterAcceptsRow(1, QtCore.QModelIndex())
