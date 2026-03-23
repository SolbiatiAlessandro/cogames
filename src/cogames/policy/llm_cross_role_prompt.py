from __future__ import annotations


CROSS_ROLE_SKILL_DESCRIPTIONS = {
    "gear_up_miner": "Route to the miner station and acquire miner gear (needed for mining resources).",
    "gear_up_aligner": "Route to the aligner station and acquire aligner gear (needed for aligning junctions).",
    "mine_resources": "Mine resources at nearby extractors until cargo is full.",
    "deposit_resources": "Route to the hub and deposit all carried resources.",
    "get_heart": "Route to the hub and obtain a heart (needed to align a junction).",
    "align_junction": "Route to a known neutral or enemy junction and align it to our team.",
    "explore": "Move toward unexplored frontier to discover junctions, extractors, and routes.",
    "unstuck": "Try a short escape pattern to recover from repeated blocked moves.",
}


def build_cross_role_prompt(
    *,
    current_gear: str,
    has_heart: bool,
    carried_resources: int,
    return_load: int,
    known_neutral_junctions: int,
    known_friendly_junctions: int,
    known_enemy_junctions: int,
    known_extractors: int,
    team_aligners: int,
    team_miners: int,
    total_agents: int,
    hub_known: bool,
    current_skill: str | None,
    no_move_steps: int,
    recent_events: list[str],
) -> str:
    skills = "\n".join(f"- {name}: {desc}" for name, desc in CROSS_ROLE_SKILL_DESCRIPTIONS.items())
    events = "\n".join(f"- {event}" for event in recent_events[-6:]) or "- none"
    alignable = known_neutral_junctions + known_enemy_junctions

    # Build team-need analysis hint
    need_hints: list[str] = []
    if team_aligners == 0 and alignable > 0:
        need_hints.append("URGENT: no aligners active — team needs aligners to capture junctions")
    elif team_aligners < min(3, alignable) and current_gear != "aligner":
        need_hints.append(f"Team only has {team_aligners} aligner(s) but {alignable} capturable junctions — consider switching to aligner")
    if team_miners == 0 and known_extractors > 0:
        need_hints.append("No miners active — hub needs resources to craft hearts")
    if known_friendly_junctions >= alignable and alignable == 0 and current_gear == "miner":
        need_hints.append("All known junctions aligned — consider exploring or aligning enemy junctions")
    team_need_str = " | ".join(need_hints) if need_hints else "balanced — choose what benefits the team most"

    return (
        "You control one cog in CoGames. Your goal is to maximize aligned_junction_held for your team.\n"
        "You can switch between miner role (gather resources for heart crafting) and aligner role (capture junctions).\n"
        "Choose exactly one next skill from the available skills.\n"
        "Valid skill names are exactly: gear_up_miner, gear_up_aligner, mine_resources, deposit_resources, get_heart, align_junction, explore, unstuck.\n"
        "Preconditions:\n"
        "- To mine_resources or deposit_resources you need miner gear (current_gear=miner).\n"
        "- To align_junction you need aligner gear AND a heart.\n"
        "- To get_heart you need aligner gear and a known hub.\n"
        "- If carried_resources >= return_load, prefer deposit_resources.\n"
        "- If current_gear=aligner and has_heart and alignable junctions exist, prefer align_junction.\n"
        "- If current_gear=aligner and not has_heart and hub_known, prefer get_heart.\n"
        "Role switching: You can switch roles by choosing gear_up_aligner or gear_up_miner.\n"
        "Switching loses your current gear — only switch if the team clearly needs it.\n"
        "Respond as JSON like {\"skill\": \"mine_resources\", \"reason\": \"...\"}.\n\n"
        f"Available skills:\n{skills}\n\n"
        f"Agent state:\n"
        f"- current_gear: {current_gear}\n"
        f"- has_heart: {has_heart}\n"
        f"- carried_resources: {carried_resources} (return_load={return_load})\n"
        f"- hub_known: {hub_known}\n"
        f"- known_neutral_junctions: {known_neutral_junctions}\n"
        f"- known_friendly_junctions: {known_friendly_junctions}\n"
        f"- known_enemy_junctions: {known_enemy_junctions}\n"
        f"- known_extractors: {known_extractors}\n"
        f"- current_skill: {current_skill or 'none'}\n"
        f"- no_move_steps: {no_move_steps}\n\n"
        f"Team state ({total_agents} agents total):\n"
        f"- team_aligners: {team_aligners}\n"
        f"- team_miners: {team_miners}\n"
        f"- team_need: {team_need_str}\n\n"
        f"Recent events:\n{events}\n"
    )
