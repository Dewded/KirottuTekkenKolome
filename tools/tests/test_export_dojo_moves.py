"""The DORYA HERO export on a synthetic capture: graph, cancels, sequences, root motion only."""
import json
import struct
import tempfile
import unittest
from pathlib import Path
from tools import export_dojo_moves as dojo


def fixture():
    ram = bytearray(0x400000)
    bank = bytearray(0x400)
    bank[0] = 2  # two frames: frame 0 from +2, the last from +0x74
    struct.pack_into('<3H', bank, 2, 10, 20, 30)
    struct.pack_into('<3H', bank, 0x74, 11, 21, 40)
    cancels = 0x300000
    struct.pack_into('<7H', ram, cancels, 0x8010, 0, 0, 57, 0, 0x0500, 0x000a)  # sequence 0x8010 -> alias 57
    struct.pack_into('<7H', ram, cancels + 14, 0x8000, 0, 0, 56, 6, 0, 0)  # end of animation -> alias 56
    struct.pack_into('<3H', ram, 0x772 + 0x8010 * 2, 8, 0x40, 0)
    struct.pack_into('<5H', ram, 0xEC8BC, 0xFFFF, 0, 0, 0, 0)
    for i in range(120):
        address = 0x80200000 + i * 64
        struct.pack_into('<I', ram, dojo.ALIASES + i * 4, address)
        struct.pack_into('<13I', ram, address & 0x3FFFFF, 0, 0, 0, 0x80000000 | cancels, 56, *[0] * 8)
    return bytes(ram), bytes(bank)


class ExportTests(unittest.TestCase):
    def test_records_carry_numbers_not_poses(self):
        ram, bank = fixture()
        data = dojo.export(ram, bank, 'jin')
        self.assertEqual(len(data['records']), 120)
        first = data['records'][data['aliases'][0]]
        self.assertEqual(first['frames'], 2)
        self.assertEqual(first['root'], [[10, 20, 30], [11, 21, 40]])  # heading, height, distance only
        self.assertEqual(first['cancels'][0][:4], [0x8010, 0, 0, 57])
        self.assertEqual(data['sequences'][str(0x8010)], [8, 0x40, 0])
        self.assertEqual(data['problems'], [])

    def test_written_file_reads_back(self):
        ram, bank = fixture()
        data = dojo.export(ram, bank, 'jin')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'jin-ttt1.json'
            dojo.write(data, path)
            self.assertEqual(json.loads(path.read_text()), json.loads(json.dumps(data)))

    def test_empty_select_screen_is_refused(self):
        with self.assertRaises(ValueError):
            dojo.export(bytes(0x400000), bytes(0x400), 'kazuya')


if __name__ == '__main__':
    unittest.main()
