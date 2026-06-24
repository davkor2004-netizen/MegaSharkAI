"""Одноразовый скрипт миграции fetch+localStorage -> apiFetch."""
import re
import pathlib

root = pathlib.Path(__file__).resolve().parents[1] / "src"

for path in root.rglob("*.svelte"):
    text = path.read_text(encoding="utf-8")
    original = text

    if "access_token" not in text and "await fetch(" not in text:
        continue

    if "apiFetch" not in text and ("await fetch(" in text or "access_token" in text):
        text = text.replace(
            '<script lang="ts">',
            '<script lang="ts">\n  import { apiFetch } from \'$lib/utils/api\';',
            1,
        )

    text = text.replace("await fetch(", "await apiFetch(")
    text = re.sub(r"\n\s*const token = localStorage\.getItem\('access_token'\);", "", text)
    text = re.sub(r"\n\s*if \(!token\) return;", "", text)
    text = re.sub(r"\n\s*headers\['Authorization'\] = `Bearer \$\{token\}`;", "", text)
    text = re.sub(r"\n\s*Authorization: `Bearer \$\{token\}`,?", "", text)
    text = re.sub(r"\n\s*'Authorization': `Bearer \$\{token\}`,?", "", text)
    text = re.sub(
        r"localStorage\.removeItem\('access_token'\);\s*\n\s*localStorage\.removeItem\('refresh_token'\);\s*\n\s*localStorage\.removeItem\('token_type'\);\s*\n",
        "",
        text,
    )
    text = re.sub(r"localStorage\.setItem\('access_token',[^;]+;\s*\n", "", text)

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"updated {path}")
