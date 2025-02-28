import re
from functools import cache
from importlib import metadata
from io import StringIO
from pathlib import Path
from typing import Sequence

from mypy.build import build
from mypy.errors import CompileError
from mypy.main import process_options

from .error import Error, ErrorCode
from .explain import explain
from .gen import main as generate
from .loader import load_checks
from .settings import Settings, load_settings
from .visitor import RefurbVisitor


def usage() -> None:
    print(
        """\
usage: refurb [--ignore err] [--load path] [--debug] [--quiet] src [srcs...]
       refurb [--help | -h]
       refurb [--version | -v]
       refurb --explain err
       refurb gen

Command Line Options:

-h, --help       This help menu.
--version, -v    Print version information.
--ignore err     Ignore an error. Can be repeated.
--load module    Add a module to the list of paths to be searched when looking
                 for checks. Can be repeated.
--debug          Print the AST representation of all files that where checked.
--quiet          Suppress default "--explain" suggestion when an error occurs.
src              A file or folder.


Subcommands:

gen              Generate boilerplate code for a new check, meant for
                 developers.
"""
    )


def version() -> str:  # pragma: no cover
    refurb_version = metadata.version("refurb")
    mypy_version = metadata.version("mypy")

    return f"Refurb: v{refurb_version}\nMypy: v{mypy_version}"


@cache
def get_source_lines(filepath: str) -> list[str]:
    return Path(filepath).read_text("utf8").splitlines()


def ignored_via_comment(error: Error | str) -> bool:
    if isinstance(error, str) or not error.filename:
        return False

    line = get_source_lines(error.filename)[error.line - 1]

    if comment := re.search("# noqa(: [A-Z]{3,4}\\d{3})?$", line):
        ignore = comment.group(1)
        error_code = str(ErrorCode.from_error(type(error)))

        if not ignore or ignore[2:] == error_code:
            return True

    return False


def run_refurb(settings: Settings) -> Sequence[Error | str]:
    stderr = StringIO()

    try:
        files, opt = process_options(settings.files or [], stderr=stderr)

    except SystemExit:
        return ["refurb: " + err for err in stderr.getvalue().splitlines()]

    finally:
        stderr.close()

    opt.incremental = True
    opt.fine_grained_incremental = True
    opt.cache_fine_grained = True

    try:
        result = build(files, options=opt)

    except CompileError as e:
        return [re.sub("^mypy: ", "refurb: ", msg) for msg in e.messages]

    errors: list[Error | str] = []

    for file in files:
        if tree := result.graph[file.module].tree:
            if settings.debug:
                errors.append(str(tree))

            checks = load_checks(settings)
            visitor = RefurbVisitor(checks)

            tree.accept(visitor)

            for error in visitor.errors:
                error.filename = file.path

            errors += visitor.errors

    return sorted(
        [error for error in errors if not ignored_via_comment(error)],
        key=sort_errors,
    )


def sort_errors(
    error: Error | str,
) -> tuple[str, int, int, str, int] | tuple[str, str]:
    if isinstance(error, str):
        return ("", error)

    return (
        error.filename or "",
        error.line,
        error.column,
        error.prefix,
        error.code,
    )


def format_errors(errors: Sequence[Error | str], quiet: bool) -> str:
    done = "\n".join((str(error) for error in errors))

    if not quiet and any(isinstance(error, Error) for error in errors):
        done += "\n\nRun `refurb --explain ERR` to further explain an error. Use `--quiet` to silence this message"  # noqa: E501

    return done


def main(args: list[str]) -> int:
    try:
        settings = load_settings(args)

    except ValueError as e:
        print(e)
        return 1

    if settings.help:
        usage()

        return 0

    if settings.version:
        print(version())

        return 0

    if settings.generate:
        generate()

        return 0

    if settings.explain:
        print(explain(settings.explain, settings.load or []))

        return 0

    errors = run_refurb(settings)

    if formatted_errors := format_errors(errors, settings.quiet):
        print(formatted_errors)

    return 1 if errors else 0
