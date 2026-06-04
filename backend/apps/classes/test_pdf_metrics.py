"""Numeric unit tests for the PDF extraction metrics (pure, no DB/network)."""

from __future__ import annotations

from apps.classes.services.pdf_metrics import (
    cer,
    wer,
    levenshtein,
    table_cell_accuracy,
    normalize_persian,
)


class TestNormalizePersian:
    def test_folds_arabic_to_persian_letters(self):
        # Arabic yeh/kaf -> Persian yeh/kaf
        assert normalize_persian('علي كتاب') == normalize_persian('علی کتاب')

    def test_unifies_digit_scripts(self):
        assert normalize_persian('۱۲۳') == '123'
        assert normalize_persian('٤٥٦') == '456'  # Arabic-Indic

    def test_strips_tatweel_and_diacritics(self):
        assert normalize_persian('کـــتاب') == 'کتاب'

    def test_collapses_whitespace(self):
        assert normalize_persian('  a\t b\n c ') == 'a b c'


class TestLevenshtein:
    def test_identical(self):
        assert levenshtein('abc', 'abc') == 0

    def test_one_substitution(self):
        assert levenshtein('abc', 'abd') == 1

    def test_insertion_deletion(self):
        assert levenshtein('abc', 'ab') == 1
        assert levenshtein('ab', 'abc') == 1

    def test_token_lists(self):
        assert levenshtein(['the', 'cat'], ['the', 'dog']) == 1


class TestCER:
    def test_identical_is_zero(self):
        assert cer('سلام دنیا', 'سلام دنیا') == 0.0

    def test_normalization_makes_equivalent_zero(self):
        # Arabic vs Persian yeh + Persian digits vs ASCII -> identical
        assert cer('علي ۱۲۳', 'علی 123') == 0.0

    def test_one_char_substitution_in_four(self):
        # 'کتاب' vs 'کتیب' = 1 edit / 4 chars
        assert abs(cer('کتاب', 'کتیب') - 0.25) < 1e-9

    def test_empty_reference(self):
        assert cer('', '') == 0.0
        assert cer('', 'x') == 1.0


class TestWER:
    def test_identical(self):
        assert wer('این یک تست است', 'این یک تست است') == 0.0

    def test_one_word_dropped_in_four(self):
        assert abs(wer('این یک تست است', 'این یک تست') - 0.25) < 1e-9


class TestTableCellAccuracy:
    def test_perfect(self):
        ref = [['a', 'b'], ['1', '2']]
        assert table_cell_accuracy(ref, ref) == 1.0

    def test_one_wrong_in_four(self):
        ref = [['a', 'b'], ['1', '2']]
        hyp = [['a', 'b'], ['1', '9']]
        assert table_cell_accuracy(ref, hyp) == 0.75

    def test_missing_row_counts_as_wrong(self):
        ref = [['a', 'b'], ['1', '2']]
        hyp = [['a', 'b']]
        assert table_cell_accuracy(ref, hyp) == 0.5

    def test_persian_normalized_cells_match(self):
        ref = [['علی', '۲۰']]
        hyp = [['علي', '20']]
        assert table_cell_accuracy(ref, hyp) == 1.0
