import gzip

import pytest

from muxfind.liberty.lex_error import LibertyLexError
from muxfind.liberty.parser import parse_liberty
from muxfind.liberty.tokenizer import tokenize_liberty
from muxfind.reader import read_text


def test_reader_reads_plain_text(tmp_path):
    path = tmp_path / "small.lib"
    path.write_text("library(test) {}", encoding="utf-8")

    assert read_text(path) == "library(test) {}"


def test_reader_reads_gzip_text(tmp_path):
    path = tmp_path / "small.lib.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("library(test) {}")

    assert read_text(path) == "library(test) {}"


def test_comments_inside_quoted_values_are_preserved():
    text = '''
    cell("C//name") {
      pin("Y") { function : "A/*not a comment*/ + B"; }
    }
    '''

    cells = parse_liberty(tokenize_liberty(text))

    assert cells[0].name == "C//name"
    assert cells[0].output_pins[0].function == "A/*not a comment*/ + B"


def test_comments_and_line_continuations_outside_strings_are_removed():
    text = '''/* header
       comment */
    cell(\\
      C) {
      pin(Y) { function : A B; } // trailing comment
    }
    '''

    cells = parse_liberty(tokenize_liberty(text))

    assert cells[0].name == "C"
    assert cells[0].output_pins[0].function == "A B"


def test_quoted_delimiter_names_are_not_treated_as_structure():
    text = 'cell(")") { pin("(") { direction : output; function : A; } }'

    cells = parse_liberty(tokenize_liberty(text))

    assert cells[0].name == ")"
    assert cells[0].output_pins[0].name == "("


def test_tokenizer_distinguishes_barewords_from_quoted_strings():
    tokens = tokenize_liberty('function "function" : output ;')

    assert [(token.kind, token.value) for token in tokens] == [
        ("BAREWORD", "function"),
        ("STRING", "function"),
        ("SYMBOL", ":"),
        ("BAREWORD", "output"),
        ("SYMBOL", ";"),
    ]


@pytest.mark.parametrize(
    "text",
    ['/* unterminated', 'cell("unterminated) {'],
)
def test_unterminated_comment_or_string_is_reported(text):
    with pytest.raises(LibertyLexError):
        tokenize_liberty(text)
