"""Interface with Sphinx."""

import datetime
import logging
import multiprocessing
import os
import sys
from shutil import copyfile, rmtree

from sphinx import application, locale
from sphinx.cmd.build import build_main, make_main
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.config import Config as SphinxConfig
from sphinx.errors import SphinxError
from sphinx.jinja2glue import SphinxFileSystemLoader
from sphinx.util.i18n import format_date

from sphinxcontrib.versioning import __version__
from sphinxcontrib.versioning.lib import Config, HandledError, TempDir
from sphinxcontrib.versioning.versions import Versions

SC_VERSIONING_VERSIONS = list()  # Updated after forking.
STATIC_DIR = os.path.join(os.path.dirname(__file__), '_static')


class EventHandlers(object):
    """Hold Sphinx event handlers as static or class methods.

    :ivar multiprocessing.queues.Queue ABORT_AFTER_READ: Communication channel to parent process.
    :ivar bool BANNER_GREATEST_TAG: Banner URLs point to greatest/highest (semver) tag.
    :ivar str BANNER_MAIN_VERSION: Banner URLs point to this remote name (from Versions.__getitem__()).
    :ivar bool BANNER_RECENT_TAG: Banner URLs point to most recently committed tag.
    :ivar str CURRENT_VERSION: Current version being built.
    :ivar bool IS_ROOT: Value for context['scv_is_root'].
    :ivar bool SHOW_BANNER: Display the banner.
    :ivar sphinxcontrib.versioning.versions.Versions VERSIONS: Versions class instance.
    """

    ABORT_AFTER_READ = None
    BANNER_GREATEST_TAG = False
    BANNER_MAIN_VERSION = None
    BANNER_RECENT_TAG = False
    CURRENT_VERSION = None
    IS_ROOT = False
    SHOW_BANNER = False
    VERSIONS = None

    @staticmethod
    def builder_inited(app):
        """Update the Sphinx builder.

        :param sphinx.application.Sphinx app: Sphinx application object.
        """
        # Add this extension's _templates directory to Sphinx.
        templates_dir = os.path.join(os.path.dirname(__file__), '_templates')
        if app.builder.name != "latex":
            app.builder.templates.pathchain.insert(0, templates_dir)
            app.builder.templates.loaders.insert(0, SphinxFileSystemLoader(templates_dir))
            app.builder.templates.templatepathlen += 1

        # Add versions.html to sidebar.
        if '**' not in app.config.html_sidebars:
            # default_sidebars was deprecated in Sphinx 1.6+, so only use it if possible (to maintain
            # backwards compatibility), else don't use it.
            try:
                app.config.html_sidebars['**'] = StandaloneHTMLBuilder.default_sidebars + ['versions.html']
            except AttributeError:
                app.config.html_sidebars['**'] = ['versions.html']
        elif 'versions.html' not in app.config.html_sidebars['**']:
            app.config.html_sidebars['**'].append('versions.html')

    @classmethod
    def env_updated(cls, app, env):
        """Abort Sphinx after initializing config and discovering all pages to build.

        :param sphinx.application.Sphinx app: Sphinx application object.
        :param sphinx.environment.BuildEnvironment env: Sphinx build environment.
        """
        if cls.ABORT_AFTER_READ:
            config = {n: getattr(app.config, n) for n in (a for a in dir(app.config) if a.startswith('scv_'))}
            config['found_docs'] = tuple(str(d) for d in env.found_docs)
            config['master_doc'] = str(app.config.master_doc)
            cls.ABORT_AFTER_READ.put(config)
            sys.exit(0)

    @classmethod
    def html_page_context(cls, app, pagename, templatename, context, doctree):
        """Update the Jinja2 HTML context, exposes the Versions class instance to it.

        :param sphinx.application.Sphinx app: Sphinx application object.
        :param str pagename: Name of the page being rendered (without .html or any file extension).
        :param str templatename: Page name with .html.
        :param dict context: Jinja2 HTML context.
        :param docutils.nodes.document doctree: Tree of docutils nodes.
        """
        assert templatename or doctree  # Unused, for linting.
        cls.VERSIONS.context = context
        versions = cls.VERSIONS
        this_remote = versions[cls.CURRENT_VERSION]
        banner_main_remote = versions[cls.BANNER_MAIN_VERSION] if cls.SHOW_BANNER else None

        # Update Jinja2 context.
        context['bitbucket_version'] = cls.CURRENT_VERSION
        context['current_version'] = cls.CURRENT_VERSION
        context['github_version'] = cls.CURRENT_VERSION
        context['html_theme'] = app.config.html_theme
        context['scv_banner_greatest_tag'] = cls.BANNER_GREATEST_TAG
        context['scv_banner_main_ref_is_branch'] = banner_main_remote['kind'] == 'heads' if cls.SHOW_BANNER else None
        context['scv_banner_main_ref_is_tag'] = banner_main_remote['kind'] == 'tags' if cls.SHOW_BANNER else None
        context['scv_banner_main_version'] = banner_main_remote['name'] if cls.SHOW_BANNER else None
        context['scv_banner_recent_tag'] = cls.BANNER_RECENT_TAG
        context['scv_is_branch'] = this_remote['kind'] == 'heads'
        context['scv_is_greatest_tag'] = this_remote == versions.greatest_tag_remote
        context['scv_is_recent_branch'] = this_remote == versions.recent_branch_remote
        context['scv_is_recent_ref'] = this_remote == versions.recent_remote
        context['scv_is_recent_tag'] = this_remote == versions.recent_tag_remote
        context['scv_is_root'] = cls.IS_ROOT
        context['scv_is_tag'] = this_remote['kind'] == 'tags'
        context['scv_show_banner'] = cls.SHOW_BANNER
        context['versions'] = versions
        context['vhasdoc'] = versions.vhasdoc
        context['vpathto'] = versions.vpathto

        # Insert banner into body.
        if cls.SHOW_BANNER and 'body' in context:
            parsed = app.builder.templates.render('banner.html', context)
            context['body'] = parsed + context['body']
            # Handle overridden css_files.
            css_files = context.setdefault('css_files', list())
            if '_static/banner.css' not in css_files:
                css_files.append('_static/banner.css')
            # Handle overridden html_static_path.
            if STATIC_DIR not in app.config.html_static_path:
                app.config.html_static_path.append(STATIC_DIR)

        # Reset last_updated with file's mtime (will be last git commit authored date).
        if app.config.html_last_updated_fmt is not None:
            file_path = app.env.doc2path(pagename)
            if os.path.isfile(file_path):
                lufmt = app.config.html_last_updated_fmt or getattr(locale, '_')('%b %d, %Y')
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                context['last_updated'] = format_date(lufmt, mtime, language=app.config.language)


def setup(app):
    """Called by Sphinx during phase 0 (initialization).

    :param sphinx.application.Sphinx app: Sphinx application object.

    :returns: Extension version.
    :rtype: dict
    """
    # Used internally. For rebuilding all pages when one or versions fail.
    app.add_config_value('sphinxcontrib_versioning_versions', SC_VERSIONING_VERSIONS, 'html')

    # Needed for banner.
    app.config.html_static_path.append(STATIC_DIR)
    app.add_css_file('banner.css')

    # Tell Sphinx which config values can be set by the user.
    for name, default in Config():
        app.add_config_value('scv_{}'.format(name), default, 'html')

    # Event handlers.
    app.connect('builder-inited', EventHandlers.builder_inited)
    app.connect('env-updated', EventHandlers.env_updated)
    app.connect('html-page-context', EventHandlers.html_page_context)
    return dict(version=__version__)


class ConfigInject(SphinxConfig):
    """Inject this extension info self.extensions. Append after user's extensions."""

    def __init__(self, *args):
        """Constructor."""
        super(ConfigInject, self).__init__(*args)
        self.extensions.append('sphinxcontrib.versioning.sphinx_')


def _build(argv, config, versions, current_name, is_root):
    """Build Sphinx docs via multiprocessing for isolation.

    :param tuple argv: Arguments to pass to Sphinx.
    :param sphinxcontrib.versioning.lib.Config config: Runtime configuration.
    :param sphinxcontrib.versioning.versions.Versions versions: Versions class instance.
    :param str current_name: The ref name of the current version being built.
    :param bool is_root: Is this build in the web root?
    """
    # Patch.
    application.Config = ConfigInject
    if config.show_banner:
        EventHandlers.BANNER_GREATEST_TAG = config.banner_greatest_tag
        EventHandlers.BANNER_MAIN_VERSION = config.banner_main_ref
        EventHandlers.BANNER_RECENT_TAG = config.banner_recent_tag
        EventHandlers.SHOW_BANNER = True
    EventHandlers.CURRENT_VERSION = current_name
    EventHandlers.IS_ROOT = is_root
    EventHandlers.VERSIONS = versions
    SC_VERSIONING_VERSIONS[:] = [p for r in versions.remotes for p in sorted(r.items()) if p[0] not in ('sha', 'date')]

    # Update argv.
    if config.verbose > 1:
        argv += ('-v',) * (config.verbose - 1)
    if config.no_colors:
        argv += ('-N',)
    if config.overflow:
        argv += config.overflow

    # Build.
    result = build_main(argv)

    if result != 0:
        raise SphinxError

    # Build pdf if required
    if config.pdf_file:
        args = list(argv)
        args.insert(0,"latexpdf")   # Builder type
        args.insert(0,"ignore")     # Will be ignored
        result = make_main(args)
        # Copy to _static dir of src
        latexDir = argv[1] + "/latex/";
        copyfile( latexDir + config.pdf_file, argv[1] + "/_static/" + config.pdf_file)
        rmtree(latexDir)

    if result != 0:
        raise SphinxError


def _read_config(argv, config, current_name, queue):
    """Read the Sphinx config via multiprocessing for isolation.

    :param tuple argv: Arguments to pass to Sphinx.
    :param sphinxcontrib.versioning.lib.Config config: Runtime configuration.
    :param str current_name: The ref name of the current version being built.
    :param multiprocessing.queues.Queue queue: Communication channel to parent process.
    """
    # Patch.
    EventHandlers.ABORT_AFTER_READ = queue

    # Run.
    _build(argv, config, Versions(list()), current_name, False)


def build(source, target, versions, current_name, is_root):
    """Build Sphinx docs for one version. Includes Versions class instance with names/urls in the HTML context.

    :raise HandledError: If sphinx-build fails. Will be logged before raising.

    :param str source: Source directory to pass to sphinx-build.
    :param str target: Destination directory to write documentation to (passed to sphinx-build).
    :param sphinxcontrib.versioning.versions.Versions versions: Versions class instance.
    :param str current_name: The ref name of the current version being built.
    :param bool is_root: Is this build in the web root?
    """
    log = logging.getLogger(__name__)
    argv = (source, target)
    config = Config.from_context()

    log.debug('Running sphinx-build for %s with args: %s', current_name, str(argv))
    child = multiprocessing.Process(target=_build, args=(argv, config, versions, current_name, is_root))
    child.start()
    child.join()  # Block.
    if child.exitcode != 0:
        log.error('sphinx-build failed for branch/tag: %s', current_name)
        raise HandledError


def read_config(source, current_name):
    """Read the Sphinx config for one version.

    :raise HandledError: If sphinx-build fails. Will be logged before raising.

    :param str source: Source directory to pass to sphinx-build.
    :param str current_name: The ref name of the current version being built.

    :return: Specific Sphinx config values.
    :rtype: dict
    """
    log = logging.getLogger(__name__)
    queue = multiprocessing.Queue()
    config = Config.from_context()

    with TempDir() as temp_dir:
        argv = (source, temp_dir)
        log.debug('Running sphinx-build for config values with args: %s', str(argv))
        child = multiprocessing.Process(target=_read_config, args=(argv, config, current_name, queue))
        child.start()
        child.join()  # Block.
        if child.exitcode != 0:
            log.error('sphinx-build failed for branch/tag while reading config: %s', current_name)
            raise HandledError

    config = queue.get()
    return config
