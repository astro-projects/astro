"""Nox automation definitions."""

import pathlib

import nox

nox.options.sessions = ["dev"]
nox.options.reuse_existing_virtualenvs = True


@nox.session(python="3.10")
def dev(session: nox.Session) -> None:
    """Create a dev environment with everything installed.

    This is useful for setting up IDE for autocompletion etc. Point the
    development environment to ``.nox/dev``.
    """
    session.install("nox")
    session.install("-e", ".[all,tests]")


@nox.session(python=["3.7", "3.8", "3.9"])
@nox.parametrize("airflow", ["2.2.5", "2.4", "2.5"])
def test(session: nox.Session, airflow) -> None:
    """Run both unit and integration tests."""
    # 2.2.5 requires a certain version of pandas and sqlalchemy
    # Otherwise it fails with
    # Pandas requires version '1.4.0' or newer of 'sqlalchemy' (version '1.3.24' currently installed).
    constraints_url = (
        "https://raw.githubusercontent.com/apache/airflow/"
        f"constraints-{airflow}/constraints-{session.python}.txt"
    )
    constraints = ["-c", constraints_url] if airflow == "2.2.5" else []
    if airflow == "2.5":
        session.install("git+https://github.com/bolkedebruin/airflow.git@taskflow_datasets")
    else:
        session.install(f"apache-airflow=={airflow}", *constraints)
    session.install("-e", ".[all,tests]", *constraints)
    # Log all the installed dependencies
    session.log("Installed Dependencies:")
    session.run("pip3", "freeze")
    AIRFLOW_HOME = f"~/airflow-{airflow}-{session.python}"
    session.run("airflow", "db", "init", env={"AIRFLOW_HOME": AIRFLOW_HOME})
    # Since pytest is not installed in the nox session directly, we need to set `external=true`.
    session.run("pytest", *session.posargs, env={"AIRFLOW_HOME": AIRFLOW_HOME}, external=True)


@nox.session(python=["3.8"])
def type_check(session: nox.Session) -> None:
    """Run MyPy checks."""
    session.install("-e", ".[all,tests]")
    session.run("mypy", "--version")
    session.run("mypy")


@nox.session()
@nox.parametrize(
    "extras",
    [
        ("postgres-amazon", {"include": ["postgres", "amazon"]}),
        ("snowflake-amazon", {"include": ["snowflake", "amazon"]}),
        ("sqlite", {"include": ["sqlite"]}),
    ],
)
def test_examples_by_dependency(session: nox.Session, extras):
    _, extras = extras
    pypi_deps = ",".join(extras["include"])
    pytest_options = " and ".join(extras["include"])
    pytest_options = " and not ".join([pytest_options, *extras.get("exclude", [])])
    pytest_args = ["-k", pytest_options]

    session.install("-e", f".[{pypi_deps}]")
    session.install("-e", ".[tests]")
    session.run("airflow", "db", "init")

    # Since pytest is not installed in the nox session directly, we need to set `external=true`.
    session.run("pytest", "tests/test_example_dags.py", *pytest_args, *session.posargs, external=True)


@nox.session()
def lint(session: nox.Session) -> None:
    """Run linters."""
    session.install("pre-commit")
    if session.posargs:
        args = [*session.posargs, "--all-files"]
    else:
        args = ["--all-files", "--show-diff-on-failure"]
    session.run("pre-commit", "run", *args)


@nox.session()
def build(session: nox.Session) -> None:
    """Build release artifacts."""
    session.install("build")

    # TODO: Automate version bumping, Git tagging, and more?

    dist = pathlib.Path("dist")
    if dist.exists() and next(dist.iterdir(), None) is not None:
        session.error(
            "There are files in dist/. Remove them and try again. "
            "You can use `git clean -fxdi -- dist` command to do this."
        )
    dist.mkdir(exist_ok=True)

    session.run("python", "-m", "build", *session.posargs)


@nox.session(python="3.9")
def build_docs(session: nox.Session) -> None:
    """Build release artifacts."""
    session.install("-e", ".[doc]")
    session.chdir("./docs")
    session.run("make", "html")


@nox.session()
def release(session: nox.Session) -> None:
    """Publish a release."""
    session.install("twine")
    # TODO: Better artifact checking.
    session.run("twine", "check", *session.posargs)
    session.run("twine", "upload", *session.posargs)
