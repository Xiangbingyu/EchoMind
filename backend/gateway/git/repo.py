import os
from dataclasses import dataclass
from git import Repo, InvalidGitRepositoryError


@dataclass
class ProposalDiff:
    proposal_id: str
    changed_files: list[str]
    patch: str


def _close_repo(repo: Repo) -> None:
    close = getattr(repo, "close", None)
    if callable(close):
        close()


def init_repository(local_path: str, remote_url: str | None = None) -> None:
    os.makedirs(local_path, exist_ok=True)
    repo = Repo.init(local_path)
    try:
        if not repo.heads:
            open(os.path.join(local_path, ".gitkeep"), "w").close()
            repo.index.add([".gitkeep"])
            repo.index.commit("init")
        if remote_url and "origin" not in [r.name for r in repo.remotes]:
            repo.create_remote("origin", remote_url)
    finally:
        _close_repo(repo)


def _get_repo(local_path: str) -> Repo:
    return Repo(local_path)


def _get_base_branch(repo: Repo):
    return next((h for h in repo.heads if h.name in ("main", "master")), repo.heads[0])


def create_proposal_branch(local_path: str, proposal_id: str) -> str:
    repo = _get_repo(local_path)
    try:
        branch_name = f"proposal/{proposal_id}"
        repo.create_head(branch_name, _get_base_branch(repo))
        return branch_name
    finally:
        _close_repo(repo)


def get_proposal_diff(local_path: str, proposal_id: str) -> ProposalDiff:
    repo = _get_repo(local_path)
    try:
        branch_name = f"proposal/{proposal_id}"
        branch = repo.heads[branch_name]
        # find merge base with main/master
        base = _get_base_branch(repo)
        merge_base = repo.merge_base(base, branch)
        if not merge_base:
            return ProposalDiff(proposal_id=proposal_id, changed_files=[], patch="")
        diff = merge_base[0].diff(branch.commit)
        changed_files = [d.a_path or d.b_path for d in diff]
        patch = repo.git.diff(merge_base[0].hexsha, branch.commit.hexsha)
        return ProposalDiff(proposal_id=proposal_id, changed_files=changed_files, patch=patch)
    finally:
        _close_repo(repo)


def commit_to_proposal(local_path: str, proposal_id: str, message: str) -> str:
    repo = _get_repo(local_path)
    try:
        branch_name = f"proposal/{proposal_id}"
        repo.heads[branch_name].checkout()
        repo.git.add(A=True)
        if repo.is_dirty(index=True):
            commit = repo.index.commit(message)
            return commit.hexsha
        return repo.head.commit.hexsha
    finally:
        _close_repo(repo)


def confirm_proposal(local_path: str, proposal_id: str) -> str:
    repo = _get_repo(local_path)
    try:
        branch_name = f"proposal/{proposal_id}"
        base = _get_base_branch(repo)
        base.checkout()
        repo.git.merge(branch_name, no_ff=True, m=f"Merge {branch_name}")
        return repo.head.commit.hexsha
    finally:
        _close_repo(repo)


def push_project(local_path: str, branch: str = "master") -> None:
    repo = _get_repo(local_path)
    try:
        origin = repo.remote("origin")
        origin.push(branch)
    finally:
        _close_repo(repo)


def get_project_history(local_path: str, limit: int = 20) -> list[dict]:
    repo = _get_repo(local_path)
    try:
        return [
            {"hexsha": c.hexsha[:8], "message": c.message.strip(), "author": c.author.name, "date": c.committed_datetime.isoformat()}
            for c in repo.iter_commits(max_count=limit)
        ]
    finally:
        _close_repo(repo)


def get_working_copy_status(local_path: str) -> dict:
    repo = _get_repo(local_path)
    try:
        return {
            "is_dirty": repo.is_dirty(),
            "untracked": repo.untracked_files,
            "modified": [d.a_path for d in repo.index.diff(None)],
        }
    finally:
        _close_repo(repo)
