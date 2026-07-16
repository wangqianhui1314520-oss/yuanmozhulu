"""Fix frame HTML structure for hyperframes lint compliance."""
import re
import os

FRAMES_DIR = r"d:\AI\元末逐鹿\videos\yuanmo-promo\compositions\frames"

for fname in os.listdir(FRAMES_DIR):
    if not fname.endswith(".html"):
        continue
    fpath = os.path.join(FRAMES_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract composition id from template tag
    m = re.search(r'<template data-composition-id="([^"]+)"', content)
    if not m:
        print(f"SKIP {fname}: no data-composition-id on template")
        continue
    comp_id = m.group(1)

    # Replace <template data-composition-id="XX"> with <template>
    # and add root div with comp-id + root id + dimensions
    content = re.sub(
        r'<template data-composition-id="[^"]+"[^>]*>',
        f'<template>\n<div id="root" data-composition-id="{comp_id}" data-width="1920" data-height="1080">',
        content,
    )

    # Replace closing </template> with </div>\n</template>
    content = content.replace("</template>", "</div>\n</template>")

    # Fix #root → #root in CSS (stays same since we added id="root")
    # No change needed for CSS selectors

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"FIXED {fname} ({comp_id})")

print("Done!")
