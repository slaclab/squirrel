Config
======

Local config files use the `ini format`_.

.. _ini format: https://docs.python.org/3/library/configparser.html#supported-ini-file-structure

Sections
--------

[backend]
^^^^^^^^^

* ``type``: which type of backend to use e.g. ``mongo``
* ``path``: where the backend is located e.g. a URL for ``mongo`` or a filepath for ``directory``

[control_layer]
^^^^^^^^^^^^^^^

* ``ca``: boolean flag for whether to use channel access protocol for accessing PVs
* ``pva``: boolean flag for whether to use PVAccess protocol for accessing PVs

[meta PVs]
^^^^^^^^^^

* ``pvs``: list of strings to use as PV addresses

.. admonition:: Example
    :collapsible: closed

    pvs=BEND:DMPH:400:BDES
        BEND:DMPH:400:EDES
        SIOC:SYS0:ML00:CALC252

[demo] (deprecated)
^^^^^^^^^^^^^^^^^^^

* ``fixtures``: a list of data sources from conftest / conftest_data to load into a test IOC during demo mode
