"""Splitting words, tagging them from spans, and reading the tags back."""

from katib.core import tokens


def test_words_and_punctuation_are_split_with_their_places() -> None:
    found = tokens.split("Ada works at Katib, daily.")
    assert [t.text for t in found] == ["Ada", "works", "at", "Katib", ",", "daily", "."]
    # Every token knows where it came from, so a tag on it can become characters again.
    assert all(t.text == "Ada works at Katib, daily."[t.start : t.end] for t in found)


def test_spans_become_bio_tags() -> None:
    text = "Ada works at Katib."
    tagged = tokens.tag(text, [(0, 3, "person"), (13, 18, "org")])
    assert list(zip([t.text for t in tagged.tokens], tagged.tags, strict=True)) == [
        ("Ada", "B-person"),
        ("works", "O"),
        ("at", "O"),
        ("Katib", "B-org"),
        (".", "O"),
    ]
    assert tagged.widened == 0


def test_a_span_over_several_words_continues_with_i() -> None:
    tagged = tokens.tag("The Katib Project ships.", [(4, 17, "product")])
    assert tagged.tags == ["O", "B-product", "I-product", "O", "O"]


def test_a_span_cutting_a_word_is_widened_and_counted() -> None:
    """One token per line cannot say that half a word was labelled, so the span grows to fit."""
    text = "Katibs everywhere."
    tagged = tokens.tag(text, [(0, 5, "product")])
    assert tagged.tags[0] == "B-product"
    assert tagged.widened == 1
    # The widened tag covers the whole word it cut into.
    [(start, end, label)] = tokens.spans_from_tags(tagged.tokens, tagged.tags)
    assert (text[start:end], label) == ("Katibs", "product")


def test_overlapping_spans_keep_the_one_that_starts_first() -> None:
    """BIO holds one tag per token, so the longer, earlier span wins the words they share."""
    text = "The Katib Project ships."
    tagged = tokens.tag(text, [(4, 17, "product"), (4, 9, "org")])
    assert tagged.tags == ["O", "B-product", "I-product", "O", "O"]


def test_tags_read_back_into_the_characters_they_came_from() -> None:
    text = "Ada works at Katib."
    tagged = tokens.tag(text, [(0, 3, "person"), (13, 18, "org")])
    back = tokens.spans_from_tags(tagged.tokens, tagged.tags)
    assert back == [(0, 3, "person"), (13, 18, "org")]
    assert [text[s:e] for s, e, _ in back] == ["Ada", "Katib"]


def test_a_file_that_is_not_strict_is_still_read() -> None:
    """`I-` with nothing open, or continuing another label, starts a run instead of being lost."""
    found = tokens.split("Ada Lovelace met Grace")
    tags = ["I-person", "I-person", "O", "I-name"]
    assert tokens.spans_from_tags(found, tags) == [(0, 12, "person"), (17, 22, "name")]


def test_text_can_be_rebuilt_from_tokens_alone() -> None:
    """Some formats hold tokens and no original text, so the words are put back together."""
    text, found = tokens.rebuild(["Ada", "works", "at", "Katib", "."])
    assert text == "Ada works at Katib."
    assert all(t.text == text[t.start : t.end] for t in found)


def test_round_trip_through_tags_keeps_every_span() -> None:
    text = "Grace Hopper wrote COBOL at Remington Rand in 1959."
    spans = [(0, 12, "person"), (19, 24, "language"), (28, 42, "org"), (46, 50, "year")]
    tagged = tokens.tag(text, spans)
    assert tagged.widened == 0
    assert tokens.spans_from_tags(tagged.tokens, tagged.tags) == spans
