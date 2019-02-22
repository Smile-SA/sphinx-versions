.. _install:

============
Installation
============

.. _requirements-to-use:

Requirements
============

Install Python & PIP & pipenv
-----------------------------

First, you need to install Python 3 and PIP (if not already present on your system):

.. code-block:: shell

   $ sudo apt-get install python3-pip

You might need to update PIP right away

.. code-block:: shell

   $ pip3 install -U pip

Then, install ``pipenv``

.. code-block:: shell

   $ pip install --user -U pipenv

Installation
============

`pipenv` install
----------------

The suggested way to get `sphinx-versions` is to use `pipenv <https://pipenv.readthedocs.io>`_. Simply run this command, from your current project:

.. code-block:: bash

    pipenv install sphinx-versions

Clone and Install
-----------------

Lastly you can also just clone the repo and install from it. Usually you only need to do this if you plan on :ref:`contributing <contributing>` to the project.

.. code-block:: bash

    git clone git@github.com:Smile-SA/sphinx-versions.git
    cd sphinx-versions
    python setup.py install
