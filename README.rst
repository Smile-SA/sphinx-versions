===============
sphinx-versions
===============

Sphinx extension that allows building versioned docs for self-hosting.

* Python 3.4, and 3.5 supported on Linux and OS X.
* Python 3.4, and 3.5 supported on Windows (both 32 and 64 bit versions of Python).

Full documentation: https://sphinx-versions.readthedocs.io

This project is, for the most part, a fork of https://github.com/Robpol86/sphinxcontrib-versioning, with some additions and removals.

How to use
==========

Most basic usage:

.. code:: bash

    sphinx-versions --help
    sphinx-versions build --help


.. changelog-section-start

Changelog
=========

This project adheres to `Semantic Versioning <http://semver.org/>`_.

1.0.0 - 2018-12-08
------------------

Changes
    * From *sphinxcontrib-versionning* *v2.2.1*, added compatibility with *Sphinx 1.8.2*.
    * From *sphinxcontrib-versionning* *v2.2.1*, removed `push` commands, considered not core for our own usage.
    * Migrates to ``pipenv`` as the recommanded installation process.
    * Use `-s` option instead of `--no-patch` in `git show` (this is for git 1.8.3.1 compatibility).

.. changelog-section-end