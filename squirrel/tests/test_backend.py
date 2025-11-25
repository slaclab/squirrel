import pytest

from squirrel.backends import SearchTerm, TestBackend, _Backend
from squirrel.errors import BackendError, EntryExistsError, EntryNotFoundError
from squirrel.model import PV, Snapshot
from squirrel.tests.conftest import setup_test_stack
from squirrel.type_hints import UUID


@pytest.mark.skip(reason="Rewrite to test add_pv and add_snapshot")
@setup_test_stack(backend_type=[TestBackend])
def test_save_entry(test_backend: _Backend):
    added_pv = test_backend.add_pv(
        setpoint="TEST:SETPT",
        readback="TEST:RDBK",
        description="This is a test",
    )
    assert test_backend.get_all_pvs() == [added_pv]

    # Cannot save an entry that already exists.
    with pytest.raises(EntryExistsError):
        test_backend.save_entry(added_pv)


@pytest.mark.skip(reason="Rewrite to test archive_pv and delete_snapshot")
@setup_test_stack(
    sources=["sample_database"], backend_type=[TestBackend]
)
def test_delete_entry(test_backend: _Backend):
    entry = test_backend.root.entries[0]
    test_backend.delete_entry(entry)

    with pytest.raises(EntryNotFoundError):
        test_backend.get_entry(entry.uuid)


@pytest.mark.skip(reason="Rewrite 'data' field tests")
@setup_test_stack(
    sources=["sample_database"], backend_type=[TestBackend]
)
def test_search_entry(test_backend: _Backend):
    # Given an entry we know is in the backend
    results = test_backend.search(
        SearchTerm('description', 'eq', 'Snapshot 1')
    )
    assert len() == 1
    # Search by field name
    results = test_backend.search(
        SearchTerm('uuid', 'eq', UUID('ffd668d3-57d9-404e-8366-0778af7aee61'))
    )
    assert len(results) == 1
    # Search by field name
    results = test_backend.search(
        SearchTerm('data', 'eq', 2)
    )
    assert len(results) == 2
    # Search by field name
    results = test_backend.search(
        SearchTerm('uuid', 'eq', UUID('ecb42cdb-b703-4562-86e1-45bd67a2ab1a')),
        SearchTerm('data', 'eq', 2)
    )
    assert len(results) == 1

    results = test_backend.search(
        SearchTerm('entry_type', 'eq', Snapshot)
    )
    assert len(results) == 1

    results = test_backend.search(
        SearchTerm('entry_type', 'in', (Snapshot))
    )
    assert len(results) == 2

    results = test_backend.search(
        SearchTerm('data', 'lt', 3)
    )
    assert len(results) == 3

    results = test_backend.search(
        SearchTerm('data', 'gt', 3)
    )
    assert len(results) == 1


@setup_test_stack(
    sources=["sample_database"], backend_type=[TestBackend]
)
def test_fuzzy_search(test_backend: _Backend):
    results = test_backend.search(
        SearchTerm('description', 'like', 'motor')
    )
    assert len(results) == 3

    results = test_backend.search(
        SearchTerm('description', 'like', 'motor field (?!PREC)')
    )
    assert len(results) == 2


@setup_test_stack(
    sources=["sample_database"], backend_type=[TestBackend]
)
def test_tag_search(test_backend: _Backend):
    results = test_backend.search(
        SearchTerm('tags', 'gt', {})
    )
    assert len(results) == 4

    smaller_tag_set = {0: {1}}
    bigger_tag_set = {0: {0, 1}}

    results = test_backend.search(
        SearchTerm('tags', 'gt', smaller_tag_set)
    )
    assert len(results) == 2

    results = test_backend.search(
        SearchTerm('tags', 'gt', bigger_tag_set)
    )
    assert len(results) == 0


@pytest.mark.skip(reason="Check test validity and necessity")
@setup_test_stack(
    sources=["sample_database"], backend_type=[TestBackend]
)
def test_search_error(test_backend: _Backend):
    with pytest.raises(TypeError):
        test_backend.search(
            SearchTerm('data', 'like', 5)
        )
    with pytest.raises(ValueError):
        test_backend.search(
            SearchTerm('data', 'near', 5)
        )


@pytest.mark.skip(reason="Rewrite to test update_pv")
@setup_test_stack(
    sources=["sample_database"], backend_type=[TestBackend]
)
def test_update_entry(test_backend: _Backend):
    # grab an entry from the database and modify it.
    entry = test_backend.search(
        SearchTerm('description', 'eq', 'collection 1 defining some motor fields')
    )[0]
    old_uuid = entry.uuid

    entry.description = 'new_description'
    test_backend.update_entry(entry)
    new_entry = test_backend.search(
        SearchTerm('description', 'eq', 'new_description')
    )[0]
    new_uuid = new_entry.uuid

    assert old_uuid == new_uuid

    # fail if we try to modify with a new entry
    p1 = PV()
    with pytest.raises(BackendError):
        test_backend.update_entry(p1)


@pytest.mark.skip(reason="Reactivate once DirectoryBackend is re-implemented")
@setup_test_stack(
    sources=["linac_data"], backend_type=[]
)
def test_gather_reachable(test_backend: _Backend):
    # snapshot
    reachable = test_backend._gather_reachable(UUID("06282731-33ea-4270-ba14-098872e627dc"))
    assert len(reachable) == 13
    assert UUID("927ef6cb-e45f-4175-aa5f-6c6eec1f3ae4") in reachable

    # works with UUID or Entry
    entry = test_backend.get_entry(UUID("06282731-33ea-4270-ba14-098872e627dc"))
    reachable = test_backend._gather_reachable(entry)
    assert len(reachable) == 13
    assert UUID("927ef6cb-e45f-4175-aa5f-6c6eec1f3ae4") in reachable


@setup_test_stack(
    sources=["linac_data"], backend_type=[TestBackend],
)
def test_tags(test_backend: _Backend):
    tag_groups = test_backend.get_tags()
    dest_tags = {0: "SXR", 1: "HXR"}
    assert tag_groups[3][0] == 'Destination'
    assert tag_groups[3][2] == dest_tags

    new_tags = {0: "SXR-2", 1: "HXR", 2: "BSYD"}
    tag_groups[3][2] = new_tags
    test_backend.set_tags(tag_groups)
    assert test_backend.get_tags()[3][2] == new_tags
