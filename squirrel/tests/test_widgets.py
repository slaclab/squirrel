from unittest.mock import MagicMock

import pytest
from pytestqt.qtbot import QtBot
from qtpy import QtCore, QtGui

from squirrel.backends import TestBackend
from squirrel.client import Client
from squirrel.color import LIVE_SETPOINT_HIGHLIGHT
from squirrel.model import EpicsData, Snapshot
from squirrel.tables import PVTableModel
from squirrel.tests.conftest import setup_test_stack
from squirrel.widgets import TagsWidget


@pytest.fixture(scope='function')
def pv_table_model(
    test_client: Client,
    simple_snapshot_fixture: Snapshot,
    qtbot: QtBot
):
    for i in range(3):
        simple_snapshot_fixture.pvs[i].data = i + 1
    test_client.backend.save_entry(simple_snapshot_fixture)

    """Minimal PVTableModel"""
    model = PVTableModel(
        snapshot=simple_snapshot_fixture.uuid,
        client=test_client,
    )

    # Make sure we never actually call EPICS. Second child has different live data
    model.client.cl.get = MagicMock(side_effect=[EpicsData(1), EpicsData(1), EpicsData(3)])
    # TODO: uncomment or remove this line once PV table live columns are re-implemented
    # qtbot.wait_until(lambda: model._poll_thread.running)
    yield model

    model.stop_polling()

    # TODO: uncomment or remove this line once PV table live columns are re-implemented
    # qtbot.wait_until(lambda: not model._poll_thread.isRunning())


def test_tags_widget(qtbot):
    tag_groups = {
        0: (
            "Dest",
            "Which endpoint the beam is directed towards",
            {
                0: "SXR",
                1: "HXR",
            }
        )
    }

    widget = TagsWidget(tag_groups=tag_groups, enabled=True)
    qtbot.addWidget(widget)

    assert widget.layout().count() == 1

    chip = widget.layout().itemAt(0).widget()
    assert len(chip.tags) == 0

    selection_model = chip.editor.choice_list.selectionModel()
    Select = selection_model.SelectionFlag.Select
    index = selection_model.model().index(0, 0)
    selection_model.select(index, Select)
    index = selection_model.model().index(1, 0)
    selection_model.select(index, Select)
    assert len(chip.tags) == 2
    assert 0 in chip.tags
    assert 1 in chip.tags

    Deselect = selection_model.SelectionFlag.Deselect
    selection_model.select(index, Deselect)
    assert len(chip.tags) == 1
    assert 0 in chip.tags
    assert 1 not in chip.tags

    chip.clear()
    assert len(chip.tags) == 0
    assert 0 not in chip.tags
    assert 1 not in chip.tags


def test_pv_table_model(qtmodeltester, pv_table_model: PVTableModel):
    qtmodeltester.check(pv_table_model, force_py=True)


@pytest.mark.skip(reason="QThreads aren't behaving with mocked control layer methods")
@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_pv_table_model_data(test_client, pv_table_model: PVTableModel):
    # Expected model data based on the pv_table_model setup
    expected_data = [[None, None, None, 'MY:FLOAT', 1, 1, None, None, None],
                     [None, None, None, 'MY:INT', 2, 1, None, None, None],
                     [None, None, None, 'MY:ENUM', 3, 3, None, None, None]]

    actual_data = []
    for row, expected in enumerate(expected_data):
        actual_row = []
        for col in range(len(expected)):
            index = pv_table_model.index(row, col)
            data = pv_table_model.data(index)
            actual_row.append(data)
        actual_data.append(actual_row)
    assert actual_data == expected_data


@pytest.mark.skip(reason="QThreads aren't behaving with mocked control layer methods")
@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_pv_table_model_color(test_client: Client, pv_table_model: PVTableModel):
    # Expected model colors based on the pv_table_model setup
    diff_color = QtGui.QColor(LIVE_SETPOINT_HIGHLIGHT)
    expected_color = [[None, None, None, None, None, None, None, None, None],
                      [None, None, None, None, None, diff_color, None, None, None],
                      [None, None, None, None, None, None, None, None, None]]

    actual_colors = []
    for row, expected in enumerate(expected_color):
        actual_row = []
        for col in range(len(expected)):
            index = pv_table_model.index(row, col)
            color = pv_table_model.data(index, QtCore.Qt.BackgroundRole)
            actual_row.append(color)
        actual_colors.append(actual_row)
    assert actual_colors == expected_color
