"""
Profile distance metric for filesystem profile novelty checking.

Computes multi-dimensional Jaccard distance between two filesystem profiles
across OS family, services, lure files, users, and ports.
"""


def _jaccard_distance(set_a: set, set_b: set) -> float:
    """Jaccard distance: 1 - |A & B| / |A | B|. Returns 1.0 if both empty."""
    if not set_a and not set_b:
        return 0.0
    return 1.0 - len(set_a & set_b) / len(set_a | set_b)


def profile_distance(profile_a: dict, profile_b: dict) -> float:
    """
    Compute distance between two filesystem profiles.

    Returns 0.0 (identical) to 1.0 (completely different).
    Uses a weighted average of 5 dimensions:
      - OS family (binary)
      - Service set (Jaccard)
      - Lure file paths (Jaccard)
      - Non-root users (Jaccard)
      - Listening ports (Jaccard)
    """
    scores = []

    # 1. OS family distance (binary: same distro family or not)
    os_a = profile_a.get("system", {}).get("os", "").split()[0].lower()
    os_b = profile_b.get("system", {}).get("os", "").split()[0].lower()
    scores.append(0.0 if os_a == os_b else 1.0)

    # 2. Service set Jaccard distance
    svc_a = {s["name"] for s in profile_a.get("services", [])}
    svc_b = {s["name"] for s in profile_b.get("services", [])}
    if svc_a or svc_b:
        scores.append(_jaccard_distance(svc_a, svc_b))

    # 3. Lure file path Jaccard distance
    files_a = set(profile_a.get("file_contents", {}).keys())
    files_b = set(profile_b.get("file_contents", {}).keys())
    if files_a or files_b:
        scores.append(_jaccard_distance(files_a, files_b))

    # 4. Non-root user set distance
    users_a = {u["name"] for u in profile_a.get("users", []) if u["name"] != "root"}
    users_b = {u["name"] for u in profile_b.get("users", []) if u["name"] != "root"}
    if users_a or users_b:
        scores.append(_jaccard_distance(users_a, users_b))

    # 5. Port set Jaccard distance
    ports_a = {p for s in profile_a.get("services", []) for p in s.get("ports", [])}
    ports_b = {p for s in profile_b.get("services", []) for p in s.get("ports", [])}
    if ports_a or ports_b:
        scores.append(_jaccard_distance(ports_a, ports_b))

    return sum(scores) / len(scores) if scores else 0.0


def is_novel(
    new_profile: dict,
    previous_profiles: list[dict],
    threshold: float = 0.4,
) -> bool:
    """
    Check if a new profile is sufficiently different from all previous ones.

    Returns True if the minimum distance to any previous profile is >= threshold.
    Returns True if there are no previous profiles.
    """
    if not previous_profiles:
        return True
    for prev in previous_profiles:
        if profile_distance(new_profile, prev) < threshold:
            return False
    return True
