from __future__ import annotations

from .policy import PolicyError, validate_git_sha


class StaleCheckpoint(PolicyError):
    """Raised when the expected base SHA is not the current branch head."""


def compare_and_swap_checkpoint(expected_base_sha: str, current_head_sha: str, proposed_commit_sha: str) -> str:
    validate_git_sha(expected_base_sha)
    validate_git_sha(current_head_sha)
    validate_git_sha(proposed_commit_sha)
    if expected_base_sha != current_head_sha:
        raise StaleCheckpoint("branch head changed; re-fetch and rebuild from the latest checkpoint")
    return proposed_commit_sha
