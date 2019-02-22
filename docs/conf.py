"""Sphinx configuration file."""

import os
import sys
import time

# -- Project information -----------------------------------------------------

copyright = '2018, Smile'
author = 'Smile'

# General configuration.
sys.path.append(os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
html_last_updated_fmt = '%c'
master_doc = 'index'
project = __import__('setup').NAME
pygments_style = 'friendly'
release = version = __import__('setup').VERSION
templates_path = ['_templates']
extensions = list()


# Options for HTML output.
html_context = dict(
    conf_py_path='/docs/',
    source_suffix='.rst',
)
html_copy_source = False
html_favicon='_static/Favicon_logo_Smile.png'
html_logo=''
html_theme = 'sphinx_rtd_theme'
html_title = project


# sphinx-versions
scv_banner_greatest_tag = True
scv_show_banner = True
scv_sort = ('semver', 'time')
