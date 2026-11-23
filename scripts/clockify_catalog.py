#!/usr/bin/env python3
"""
Print your live Clockify workspace/project/task catalog, so config/config.yaml
can be filled in by matching real IDs instead of guessing them.

Requires CLOCKIFY_API_KEY to be set (see credentials/.env / .env.example).
Used by SETUP.md as the first real step of configuring this tool.

Usage:
    python scripts/clockify_catalog.py
    python scripts/clockify_catalog.py --workspace-id YOUR_WORKSPACE_ID
    python scripts/clockify_catalog.py --json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clockify.client import ClockifyClient


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace-id', help='Clockify workspace id (auto-detected '
                                            'if you only belong to one)')
    ap.add_argument('--json', action='store_true', help='Print machine-readable JSON '
                                                          'instead of a human-readable listing')
    args = ap.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv('credentials/.env')
    except ImportError:
        pass

    if not os.getenv('CLOCKIFY_API_KEY'):
        print("ERROR: CLOCKIFY_API_KEY not set.\n"
              "Copy .env.example to credentials/.env and fill in your API key "
              "(https://clockify.me/user/settings), then either install "
              "python-dotenv or run: set -a && source credentials/.env && set +a",
              file=sys.stderr)
        sys.exit(1)

    client = ClockifyClient()

    workspace_id = args.workspace_id
    workspaces = client.get_workspaces()
    if not workspace_id:
        if len(workspaces) == 1:
            workspace_id = workspaces[0]['id']
        else:
            print("Multiple workspaces found - pass --workspace-id explicitly:",
                  file=sys.stderr)
            for w in workspaces:
                print(f"  {w['id']}  {w['name']}", file=sys.stderr)
            sys.exit(1)

    workspace_name = next((w['name'] for w in workspaces if w['id'] == workspace_id),
                           workspace_id)
    projects = client.get_projects(workspace_id)

    catalog = {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "projects": [],
    }
    for project in projects:
        tasks = client.get_tasks(workspace_id, project["id"])
        catalog["projects"].append({
            "id": project["id"],
            "name": project["name"],
            "tasks": [{"id": t["id"], "name": t["name"]} for t in tasks],
        })

    if args.json:
        print(json.dumps(catalog, indent=2))
        return

    print(f"Workspace: {catalog['workspace_name']}  ({catalog['workspace_id']})")
    print(f"clockify.workspace_id: \"{catalog['workspace_id']}\"\n")
    for project in catalog["projects"]:
        print(f"Project: {project['name']}")
        print(f"  id: {project['id']}")
        if project["tasks"]:
            print("  tasks:")
            for t in project["tasks"]:
                print(f"    {t['id']}  {t['name']}")
        else:
            print("  (no tasks)")
        print()


if __name__ == '__main__':
    main()
