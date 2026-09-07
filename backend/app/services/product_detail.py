def parse_benefits(benefits_raw: str | None) -> list[dict]:
    """Parses the real 'icon|title|description' newline-delimited format
    from the CSV export into structured entries. Returns [] if empty/malformed
    rather than guessing at missing pieces."""
    if not benefits_raw:
        return []

    entries = []
    for line in benefits_raw.split("\n"):
        parts = line.split("|")
        if len(parts) >= 3:
            entries.append({"icon": parts[0].strip(), "title": parts[1].strip(), "description": parts[2].strip()})
    return entries