"""Entry point of project via setuptools which calls cli()."""

import logging
import os
import shutil
import sys
import time

import click

from sphinxcontrib.versioning import __version__
from sphinxcontrib.versioning.git import clone, get_root, GitError
from sphinxcontrib.versioning.lib import Config, HandledError, TempDir
from sphinxcontrib.versioning.routines import build_all, gather_git_info, pre_build, read_local_conf
from sphinxcontrib.versioning.setup_logging import setup_logging
from sphinxcontrib.versioning.versions import multi_sort, Versions

IS_EXISTS_DIR = click.Path(exists=True, file_okay=False, dir_okay=True)
IS_EXISTS_FILE = click.Path(exists=True, file_okay=True, dir_okay=False)
NO_EXECUTE = False  # Used in tests.
PUSH_RETRIES = 3
PUSH_SLEEP = 3  # Seconds.


class ClickGroup(click.Group):
    """Truncate docstrings at form-feed character and implement overflow arguments."""

    def __init__(self, *args, **kwargs):
        """Constructor.

        :param list args: Passed to super().
        :param dict kwargs: Passed to super().
        """
        self.overflow = None
        if 'help' in kwargs and kwargs['help'] and '\f' in kwargs['help']:
            kwargs['help'] = kwargs['help'].split('\f', 1)[0]
        super(ClickGroup, self).__init__(*args, **kwargs)

    @staticmethod
    def custom_sort(param):
        """Custom Click(Command|Group).params sorter.

        Case insensitive sort with capitals after lowercase. --version at the end since I can't sort --help.

        :param click.core.Option param: Parameter to evaluate.

        :return: Sort weight.
        :rtype: int
        """
        option = param.opts[0].lstrip('-')
        if param.param_type_name != 'option':
            return False,
        return True, option == 'version', option.lower(), option.swapcase()

    def get_params(self, ctx):
        """Sort order of options before displaying.

        :param click.core.Context ctx: Click context.

        :return: super() return value.
        """
        self.params.sort(key=self.custom_sort)
        return super(ClickGroup, self).get_params(ctx)

    def main(self, *args, **kwargs):
        """Main function called by setuptools.

        :param list args: Passed to super().
        :param dict kwargs: Passed to super().

        :return: super() return value.
        """
        argv = kwargs.pop('args', sys.argv[1:])
        if '--' in argv:
            pos = argv.index('--')
            argv, self.overflow = argv[:pos], tuple(argv[pos + 1:])
        else:
            argv, self.overflow = argv, tuple()
        return super(ClickGroup, self).main(args=argv, *args, **kwargs)

    def invoke(self, ctx):
        """Inject overflow arguments into context state.

        :param click.core.Context ctx: Click context.

        :return: super() return value.
        """
        if self.overflow:
            ctx.ensure_object(Config).update(dict(overflow=self.overflow))
        return super(ClickGroup, self).invoke(ctx)


class ClickCommand(click.Command):
    """Truncate docstrings at form-feed character for click.command()."""

    def __init__(self, *args, **kwargs):
        """Constructor."""
        if 'help' in kwargs and kwargs['help'] and '\f' in kwargs['help']:
            kwargs['help'] = kwargs['help'].split('\f', 1)[0]
        super(ClickCommand, self).__init__(*args, **kwargs)

    def get_params(self, ctx):
        """Sort order of options before displaying.

        :param click.core.Context ctx: Click context.

        :return: super() return value.
        """
        self.params.sort(key=ClickGroup.custom_sort)
        return super(ClickCommand, self).get_params(ctx)


@click.group(cls=ClickGroup)
@click.option('-c', '--chdir', help='Make this the current working directory before running.', type=IS_EXISTS_DIR)
@click.option('-g', '--git-root', help='Path to directory in the local repo. Default is CWD.', type=IS_EXISTS_DIR)
@click.option('-l', '--local-conf', help='Path to conf.py for sphinx-versions to read config from.', type=IS_EXISTS_FILE)
@click.option('-L', '--no-local-conf', help="Don't attempt to search for nor load a local conf.py file.", is_flag=True)
@click.option('-N', '--no-colors', help='Disable colors in the terminal output.', is_flag=True)
@click.option('-v', '--verbose', help='Debug logging. Specify more than once for more logging.', count=True)
@click.version_option(version=__version__)
@click.make_pass_decorator(Config, ensure=True)
def cli(config, **options):
    """Build versioned Sphinx docs for every branch and tag pushed to origin.

    Supports only building locally with the "build" sub command
    For more information, run with its own --help.

    The options below are global and must be specified before the sub command name (e.g. -N build ...).
    \f

    :param sphinxcontrib.versioning.lib.Config config: Runtime configuration.
    :param dict options: Additional Click options.
    """
    def pre(rel_source):
        """To be executed in a Click sub command.

        Needed because if this code is in cli() it will be executed when the user runs: <command> <sub command> --help

        :param tuple rel_source: Possible relative paths (to git root) of Sphinx directory containing conf.py.
        """
        # Setup logging.
        if not NO_EXECUTE:
            setup_logging(verbose=config.verbose, colors=not config.no_colors)
        log = logging.getLogger(__name__)

        # Change current working directory.
        if config.chdir:
            os.chdir(config.chdir)
            log.debug('Working directory: %s', os.getcwd())
        else:
            config.update(dict(chdir=os.getcwd()), overwrite=True)

        # Get and verify git root.
        try:
            config.update(dict(git_root=get_root(config.git_root or os.getcwd())), overwrite=True)
        except GitError as exc:
            log.error(exc.message)
            log.error(exc.output)
            raise HandledError

        # Look for local config.
        if config.no_local_conf:
            config.update(dict(local_conf=None), overwrite=True)
        elif not config.local_conf:
            candidates = [p for p in (os.path.join(s, 'conf.py') for s in rel_source) if os.path.isfile(p)]
            if candidates:
                config.update(dict(local_conf=candidates[0]), overwrite=True)
            else:
                log.debug("Didn't find a conf.py in any REL_SOURCE.")
        elif os.path.basename(config.local_conf) != 'conf.py':
            log.error('Path "%s" must end with conf.py.', config.local_conf)
            raise HandledError
    config['pre'] = pre  # To be called by Click sub commands.
    config.update(options)


def build_options(func):
    """Add "build" Click options to function.

    :param function func: The function to wrap.

    :return: The wrapped function.
    :rtype: function
    """
    func = click.option('-a', '--banner-greatest-tag', is_flag=True,
                        help='Override banner-main-ref to be the tag with the highest version number.')(func)
    func = click.option('-A', '--banner-recent-tag', is_flag=True,
                        help='Override banner-main-ref to be the most recent committed tag.')(func)
    func = click.option('-b', '--show-banner', help='Show a warning banner.', is_flag=True)(func)
    func = click.option('-B', '--banner-main-ref',
                        help="Don't show banner on this ref and point banner URLs to this ref. Default master.")(func)
    func = click.option('-i', '--invert', help='Invert/reverse order of versions.', is_flag=True)(func)
    func = click.option('-p', '--priority', type=click.Choice(('branches', 'tags')),
                        help="Group these kinds of versions at the top (for themes that don't separate them).")(func)
    func = click.option('-r', '--root-ref',
                        help='The branch/tag at the root of DESTINATION. Will also be in subdir. Default master.')(func)
    func = click.option('-s', '--sort', multiple=True, type=click.Choice(('semver', 'alpha', 'time')),
                        help='Sort versions. Specify multiple times to sort equal values of one kind.')(func)
    func = click.option('-t', '--greatest-tag', is_flag=True,
                        help='Override root-ref to be the tag with the highest version number.')(func)
    func = click.option('-T', '--recent-tag', is_flag=True,
                        help='Override root-ref to be the most recent committed tag.')(func)
    func = click.option('-w', '--whitelist-branches', multiple=True,
                        help='Whitelist branches that match the pattern. Can be specified more than once.')(func)
    func = click.option('-W', '--whitelist-tags', multiple=True,
                        help='Whitelist tags that match the pattern. Can be specified more than once.')(func)
    func = click.option('-P', '--pdf-file',
                        help='Name of the generated PDF file.')(func)
    return func


def override_root_main_ref(config, remotes, banner):
    """Override root_ref or banner_main_ref with tags in config if user requested.

    :param sphinxcontrib.versioning.lib.Config config: Runtime configuration.
    :param iter remotes: List of dicts from Versions.remotes.
    :param bool banner: Evaluate banner main ref instead of root ref.

    :return: If root/main ref exists.
    :rtype: bool
    """
    log = logging.getLogger(__name__)
    greatest_tag = config.banner_greatest_tag if banner else config.greatest_tag
    recent_tag = config.banner_recent_tag if banner else config.recent_tag

    if greatest_tag or recent_tag:
        candidates = [r for r in remotes if r['kind'] == 'tags']
        if candidates:
            multi_sort(candidates, ['semver' if greatest_tag else 'time'])
            config.update({'banner_main_ref' if banner else 'root_ref': candidates[0]['name']}, overwrite=True)
        else:
            flag = '--banner-main-ref' if banner else '--root-ref'
            log.warning('No git tags with docs found in remote. Falling back to %s value.', flag)

    ref = config.banner_main_ref if banner else config.root_ref
    return ref in [r['name'] for r in remotes]


@cli.command(cls=ClickCommand)
@build_options
@click.argument('REL_SOURCE', nargs=-1, required=True)
@click.argument('DESTINATION', type=click.Path(file_okay=False, dir_okay=True))
@click.make_pass_decorator(Config)
def build(config, rel_source, destination, **options):
    """Fetch branches/tags and build all locally.

    Just fetch all remote branches and tags, export them to a temporary directory, run
    sphinx-build on each one, and then store all built documentation in DESTINATION.

    REL_SOURCE is the path to the docs directory relative to the git root. If the source directory has moved around
    between git tags you can specify additional directories.

    DESTINATION is the path to the local directory that will hold all generated docs for all versions.

    To pass options to sphinx-build (run for every branch/tag) use a double hyphen
    (e.g. build docs docs/_build/html -- -D setting=value).
    \f

    :param sphinxcontrib.versioning.lib.Config config: Runtime configuration.
    :param tuple rel_source: Possible relative paths (to git root) of Sphinx directory containing conf.py (e.g. docs).
    :param str destination: Destination directory to copy/overwrite built docs to. Does not delete old files.
    :param dict options: Additional Click options.
    """
    if 'pre' in config:
        config.pop('pre')(rel_source)
        config.update({k: v for k, v in options.items() if v})
        if config.local_conf:
            config.update(read_local_conf(config.local_conf), ignore_set=True)
    if NO_EXECUTE:
        raise RuntimeError(config, rel_source, destination)
    log = logging.getLogger(__name__)

    # Gather git data.
    log.info('Gathering info about the remote git repository...')
    conf_rel_paths = [os.path.join(s, 'conf.py') for s in rel_source]
    remotes = gather_git_info(config.git_root, conf_rel_paths, config.whitelist_branches, config.whitelist_tags)
    if not remotes:
        log.error('No docs found in any remote branch/tag. Nothing to do.')
        raise HandledError
    versions = Versions(
        remotes,
        sort=config.sort,
        priority=config.priority,
        invert=config.invert,
        pdf_file=config.pdf_file,
    )

    # Get root ref.
    if not override_root_main_ref(config, versions.remotes, False):
        log.error('Root ref %s not found in: %s', config.root_ref, ' '.join(r[1] for r in remotes))
        raise HandledError
    log.info('Root ref is: %s', config.root_ref)

    # Get banner main ref.
    if not config.show_banner:
        config.update(dict(banner_greatest_tag=False, banner_main_ref=None, banner_recent_tag=False), overwrite=True)
    elif not override_root_main_ref(config, versions.remotes, True):
        log.warning('Banner main ref %s not found in: %s', config.banner_main_ref, ' '.join(r[1] for r in remotes))
        log.warning('Disabling banner.')
        config.update(dict(banner_greatest_tag=False, banner_main_ref=None, banner_recent_tag=False, show_banner=False),
                      overwrite=True)
    else:
        log.info('Banner main ref is: %s', config.banner_main_ref)

    # Pre-build.
    log.info("Pre-running Sphinx to collect versions' master_doc and other info.")
    exported_root = pre_build(config.git_root, versions)
    if config.banner_main_ref and config.banner_main_ref not in [r['name'] for r in versions.remotes]:
        log.warning('Banner main ref %s failed during pre-run. Disabling banner.', config.banner_main_ref)
        config.update(dict(banner_greatest_tag=False, banner_main_ref=None, banner_recent_tag=False, show_banner=False),
                      overwrite=True)

    # Build.
    build_all(exported_root, destination, versions)

    # Cleanup.
    log.debug('Removing: %s', exported_root)
    shutil.rmtree(exported_root)

    # Store versions in state for push().
    config['versions'] = versions
