#!/usr/bin/env python3

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Local cache for resolved names
NAME_CACHE_FILE = Path("uuid-names.json")

# Distance stat keys (cm)
DISTANCE_KEYS = [
    "minecraft:walk_one_cm",
    "minecraft:sprint_one_cm",
    "minecraft:crouch_one_cm",
]

# Minecraft zaehlt gesetzte Bloecke nicht direkt. Die einzige Quelle ist
# minecraft:used, das jede Item-Benutzung zaehlt. Hier fliegen die
# offensichtlichen Nicht-Bloecke raus, damit die Zahl nahe an
# "gesetzte Bloecke" liegt. Eine Naeherung, kein exakter Wert.
NON_BLOCK_SUFFIXES = (
    "_sword", "_pickaxe", "_axe", "_shovel", "_hoe",
    "_helmet", "_chestplate", "_leggings", "_boots",
    "_bucket", "_spawn_egg", "_boat", "_minecart",
    "_horse_armor", "_upgrade_smithing_template",
)

NON_BLOCK_ITEMS = {
    "minecraft:bucket", "minecraft:bow", "minecraft:crossbow", "minecraft:arrow",
    "minecraft:spectral_arrow", "minecraft:tipped_arrow", "minecraft:trident",
    "minecraft:shield", "minecraft:elytra", "minecraft:fishing_rod",
    "minecraft:flint_and_steel", "minecraft:shears", "minecraft:spyglass",
    "minecraft:compass", "minecraft:clock", "minecraft:map", "minecraft:filled_map",
    "minecraft:book", "minecraft:writable_book", "minecraft:written_book",
    "minecraft:potion", "minecraft:splash_potion", "minecraft:lingering_potion",
    "minecraft:experience_bottle", "minecraft:ender_pearl", "minecraft:ender_eye",
    "minecraft:snowball", "minecraft:egg", "minecraft:firework_rocket",
    "minecraft:fire_charge", "minecraft:bone_meal", "minecraft:name_tag",
    "minecraft:lead", "minecraft:saddle", "minecraft:glass_bottle",
    "minecraft:milk_bucket", "minecraft:honey_bottle", "minecraft:goat_horn",
    "minecraft:brush", "minecraft:mace", "minecraft:wind_charge",
}


def is_block_item(item_id):
    """Grobe Unterscheidung Block gegen Werkzeug/Nahrung/Ausruestung."""
    if item_id in NON_BLOCK_ITEMS:
        return False
    if item_id.endswith(NON_BLOCK_SUFFIXES):
        return False
    return True


def count_placed(stats):
    """Naeherung fuer gesetzte Bloecke aus minecraft:used."""
    used = stats.get("minecraft:used", {})
    return sum(count for item, count in used.items() if is_block_item(item))


def load_usercache(server_dir):
    """UUID -> Name Mapping laden."""
    cache_file = server_dir / "usercache.json"
    mapping = {}
    if cache_file.exists():
        for entry in json.loads(cache_file.read_text(encoding="utf-8")):
            mapping[entry["uuid"].lower()] = entry["name"]
    return mapping


def load_name_cache():
    if NAME_CACHE_FILE.exists():
        return json.loads(NAME_CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def resolve_name(uuid, cache):
    """Mojang API lookup for unknown UUIDs."""
    if uuid in cache:
        return cache[uuid]
    url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid.replace('-', '')}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            name = data.get("name")
    except Exception:
        name = None
    cache[uuid] = name
    time.sleep(0.5)  # rate limit
    return name


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
    name_cache = load_name_cache()
    players = []

    for stats_file in sorted(stats_dir.glob("*.json")):
        uuid = stats_file.stem.lower()
        name = names.get(uuid) or resolve_name(uuid, name_cache)
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
            "blocksPlaced": count_placed(stats),
            "distanceCm": sum(custom.get(k, 0) for k in DISTANCE_KEYS),
        })

    # Never overwrite good data with an empty result
    if not players:
        print("Fehler: keine Spieler gefunden, stats.json bleibt unveraendert.")
        sys.exit(1)

    players.sort(key=lambda p: p["playTimeTicks"], reverse=True)

    totals = {
        "playTimeTicks": sum(p["playTimeTicks"] for p in players),
        "deaths": sum(p["deaths"] for p in players),
        "mobKills": sum(p["mobKills"] for p in players),
        "blocksMined": sum(p["blocksMined"] for p in players),
        "blocksPlaced": sum(p["blocksPlaced"] for p in players),
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
    NAME_CACHE_FILE.write_text(json.dumps(name_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(players)} Spieler -> {out_file}")


if __name__ == "__main__":
    main()
