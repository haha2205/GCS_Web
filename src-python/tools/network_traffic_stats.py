from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path


FRAME_OVERHEAD_BYTES = 8
COMM_LOG_PATTERN = re.compile(r" - apollo\.communication - [A-Z]+ - (\{.*\})$")


def _load_report(report_path: Path) -> dict:
    return json.loads(report_path.read_text(encoding="utf-8"))


def _iter_reports(records_root: Path) -> list[Path]:
    return sorted(records_root.glob("*/data_quality_report.json"))


def _summarize_report(report_path: Path) -> dict:
    data = _load_report(report_path)
    duration = float(data.get("duration") or 0.0)
    func_stats = data.get("func_stats") or []
    total_packets = sum(int(item.get("packet_count") or 0) for item in func_stats)
    total_bytes = int(data.get("total_bytes") or 0)
    return {
        "session": report_path.parent.name,
        "duration": duration,
        "storage_total_bytes": total_bytes,
        "storage_Bps": (total_bytes / duration) if duration else 0.0,
        "storage_kbps": (total_bytes * 8 / duration / 1000.0) if duration else 0.0,
        "total_packets": total_packets,
        "func_stats": func_stats,
    }


def _parse_comm_log(session_dir: Path) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    comm_log = session_dir / "records" / "communication" / "backend_communication.log"
    uplink: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "bytes": 0})
    downlink: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "bytes": 0})

    if not comm_log.exists():
        return uplink, downlink

    for line in comm_log.read_text(encoding="utf-8").splitlines():
        match = COMM_LOG_PATTERN.search(line)
        if not match:
            continue
        payload = json.loads(match.group(1))
        event = payload.get("event")

        if event == "downlink_packet_received":
            msg_type = str(payload.get("msg_type") or "unknown")
            downlink[msg_type]["count"] += 1
            downlink[msg_type]["bytes"] += int(payload.get("bytes") or 0)
        elif event == "uplink_command_sent":
            command_type = str(payload.get("command_type") or "unknown")
            repeat_count = int(payload.get("repeat_count") or 1)
            packet_bytes = int(payload.get("bytes") or 0)
            uplink[command_type]["count"] += repeat_count
            uplink[command_type]["bytes"] += packet_bytes * repeat_count
        elif event == "uplink_heartbeat_sent":
            uplink["heartbeat"]["count"] += 1
            uplink["heartbeat"]["bytes"] += int(payload.get("bytes") or 0)

    return uplink, downlink


def _format_rate(byte_count: int, packet_count: int, duration: float) -> dict:
    if duration <= 0:
        return {"pps": 0.0, "payload_kbps": 0.0, "frame_kbps": 0.0, "avg_payload_bytes": 0.0}
    return {
        "pps": packet_count / duration,
        "payload_kbps": byte_count * 8 / duration / 1000.0,
        "frame_kbps": (byte_count + packet_count * FRAME_OVERHEAD_BYTES) * 8 / duration / 1000.0,
        "avg_payload_bytes": (byte_count / packet_count) if packet_count else 0.0,
    }


def _print_latest_session(records_root: Path) -> int:
    report_paths = _iter_reports(records_root)
    if not report_paths:
        print("No data_quality_report.json files found.")
        return 1

    latest_report = report_paths[-1]
    summary = _summarize_report(latest_report)
    uplink, downlink = _parse_comm_log(latest_report.parent)
    duration = summary["duration"]

    print(f"LATEST_SESSION {summary['session']}")
    print(json.dumps({
        "duration_s": round(duration, 3),
        "storage_total_bytes": summary["storage_total_bytes"],
        "storage_Bps": round(summary["storage_Bps"], 3),
        "storage_kbps": round(summary["storage_kbps"], 3),
        "total_packets": summary["total_packets"],
    }, ensure_ascii=False))

    print("WIRE_DOWNLINK")
    total_payload = 0
    total_packets = 0
    for msg_type in sorted(downlink):
        info = downlink[msg_type]
        total_payload += info["bytes"]
        total_packets += info["count"]
        rates = _format_rate(info["bytes"], info["count"], duration)
        print(json.dumps({
            "msg_type": msg_type,
            "pps": round(rates["pps"], 3),
            "avg_payload_bytes": round(rates["avg_payload_bytes"], 2),
            "payload_kbps": round(rates["payload_kbps"], 3),
            "frame_kbps": round(rates["frame_kbps"], 3),
        }, ensure_ascii=False))

    total_rates = _format_rate(total_payload, total_packets, duration)
    print("WIRE_DOWNLINK_TOTAL")
    print(json.dumps({
        "packets": total_packets,
        "payload_bytes_total": total_payload,
        "payload_kbps": round(total_rates["payload_kbps"], 3),
        "frame_kbps": round(total_rates["frame_kbps"], 3),
        "frame_overhead_pct": round(
            (total_packets * FRAME_OVERHEAD_BYTES) / (total_payload + total_packets * FRAME_OVERHEAD_BYTES) * 100,
            3,
        ) if (total_payload + total_packets * FRAME_OVERHEAD_BYTES) else 0.0,
    }, ensure_ascii=False))

    print("WIRE_UPLINK")
    for command_type in sorted(uplink):
        info = uplink[command_type]
        rates = _format_rate(info["bytes"], info["count"], duration)
        print(json.dumps({
            "type": command_type,
            "pps": round(rates["pps"], 3),
            "avg_payload_bytes": round(rates["avg_payload_bytes"], 2),
            "payload_kbps": round(rates["payload_kbps"], 3),
            "frame_kbps": round(rates["frame_kbps"], 3),
        }, ensure_ascii=False))

    print("STORAGE_FUNC_STATS")
    for item in summary["func_stats"]:
        count = int(item.get("packet_count") or 0)
        total = int(item.get("total_bytes") or 0)
        rates = _format_rate(total, count, duration)
        print(json.dumps({
            "func": item.get("func_code"),
            "msg_type": item.get("last_msg_type"),
            "avg_storage_bytes": round(float(item.get("avg_bytes") or 0.0), 2),
            "pps": round(rates["pps"], 3),
            "storage_kbps": round(rates["payload_kbps"], 3),
        }, ensure_ascii=False))

    return 0


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        records_root = Path(argv[1])
    else:
        records_root = Path(__file__).resolve().parents[2] / "Log" / "Records"
    return _print_latest_session(records_root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))