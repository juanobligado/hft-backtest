import unittest
import datetime

from python.scripts.download_data import to_filename

class TestDownloadData(unittest.TestCase):
    def test_to_filename(self):
        self.assertEqual(to_filename('ethusdt', datetime.date(2024,8,8)), 'ethusdt_20240808.gz')
        self.assertEqual(to_filename('btcusdt', datetime.date(2024,8,31)), 'btcusdt_20240831.gz')



if __name__ == '__main__':
    unittest.main()