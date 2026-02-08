#!/usr/bin/env python3
"""
Notion sync: push UNLOCKED events from ops/hub_events_v1.jsonl to Notion DB.
Uses contracts/master_plan_v1.json for unlock_id -> maps_to_plan_ids.
Cursor: ops/notion_sync_cursor.json (last_processed_line_index).
Config: ops/notion.local.json (token, database_id, properties).
FAIL 금지: 실패해도 exit 0, stderr에 경고만.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER_PLAN_PATH = REPO_ROOT / "contracts" / "master_plan_v1.json"
HUB_EVENTS_PATH = REPO_ROOT / "ops" / "hub_events_v1.jsonl"
CURSOR_PATH = REPO_ROOT / "ops" / "notion_sync_cursor.json"
NOTION_CONFIG_PATH = REPO_ROOT / "ops" / "notion.local.json"
STATUS_PATH = REPO_ROOT / "ops" / "notion_sync_status.json"

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

DEFAULT_PROPERTIES = {
    "plan_id": "Plan ID",
    "status": "Status",
    "target_agent": "Target Agent",
    "brief_path": "LLM Briefing Path",
    "last_sync": "Last Sync",
    "last_event_id": "Last Event ID",
}


def _warn(msg: str) -> None:
    print(msg, file=sys.stderr)


def _load_master_plan() -> dict:
    """Load master_plan; return {} on failure."""
    if not MASTER_PLAN_PATH.exists():
        _warn("notion_sync: SKIPPED master_plan not found")
        return {}
    try:
        with open(MASTER_PLAN_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _warn(f"notion_sync: SKIPPED master_plan load failed: {e}")
        return {}


def unlock_id_to_plan_ids(plan: dict) -> dict[str, list[str]]:
    """Build unlock_id -> list of plan_id from plan.unlocks[].maps_to_plan_ids."""
    out = {}
    for u in plan.get("unlocks") or []:
        uid = u.get("unlock_id")
        if not uid:
            continue
        maps = u.get("maps_to_plan_ids")
        if isinstance(maps, list) and maps:
            out[uid] = [str(p) for p in maps]
        else:
            out[uid] = []
    return out


def _load_events(path: Path) -> list[tuple[int, dict]]:
    """Read jsonl; return [(line_index, event_dict), ...] for event_type==UNLOCKED."""
    events = []
    if not path.exists():
        return events
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except Exception as e:
        _warn(f"notion_sync: SKIPPED events read failed: {e}")
        return events
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            if (ev.get("event_type") or "").strip().upper() == "UNLOCKED":
                events.append((i, ev))
        except json.JSONDecodeError:
            continue
    return events


def _load_cursor() -> int:
    """Return last_processed_line_index (0-based); -1 if none."""
    if not CURSOR_PATH.exists():
        return -1
    try:
        with open(CURSOR_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return int(d.get("last_processed_line_index", -1))
    except Exception:
        return -1


def _save_cursor(last_index: int) -> None:
    """Write cursor (warn-only on failure)."""
    try:
        CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CURSOR_PATH, "w", encoding="utf-8") as f:
            json.dump({"last_processed_line_index": last_index}, f, indent=2)
    except Exception as e:
        _warn(f"notion_sync: cursor save failed: {e}")


def _write_status(
    mode: str,
    reason: str,
    processed: int = 0,
    updated: int = 0,
    skipped: int = 0,
    error_count: int = 0,
    cursor: int | None = None,
) -> None:
    """Write ops/notion_sync_status.json (git-tracked). Overwrites each run."""
    try:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("Asia/Seoul")
        except ImportError:
            tz = timezone.utc
        updated_at = datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema_version": "notion_sync_status.v1",
        "updated_at": updated_at,
        "mode": mode,
        "reason": reason,
        "processed": processed,
        "updated": updated,
        "skipped": skipped,
        "error_count": error_count,
        "cursor": cursor,
    }
    try:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        _warn(f"notion_sync: status write failed: {e}")


def _load_notion_config() -> tuple[dict, list[str]]:
    """Load ops/notion.local.json. Return (config, warnings)."""
    warnings = []
    if not NOTION_CONFIG_PATH.exists():
        warnings.append("notion_sync: SKIPPED ops/notion.local.json not found")
        return {}, warnings
    try:
        with open(NOTION_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        warnings.append(f"notion_sync: SKIPPED notion config load failed: {e}")
        return {}, warnings
    token = (cfg.get("token") or "").strip()
    database_id = (cfg.get("database_id") or "").strip()
    if not token or not database_id:
        warnings.append("notion_sync: SKIPPED token or database_id empty in ops/notion.local.json")
        return {}, warnings
    props = {**DEFAULT_PROPERTIES, **(cfg.get("properties") or {})}
    cfg["_properties"] = props
    return cfg, warnings


def _query_page_id_by_plan_id(headers: dict, database_id: str, plan_id: str, prop_plan_id: str) -> str | None:
    """Query Notion DB for page with Plan ID == plan_id. Return page_id or None."""
    try:
        import requests
    except ImportError:
        return _query_page_id_urllib(headers, database_id, plan_id, prop_plan_id)
    url = f"{NOTION_API_BASE}/databases/{database_id}/query"
    body = {
        "filter": {
            "property": prop_plan_id,
            "rich_text": {"equals": plan_id},
        },
        "page_size": 1,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        return results[0].get("id")
    except Exception:
        return None


def _query_page_id_urllib(headers: dict, database_id: str, plan_id: str, prop_plan_id: str) -> str | None:
    """Fallback: query via urllib (no requests)."""
    import urllib.request
    import urllib.error
    url = f"{NOTION_API_BASE}/databases/{database_id}/query"
    body = json.dumps({
        "filter": {"property": prop_plan_id, "rich_text": {"equals": plan_id}},
        "page_size": 1,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results") or []
        if not results:
            return None
        return results[0].get("id")
    except Exception:
        return None


def _patch_page(headers: dict, page_id: str, properties: dict, props_schema: dict, event: dict, event_id: str) -> bool:
    """PATCH Notion page with Status=Done, Target Agent, LLM Briefing Path, Last Sync, Last Event ID. Return True on success."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {}
    status_key = props_schema.get("status") or "Status"
    payload[status_key] = {"status": {"name": "Done"}}
    target_key = props_schema.get("target_agent") or "Target Agent"
    if target_key:
        payload[target_key] = {"rich_text": [{"text": {"content": (event.get("target_agent") or "")[:2000]}}]}
    brief_key = props_schema.get("brief_path") or "LLM Briefing Path"
    if brief_key:
        payload[brief_key] = {"rich_text": [{"text": {"content": (event.get("brief_path") or "")[:2000]}}]}
    last_sync_key = props_schema.get("last_sync") or "Last Sync"
    if last_sync_key:
        payload[last_sync_key] = {"date": {"start": now}}
    last_event_key = props_schema.get("last_event_id") or "Last Event ID"
    if last_event_key:
        payload[last_event_key] = {"rich_text": [{"text": {"content": event_id[:2000]}}]}
    body = {"properties": payload}
    try:
        import requests
    except ImportError:
        return _patch_page_urllib(headers, page_id, body)
    try:
        r = requests.patch(f"{NOTION_API_BASE}/pages/{page_id}", headers=headers, json=body, timeout=30)
        r.raise_for_status()
        return True
    except Exception:
        return False


def _patch_page_urllib(headers: dict, page_id: str, body: dict) -> bool:
    import urllib.request
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH", headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as _:
            return True
    except Exception:
        return False


def _config_skip_reason(warnings: list[str]) -> str:
    """Map config load warnings to status reason."""
    for w in warnings:
        wl = w.lower()
        if "empty" in wl or "token or database_id" in wl:
            return "empty_token"
        if "not found" in wl:
            return "missing_config"
    return "error"


def main() -> int:
    processed = 0
    updated = 0
    skipped = 0
    error_count = 0
    cursor_val: int | None = None

    try:
        plan = _load_master_plan()
        if not plan:
            _write_status("skipped", "error", error_count=1, cursor=None)
            return 0

        uid_to_plan_ids = unlock_id_to_plan_ids(plan)
        events_with_index = _load_events(HUB_EVENTS_PATH)
        cursor_val = _load_cursor()
        new_events = [(i, ev) for i, ev in events_with_index if i > cursor_val]
        if not new_events:
            _write_status("skipped", "no_new_events", cursor=cursor_val)
            print("notion_sync: no new UNLOCKED events")
            return 0

        config, cfg_warnings = _load_notion_config()
        for w in cfg_warnings:
            _warn(w)
        if not config:
            reason = _config_skip_reason(cfg_warnings)
            _write_status("skipped", reason, cursor=cursor_val)
            return 0

        token = config.get("token", "").strip()
        database_id = config.get("database_id", "").strip()
        props_schema = config.get("_properties") or DEFAULT_PROPERTIES
        prop_plan_id = props_schema.get("plan_id") or "Plan ID"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }
        max_index = cursor_val
        for line_index, ev in new_events:
            unlock_id = (ev.get("unlock_id") or "").strip()
            plan_ids = uid_to_plan_ids.get(unlock_id) or []
            if not plan_ids:
                _warn(f"notion_sync: SKIPPED unlock_id={unlock_id} has no maps_to_plan_ids")
                skipped += 1
                max_index = max(max_index, line_index)
                continue
            event_id = f"{line_index}"
            for plan_id in plan_ids:
                page_id = _query_page_id_by_plan_id(headers, database_id, plan_id, prop_plan_id)
                if not page_id:
                    _warn(f"notion_sync: SKIPPED plan_id={plan_id} row not found in Notion DB")
                    skipped += 1
                    continue
                if _patch_page(headers, page_id, {}, props_schema, ev, event_id):
                    updated += 1
                else:
                    _warn(f"notion_sync: SKIPPED PATCH failed for plan_id={plan_id}")
                    error_count += 1
            max_index = max(max_index, line_index)
        processed = len(new_events)
        _save_cursor(max_index)
        cursor_val = max_index
        _write_status("live", "ok", processed=processed, updated=updated, skipped=skipped, error_count=error_count, cursor=cursor_val)
        print(f"notion_sync: processed={processed} updated={updated} cursor={max_index}")
        return 0
    except Exception:
        error_count += 1
        _write_status("skipped", "error", processed=processed, updated=updated, skipped=skipped, error_count=error_count, cursor=cursor_val)
        _warn("notion_sync: exception (exit 0, warn-only)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
