import os
from pathlib import Path
from unittest.mock import patch

import pytest

from squirrel.backends import MongoBackend, SearchTerm, TestBackend
from squirrel.client import Client
from squirrel.errors import CommunicationError
from squirrel.model import PV, EpicsData
from squirrel.tests.conftest import MockTaskStatus, setup_test_stack
from squirrel.tests.conftest_data import Root
from squirrel.type_hints import UUID

SAMPLE_CFG = Path(__file__).parent / 'demo.cfg'


@pytest.fixture(scope='function')
def xdg_config_patch(tmp_path):
    config_home = tmp_path / 'xdg_config_home'
    config_home.mkdir()
    return config_home


@pytest.fixture(scope='function')
def sscore_cfg(xdg_config_patch: Path):
    # patch config discovery paths
    xdg_cfg = os.environ.get("XDG_CONFIG_HOME", '')
    sscore_cfg = os.environ.get("SQUIRREL_CFG", '')

    os.environ['XDG_CONFIG_HOME'] = str(xdg_config_patch)
    os.environ['SQUIRREL_CFG'] = ''

    sscore_cfg_path = xdg_config_patch / "squirrel.cfg"
    sscore_cfg_path.symlink_to(SAMPLE_CFG)

    yield str(sscore_cfg_path)

    # reset env vars
    os.environ["SQUIRREL_CFG"] = str(sscore_cfg)
    os.environ["XDG_CONFIG_HOME"] = xdg_cfg


def test_apply(
    test_client: Client,
    sample_database_fixture: Root,
    setpoint_with_readback_fixture: PV
):
    put_mock = test_client.cl.put
    put_mock.return_value = MockTaskStatus()
    snap = sample_database_fixture.snapshots[0]
    test_client.apply(snap)
    assert put_mock.call_count == 1
    call_args = put_mock.call_args[0]
    assert len(call_args[0]) == len(call_args[1]) == 3

    put_mock.reset_mock()

    test_client.apply(snap, sequential=True)
    assert put_mock.call_count == 3

    put_mock.reset_mock()
    test_client.apply(setpoint_with_readback_fixture, sequential=True)
    assert put_mock.call_count == 1


@patch('squirrel.control_layer.core.ControlLayer._get_one')
@setup_test_stack(backend_type=[TestBackend], mock_cl=False)
def test_snap(
    get_mock,
    test_client: Client,
    sample_database_fixture: Root,
    parameter_with_readback_fixture: PV
):
    # Testing get -> _get_one chain, must not mock control layer

    for pv in sample_database_fixture.pvs:
        test_client.backend.add_pv(
            pv.setpoint,
            pv.readback,
            pv.description,
            tags=pv.tags,
            abs_tolerance=pv.abs_tolerance,
            rel_tolerance=pv.rel_tolerance,
        )
    test_client.backend.add_pv(
        parameter_with_readback_fixture.setpoint,
        parameter_with_readback_fixture.readback,
        parameter_with_readback_fixture.description,
        tags=parameter_with_readback_fixture.tags,
        abs_tolerance=parameter_with_readback_fixture.abs_tolerance,
        rel_tolerance=parameter_with_readback_fixture.rel_tolerance,
    )

    get_mock.side_effect = [EpicsData(i) for i in range(6)]
    snapshot = test_client.snap()
    assert get_mock.call_count == 6
    assert all([snapshot.pvs[i].setpoint_data.data == i for i in range(5)])  # PVs saved in order


@patch('squirrel.control_layer.core.ControlLayer._get_one')
@setup_test_stack(backend_type=[TestBackend], mock_cl=False)
def test_snap_exception(get_mock, test_client: Client, sample_database_fixture: Root):
    # Testing get -> _get_one chain, must not mock control layer
    for pv in sample_database_fixture.pvs:
        test_client.backend.add_pv(
            pv.setpoint,
            pv.readback,
            pv.description,
            tags=pv.tags,
            abs_tolerance=pv.abs_tolerance,
            rel_tolerance=pv.rel_tolerance,
        )
    get_mock.side_effect = [EpicsData(0), EpicsData(1), CommunicationError,
                            EpicsData(3), EpicsData(4)]
    snapshot = test_client.snap()
    assert snapshot.pvs[2].setpoint_data.data is None


@pytest.mark.skip(reason="Mongo backend not reachable from GitHub action")
def test_from_cfg(sscore_cfg: str):
    client = Client.from_config()
    assert isinstance(client.backend, MongoBackend)
    assert 'ca' in client.cl.shims


def test_find_config(sscore_cfg: str):
    assert sscore_cfg == Client.find_config()

    # explicit SQUIRREL_CFG env var supercedes XDG_CONFIG_HOME
    os.environ['SQUIRREL_CFG'] = 'other/cfg'
    assert 'other/cfg' == Client.find_config()


@pytest.mark.skip(reason="Rewrite search to check data values within Snapshots")
@setup_test_stack(sources=["sample_database"], backend_type=TestBackend)
def test_search(test_client):
    results = list(test_client.search(
        ('setpoint_data.data', 'isclose', (4, 0, 0))
    ))
    assert len(results) == 0

    results = list(test_client.search(
        SearchTerm(operator='isclose', attr='setpoint_data.data', value=(4, .5, 1))
    ))
    assert len(results) == 4


@pytest.mark.skip(reason="Rewrite to get PV values through Snapshot")
@setup_test_stack(
    sources=["linac_with_comparison_snapshot"],
    backend_type=TestBackend
)
def test_search_entries_by_ancestor(test_client: Client):
    entries = tuple(test_client.search(
        ("entry_type", "eq", PV),
        ("pv_name", "eq", "LASR:GUNB:TEST1"),
    ))
    assert len(entries) == 2
    entries = tuple(test_client.search(
        ("entry_type", "eq", PV),
        ("pv_name", "eq", "LASR:GUNB:TEST1"),
        ("ancestor", "eq", UUID("06282731-33ea-4270-ba14-098872e627dc")),  # top-level snapshot
    ))
    assert len(entries) == 1


@pytest.mark.skip(reason="Rewrite to use new backend API")
@setup_test_stack(
    sources=["linac_with_comparison_snapshot"],
    backend_type=TestBackend
)
def test_search_caching(test_client: Client):
    entry = test_client.backend.get_entry(UUID("06282731-33ea-4270-ba14-098872e627dc"))
    result = test_client.search(
        ("ancestor", "eq", UUID("06282731-33ea-4270-ba14-098872e627dc")),
    )
    assert len(tuple(result)) == 13
    entry.pvs = []
    test_client.backend.update_entry(entry)
    result = test_client.search(
        ("ancestor", "eq", UUID("06282731-33ea-4270-ba14-098872e627dc")),
    )
    assert len(tuple(result)) == 1  # update is picked up in new search


def test_parametrized_filestore_empty(test_client: Client):
    assert len(list(test_client.search())) == 0
