"""Largely smoke tests for various pages"""

import pytest
from qtpy import QtCore

from squirrel.backends import TestBackend
from squirrel.client import Client
from squirrel.model import Snapshot
from squirrel.pages import SnapshotComparisonPage, SnapshotDetailsPage
from squirrel.tables import COMPARE_HEADER, PV_HEADER
from squirrel.tests.conftest import setup_test_stack


@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_restore_all(
    qtbot,
    test_client: Client,
    simple_snapshot_fixture: Snapshot,
):
    test_client.backend.add_snapshot(simple_snapshot_fixture)
    put_mock = test_client.cl.put
    detail_page = SnapshotDetailsPage(None, test_client, simple_snapshot_fixture)
    qtbot.add_widget(detail_page)
    detail_page.restore_from_table()

    # get table model through proxy model
    table_model = detail_page.snapshot_details_table.model().sourceModel()
    all_pv_names = [
        table_model.data(table_model.index(row, PV_HEADER.PV.value), role=QtCore.Qt.DisplayRole) for row in range(table_model.rowCount())
    ]
    assert put_mock.call_args.args[0] == all_pv_names

    table_model.close()


@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_restore_selected(
    qtbot,
    test_client: Client,
    simple_snapshot_fixture: Snapshot
):
    test_client.backend.add_snapshot(simple_snapshot_fixture)
    put_mock = test_client.cl.put
    detail_page = SnapshotDetailsPage(None, test_client, simple_snapshot_fixture)
    qtbot.add_widget(detail_page)
    table_model = detail_page.snapshot_details_model
    assert table_model.rowCount() == len(simple_snapshot_fixture.pvs)

    checkstate_index = table_model.index(0, PV_HEADER.CHECKBOX.value)
    table_model.setData(checkstate_index, QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
    detail_page.restore_from_table()
    pv_index = table_model.index(0, PV_HEADER.PV.value)
    assert put_mock.call_args.args[0] == [table_model.data(pv_index, role=QtCore.Qt.DisplayRole)]

    table_model.close()


@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_snapshot_comparison_page_set_main(
    test_client: Client,
    simple_snapshot_fixture: Snapshot,
):
    page = SnapshotComparisonPage(
        client=test_client,
    )
    page.set_main_snapshot(simple_snapshot_fixture)

    # Check that the comparison table model is empty
    assert page.comparison_table_model.rowCount() == 0

    assert page.main_snapshot == simple_snapshot_fixture
    assert page.main_snapshot_title_label.text() == simple_snapshot_fixture.title
    assert page.main_snapshot_time_label.text() == simple_snapshot_fixture.creation_time.strftime("%Y-%m-%d %H:%M:%S")


@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_snapshot_comparison_page_set_comp(
    test_client: Client,
    simple_snapshot_fixture: Snapshot,
):
    page = SnapshotComparisonPage(
        client=test_client,
    )
    page.set_comparison_snapshot(simple_snapshot_fixture)

    # Check that the comparison table model is empty
    assert page.comparison_table_model.rowCount() == 0

    # Check that the comparison snapshot is set correctly
    assert page.comparison_snapshot == simple_snapshot_fixture
    assert page.comp_snapshot_title_label.text() == simple_snapshot_fixture.title
    assert page.comp_snapshot_time_label.text() == simple_snapshot_fixture.creation_time.strftime("%Y-%m-%d %H:%M:%S")


@pytest.mark.skip(reason="compare_model.index is returning index(-1, -1) during test")
@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_snapshot_comparison_page_set_both(
    test_client: Client,
    simple_snapshot_fixture: Snapshot,
    simple_comparison_snapshot_fixture: Snapshot
):
    # Setup the test backend and model
    test_client.backend.add_snapshot(simple_snapshot_fixture)
    test_client.backend.add_snapshot(simple_comparison_snapshot_fixture)

    page = SnapshotComparisonPage(
        client=test_client,
    )
    page.set_main_snapshot(simple_snapshot_fixture)
    page.set_comparison_snapshot(simple_comparison_snapshot_fixture)

    compare_model = page.comparison_table_model
    assert compare_model.rowCount() == 3

    # Setup the data expected from the model
    expected_data = [["MY:FLOAT", None, "--"],
                     ["MY:INT", None, 1],
                     ["MY:ENUM", None, None],
                     ["MY:NEW:ENUM", "--", None]]

    # Check that the model data matches the expected data
    actual_data = []
    for row in range(len(expected_data)):
        actual_row = []
        for column_header in (COMPARE_HEADER.PV, COMPARE_HEADER.SETPOINT, COMPARE_HEADER.COMPARE_SETPOINT):
            col = column_header.value
            index = compare_model.index(row, col)
            actual_row.append(compare_model.data(index, QtCore.Qt.DisplayRole))
        actual_data.append(actual_row)
    assert actual_data == expected_data
