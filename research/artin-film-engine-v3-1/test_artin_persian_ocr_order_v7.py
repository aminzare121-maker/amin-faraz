"""Guard against actual Persian RTL OCR word order reversal."""
import unittest
from artin_persian_chat_ocr_trial_v7 import reading_order_fa


class PersianOCRReadingOrderTests(unittest.TestCase):
    def test_farsi_words_on_same_line_go_from_right_to_left(self):
        rows=reading_order_fa(['نیس','صدا'],[.83,.85],
                [[150,10,235,46],[300,11,400,47]])
        self.assertEqual([x['ocr_candidate'] for x in rows],['صدا','نیس'])
        self.assertTrue(all(x['source_reading_order']=='RTL' for x in rows))

    def test_two_line_persian_question_stays_top_to_bottom(self):
        rows=reading_order_fa(['هست؟','یعنی همیشه اون عدد بالاتر از یک'],[.9,.86],
                    [[350,100,500,140],[60,10,500,60]])
        self.assertEqual([x['ocr_candidate'] for x in rows],
              ['یعنی همیشه اون عدد بالاتر از یک','هست؟'])

    def test_english_right_is_not_falsely_reversed(self):
        rows=reading_order_fa(['buy','sell'],[.8,.82],
                   [[20,10,80,40],[160,10,220,40]])
        self.assertEqual([x['ocr_candidate'] for x in rows],['buy','sell'])
        self.assertEqual(rows[0]['source_reading_order'],'LTR')

    def test_invalid_or_missing_bbox_rejected(self):
        with self.assertRaisesRegex(ValueError,'count mismatch'):
            reading_order_fa(['خرید'],[.9],[])
        with self.assertRaisesRegex(ValueError,'geometry'):
            reading_order_fa(['خرید'],[.9],[[5,20,1,3]])

    def test_out_of_range_confidence_rejected(self):
        with self.assertRaisesRegex(ValueError,'geometry'):
            reading_order_fa(['خرید'],[2.0],[[1,1,40,40]])


if __name__=='__main__':unittest.main()
