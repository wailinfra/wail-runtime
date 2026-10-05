import wail.bootstrap
from wail.wrapper import wrap
from wail.runtime_config import configure

wail.bootstrap.bootstrap_import_alias()


def wail_start(*args, **kwargs):
    from wail.runtime.context import wail_start as _wail_start

    return _wail_start(*args, **kwargs)


def wail_end(*args, **kwargs):
    from wail.runtime.context import wail_end as _wail_end

    return _wail_end(*args, **kwargs)


def wail_retry(*args, **kwargs):
    from wail.runtime.context import wail_retry as _wail_retry

    return _wail_retry(*args, **kwargs)


def execution_parent(
    unit_id,
    *,
    kind="calls",
):
    from wail.execution.bridge import execution_parent_scope

    return execution_parent_scope(
        unit_id,
        kind=kind,
    )


def execution_run(
    *,
    run_id=None,
    attributes=None,
):
    from wail.execution.bridge import execution_run_scope

    return execution_run_scope(
        run_id=run_id,
        attributes=attributes,
    )


__all__ = [
    "configure",
    "wrap",
    "wail_start",
    "wail_end",
    "wail_retry",
    "execution_run",
    "execution_parent",
]