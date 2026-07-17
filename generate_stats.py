#!/usr/bin/env python3
"""Kyros SMP stats generator.

Liest die Vanilla-Statistikdateien der Welt und erzeugt das stats.json,
das die Webseite laedt (Totals + pro Spieler).

Verwendung:
  python3 generate_stats.py <weltordner> [ausgabedatei]

Beispiel:
  python3 generate_stats.py /pfad/zum/server/world stats.json

Danach stats.json ins GitHub-Repo PantriMasi/smp-stats pushen
(oder direkt per Cronjob/GitHub Action laufen lassen).

Benoetigt: usercache.json im Serverordner (eine Ebene ueber der Welt),
damit UUIDs zu Namen aufgeloest werden koennen.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Distance stat keys (cm)
DISTANCE_KEYS = [
    "minecraft:walk_one_cm",
    "minecraft:sprint_one_cm",
    "minecraft:crouch_one_cm",
]


def load_usercache(server_dir):
    """UUID -> Name Mapping laden."""
    cache_file = server_dir / "usercache.json"
    mapping = {}
    if cache_file.exists():
        for entry in json.loads(cache_file.read_text(encoding="utf-8")):
            mapping[entry["uuid"].lower()] = entry["name"]
    return mapping


def sum_category(stats, category):
    """Summe einer ganzen Kategorie."""
    return sum(stats.get(category, {}).values())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    world_dir = Path(sys.argv[1])
    out_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("stats.json")
    stats_dir = world_dir / "stats"
    if not stats_dir.is_dir():
        print(f"Fehler: {stats_dir} nicht gefunden.")
        sys.exit(1)

    names = load_usercache(world_dir.parent)
    players = []

    for stats_file in sorted(stats_dir.glob("*.json")):
        uuid = stats_file.stem.lower()
        name = names.get(uuid)
        if not name:
            # Unknown UUID, skip
            continue

        data = json.loads(stats_file.read_text(encoding="utf-8"))
        stats = data.get("stats", {})
        custom = stats.get("minecraft:custom", {})

        players.append({
            "name": name,
            "playTimeTicks": custom.get("minecraft:play_time",
                             custom.get("minecraft:play_one_minute", 0)),
            "deaths": custom.get("minecraft:deaths", 0),
            "mobKills": custom.get("minecraft:mob_kills", 0),
            "playerKills": custom.get("minecraft:player_kills", 0),
            "blocksMined": sum_category(stats, "minecraft:mined"),
            "distanceCm": sum(custom.get(k, 0) for k in DISTANCE_KEYS),
        })

    players.sort(key=lambda p: p["playTimeTicks"], reverse=True)

    totals = {
        "playTimeTicks": sum(p["playTimeTicks"] for p in players),
        "deaths": sum(p["deaths"] for p in players),
        "mobKills": sum(p["mobKills"] for p in players),
        "blocksMined": sum(p["blocksMined"] for p in players),
        "distanceCm": sum(p["distanceCm"] for p in players),
    }

    result = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "players": players,
        # Legacy field, kept for compatibility
        "topPlaytime": players[:10],
    }

    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(players)} Spieler -> {out_file}")


if __name__ == "__main__":
    main()
