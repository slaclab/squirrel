import logging

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from datetime import datetime, timedelta
from typing import Iterable

import requests

from squirrel.backends import SearchTermType, _Backend
from squirrel.errors import BackendError
from squirrel.model import PV, EpicsData, Severity, Snapshot, Status
from squirrel.type_hints import TagDef, TagSet

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "TAGS": "/v1/tags",
    "PVS": "/v1/pvs",
    "PVS_MULTI": "/v1/pvs/multi",
    "SNAPSHOTS": "/v1/snapshots",
}


class MongoBackend(_Backend):
    """An integration layer between the Client and a MongoDB instance"""

    def __init__(self, address: str):
        super().__init__()
        self.address = address
        self._tag_cache = {}
        self._last_tag_fetch = datetime.now() - timedelta(minutes=1)

    def search(self, *search_terms: SearchTermType, meta_pvs=None):
        """
        Search for all entries matching the passed search terms.

        .. deprecated

        Raises
        ------
        BackendError
        """
        entries = []
        for attr, op, target in search_terms:
            if attr == "entry_type":
                if target is Snapshot:
                    entries = self.get_snapshots(meta_pvs=meta_pvs)
                else:
                    entries = self.get_all_pvs()
        matching = []
        for entry in entries:
            conditions = []
            for attr, op, target in search_terms:
                if attr == "entry_type":
                    conditions.append(isinstance(entry, target))
                elif attr == "ancestor":
                    pass
                else:
                    try:
                        # check entry attribute by name
                        value = getattr(entry, attr)
                        conditions.append(self.compare(op, value, target))
                    except AttributeError:
                        conditions.append(False)
            if all(conditions):
                matching.append(entry)
        return matching

    def get_tags(self) -> TagDef:
        """
        Fetch tag definition from the backend. Caches data for one minute.

        Returns
        -------
        TagDef
            Full tag definition received from the backend

        Raises
        ------
        BackendError
        """
        if datetime.now() - self._last_tag_fetch > timedelta(minutes=1):
            tag_def = {}
            r = requests.get(self.address + ENDPOINTS["TAGS"])
            logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
            if r.ok:
                for dct in r.json()["payload"]:
                    idx = dct['id']
                    name = dct['name']
                    r = requests.get(self.address + ENDPOINTS["TAGS"] + f"/{idx}")
                    logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
                    if r.ok:
                        dct = r.json()["payload"][0]
                        description = dct.get("description", "")
                        tags = {d["id"]: d["name"] for d in dct["tags"]}
                        tag_def[idx] = [name, description, tags]
            self._tag_cache = tag_def
            self._last_tag_fetch = datetime.now()
        return self._tag_cache

    def add_tag_group(self, name, description) -> int:
        """
        Add new tag group.

        Parameters
        ----------
        name : str
            Name of the new tag group
        description : str
            Description of the new tag group. May be empty, but must be set
            explicitly.

        Returns
        -------
        int
            ID of the newly created tag group, received from the backend

        Raises
        ------
        BackendError
        """
        body = {
            "name": name,
            "description": description,
        }
        r = requests.post(self.address + ENDPOINTS["TAGS"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)
        return r.json()["payload"]["id"]

    def update_tag_group(self, group_id, name="", description="") -> None:
        """
        Update name and/or description of a tag group.

        Parameters
        ----------
        group_id : int
            ID of the tag group
        name : str, optional
            New name to use for the tag group
        description : str, optional
            New description to use for the tag group

        Raises
        ------
        BackendError
        """
        body = {}
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def delete_tag_group(self, group_id) -> None:
        """
        Delete entire tag group.

        Parameters
        ----------
        group_id : int
            ID of the tag group to delete

        Raises
        ------
        BackendError
        """
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", params={"force": True})
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def add_tag_to_group(self, group_id: int, name, description="") -> None:
        """
        Add new tag to a tag group.

        Parameters
        ----------
        group_id : int
            ID of the tag group
        name : str
            Name to use for the new tag
        description : str, optional
            Description to use for the new tag

        Raises
        ------
        BackendError
        """
        params = {
            "groupId": group_id,
        }
        body = {
            "name": name,
            "description": description,
        }
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags", params=params, json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def update_tag_in_group(self, group_id, tag_id, name="", description="") -> None:
        """
        Update tag in a tag group. Name and/or description will be updated if
        passed as parameters.

        Parameters
        ----------
        group_id : int
            ID of the tag group
        tag_id : int
            ID of the tag to in the tag group
        name : str, optional
            New name to use for the tag
        description : str, optional
            New description to use for the tag

        Raises
        ------
        BackendError
        """
        params = {
            "groupId": group_id,
            "tagId": tag_id,
        }
        body = {}
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags/{tag_id}", params=params, json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def delete_tag_from_group(self, group_id, tag_id) -> None:
        """
        Delete tag from a tag group

        Parameters
        ----------
        group_id : int
            ID of the tag group
        tag_id : int
            ID of the tag to remove from the group

        Raises
        ------
        BackendError
        """
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags/{tag_id}")
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

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
        """
        Add PV to the backend. The new PV will have data according to the passed
        parameters.

        Parameters
        ----------
        setpoint : str
            EPICS address to use as a setpoint. May be empty, but must be set
            explicitly.
        readback : str
            EPICS address to use as a readback. May be empty, but must be set
            explicitly.
        description : str
            Description of the new PV
        device : str, optional
            Alias device name of the new PV, defaults to empty string
        tags : TagSet, optional
            Set of tags assigned to the PV
        abs_tolerance : float, optional
            Absolute tolerance
        rel_tolerance : float, optional
            Relative tolerance
        config_address : str, optional
            EPICS address for reading last config value. Defaults to empty.

        Returns
        -------
        PV
            PV instance containing all data received from the backend

        Raises
        ------
        BackendError
        """
        body = {
            "setpointAddress": setpoint,
            "readbackAddress": readback,
            "configAddress": config_address,
            "description": description,
            "device": device,
            "absTolerance": abs_tolerance,
            "relTolerance": rel_tolerance,
            "tags": self._pack_tags(tags) if tags else [],
            "readOnly": False,
        }
        r = requests.post(self.address + ENDPOINTS["PVS"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)
        pv_dict = r.json()["payload"]
        return self._unpack_pv(pv_dict)

    def add_multiple_pvs(self, pvs: Iterable[PV]) -> Iterable[PV]:
        body = []
        for pv in pvs:
            body.append(
                {
                    "setpointAddress": pv.setpoint or None,
                    "readbackAddress": pv.readback or None,
                    "configAddress": pv.config or None,
                    "description": pv.description,
                    "device": pv.device or None,
                    "absTolerance": pv.abs_tolerance,
                    "relTolerance": pv.rel_tolerance,
                    "tags": self._pack_tags(pv.tags),
                }
            )
        r = requests.post(self.address + ENDPOINTS["PVS_MULTI"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)
        pv_dicts = r.json()["payload"]
        return [self._unpack_pv(pv_dict) for pv_dict in pv_dicts]

    def update_pv(self, pv_id, setpoint="", readback="", description="", device="", tags=None, abs_tolerance=None, rel_tolerance=None) -> None:
        """
        Update PV in the backend. Data will be updated for any passed parameter;
        data for other parameters will not be affected.

        Parameters
        ----------
        pv_id : str
            ID of the PV to update
        setpoint : str, optional
            A new setpoint address
        readback : str, optional
            A new readback address
        description : str, optional
            A new description
        device : str, optional
            A new device name
        tags : TagSet, optional
            A new set of tags
        abs_tolerance : float, optional
            A new absolute tolerance
        rel_tolerance : float, optional
            A new relative tolerance

        Raises
        ------
        BackendError
        """
        body = {}
        if setpoint:
            body["setpointAddress"] = setpoint
        if readback:
            body["readbackAddress"] = readback
        if description:
            body["description"] = description
        if device:
            body["device"] = device
        if tags:
            body["tags"] = self._pack_tags(tags)
        if abs_tolerance is not None:
            body["absTolerance"] = abs_tolerance
        if rel_tolerance is not None:
            body["relTolerance"] = rel_tolerance
        body["readOnly"] = False
        r = requests.put(self.address + ENDPOINTS["PVS"] + f"/{pv_id}", json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def archive_pv(self, pv_id) -> None:
        """
        Archive PV in the backend. The PV will still appear in Snapshots that
        already exist, but will not appear in the list of current PVs nor will
        data for this PV be saved in future Snapshots.

        Parameters
        ----------
        pv_id : str
            ID of the PV to archive

        Raises
        ------
        BackendError
        """
        r = requests.delete(self.address + ENDPOINTS["PVS"] + f"/{pv_id}")
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def get_all_pvs(self) -> Iterable[PV]:
        """
        Get all PVs from the backend

        Returns
        -------
        Iterable[PV]

        Raises
        ------
        BackendError
        """
        r = requests.get(self.address + ENDPOINTS["PVS"])
        self._raise_for_status(r)
        return [self._unpack_pv(d) for d in r.json()["payload"]]

    def get_pvs(self, search_string="") -> Iterable[PV]:
        """
        Get PVs with setpoint or readback matching search_string

        Parameters
        ----------
        search_string : str

        Returns
        -------
        Iterable[PV]

        Raises
        ------
        BackendError
        """
        r = requests.get(
            self.address + ENDPOINTS["PVS"],
            params={
                "pvName": search_string,
            }
        )
        self._raise_for_status(r)
        return [self._unpack_pv(d) for d in r.json()["payload"]]

    def add_snapshot(self, snapshot: Snapshot) -> None:
        """
        Add snapshot to the backend.

        Parameters
        ----------
        snapshot : Snapshot

        Raises
        ------
        BackendError
        """
        r = requests.post(
            self.address + ENDPOINTS["SNAPSHOTS"],
            json=self._pack_snapshot(snapshot)
        )
        self._raise_for_status(r)

    def get_snapshots(self, uuid=None, title="", tags=None, meta_pvs=None) -> Iterable[Snapshot]:
        """
        Fetch snapshots from the backend.

        Parameters
        ----------
        uuid : str, optional
            ID of one specific Snapshot; if present, other parameters are ignored
        title : str, optional
            Substring contained in the title field of desired Snapshots
        tags : TagSet, optional
            Tags contained in the tags field of desired Snapshots
        meta_pvs
            Not Implemented

        Returns
        -------
        Iterable[Snapshot]
            Snapshot instances that match the selected filters

        Raises
        ------
        BackendError
        """
        if uuid:
            r = requests.get(self.address + ENDPOINTS["SNAPSHOTS"] + f"/{uuid}")
            self._raise_for_status(r)
            snapshot_dict = r.json()["payload"]
            return [self._unpack_snapshot(snapshot_dict)]

        tags = tags or {}
        meta_pvs = meta_pvs or []
        r = requests.get(
            self.address + ENDPOINTS["SNAPSHOTS"],
            params={
                "title": title,
                "tags": tags,
                "metadataPVs": [pv.readback for pv in meta_pvs if pv.readback]
            }
        )
        self._raise_for_status(r)
        return [self._unpack_snapshot_metadata(snapshot_dict) for snapshot_dict in r.json()["payload"]]

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        """
        Delete the given snapshot from the backend.

        Raises
        ------
        BackendError
        """
        r = requests.delete(
            self.address + ENDPOINTS["SNAPSHOTS"] + f"/{snapshot.uuid}",
            params={
                "deleteData": False,
            }
        )
        self._raise_for_status(r)

    def get_snapshots_in_date_range(self) -> None:
        """TODO: Returns snapshots with timestamps in a given range. This method
        is potentially valuable for limiting how much data is sent by the backend
        at once."""
        raise NotImplementedError

    def get_snapshots_in_index_range(self) -> None:
        """TODO: Returns snapshots with indicies in a given range, indexed by
        reverse-chronological position in the complete list of snapshots. This
        method is potentially valuable for limiting how much data is sent by the
        backend at once."""
        raise NotImplementedError

    @staticmethod
    def _raise_for_status(response):
        """Wraps response errors from the requests package in an app-specific
        error class

        Raises
        ------
        BackendError
            If the backend's response raises an HTTPError; contains error message
            from the response's json body
        """
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # server response can have "errorMessage" or "message" key depending on error
            message = response.json().get("errorMessage", "") or response.json().get("message", e)
            raise BackendError(message)

    def _unpack_tags(self, tag_list) -> TagSet:
        """
        Converts data received from backend endpoints into a TagSet instance.
        This method is intended for processing tag data embedded within snapshot
        data that is received from backend endpoints.

        Parameters
        ----------
        tag_list : Iterable[int]
            Encoded tags for one PV received from the backend

        Returns
        -------
        TagSet
            Tags for one PV formatted as a TagSet
        """
        tag_def = self.get_tags()
        id_to_group = {
            tag_id: group for group, group_def in tag_def.items() for tag_id in group_def[2]
        }
        tag_set = {}
        for d in tag_list:
            group = id_to_group[d["id"]]
            if group not in tag_set:
                tag_set[group] = set()
            tag_set[group].add(d["id"])
        return tag_set

    @staticmethod
    def _pack_tags(tags: TagSet) -> Iterable[int]:
        """
        Converts the TagSet to a format that is accepted by backend endpoints

        Parameters
        ----------
        tags : TagSet
            Tags for one PV

        Returns
        -------
        Iterable[int]
            All tags for one PV
        """
        return [tag for group in tags.values() for tag in group]

    def _unpack_pv(self, pv_dict) -> PV:
        """
        Converts data received from backend endpoints into a PV instance

        Parameters
        ----------
        pv_dict : dict
            Encoded data received from the backend

        Returns
        -------
        PV
            PV instance containing all encoded data received from the backend
        """
        return PV(
            uuid=pv_dict["id"],
            setpoint=pv_dict.get("setpointAddress"),
            readback=pv_dict.get("readbackAddress"),
            config=pv_dict.get("configAddress"),
            description=pv_dict["description"],
            device=pv_dict.get("device", ""),
            tags=self._unpack_tags(pv_dict["tags"]),
            abs_tolerance=pv_dict["absTolerance"],
            rel_tolerance=pv_dict["relTolerance"],
            creation_time=datetime.fromisoformat(pv_dict["createdDate"]).replace(tzinfo=UTC),
        )

    @staticmethod
    def _unpack_snapshot_metadata(metadata_dict) -> Snapshot:
        """
        Converts data received from backend endpoints into a Snapshot instance
        without PV data. This method only parses metadata, such as title,
        description, timestamp, and meta PV data. It is intended for processing
        rows in the snapshot table.

        Parameters
        ----------
        metadata_dict : dict
            Encoded snapshot metadata received from the backend

        Returns
        -------
        Snapshot
            Snapshot instance containing all encoded metadata received from the
            backend
        """
        return Snapshot(
            uuid=metadata_dict["id"],
            title=metadata_dict["title"],
            description=metadata_dict["description"],
            # tags=metadata_dict["tags"],
            meta_pvs=[
                PV(
                    setpoint=pv.get("setpointAddress", ""),
                    setpoint_data=EpicsData(
                        data=pv.get("data", None),
                        status=getattr(Status, pv["status"]),
                        severity=getattr(Severity, pv["severity"]),
                        timestamp=datetime.fromisoformat(pv["createdDate"]).replace(tzinfo=UTC),
                    ),
                    readback=pv.get("readbackAddress", ""),
                    readback_data=EpicsData(
                        data=pv.get("data", None),
                        status=getattr(Status, pv["status"]),
                        severity=getattr(Severity, pv["severity"]),
                        timestamp=datetime.fromisoformat(pv["createdDate"]).replace(tzinfo=UTC),
                    ),
                    creation_time=datetime.fromisoformat(pv["createdDate"]).replace(tzinfo=UTC),
                ) for pv in metadata_dict["metadataPVs"]
            ],
            creation_time=datetime.fromisoformat(metadata_dict["createdDate"]).replace(tzinfo=UTC),
        )

    def _unpack_snapshot(self, snapshot_dict) -> Snapshot:
        """
        Converts data received from backend endpoints into a complete Snapshot
        instance.

        Parameters
        ----------
        snapshot_dict : dict
            Encoded snapshot data received from the backend

        Returns
        -------
        Snapshot
            Snapshot instance containing all encoded data received from the
            backend
        """
        pv_defs = self.get_all_pvs()
        pvs = []
        pv_values_map = {}
        for pv in pv_defs:
            pv_with_values = PV(
                setpoint=pv.setpoint,
                readback=pv.readback,
            )
            if pv.setpoint:
                pv_values_map[pv.setpoint] = pv_with_values
            if pv.readback:
                pv_values_map[pv.readback] = pv_with_values
            pvs.append(pv_with_values)

        for value_dict in snapshot_dict["data"]:
            data = EpicsData(
                data=value_dict.get("data", None),
                status=getattr(Status, value_dict["status"]),
                severity=getattr(Severity, value_dict["severity"]),
                timestamp=datetime.fromisoformat(value_dict["createdDate"]).replace(tzinfo=UTC),
            )
            address = value_dict["pvName"]
            try:
                pv = pv_values_map[address]
            except KeyError:
                logging.debug(f"Address {address} within Snapshot did not match any PV from backend")
            else:
                if address == pv.setpoint:
                    pv.setpoint_data = data
                elif address == pv.readback:
                    pv.readback_data = data
                else:
                    logging.debug("Address {address} did not match PV address {pv.setpoint} or {pv.readback}; skipping")
        return Snapshot(
            uuid=snapshot_dict["id"],
            title=snapshot_dict["title"],
            description=snapshot_dict["description"],
            # tags=snapshot_dict["tags"],
            pvs=pvs,
            creation_time=datetime.fromisoformat(snapshot_dict["createdDate"]).replace(tzinfo=UTC),
        )

    @staticmethod
    def _pack_snapshot(snapshot: Snapshot) -> dict:
        """
        Converts the Snapshot to a format that is accepted by backend endpoints

        Parameters
        ----------
        snapshot : Snapshot

        Returns
        -------
        dict
        """
        setpoint_values = [
            {
                "pvName": pv.setpoint,
                "status": pv.setpoint_data.status.name,
                "severity": pv.setpoint_data.severity.name,
                "data": pv.setpoint_data.data,
            } for pv in snapshot.pvs if pv.setpoint
        ]
        readback_values = [
            {
                "pvName": pv.readback,
                "status": pv.readback_data.status.name,
                "severity": pv.readback_data.severity.name,
                "data": pv.readback_data.data,
            } for pv in snapshot.pvs if pv.readback
        ]
        return {
            "title": snapshot.title,
            "description": snapshot.description,
            "values": setpoint_values + readback_values,
        }
