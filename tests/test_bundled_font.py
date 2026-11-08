from pathlib import Path
import unittest
from fontTools.ttLib import TTFont

class BundledFontTests(unittest.TestCase):
 def test_unmodified_bundled_font_contains_english_russian_and_ui_punctuation(self):
  root=Path(__file__).resolve().parents[1]
  with TTFont(root/'public/fonts/MysticCards.ttf') as font:
   cmap=font.getBestCmap()
   for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя“”—…':
    self.assertIn(ord(char),cmap,char)
    self.assertNotEqual(cmap[ord(char)],'.notdef')
  self.assertIn('SIL OPEN FONT LICENSE',(root/'public/fonts/MysticCardsFontLicense.txt').read_text(encoding='utf8'))

if __name__=='__main__':unittest.main()
