Alpha Testing
=============

Accessing the Test Environment
------------------------------
Squirrel is available for testing from a conda environment on the ``dev-srv09`` filesystem.

0. If you do not have conda installed, follow `S3DF's instructions`_.
#. In your ``.condarc``, add ``/sdf/group/ad/eed/swapps/conda/envs`` under ``env_dirs``.
#. Run ``conda info --envs`` to confirm ``squirrel-alpha`` is an option.
#. Run ``conda activate squirrel-alpha`` to activate the environment, and ``conda deactivate`` to leave the environment.

.. _S3DF's instructions: https://s3df.slac.stanford.edu/#/reference?id=conda

Notes
-----
This test environment uses a shared backend, so any changes such as PVs edits
and new snapshots will be available to other testers.

To enable fetching real PV values on a dev server, source
``/afs/slac/g/lcls/epics/setup/envSet_prodOnDev.bash``. Live values can then be disabled by
sourcing ``/afs/slac/g/lcls/epics/setup/envSet_dev.bash`` or loading a new session.

Feedback
--------
Bug reports and feature requests can be made by filling out `this form`_.

.. _this form: https://forms.cloud.microsoft/Pages/ResponsePage.aspx?id=Wq7yzmYmFkebYOiOKuv0mhonqK7sP55ItMgN_T_cXr5URjRWWE42T0FTOElSNEk5RzhWTkRFT1pMSyQlQCN0PWcu
