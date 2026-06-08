"""
Git Service integration tests.
Run: python tests/test_git.py
Requires: gateway on :8000, a temp dir for git repo
"""
import asyncio
import tempfile
import os
import httpx

BASE = "http://localhost:8000"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return condition


async def main():
    print("\n=== Git Service ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = os.path.join(tmpdir, "test_project")
        missing_repo_path = os.path.join(tmpdir, "missing_repo")

        async with httpx.AsyncClient() as c:
            # 创建 workspace + project
            ws = await c.post(f"{BASE}/api/workspaces", json={"name": "git-test", "endpoint": "local://git"})
            ws_id = ws.json()["id"]

            proj = await c.post(f"{BASE}/api/workspaces/{ws_id}/projects", json={
                "name": "git-proj", "path": repo_path
            })
            proj_id = proj.json()["id"]

            missing_proj = await c.post(f"{BASE}/api/workspaces/{ws_id}/projects", json={
                "name": "git-missing-repo", "path": missing_repo_path
            })
            missing_proj_id = missing_proj.json()["id"]

            # missing repo should fail before proposal creation
            r = await c.post(f"{BASE}/api/projects/{missing_proj_id}/proposals")
            check("POST /projects/{id}/proposals fails when repo missing", r.status_code == 400, r.text[:120])

            # init repo
            r = await c.post(f"{BASE}/api/projects/{proj_id}/repo/init")
            check("POST /projects/{id}/repo/init", r.status_code == 200)

            with open(os.path.join(repo_path, ".git", "HEAD"), "r", encoding="utf-8") as f:
                head_ref = f.read().strip()
            base_branch = head_ref.rsplit("/", 1)[-1]

            # working copy before edits
            r = await c.get(f"{BASE}/api/projects/{proj_id}/working-copy")
            check("GET /projects/{id}/working-copy 200", r.status_code == 200, r.text[:100])
            if r.status_code != 200:
                return
            status = r.json()
            check("working copy initially clean", status["is_dirty"] is False)

            # invalid base branch should fail clearly
            r = await c.post(f"{BASE}/api/projects/{proj_id}/proposals", json={"base_branch": "does-not-exist"})
            check("POST /projects/{id}/proposals rejects invalid base_branch", r.status_code == 400, r.text[:120])

            # create proposal
            r = await c.post(f"{BASE}/api/projects/{proj_id}/proposals", json={"base_branch": base_branch})
            check("POST /projects/{id}/proposals", r.status_code == 200, r.text[:100])
            if r.status_code != 200:
                return
            proposal_id = r.json()["id"]
            branch = r.json()["branch_name"]
            check("branch created", branch.startswith("proposal/"))
            check("proposal stores base_branch", r.json().get("base_branch") == base_branch, str(r.json()))

            # write a file into the proposal branch working dir, then commit
            test_file = os.path.join(repo_path, "hello.txt")
            with open(test_file, "w") as f:
                f.write("hello from proposal")

            r = await c.get(f"{BASE}/api/projects/{proj_id}/working-copy")
            check(
                "working copy detects pending change",
                r.status_code == 200 and (r.json()["is_dirty"] is True or len(r.json()["untracked"]) > 0),
                r.text[:120],
            )

            r = await c.post(f"{BASE}/api/proposals/{proposal_id}/commit?message=add+hello")
            check("POST /proposals/{id}/commit", r.status_code == 200)

            # get diff
            r = await c.get(f"{BASE}/api/proposals/{proposal_id}/diff")
            check("GET /proposals/{id}/diff", r.status_code == 200)
            diff = r.json()
            check("diff has changed_files", len(diff["changed_files"]) > 0)

            # list proposals
            r = await c.get(f"{BASE}/api/projects/{proj_id}/proposals")
            check("GET /projects/{id}/proposals", r.status_code == 200)
            check("proposal in list", any(p["id"] == proposal_id for p in r.json()))
            check("proposal status becomes committed", any(p["id"] == proposal_id and p["status"] == "committed" for p in r.json()))

            # missing proposal diff should fail clearly
            r = await c.get(f"{BASE}/api/proposals/not-found/diff")
            check("GET /proposals/{id}/diff returns 404 for missing proposal", r.status_code == 404)

            # history
            r = await c.get(f"{BASE}/api/projects/{proj_id}/history")
            check("GET /projects/{id}/history", r.status_code == 200)
            check("history not empty", len(r.json()) > 0)

    print()


asyncio.run(main())
