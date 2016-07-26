import click
import os
import warnings
import pip
import re
import sys

from pip.wheel import WheelCache
from pip.commands.freeze import FreezeCommand, freeze


PKG_VERSION_REGEX = re.compile(r'([\d]+\.)+[\d]+|([\d]+)|[\d]+$')
GLOBAL = None


def run(self, options, args):
    format_control = pip.index.FormatControl(set(), set())
    wheel_cache = WheelCache(options.cache_dir, format_control)
    freeze_kwargs = dict(
        requirement=options.requirement,
        find_links=options.find_links,
        local_only=options.local,
        user_only=options.user,
        skip_regex=options.skip_requirements_regex,
        isolated=options.isolated_mode,
        wheel_cache=wheel_cache)

    pkgs = []
    for line in freeze(**freeze_kwargs):
        pkgs.append(line)

    os.environ['packages'] = ','.join(pkgs)
    return pkgs


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    try:
        cmd_name, cmd_args = pip.parseopts(args)
    except pip.PipError as exc:
        sys.stderr.write("ERROR: %s" % exc)
        sys.stderr.write(os.linesep)
        sys.exit(1)

    freeze_command = pip.commands_dict[cmd_name]
    freeze_command.run = run
    command = pip.commands_dict[cmd_name](isolated=pip.check_isolated(cmd_args))
    return command.main(cmd_args)


def get_pkg_name(pkg_name):
    if ">=" in pkg_name:
        return pkg_name.split('>=')[0]
    elif ">" in pkg_name:
        return pkg_name.split('>')[0]
    elif "<=" in pkg_name:
        return pkg_name.split('<=')[0]
    elif "<" in pkg_name:
        return pkg_name.split('<')[0]
    elif "==" in pkg_name:
        return pkg_name.split('==')[0]


def get_version(pkg_name):
    if pkg_name.startswith('-e'):
        return None, None

    version = PKG_VERSION_REGEX.search(pkg_name)
    if version:
        return version.group()


def pkg_tuple(pkg_v):
    return tuple(map(int, (pkg_v.split("."))))


def compare_package_version(installed_pkg, requirement_pkg):
    requirement_pkg_v = get_version(requirement_pkg)
    installed_pkg_v = get_version(installed_pkg)

    requirement_pkg_v = pkg_tuple(requirement_pkg_v)
    installed_pkg_v = pkg_tuple(installed_pkg_v)

    if ">" in requirement_pkg:
        return requirement_pkg_v > installed_pkg_v
    elif ">=" in requirement_pkg:
        return requirement_pkg_v >= installed_pkg_v
    elif "<" in requirement_pkg:
        return requirement_pkg_v < installed_pkg_v
    elif "<=" in requirement_pkg:
        return requirement_pkg_v <= installed_pkg_v
    elif "==" in requirement_pkg:
        return requirement_pkg_v == installed_pkg_v


@click.command()
@click.argument('requirement_txt_file_path', type=click.File('r'), required=True)
def pip_diff_main(requirement_txt_file_path):
    """
    Pip diff will show difference with requirement.txt and installed packages in
    current environment.
    """
    errors = []
    parser = pip.create_main_parser()
    options, _ = parser.parse_args(['freeze'])
    main(['freeze'])
    installed_pkgs = os.environ.get('packages', '')
    installed_pkgs_dict = {}
    for pkg in installed_pkgs.split(','):
        if pkg.startswith('-e'):
            continue

        installed_pkg_name = get_pkg_name(pkg)
        installed_pkgs_dict[installed_pkg_name] = pkg

    for req_pkg in requirement_txt_file_path.readlines():
        req_pkg = req_pkg.replace('\n', '')
        if req_pkg.startswith('-e'):
            continue

        req_pkg_name = get_pkg_name(req_pkg)
        installed_pkg_name = installed_pkgs_dict.get(req_pkg_name)
        if installed_pkg_name:
            if not compare_package_version(installed_pkg_name, req_pkg):
                errors.append({
                    'installed_pkg': installed_pkg_name,
                    'requirement_pkg': req_pkg
                })
        else:
            errors.append({
                'installed_pkg': installed_pkg_name,
                'requirement_pkg': req_pkg
            })

    if errors:
        print("Installed packages and requirement.txt[%s] diff \n" % requirement_txt_file_path.name)

        for err in errors:
            print("Installed package \033[91m[%s]\033[00m | requirement.txt package \033[93m[%s]\033[00m" % (
                err['installed_pkg'],
                err['requirement_pkg']
            ))


if __name__ == '__main__':
    pip_diff_main()
