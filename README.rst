===============================
superscore
===============================

.. image:: https://github.com/slaclab/superscore/actions/workflows/standard.yml/badge.svg
        :target: https://github.com/slaclab/superscore/actions/workflows/standard.yml

.. image:: https://img.shields.io/pypi/v/superscore.svg
        :target: https://pypi.python.org/pypi/superscore


`Documentation <https://slaclab.github.io/superscore/>`_

Configuration Management for EPICS PVs

Requirements
------------

* Python 3.10+

Installation
------------

::

  $ conda create --name superscore pip
  $ conda activate superscore
  $
  $ conda install --file requirements.txt  # install statically, and only include packages necessary to run
  $ pip install .
  $ #or
  $ conda install --file requirements.txt --file dev-requirements.txt # include packages for development and testing
  $ pip install -e .  # install as editable package

Running the Tests
-----------------
::

  $ pytest
