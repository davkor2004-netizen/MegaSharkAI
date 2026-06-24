"""Удалить остатки Bearer/token из svelte после миграции на cookies."""
import re
import pathlib

root = pathlib.Path(__file__).resolve().parents[1] / "src"

patterns = [
    (r"\n\s*headers: \{ Authorization: `Bearer \$\{token\}` \}", ""),
    (r"\n\s*const token = getTokenOrThrow\(\);", ""),
    (r"\n\s*function getTokenOrThrow\(\): string \{[^}]+\}", ""),
    (r"\n\s*function getAuthHeaders\([^)]*\): Record<string, string> \{[^}]+\}", ""),
]

for path in root.rglob("*.svelte"):
    text = path.read_text(encoding="utf-8")
    original = text
    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text, flags=re.DOTALL)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print("cleaned", path)
