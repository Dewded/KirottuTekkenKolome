#!/usr/bin/env python3
"""Export a TTT1 fighter's movement data as plain numbers, for DORYA HERO (a browser game on Hemmo's site).

Reads select-screen RAM captures (capture_ttt1_fighters.lua, or the Jun import's Jin capture) and the verified
arcade bank. For every record in the fighter's alias table: the 13 raw record words, its clip's frame count, the
root motion per frame (the first three motion channels: heading, height, distance), the flattened cancel rows, the
hit rows and the reactions they name, plus the input sequences the cancel rows use. Joint rotations (the animation
itself) are deliberately not exported. Run locally: the ROM and captures never leave this PC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

try:
    from .convert_jun_moves import cancel_rows, hit_rows
    from .prepare_jun_import import BANK_SHA, verified
    from .ttt1_motion import decode
    from . import jun_solo_semantics as solo
except ImportError:
    from convert_jun_moves import cancel_rows, hit_rows
    from prepare_jun_import import BANK_SHA, verified
    from ttt1_motion import decode
    import jun_solo_semantics as solo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workspace/dojo-export'
JUN = ROOT / 'workspace/jun-import'
ALIASES, COUNT = 0x2A7350, 5515
DEFAULT = 0x8009374C  # the shared placeholder record unused aliases point at
FIGHTERS = ('kazuya', 'heihachi', 'jin')


def ram_record(address: int) -> bool:
    return 0x80000000 <= address < 0x80400000


def sequence(ram: bytes, cmd: int) -> list[int]:
    """An input sequence's raw words, read as convert_jun_moves.input_pattern does (terminating 0 kept)."""
    start, words = 0x772 + cmd * 2, []
    for k in range(65):
        value = struct.unpack_from('<H', ram, start + k * 2)[0]
        words.append(value)
        if k and not value:
            return words
    raise ValueError(f'Unterminated input sequence {cmd:04x}')


def root_motion(bank: bytes, source: int) -> list[list[int]] | None:
    if not 0 <= source < len(bank) - 0x130 or not bank[source]:
        return None
    try:
        return [decode(bank, source, f, 3) for f in range(bank[source])]
    except (ValueError, struct.error, IndexError):
        return None


def export(ram: bytes, bank: bytes, fighter: str) -> dict:
    aliases = struct.unpack_from(f'<{COUNT}I', ram, ALIASES)
    addresses = sorted({a for a in aliases if ram_record(a)})
    if len(addresses) < 100 or not ram_record(aliases[56]):
        raise ValueError(f'{fighter}: no moveset at the alias table; was a fighter highlighted on the select screen?')
    index = {a: i for i, a in enumerate(addresses)}
    records, sequences, reactions, problems = [], {}, {}, []
    for a in addresses:
        words = list(struct.unpack_from('<13I', ram, a & 0x3FFFFF))
        record = dict(address=a, words=words, frames=None, root=None, cancels=[], hits=[])
        record['root'] = root_motion(bank, words[0])
        if record['root'] is not None:
            record['frames'] = len(record['root'])
        try:
            if ram_record(words[3]):
                record['cancels'] = [list(row) for row in cancel_rows(ram, words[3])]
        except (ValueError, struct.error) as error:
            problems.append(f'{a:08x} cancels: {error}')
        for cmd, *_ in record['cancels']:
            if 0x800F <= cmd < 0xFFFF and cmd not in sequences:
                try:
                    sequences[cmd] = sequence(ram, cmd)
                except (ValueError, struct.error) as error:
                    problems.append(f'{a:08x} sequence {cmd:04x}: {error}')
        try:
            record['hits'] = [list(row) for row in hit_rows(ram, words[5] & 0xFFFF)]
        except (ValueError, struct.error) as error:
            problems.append(f'{a:08x} hits: {error}')
        for row in record['hits']:
            for rx in row[2:4]:
                if rx and rx not in reactions:
                    try:
                        reactions[rx] = list(solo.reaction(ram, rx))
                    except struct.error:
                        problems.append(f'{a:08x} reaction {rx}: outside RAM')
        records.append(record)
    return dict(
        schema=1, fighter=fighter, game='tektagt World TEG2/VER.C1',
        ram_sha256=hashlib.sha256(ram).hexdigest(), bank_sha256=hashlib.sha256(bank).hexdigest(),
        about='Plain numbers for DORYA HERO; joint rotations are not included.',
        aliases=[index.get(a, -1) for a in aliases], default=index.get(DEFAULT, -1),
        native_aliases={str(k): v for k, v in solo.native_aliases().items()},
        records=records, sequences={str(k): v for k, v in sorted(sequences.items())},
        reactions={str(k): v for k, v in sorted(reactions.items())}, problems=problems)


def write(data: dict, path: Path) -> None:
    """One record per line: small enough to read, diff and send."""
    head = {k: v for k, v in data.items() if k != 'records'}
    lines = [json.dumps(r, separators=(',', ':')) for r in data['records']]
    text = json.dumps(head, separators=(',', ':'))[:-1] + ',"records":[\n' + ',\n'.join(lines) + '\n]}\n'
    path.write_text(text, encoding='utf-8')


def bank_bytes(ttt1: Path | None) -> bytes:
    saved = JUN / 'ttt1/bankedroms.bin'
    if saved.is_file():
        return verified(saved, BANK_SHA)
    if not ttt1:
        raise ValueError('No tektagt.zip found: put it in roms\\ next to Export-Dojo-Moves.cmd')
    import arcade_model_probe as probe
    definition = json.loads(probe.MANIFEST.read_text(encoding='utf-8'))['sets']['tektagt']
    bank = probe.reconstruct(ttt1, definition)[0]['bankedroms']
    if hashlib.sha256(bank).hexdigest() != BANK_SHA:
        raise ValueError('That tektagt.zip is not the World TEG2/VER.C1 set the decoders were checked on')
    return bank


def setup_inputs() -> dict:
    try:
        return json.loads((ROOT / '.setup/last-inputs.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def find_ttt1() -> Path | None:
    """The zip (or extracted folder) setup used, else one in roms\\ next to the .cmd, else ask."""
    used = setup_inputs().get('ttt1')
    for path in ([Path(used)] if used else []) + [ROOT / 'roms/tektagt.zip', ROOT / 'roms/tektagt',
                                                   ROOT / 'tektagt.zip', JUN / 'roms/tektagt.zip']:
        if path.is_file() or (path.is_dir() and any(path.iterdir())):
            return path
    try:
        import tkinter as tk
        from tkinter import filedialog
        window = tk.Tk()
        window.withdraw()
        chosen = filedialog.askopenfilename(title='Select your tektagt.zip (TTT1 arcade)',
                                            filetypes=[('TTT1 arcade ZIP', '*.zip')])
        window.destroy()
        return Path(chosen) if chosen else None
    except Exception:  # no display or no tkinter: the error below says what to pass
        return None


def rom_zip(source: Path) -> Path:
    """A fresh copy of the set for MAME and the bank: a zip as is, an extracted folder zipped up (chips by name)."""
    import zipfile
    roms = OUT / 'mame/roms'
    roms.mkdir(parents=True, exist_ok=True)
    target = roms / 'tektagt.zip'
    if source.is_dir():
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED) as out:
            for chip in sorted(p for p in source.iterdir() if p.is_file()):
                out.write(chip, chip.name)
    elif source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    with zipfile.ZipFile(target) as z:
        names = {Path(i.filename).name.casefold() for i in z.infolist()}
    missing = [n for n in ('teg2verc1.2e', 'teg2verc1.2j') if n not in names]
    if missing:
        raise ValueError(f'{source} has no {", ".join(missing)}: it holds {", ".join(sorted(names)) or "nothing"}')
    return target


def capture(ttt1: Path, mame: Path | None) -> None:
    """Interactive MAME run with its own saves (nvram/cfg under workspace/), so arcade clears made here to unlock
    a hidden fighter stay for the next run and the player's own emulator setup is never touched."""
    if mame is None:
        sys.path.insert(0, str(ROOT / 'launcher'))
        import setup_backend
        mame = setup_backend.mame()  # the setup's pinned MAME 0.289, downloaded from the MAME project if missing
    work = OUT / 'mame'
    roms = ttt1.parent
    (work / 'cheat').mkdir(parents=True, exist_ok=True)  # drop a MAME cheat.7z here to unlock hidden fighters
    print('MAME opens now. On the character select, highlight a fighter and press K (Kazuya), H (Heihachi) or '
          'J (Jin). Close MAME with Esc when done.', flush=True)
    subprocess.run([str(mame), 'tektagt', '-rompath', str(roms), '-window', '-skip_gameinfo',
                    '-autoboot_script', str(ROOT / 'tools/capture_ttt1_fighters.lua'), '-autoboot_delay', '0',
                    '-nvram_directory', str(work / 'nvram'), '-cfg_directory', str(work / 'cfg'),
                    '-cheat', '-cheatpath', str(work / 'cheat'),
                    '-snapshot_directory', str(OUT)], cwd=OUT, check=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture', action='store_true', help='open MAME first to save highlighted fighters')
    ap.add_argument('--ttt1', type=Path, help='non-merged tektagt.zip (default: the one setup used)')
    ap.add_argument('--mame', type=Path, help='MAME 0.289 executable (default: the setup\'s)')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ttt1 = args.ttt1 or find_ttt1()
    if ttt1:
        print(f'Using the TTT1 set at {ttt1}', flush=True)
        ttt1 = rom_zip(ttt1)
    elif args.capture:
        raise ValueError('No tektagt.zip found: put it in roms\\ next to Export-Dojo-Moves.cmd')
    if args.capture:
        capture(ttt1, args.mame)
    bank = bank_bytes(ttt1)
    sources = {f: OUT / f'{f}-select-ram.bin' for f in FIGHTERS}
    if not sources['jin'].is_file() and (JUN / 'jin-select-ram.bin').is_file():
        sources['jin'] = JUN / 'jin-select-ram.bin'  # the Jun import already captured Jin
    done = []
    for fighter, path in sources.items():
        if not path.is_file():
            continue
        ram = path.read_bytes()
        if len(ram) != 0x400000:
            raise ValueError(f'{path}: not a 4 MB main RAM capture')
        data = export(ram, bank, fighter)
        out = OUT / f'{fighter}-ttt1.json'
        write(data, out)
        moving = sum(1 for r in data['records'] if r['root'])
        print(f'{fighter}: {len(data["records"])} records ({moving} with root motion), {len(data["sequences"])} '
              f'input sequences, {len(data["problems"])} problems -> {out}', flush=True)
        done.append(fighter)
    if not done:
        raise ValueError('Nothing to export: run with --capture and save a fighter first')
    print(f'\nSend these to Claude: {", ".join(f"{f}-ttt1.json" for f in done)} '
          f'(and the .png of each capture) from {OUT}', flush=True)
    if os.name == 'nt':
        os.startfile(OUT)  # type: ignore[attr-defined]


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'Export failed: {error}', file=sys.stderr)
        sys.exit(1)
    except Exception:
        import traceback
        traceback.print_exc()
        print('Export failed: paste the lines above to Claude.', file=sys.stderr)
        sys.exit(1)
