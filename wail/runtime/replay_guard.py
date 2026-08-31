class PolicyMismatchError(Exception):
    pass


def enforce_policy_pinning(
    current_policy_version: str,
    replay_policy_version: str,
    allow_mismatch: bool = False,
):
    if current_policy_version != replay_policy_version:
        if not allow_mismatch:
            raise PolicyMismatchError(
                f"Policy version mismatch: current={current_policy_version} replay={replay_policy_version}"
            )
