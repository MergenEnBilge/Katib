"""Splitting text into tokens, and turning spans of characters into per-token labels.

Katib stores a span as a run of characters, which is exact and survives any amount of
re-tokenizing. Several formats that training code reads are built the other way round: one token
per line with a label beside it. Going between the two needs one agreed way of splitting words,
which is what this is.

The split is deliberately plain: runs of word characters, and every other non-space character on
its own. It is not a language model's tokenizer and does not try to be. It is reversible, which
matters more here: reading a file back gives the character offsets it came from.

Nothing here touches the disk or the database, so it stays in `core` (ARCHITECTURE.md section 13).
"""

import re
from dataclasses import dataclass

#: A run of letters, digits or underscores, or any other single character that is not a space.
WORD = re.compile(r"\w+|[^\w\s]", re.UNICODE)

#: What a token carries when nothing is labelled on it. The usual name in BIO files.
OUTSIDE = "O"


@dataclass(frozen=True)
class Token:
    """One token and where it sits in the text it came from."""

    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Tagged:
    """Tokens and their BIO tags, with a note of any span that had to be widened to fit."""

    tokens: list[Token]
    tags: list[str]
    #: Spans that did not start or end on a token boundary and were stretched to the nearest one.
    widened: int = 0


def split(text: str) -> list[Token]:
    """The tokens of `text`, in order, each knowing where it came from."""
    return [Token(m.group(0), m.start(), m.end()) for m in WORD.finditer(text)]


def _covering(tokens: list[Token], start: int, end: int) -> tuple[int, int] | None:
    """The first and last token a run of characters touches, or None when it touches none."""
    first = last = None
    for i, token in enumerate(tokens):
        if token.end <= start or token.start >= end:
            continue
        if first is None:
            first = i
        last = i
    return None if first is None or last is None else (first, last)


def tag(text: str, spans: list[tuple[int, int, str]]) -> Tagged:
    """Label each token from the spans covering it, in the BIO scheme.

    A span that cuts a token in half is widened to that token's edges, because a file of one
    token per line cannot say that half a word was labelled. Each one widened is counted so the
    export can report how many, rather than changing the work without saying so.

    Where spans overlap, the one that starts earliest wins the tokens they share: BIO has one tag
    per token and cannot hold both.
    """
    tokens = split(text)
    tags = [OUTSIDE] * len(tokens)
    widened = 0
    for start, end, label in sorted(spans, key=lambda s: (s[0], -s[1])):
        found = _covering(tokens, start, end)
        if found is None:
            continue
        first, last = found
        if tokens[first].start != start or tokens[last].end != end:
            widened += 1
        if any(tags[i] != OUTSIDE for i in range(first, last + 1)):
            continue
        tags[first] = f"B-{label}"
        for i in range(first + 1, last + 1):
            tags[i] = f"I-{label}"
    return Tagged(tokens, tags, widened)


def spans_from_tags(tokens: list[Token], tags: list[str]) -> list[tuple[int, int, str]]:
    """Read BIO tags back into runs of characters.

    `I-` continuing a different label, or arriving with nothing open, starts a new run rather than
    being thrown away: files in the wild are not always strict, and the words are what matter.
    """
    spans: list[tuple[int, int, str]] = []
    label: str | None = None
    start = 0
    end = 0
    for token, raw in zip(tokens, tags, strict=False):
        mark = (raw or OUTSIDE).strip()
        if mark in ("", OUTSIDE, "0"):
            if label is not None:
                spans.append((start, end, label))
                label = None
            continue
        kind, _, name = mark.partition("-")
        name = name or mark
        starting = kind.upper() == "B" or label is None or name != label
        if starting:
            if label is not None:
                spans.append((start, end, label))
            label, start, end = name, token.start, token.end
        else:
            end = token.end
    if label is not None:
        spans.append((start, end, label))
    return spans


def rebuild(words: list[str]) -> tuple[str, list[Token]]:
    """Text made from a list of tokens, and where each one ended up in it."""
    out: list[str] = []
    tokens: list[Token] = []
    at = 0
    for word in words:
        if out and not (len(word) == 1 and word in ",.;:!?)]}'\"%"):
            out.append(" ")
            at += 1
        tokens.append(Token(word, at, at + len(word)))
        out.append(word)
        at += len(word)
    return "".join(out), tokens
