.. _contributing:

=================
How to contribute
=================

Make sure you meet the :ref:`requirements to use <requirements-to-use>` the project, first.

Requirements
============

Install the virtualenv dependencies
-----------------------------------

To install required dependencies, use the command:

.. code-block:: shell

   $ pipenv install --dev

This will install in your local virtualenv all the required dependencies to contribute to this project.

The ``--dev`` option allows the installation of the *dev-packages* dependencies.


Install build and distribution tools
------------------------------------

* Install latest version of required tools

.. code:: bash

   pip install --user -U setuptools wheel twine


Build and upload a new version of sphinx-versions
=================================================

Update the version
------------------

You need to update two different files :

* ``setup.py``: contains the `VERSION` constant, used to identify the version built and uploaded to the nexus.
* ``sphinxcontrib/versioning/__init__.py``: contains the ``__version__`` constant, used to identify the package version.


Update the README.rst
---------------------

You need to add a section in the ``README.rst`` for the newly created version (follow the pattern of other versions).


Generate package to distribute
------------------------------

This builds your python project and creates the `dist` directory (among other things).

.. code:: bash

   python3 setup.py sdist bdist_wheel

Upload your package to nexus
----------------------------

.. code:: bash

   twine upload dist/*

After this command, your package is available on  https://pypi.org. Anyone can install it using `pip install sphinx-versions`.
