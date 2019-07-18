.. _tutorial:

========
Tutorial
========

This guide will go over the basics of the project.

Make sure that you've already :ref:`installed <install>` it.

.. note::

   If you have installed `sphinx-versions` with `pipenv` (which you should), you need to prefix your ``sphinx-versioning`` commands with ``pipenv run ...`` or execute them in your virtualenv (see `pipenv documentation <https://pipenv.readthedocs.io/>`_ for more information on this matter).

Building Docs Locally
=====================

Before we begin make sure you have some Sphinx docs already in your project. If not, read `First Steps with Sphinx <http://www.sphinx-doc.org/en/stable/tutorial.html>`_ first. If you just want something quick
and dirty you can do the following:

.. code-block:: bash

    git checkout -b feature_branch master  # Create new branch from master.
    mkdir docs  # All documentation will go here (optional, can be anywhere).
    echo "master_doc = 'index'" > docs/conf.py  # Create Sphinx config file.
    echo -e "Test\n====\n\nSample Documentation" > docs/index.rst  # Create one doc.
    git add docs
    git commit
    git push origin feature_branch  # Required.

.. note::

    It is **required** to push doc files to origin. sphinx-versions only works with remote branches/tags and ignores any
    local changes (committed, staged, unstaged, etc). If you don't push to origin sphinx-versions won't see them. This
    eliminates race conditions when multiple CI jobs are building docs at the same time.

.. _build-all-versions:

Build All Versions
==================

Now that you've got docs pushed to origin and they build fine with ``sphinx-build`` let's try building them with
sphinx-versions:

.. code-block:: bash

    sphinx-versioning build -r feature_branch docs docs/_build/html
    open docs/_build/html/index.html

More information about all of the options can be found at :ref:`settings` or by running with ``--help`` but just for
convenience:

* ``-r feature_branch`` tells the program to build our newly created/pushed branch at the root of the "html" directory.
  We do this assuming there are no docs in master yet. Otherwise you can omit this argument.
* ``docs/_build/html`` is the destination directory that holds generated HTML files.
* The final ``docs`` argument is the directory where we put our RST files in, relative to the git root (e.g. if you
  clone your repo to another directory, that would be the git root directory). You can add more relative paths if you've
  moved the location of your RST files between different branches/tags.

The command should have worked and your docs should be available in `docs/_build/html/index.html` with a "Versions"
section in the sidebar.

.. note:: You can add a `-P pdf-file-name.pdf` option to also generate a pdf of all versions of your documentation

