#!/usr/bin/env python3
"""Проверка обращений к локализации без компилятора.

Swift собирается только на macOS, поэтому до Mac единственное, что можно
проверить в текстах, — существование ключей и совпадение числа подстановок.
Скрипт разбирает вызовы L("key", ...) со счётом скобок, а не регулярным
выражением: иначе тернарный оператор и вложенные вызовы дают ложные срабатывания.

Запуск из папки ios:
    python3 check_l10n.py
"""
import pathlib
import re
import sys


def calls(src: str):
    """Находит вызовы L(...) и возвращает (ключ, число аргументов верхнего уровня)."""
    for match in re.finditer(r'\bL\("([a-z0-9_]+)"', src):
        key = match.group(1)
        i = src.index('(', match.start())
        depth, args, j = 0, 0, i
        while j < len(src):
            ch = src[j]
            if ch in "([": depth += 1
            elif ch in ")]":
                depth -= 1
                if depth == 0:
                    break
            elif ch == "," and depth == 1:
                args += 1
            j += 1
        yield key, args


def main(root: pathlib.Path, lproj: str) -> int:
    strings_path = root / "Resources" / lproj / "Localizable.strings"
    strings = strings_path.read_text(encoding="utf-8")

    have, placeholders = set(), {}
    for line in strings.splitlines():
        m = re.match(r'^"([a-z0-9_]+)" = "(.*)";$', line)
        if m:
            have.add(m.group(1))
            placeholders[m.group(1)] = len(re.findall(r"%(?:\d+\$)?[@d]", m.group(2)))

    missing, mismatched, used = [], [], set()
    for path in sorted(root.rglob("*.swift")):
        src = path.read_text(encoding="utf-8")
        for key, args in calls(src):
            used.add(key)
            if key not in have:
                missing.append(f"{path.name}: {key}")
            elif placeholders[key] != args:
                mismatched.append(
                    f"{path.name}: {key} — формат ждёт {placeholders[key]}, передано {args}")

    print(f"ключей в коде: {len(used)}, в {lproj}: {len(have)}")
    print("отсутствующие ключи:", missing or "нет")
    print("несовпадение подстановок:", mismatched or "нет")
    return 1 if missing or mismatched else 0


if __name__ == "__main__":
    here = pathlib.Path(__file__).parent
    target = next(p for p in here.iterdir() if p.is_dir() and (p / "Resources").exists())
    sys.exit(main(target, sys.argv[1] if len(sys.argv) > 1 else "ru.lproj"))
