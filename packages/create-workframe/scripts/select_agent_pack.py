#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / 'shared' / 'WORKFRAME_AGENT_PACKS.json'

def main():
    ap = argparse.ArgumentParser(description='Print profiles for a Workframe starter pack')
    ap.add_argument('pack', nargs='?', help='Pack name (vanilla/core/product/engineering/full)')
    ap.add_argument('--list', action='store_true', help='List packs')
    ap.add_argument('--file', default=str(DEFAULT), help='Path to WORKFRAME_AGENT_PACKS.json')
    args = ap.parse_args()

    data = json.loads(Path(args.file).read_text())
    packs = data.get('packs', {})

    if args.list or not args.pack:
        for name, info in packs.items():
            print(f"{name}: {info.get('description','')}")
        return

    pack = packs.get(args.pack)
    if not pack:
        raise SystemExit(f"Unknown pack: {args.pack}. Use --list")

    for p in pack.get('profiles', []):
        print(p)

if __name__ == '__main__':
    main()
