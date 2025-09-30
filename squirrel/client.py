"""Client for squirrel.  Used for programmatic interactions with squirrel"""
import configparser
import copy
import logging
import os
from pathlib import Path
from typing import Any, Generator, Iterable, Optional, Union

from squirrel.backends import SearchTerm, SearchTermType, _Backend, get_backend
from squirrel.control_layer import ControlLayer, TaskStatus
from squirrel.model import PV, EpicsData, Snapshot
from squirrel.utils import build_abs_path

logger = logging.getLogger(__name__)


Entry = Union[PV, Snapshot]


class Client:
    backend: _Backend
    cl: ControlLayer

    def __init__(
        self,
        backend: Optional[_Backend] = None,
        control_layer: Optional[ControlLayer] = None,
    ) -> None:
        if backend is None:
            # set up a temp backend with temp file
            logger.warning('No backend specified, loading an empty test backend')
            backend = get_backend('test')()
        if control_layer is None:
            control_layer = ControlLayer()

        self.backend = backend
        self.cl = control_layer

    @classmethod
    def from_config(cls, cfg: Optional[Path] = None):
        """
        Create a client from the configuration file specification.

        Configuration file should be of an "ini" format, along the lines of:

        .. code::

            [backend]
            type = filestore
            path = ./db/filestore.json

            [control_layer]
            ca = true
            pva = true

        The ``backend`` section has one special key ("type"), and the rest of the
        settings are passed to the appropriate ``_Backend`` as keyword arguments.

        The ``control_layer`` section has a key-value pair for each available shim.
        The ``ControlLayer`` object will be created with all the valid shims with
        True values.

        Parameters
        ----------
        cfg : Path, optional
            Path to a configuration file, by default None.  If omitted,
            :meth:`.find_config` will be used to find one

        Raises
        ------
        RuntimeError
            If a configuration file cannot be found
        """
        if not cfg:
            cfg = cls.find_config()
        if not os.path.exists(cfg):
            raise RuntimeError(f"Superscore configuration file not found: {cfg}")

        cfg_parser = configparser.ConfigParser()
        cfg_parser.read(cfg)
        logger.debug(f"Loading configuration file at ({cfg})")
        return cls.from_parsed_config(cfg_parser, cfg)

    @classmethod
    def from_parsed_config(cls, cfg_parser: configparser.ConfigParser, cfg_path=""):
        """
        Initializes Client using a ConfigParser that has already read in a config.
        This method enables the caller to edit a config after parsing but before
        Client initialization.
        """
        # Gather Backend
        if 'backend' in cfg_parser.sections():
            backend_type = cfg_parser.get("backend", "type")
            kwargs = {key: value for key, value
                      in cfg_parser["backend"].items()
                      if key != "type"}
            backend_class = get_backend(backend_type)
            if 'path' in kwargs:
                kwargs['path'] = build_abs_path(Path(cfg_path).parent, kwargs['path'])
            backend = backend_class(**kwargs)
        else:
            logger.warning('No backend specified, loading an empty test backend')
            backend = get_backend('test')()

        # configure control layer and shims
        if 'control_layer' in cfg_parser.sections():
            shim_choices = [val for val, enabled
                            in cfg_parser["control_layer"].items()
                            if enabled]
            control_layer = ControlLayer(shims=shim_choices)
        else:
            logger.debug('No control layer shims specified, loading all available')
            control_layer = ControlLayer()

        return cls(backend=backend, control_layer=control_layer)

    @staticmethod
    def find_config() -> Path:
        """
        Search for a ``squirrel`` configuation file.  Searches in the following
        locations in order
        - ``$SQUIRREL_CFG`` (a full path to a config file)
        - ``$XDG_CONFIG_HOME/{squirrel.cfg, .squirrel.cfg}`` (either filename)
        - ``~/.config/{squirrel.cfg, .squirrel.cfg}``

        Returns
        -------
        path : str
            Absolute path to the configuration file

        Raises
        ------
        OSError
            If no configuration file can be found by the described methodology
        """
        # Point to with an environment variable
        if os.environ.get('SQUIRREL_CFG', False):
            squirrel_cfg = os.environ.get('SQUIRREL_CFG')
            logger.debug("Found $SQUIRREL_CFG specification for Client "
                         "configuration at %s", squirrel_cfg)
            return squirrel_cfg
        # Search in the current directory and home directory
        else:
            config_dirs = [os.environ.get('XDG_CONFIG_HOME', "."),
                           os.path.expanduser('~/.config'),]
            for directory in config_dirs:
                logger.debug('Searching for squirrel config in %s', directory)
                for path in ('.squirrel.cfg', 'squirrel.cfg'):
                    full_path = os.path.join(directory, path)

                    if os.path.exists(full_path):
                        logger.debug("Found configuration file at %r", full_path)
                        return full_path
        # If found nothing
        default_config = os.path.join(os.path.dirname(__file__), "tests/demo.cfg")
        if os.path.isfile(default_config):
            return default_config
        else:
            raise OSError("No squirrel configuration file found")

    def search(self, *post: SearchTermType) -> Generator[Entry, None, None]:
        """
        Search backend for entries matching all SearchTerms in ``post``.  Can search by any
        field, plus some special keywords. Backends support operators listed in _Backend.search.
        Some operators are supported in the UI / client and must be converted before being
        passed to the backend.
        """
        new_search_terms = []
        for search_term in post:
            if not isinstance(search_term, SearchTerm):
                search_term = SearchTerm(*search_term)
            if search_term.operator == 'isclose':
                target, rel_tol, abs_tol = search_term.value
                lower = target - target * rel_tol - abs_tol
                upper = target + target * rel_tol + abs_tol
                new_search_terms.append(SearchTerm(search_term.attr, 'gt', lower))
                new_search_terms.append(SearchTerm(search_term.attr, 'lt', upper))
            else:
                new_search_terms.append(search_term)
        return self.backend.search(*new_search_terms)

    def save(self, entry: Entry):
        """Save information in ``entry`` to database"""
        # validate entry is valid
        self.backend.save_entry(entry)

    def delete(self, entry: Entry) -> None:
        """Remove item from backend, depending on backend"""
        # check for references to ``entry`` in other objects?
        self.backend.delete_entry(entry)

    def snap(self, dest: Optional[Snapshot] = None) -> Snapshot:
        """
        Asyncronously read data for all PVs under ``entry``, and store in a
        Snapshot.  PVs that can't be read will have an exception as their value.

        Parameters
        ----------
        entry : Snapshot
            an unfilled Snapshot to fill with data

        Returns
        -------
        Snapshot
        """
        logger.debug("Saving Snapshot")
        pvs = self.backend.get_all_pvs()
        meta_pvs = self.backend.get_meta_pvs()
        all_pvs = pvs + meta_pvs
        all_addresses = [pv.setpoint for pv in all_pvs if pv.setpoint] + [pv.readback for pv in all_pvs if pv.readback]
        values = self.cl.get(all_addresses)
        data = {pv_address: value for pv_address, value in zip(all_addresses, values)}

        snapshot = dest or Snapshot()

        for pv in all_pvs:
            new_entry = copy.copy(pv)
            if pv.readback:
                value = data[pv.readback]
                edata = self._value_or_default(value)
                new_entry.readback_data = edata
            if pv.setpoint:
                value = data[pv.setpoint]
                edata = self._value_or_default(value)
                new_entry.setpoint_data = edata
            snapshot.pvs.append(new_entry)

        return snapshot

    def apply(
        self,
        entry: Union[PV, Snapshot],
        sequential: bool = False
    ) -> Optional[Iterable[TaskStatus]]:
        """
        Apply values found in ``entry``. If ``sequential`` is True, apply values
        in sequence and block during each put request; otherwise, apply all
        values asynchronously.

        Parameters
        ----------
        entry : Union[PV, Snapshot]
            The entry to apply values from
        sequential : bool, optional
            Whether to apply values sequentially, by default False

        Returns
        -------
        Optional[Iterable[TaskStatus]]
            TaskStatus(es) for each value applied
        """
        if not isinstance(entry, (PV, Snapshot)):
            logger.info("Entries must be a Snapshot or PV")
            return

        if isinstance(entry, PV):
            return [self.cl.put(entry.setpoint, entry.setpoint_data)]

        # Gather pv-value list and apply at once
        setpoints = [pv for pv in entry.pvs if pv.setpoint and pv.setpoint_data]
        if sequential:
            status_list = []
            for pv in setpoints:
                address = pv.setpoint
                value = pv.setpoint_data.data
                logger.debug(f'Putting {address} = {value}')
                status: TaskStatus = self.cl.put(address, value)
                if status.exception():
                    logger.warning(f"Failed to put {address} = {value}, "
                                   "terminating put sequence")
                    return
                status_list.append(status)
            return status_list
        else:
            address_list = [pv.setpoint for pv in setpoints]
            value_list = [pv.setpoint_data.data for pv in setpoints]
            return self.cl.put(address_list, value_list)

    def _value_or_default(self, value: Any) -> EpicsData:
        """small helper for ensuring value is an EpicsData instance"""
        if value is None or not isinstance(value, EpicsData):
            return EpicsData(data=None)
        return value
