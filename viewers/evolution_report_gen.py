"""Report generation for the world evolution test.

Takes snapshot data, change comparisons, and event logs and produces
a Markdown report analyzing what systems are dynamic vs static.
"""

from game.settings import (
    GRASS, FOREST, DENSE_FOREST, FARMLAND, WHEAT_FIELD, ROAD, WATER,
    SAND, MOUNTAIN, SNOW, SWAMP, TILLED_SOIL, TREE_STUMP,
)

# Tile names for reporting
TILE_NAMES = {
    GRASS: "Grass", FOREST: "Forest", DENSE_FOREST: "Dense Forest",
    FARMLAND: "Farmland", WHEAT_FIELD: "Wheat Field", ROAD: "Road",
    WATER: "Water", SAND: "Sand", MOUNTAIN: "Mountain", SNOW: "Snow",
    SWAMP: "Swamp", TILLED_SOIL: "Tilled Soil", TREE_STUMP: "Tree Stump",
}


def _write_baseline(lines, base):
    """Write the baseline section of the report."""
    lines.append("## Baseline (Tick 0)")
    lines.append("")
    lines.append(f"- **Game time:** {base['time_str']}, Day {base['day']}, {base['season']}")
    lines.append(f"- **NPCs alive:** {base['npc_alive']} / {base['npc_total']}")
    lines.append(f"- **Creatures:** {base['creature_count']}")
    lines.append(f"- **Settlements:** {len(base['settlements'])}")
    lines.append(f"- **Kingdoms:** {len(base['kingdoms'])}")
    lines.append(f"- **Ground items:** {base['ground_items']}")
    lines.append("")

    lines.append("### NPC Job Distribution (Baseline)")
    lines.append("| Job | Count |")
    lines.append("|-----|-------|")
    for job, count in sorted(base["job_distribution"].items(),
                             key=lambda x: -x[1]):
        lines.append(f"| {job} | {count} |")
    lines.append("")

    lines.append("### Creature Species (Baseline)")
    lines.append("| Species | Count |")
    lines.append("|---------|-------|")
    for sp, count in sorted(base["creature_species"].items(),
                            key=lambda x: -x[1])[:20]:
        lines.append(f"| {sp} | {count} |")
    lines.append("")

    lines.append("### Settlements (Baseline)")
    lines.append("| Settlement | Type | Buildings |")
    lines.append("|-----------|------|-----------|")
    for sname, sdata in sorted(base["settlements"].items()):
        lines.append(f"| {sname} | {sdata['kind']} | {sdata['buildings']} |")
    lines.append("")

    lines.append("### Kingdoms (Baseline)")
    lines.append("| Kingdom | Treasury | Army | Morale |")
    lines.append("|---------|----------|------|--------|")
    for kname, kdata in sorted(base["kingdoms"].items()):
        lines.append(f"| {kname} | {kdata['treasury']} | "
                     f"{kdata['army_size']} | {kdata['public_morale']} |")
    lines.append("")

    lines.append("### Terrain Sample (100x100 around city)")
    lines.append("| Terrain | Tiles |")
    lines.append("|---------|-------|")
    for tile_id, count in sorted(base["terrain_counts"].items(),
                                 key=lambda x: -x[1]):
        name = TILE_NAMES.get(tile_id, f"Type_{tile_id}")
        lines.append(f"| {name} | {count} |")
    lines.append("")


def _write_timeline(lines, all_changes):
    """Write the timeline section of the report."""
    lines.append("## Timeline of Changes")
    lines.append("")

    for ch in all_changes:
        lines.append(f"### Tick {ch['tick']} — Day {ch['day']}, {ch['season']}")
        lines.append("")

        if ch["npcs_died"]:
            lines.append(f"- **NPCs died:** {', '.join(ch['npcs_died'])}")
        if ch["npcs_born"]:
            lines.append(f"- **NPCs born/appeared:** {', '.join(ch['npcs_born'])}")
        lines.append(f"- **NPCs moved:** {ch['npcs_moved']}")
        if ch["npc_gold_delta"] != 0:
            lines.append(f"- **NPC total gold change:** {ch['npc_gold_delta']:+d}")

        if ch["job_changes"]:
            parts = [f"{j}: {d:+d}" for j, d in ch["job_changes"].items()]
            lines.append(f"- **Job distribution changes:** {', '.join(parts)}")

        if ch["creature_delta"] != 0:
            lines.append(f"- **Creature population change:** {ch['creature_delta']:+d}")
        if ch["species_changes"]:
            parts = [f"{sp}: {d:+d}" for sp, d in sorted(
                ch["species_changes"].items(), key=lambda x: abs(x[1]),
                reverse=True)[:10]]
            lines.append(f"- **Species changes:** {', '.join(parts)}")

        if ch["building_changes"]:
            parts = [f"{s}: {d:+d}" for s, d in ch["building_changes"].items()]
            lines.append(f"- **Building changes:** {', '.join(parts)}")

        if ch["treasury_changes"]:
            parts = [f"{k}: {d:+.0f}" for k, d in ch["treasury_changes"].items()]
            lines.append(f"- **Treasury changes:** {', '.join(parts)}")

        if ch["terrain_changes"]:
            parts = []
            for tile_id, delta in ch["terrain_changes"].items():
                name = TILE_NAMES.get(tile_id, f"Type_{tile_id}")
                parts.append(f"{name}: {delta:+d}")
            lines.append(f"- **Terrain changes:** {', '.join(parts)}")

        lines.append(f"- **Active caravans:** {ch['active_caravans']}")
        lines.append(f"- **Active events:** {ch['active_events']}")
        lines.append(f"- **Event log entries this period:** {ch['event_log_growth']}")
        lines.append(f"- **Construction projects:** {ch['construction_projects']}")
        lines.append(f"- **Vegetation tiles tracked:** {ch['vegetation_tracked']}")
        lines.append(f"- **Vegetation degraded tiles:** {ch['vegetation_degraded']}")
        if ch["ground_items_delta"] != 0:
            lines.append(f"- **Ground items change:** {ch['ground_items_delta']:+d}")
        lines.append("")


def _write_analysis(lines, all_changes):
    """Write the dynamic vs static analysis section."""
    lines.append("## Analysis: Dynamic vs Static Systems")
    lines.append("")

    total_died = sum(len(ch["npcs_died"]) for ch in all_changes)
    total_born = sum(len(ch["npcs_born"]) for ch in all_changes)
    total_moved = sum(ch["npcs_moved"] for ch in all_changes)
    total_creature_delta = sum(ch["creature_delta"] for ch in all_changes)
    total_building_changes = sum(
        sum(abs(v) for v in ch["building_changes"].values())
        for ch in all_changes)
    total_treasury_changes = sum(
        1 for ch in all_changes if ch["treasury_changes"])
    total_terrain_changes = sum(
        sum(abs(v) for v in ch["terrain_changes"].values())
        for ch in all_changes)
    total_events = sum(ch["event_log_growth"] for ch in all_changes)
    any_caravans = any(ch["active_caravans"] > 0 for ch in all_changes)
    any_construction = any(ch["construction_projects"] > 0 for ch in all_changes)
    any_species_change = any(ch["species_changes"] for ch in all_changes)
    gold_deltas = [ch["npc_gold_delta"] for ch in all_changes
                   if ch["npc_gold_delta"] != 0]
    job_change_intervals = [ch for ch in all_changes if ch["job_changes"]]

    lines.append("### Systems Producing Changes (DYNAMIC)")
    lines.append("")
    dynamic = []
    if total_moved > 0:
        dynamic.append(f"- **NPC Movement:** {total_moved} NPCs moved across "
                       f"{len(all_changes)} intervals")
    if total_died > 0:
        dynamic.append(f"- **NPC Death:** {total_died} NPCs died")
    if total_born > 0:
        dynamic.append(f"- **NPC Birth/Spawn:** {total_born} new NPCs appeared")
    if total_events > 0:
        dynamic.append(f"- **Event System:** {total_events} event log entries")
    if total_treasury_changes > 0:
        dynamic.append(f"- **Kingdom Economy:** Treasury changed in "
                       f"{total_treasury_changes} intervals")
    if total_terrain_changes > 0:
        dynamic.append(f"- **Terrain Changes:** {total_terrain_changes} tile changes")
    if total_building_changes > 0:
        dynamic.append(f"- **Construction:** {total_building_changes} building changes")
    if any_caravans:
        dynamic.append("- **Trade Caravans:** Active caravans observed")
    if any_construction:
        dynamic.append("- **Construction Projects:** Active projects observed")
    if any_species_change:
        dynamic.append("- **Creature Ecology:** Species populations shifted")
    if total_creature_delta != 0:
        dynamic.append(f"- **Creature Population:** Net change of "
                       f"{total_creature_delta:+d}")
    if gold_deltas:
        dynamic.append(f"- **NPC Gold Economy:** Gold changed in "
                       f"{len(gold_deltas)} intervals")
    if job_change_intervals:
        dynamic.append(f"- **Career Changes:** Job distribution changed in "
                       f"{len(job_change_intervals)} intervals")

    if not dynamic:
        lines.append("- *No dynamic changes detected!*")
    else:
        lines.extend(dynamic)
    lines.append("")

    lines.append("### Systems NOT Producing Changes (STATIC)")
    lines.append("")
    static = []
    if total_moved == 0:
        static.append("- **NPC Movement:** No NPCs moved at all")
    if total_died == 0:
        static.append("- **NPC Death:** No NPCs died")
    if total_born == 0:
        static.append("- **NPC Birth/Spawn:** No new NPCs appeared")
    if total_events == 0:
        static.append("- **Event System:** No events generated")
    if total_treasury_changes == 0:
        static.append("- **Kingdom Economy:** No treasury changes")
    if total_terrain_changes == 0:
        static.append("- **Terrain Changes:** No tile type changes")
    if total_building_changes == 0:
        static.append("- **Construction:** No buildings constructed or destroyed")
    if not any_caravans:
        static.append("- **Trade Caravans:** No active caravans observed")
    if not any_construction:
        static.append("- **Construction Projects:** No active projects")
    if not any_species_change:
        static.append("- **Creature Ecology:** No species population changes")
    if total_creature_delta == 0:
        static.append("- **Creature Population:** No net change")
    if not gold_deltas:
        static.append("- **NPC Gold Economy:** No gold changes")
    if not job_change_intervals:
        static.append("- **Career Changes:** No job distribution changes")

    if not static:
        lines.append("- *All measured systems are dynamic!*")
    else:
        lines.extend(static)
    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if total_terrain_changes == 0:
        lines.append("- **Terrain system needs work:** No tile changes observed. "
                      "Farming, logging, construction should change tile types.")
    if total_building_changes == 0:
        lines.append("- **Construction system needs activation:** No buildings "
                      "built or destroyed. Need NPC-driven construction triggers.")
    if not any_caravans:
        lines.append("- **Trade routes need activation:** No caravans observed. "
                      "Need to trigger inter-settlement trade.")
    if total_died == 0 and total_born == 0:
        lines.append("- **Population dynamics need work:** No births or deaths. "
                      "The world population is frozen.")
    if total_creature_delta == 0 and not any_species_change:
        lines.append("- **Creature ecology is static:** No population changes. "
                      "Breeding, predation, death should create fluctuations.")
    if total_moved == 0:
        lines.append("- **NPC movement is frozen:** NPCs aren't moving.")
    lines.append("")


def generate_report(snapshots, all_changes, all_events, timing, output_path):
    """Generate the evolution_report.md file."""
    lines = []
    lines.append("# World Evolution Test Report")
    lines.append("")
    lines.append(f"**Seed:** 42")
    lines.append(f"**Total ticks:** {timing['total_ticks']}")
    lines.append(f"**Wall-clock time:** {timing['wall_time']:.1f} seconds")
    lines.append(f"**Ticks per second:** {timing['tps']:.1f}")
    lines.append("")

    _write_baseline(lines, snapshots[0])
    _write_timeline(lines, all_changes)

    # Final state
    final = snapshots[-1]
    lines.append("## Final State")
    lines.append("")
    lines.append(f"- **Game time:** {final['time_str']}, Day {final['day']}, "
                 f"{final['season']}")
    lines.append(f"- **NPCs alive:** {final['npc_alive']} / {final['npc_total']}")
    lines.append(f"- **Creatures:** {final['creature_count']}")
    lines.append(f"- **Ground items:** {final['ground_items']}")
    lines.append("")

    _write_analysis(lines, all_changes)

    # Event log samples
    lines.append("## Sample Event Log Entries")
    lines.append("")
    all_event_entries = []
    for batch in all_events:
        all_event_entries.extend(batch)
    if all_event_entries:
        seen = set()
        unique = []
        for e in all_event_entries:
            if e not in seen:
                seen.add(e)
                unique.append(e)
        for entry in unique[:50]:
            lines.append(f"- {entry}")
    else:
        lines.append("*No event log entries were generated.*")
    lines.append("")

    # NPC action analysis
    lines.append("## NPC Action Distribution Over Time")
    lines.append("")
    lines.append("| Tick | Top Actions |")
    lines.append("|------|-------------|")
    for ch in all_changes:
        actions = ch.get("npc_actions", {})
        top = sorted(actions.items(), key=lambda x: -x[1])[:5]
        action_str = ", ".join(f"{a}:{c}" for a, c in top)
        lines.append(f"| {ch['tick']} | {action_str} |")
    lines.append("")

    report = "\n".join(lines)
    with open(output_path, "w") as f:
        f.write(report)
    return report
