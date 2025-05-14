===============================
superscore
===============================

.. image:: https://github.com/pcdshub/superscore/actions/workflows/standard.yml/badge.svg
        :target: https://github.com/pcdshub/superscore/actions/workflows/standard.yml

.. image:: https://img.shields.io/pypi/v/superscore.svg
        :target: https://pypi.python.org/pypi/superscore


`Documentation <https://pcdshub.github.io/superscore/>`_

Configuration Management for EPICS PVs

Requirements
------------

* Python 3.9+

Installation
------------

::

  $ conda create --name superscore pip
  $ conda activate superscore
  $ pip install .  # install statically, and only include packages necessary to run
  $ #or
  $ pip install -e .[test]  # install as editable package, and include packages for development and testing

Running the Tests
-----------------
::

  $ pytest
