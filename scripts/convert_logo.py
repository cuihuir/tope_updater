#!/usr/bin/env python3
"""
SVG to PNG converter for GUI logo
Generates multiple resolutions for different screen sizes
"""

from pathlib import Path


def convert_svg_to_png_with_cairosvg(svg_path: Path, output_dir: Path):
    """Convert SVG to multiple PNG sizes using cairosvg"""
    try:
        import cairosvg
    except ImportError:
        print("Error: cairosvg not installed")
        print("Install with: pip install cairosvg")
        return False

    sizes = {
        "logo_80.png": 80,    # 1024x600
        "logo_100.png": 100,  # 1920x440, 1280x800
        "logo_120.png": 120,  # 1920x1080
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, size in sizes.items():
        output_path = output_dir / filename

        print(f"Converting {svg_path.name} -> {filename} ({size}x{size})")

        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(output_path),
            output_width=size,
            output_height=size,
        )

        print(f"  ✓ Generated: {output_path}")

    return True


if __name__ == "__main__":
    svg_file = Path("specs/002-gui/tope_logo.svg")
    output_dir = Path("src/updater/gui/assets")

    if not svg_file.exists():
        print(f"Error: {svg_file} not found")
        exit(1)

    if convert_svg_to_png_with_cairosvg(svg_file, output_dir):
        print("\n✓ All logos generated successfully")
    else:
        exit(1)
