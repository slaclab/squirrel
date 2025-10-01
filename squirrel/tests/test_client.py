import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from squirrel.backends import (DirectoryBackend, FilestoreBackend, SearchTerm,
                               TestBackend)
from squirrel.client import Client
from squirrel.control_layer import EpicsData
from squirrel.errors import CommunicationError, EntryNotFoundError
from squirrel.model import (Collection, Entry, Nestable, Parameter, Readback,
                            Root, Setpoint, Snapshot)
from squirrel.tests.conftest import MockTaskStatus, setup_test_stack
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


def test_gather_data(test_client, sample_database_fixture):
    snapshot = sample_database_fixture.entries[3]
    orig_pv = snapshot.children[0]
    dup_pv = Setpoint(
        uuid=orig_pv.uuid,
        description=orig_pv.description,
        pv_name=orig_pv.pv_name,
        data="You shouldn't see this",
    )
    snapshot.children.append(dup_pv)
    pvs, data_list = test_client._gather_data(snapshot)
    assert len(pvs) == len(data_list) == 3
    assert data_list[pvs.index("MY:PREFIX:mtr1.ACCL")] == 2


def test_apply(
    test_client: Client,
    sample_database_fixture: Root,
    setpoint_with_readback_fixture: Setpoint
):
    put_mock = test_client.cl.put
    put_mock.return_value = MockTaskStatus()
    snap = sample_database_fixture.entries[3]
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
@setup_test_stack(backend_type=[DirectoryBackend], mock_cl=False)
def test_snap(
    get_mock,
    test_client: Client,
    sample_database_fixture: Root,
    parameter_with_readback_fixture: Parameter
):
    # Testing get -> _get_one chain, must not mock control layer

    for entry in sample_database_fixture.entries:
        test_client.save(entry)
    test_client.save(parameter_with_readback_fixture)

    get_mock.side_effect = [EpicsData(i) for i in range(6)]
    snapshot = test_client.snap()
    assert get_mock.call_count == 6
    assert all([snapshot.children[i].data == i for i in range(5)])  # children saved in order
    assert all(isinstance(e, Setpoint) for e in snapshot.children)
    assert any(isinstance(e.readback, Readback) for e in snapshot.children)


@patch('squirrel.control_layer.core.ControlLayer._get_one')
@setup_test_stack(backend_type=[DirectoryBackend], mock_cl=False)
def test_snap_exception(get_mock, test_client: Client, sample_database_fixture: Root):
    # Testing get -> _get_one chain, must not mock control layer
    for entry in sample_database_fixture.entries:
        test_client.save(entry)
    get_mock.side_effect = [EpicsData(0), EpicsData(1), CommunicationError,
                            EpicsData(3), EpicsData(4)]
    snapshot = test_client.snap()
    assert snapshot.children[2].data is None


@patch('squirrel.control_layer.core.ControlLayer._get_one')
@setup_test_stack(backend_type=[DirectoryBackend], mock_cl=False)
def test_snap_RO(get_mock, test_client: Client, sample_database_fixture: Root):
    # Testing get -> _get_one chain, must not mock control layer
    for entry in sample_database_fixture.entries:
        test_client.save(entry)
    test_client.save(
        Parameter(
            pv_name="RO:PV",
            abs_tolerance=1,
            rel_tolerance=-.1,
            read_only=True
        )
    )

    get_mock.side_effect = [EpicsData(i) for i in range(5)]
    snapshot = test_client.snap()

    assert get_mock.call_count == 5
    assert sum(1 for entry in snapshot.children if isinstance(entry, Readback)) == 1
    assert sum(1 for entry in snapshot.children if isinstance(entry, Setpoint)) == 4


def test_from_cfg(sscore_cfg: str):
    client = Client.from_config()
    assert isinstance(client.backend, DirectoryBackend)
    assert 'ca' in client.cl.shims


def test_find_config(sscore_cfg: str):
    assert sscore_cfg == Client.find_config()

    # explicit SQUIRREL_CFG env var supercedes XDG_CONFIG_HOME
    os.environ['SQUIRREL_CFG'] = 'other/cfg'
    assert 'other/cfg' == Client.find_config()


@setup_test_stack(sources=["db/filestore.json"], backend_type=FilestoreBackend)
def test_search(test_client):
    results = list(test_client.search(
        ('data', 'isclose', (4, 0, 0))
    ))
    assert len(results) == 0

    results = list(test_client.search(
        SearchTerm(operator='isclose', attr='data', value=(4, .5, 1))
    ))
    assert len(results) == 4


def uuids_in_entry(entry: Entry):
    """
    Returns True if there is a UUID in a spot where an Entry could be,
    False otherwise.
    """
    if isinstance(entry, Nestable):
        for child in entry.children:
            if isinstance(child, UUID):
                return True

    return False


@setup_test_stack(
    sources=["linac_with_comparison_snapshot"],
    backend_type=FilestoreBackend
)
def test_search_entries_by_ancestor(test_client: Client):
    entries = tuple(test_client.search(
        ("entry_type", "eq", Setpoint),
        ("pv_name", "eq", "LASR:GUNB:TEST1"),
    ))
    assert len(entries) == 2
    entries = tuple(test_client.search(
        ("entry_type", "eq", Setpoint),
        ("pv_name", "eq", "LASR:GUNB:TEST1"),
        ("ancestor", "eq", UUID("06282731-33ea-4270-ba14-098872e627dc")),  # top-level snapshot
    ))
    assert len(entries) == 1


@setup_test_stack(
    sources=["linac_with_comparison_snapshot"],
    backend_type=FilestoreBackend
)
def test_search_caching(test_client: Client):
    entry = test_client.backend.get_entry(UUID("06282731-33ea-4270-ba14-098872e627dc"))
    result = test_client.search(
        ("ancestor", "eq", UUID("06282731-33ea-4270-ba14-098872e627dc")),
    )
    assert len(tuple(result)) == 13
    entry.children = []
    test_client.backend.update_entry(entry)
    result = test_client.search(
        ("ancestor", "eq", UUID("06282731-33ea-4270-ba14-098872e627dc")),
    )
    assert len(tuple(result)) == 1  # update is picked up in new search


def test_parametrized_filestore_empty(test_client: Client):
    assert len(list(test_client.search())) == 0


@setup_test_stack(backend_type=TestBackend)
def test_find_origin_collection(test_client):
    collection = Collection()
    snapshot = Snapshot()
    test_client.save(collection)
    test_client.save(snapshot)

    assert test_client.find_origin_collection(collection) == collection
    with pytest.raises(ValueError):
        test_client.find_origin_collection(snapshot)
    snapshot.origin_collection = uuid4()
    with pytest.raises(EntryNotFoundError):
        test_client.find_origin_collection(snapshot)
    snapshot.origin_collection = collection.uuid
    assert test_client.find_origin_collection(snapshot) == collection
