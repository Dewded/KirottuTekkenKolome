# DORYA HERO export

DORYA HERO (the Tekken 3-style movement game on Hemmo's site) rebuilds its movement from real System 12 data:
each move a fixed-length animation with its root motion per frame and its cancel list, so Wavus and Korean
backdashes come out of the cancels instead of being special-cased.

Double-click `Export-Dojo-Moves.cmd` (or `python tools/export_dojo_moves.py --capture`):

1. MAME 0.289 opens (the setup's copy; downloaded from the MAME project if missing) with your `tektagt.zip`, its
   own saves under `workspace/dojo-export/mame/`. It finds the zip setup used, else `roms\tektagt.zip` next to
   the .cmd, else asks. It coins up and starts by itself; if not, press 5 then 1.
2. On the character select, highlight a fighter and press **K** (Kazuya), **H** (Heihachi) or **J** (Jin). The top
   line says what was saved. Close MAME with Esc.
3. The export writes `workspace/dojo-export/<fighter>-ttt1.json` and opens the folder. Jin is exported even
   without a capture, from the Jun import's `jin-select-ram.bin`.

Kazuya may be a locked "?" slot on a fresh board: TTT1 unlocks hidden fighters one by one as arcade mode is
cleared, and this MAME's saves keep those clears for the next run.

What is exported: raw record words, frame counts, root motion (the first three motion channels: heading, height,
distance) per frame, flattened cancel rows, the input sequences they use, hit rows and the reactions they name.
Joint rotations (the animation itself) are not. ROMs and captures stay in ignored `workspace/`.

```powershell
python -m unittest tools.tests.test_export_dojo_moves
```
