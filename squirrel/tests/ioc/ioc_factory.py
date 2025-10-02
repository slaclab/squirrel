from multiprocessing import Process
from typing import Iterable, Mapping

from caproto.server import PVGroup, pvproperty
from caproto.server import run as run_ioc
from epicscorelibs.ca import dbr

from squirrel.client import Client
from squirrel.model import PV


class TempIOC(PVGroup):
    """
    Makes PVs accessible via EPICS when running. Instances automatically start
    and stop running when used as a context manager, and are thus suitable for
    use in tests.
    """
    def __enter__(self):
        self.running_process = Process(
            target=run_ioc,
            args=(self.pvdb,),
            daemon=True,
        )
        self.running_process.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class IOCFactory:
    """
    Generates TempIOC subclasses bound to a set of PVs.
    """
    @staticmethod
    def from_entries(entries: Iterable[PV], client: Client, **ioc_options) -> PVGroup:
        """
        Defines and instantiates a TempIOC subclass containing all PVs reachable
        from entries.
        """
        attrs = IOCFactory.prepare_attrs(entries, client)
        IOC = type("IOC", (TempIOC,), attrs)
        return IOC

    @staticmethod
    def prepare_attrs(pvs: Iterable[PV], client: Client) -> Mapping[str, pvproperty]:
        """
        Turns a collecton of PVs into a Mapping from attribute names to
        caproto.pvproperties. The mapping is suitable for passing into a type()
        call as the dict arg.
        """
        attrs = {}
        for pv in pvs:
            if pv.setpoint_data:
                value = pv.setpoint_data.data
                prop = pvproperty(name=pv.setpoint, doc=pv.description, value=value, dtype=dbr.DBR_STRING if isinstance(value, str) else None)
                attr = "".join([c.lower() for c in pv.setpoint if c.isalnum()])
                attrs[attr] = prop
            if pv.readback_data:
                value = pv.readback_data.data
                prop = pvproperty(name=pv.readback, doc=pv.description, value=value, dtype=dbr.DBR_STRING if isinstance(value, str) else None)
                attr = "".join([c.lower() for c in pv.readback if c.isalnum()])
                attrs[attr] = prop
        return attrs
