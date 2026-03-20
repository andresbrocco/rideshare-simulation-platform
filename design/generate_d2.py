"""Generate D2 shared style classes from design tokens."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design" / "tokens.json"
D2_DIR = ROOT / "docs" / "diagrams" / "src"


def generate(variant: str) -> None:
    tokens = json.loads(TOKENS.read_text())
    key = "dark_classes" if variant == "dark" else "classes"
    classes = tokens["diagram"][key]
    suffix = "-dark" if variant == "dark" else ""
    output = D2_DIR / f"_shared{suffix}.d2"

    lines = [
        f"# Auto-generated from design/tokens.json ({variant}) — do not edit by hand",
        "",
    ]
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

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))
    print(f"Wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate D2 shared styles")
    parser.add_argument(
        "--variant",
        choices=["light", "dark", "all"],
        default="all",
        help="Which variant to generate (default: all)",
    )
    args = parser.parse_args()

    if args.variant == "all":
        generate("light")
        generate("dark")
    else:
        generate(args.variant)


if __name__ == "__main__":
    main()
