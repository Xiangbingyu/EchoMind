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

        async with httpx.AsyncClient() as c:
            # 创建 workspace + project
            ws = await c.post(f"{BASE}/api/workspaces", json={"name": "git-test"})
            ws_id = ws.json()["id"]

            proj = await c.post(f"{BASE}/api/workspaces/{ws_id}/projects", json={
                "name": "git-proj", "local_path": repo_path
            })
            proj_id = proj.json()["id"]

            # init repo
            r = await c.post(f"{BASE}/api/projects/{proj_id}/repo/init")
            check("POST /projects/{id}/repo/init", r.status_code == 200)

            # create proposal
            r = await c.post(f"{BASE}/api/projects/{proj_id}/proposals")
            check("POST /projects/{id}/proposals", r.status_code == 200, r.text[:100])
            if r.status_code != 200:
                return
            proposal_id = r.json()["id"]
            branch = r.json()["branch_name"]
            check("branch created", branch.startswith("proposal/"))

            # write a file into the proposal branch working dir, then commit
            test_file = os.path.join(repo_path, "hello.txt")
            with open(test_file, "w") as f:
                f.write("hello from proposal")

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

            # confirm proposal
            r = await c.post(f"{BASE}/api/proposals/{proposal_id}/confirm")
            check("POST /proposals/{id}/confirm", r.status_code == 200)

            # history
            r = await c.get(f"{BASE}/api/projects/{proj_id}/history")
            check("GET /projects/{id}/history", r.status_code == 200)
            check("history not empty", len(r.json()) > 0)

    print()


asyncio.run(main())
