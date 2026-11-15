#!/usr/bin/env python3
"""Offline deterministic planner. It performs no network or external actions."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.policy import validate_mission_context, validate_task
from zcira_control.queue import plan_batch


def load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-task")
    validate.add_argument("--task", required=True)
    validate.add_argument("--mission", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--tasks", required=True)
    plan.add_argument("--mission", required=True)
    args = parser.parse_args()
    mission = load(args.mission)
    validate_mission_context(mission)
    if args.command == "validate-task":
        task = load(args.task)
        validate_task(task, mission)
        print(json.dumps({"valid": True, "task_id": task["task_id"], "execution_performed": False}, ensure_ascii=False))
        return 0
    tasks = load(args.tasks)
    selected = plan_batch(tasks, mission)
    print(json.dumps({"selected_tasks": selected, "count": len(selected), "execution_performed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
