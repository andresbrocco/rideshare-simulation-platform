"""Generate D2 shared style classes from design tokens."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design" / "tokens.json"
OUTPUT = ROOT / "docs" / "diagrams" / "src" / "_shared.d2"


def main() -> None:
    tokens = json.loads(TOKENS.read_text())
    classes = tokens["diagram"]["classes"]

    lines = ["# Auto-generated from design/tokens.json — do not edit by hand", ""]
    lines.append("classes: {")
    for name, spec in classes.items():
        lines.append(f"  {name}: {{")
        lines.append(f'    style.fill: "{spec["fill"]}"')
        lines.append(f'    style.stroke: "{spec["stroke"]}"')
        lines.append("    style.border-radius: 8")
        if name == "ephemeral":
            lines.append("    style.stroke-dash: 5")
        lines.append("  }")
    lines.append("}")
    lines.append("")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
