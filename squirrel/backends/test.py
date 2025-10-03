"""
Backend that manipulates Entries in-memory for testing purposes.
"""
from typing import Iterable

from squirrel.backends import SearchTermType, _Backend
from squirrel.model import PV, Snapshot
from squirrel.type_hints import TagDef, TagSet


class TestBackend(_Backend):
    """Backend that manipulates Entries in-memory, for testing purposes."""
    __test__ = False  # Tell pytest this isn't a test case

    def __init__(
        self,
        pvs: Iterable[PV] = None,
        snapshots: Iterable[Snapshot] = None,
        tags: TagDef = None,
        meta_pvs: Iterable[PV] = None
    ):
        self.pvs = pvs or []
        self.snapshots = snapshots or []
        self.tag_groups = tags or {}
        self.meta_pvs = meta_pvs or []

    def search(self, *search_terms: SearchTermType):
        for entry in self.pvs + self.snapshots:
            conditions = []
            for attr, op, target in search_terms:
                if attr == "entry_type":
                    conditions.append(isinstance(entry, target))
                else:
                    try:
                        # check entry attribute by name
                        value = getattr(entry, attr)
                        conditions.append(self.compare(op, value, target))
                    except AttributeError:
                        conditions.append(False)
            if all(conditions):
                yield entry

    def get_tags(self) -> TagDef:
        return self.tag_groups.copy()

    def set_tags(self, tags: TagDef) -> None:
        self.tag_groups = tags

    def add_tag_group(self, name, description) -> int:
        group_id = max(self.tag_groups.keys()) + 1 if self.tag_groups else 0
        self.tag_groups[group_id] = [name, description, {}]
        return group_id

    def update_tag_group(self, group_id, name="", description="") -> None:
        cur_name, cur_desc, tags = self.tag_groups[group_id]
        self.tag_groups[group_id] = [name or cur_name, description or cur_desc, tags]

    def delete_tag_group(self, group_id) -> None:
        del self.tag_groups[group_id]

    def add_tag_to_group(self, group_id: int, name, description="") -> None:
        _, _, tags = self.tag_groups[group_id]
        tag_id = max(tags.keys()) + 1 if tags else 0
        tags[tag_id] = name

    def update_tag_in_group(self, group_id, tag_id, name="", description="") -> None:
        _, _, tags = self.tag_groups[group_id]
        cur_name = tags[tag_id]
        tags[tag_id] = name or cur_name

    def delete_tag_from_group(self, group_id, tag_id) -> None:
        del self.tag_groups[group_id][tag_id]

    def add_pv(
        self,
        setpoint,
        readback,
        description,
        device="",
        tags: TagSet = None,
        abs_tolerance=0,
        rel_tolerance=0,
        config_address=None,
    ) -> PV:
        pv = PV(
            setpoint=setpoint,
            readback=readback,
            description=description,
            device=device,
            tags=tags,
            abs_tolerance=abs_tolerance,
            rel_tolerance=rel_tolerance,
        )
        self.pvs.append(pv)
        return pv

    def add_multiple_pvs(self, pvs: Iterable[PV]) -> Iterable[PV]:
        raise NotImplementedError

    def update_pv(self, pv_id, setpoint="", description="", device="", tags=None, abs_tolerance=None, rel_tolerance=None) -> None:
        raise NotImplementedError

    def archive_pv(self, pv_id) -> None:
        raise NotImplementedError

    def get_all_pvs(self) -> Iterable[PV]:
        return self.pvs.copy()

    def add_snapshot(self, snapshot: Snapshot) -> None:
        self.snapshots.append(snapshot)

    def get_snapshots(self, uuid=None, title="", tags=None, meta_pvs=None) -> Iterable[Snapshot]:
        tags = tags or {}
        return [
            s for s in self.snapshots if (
                s.uuid == s.uuid
                and title in s.title
                and all(tags[key] <= s.tags[key] for key in tags)
            )
        ]

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        raise NotImplementedError

    def get_snapshots_in_date_range(self) -> None:
        raise NotImplementedError

    def get_snapshots_in_index_range(self) -> None:
        raise NotImplementedError

    def get_meta_pvs(self) -> Iterable[PV]:
        return self.meta_pvs

    def set_meta_pvs(self, meta_pvs: Iterable[PV]) -> None:
        self.meta_pvs = meta_pvs
