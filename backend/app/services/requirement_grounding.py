"""Resume-v3 posting grounding. Presentation normalization, never fuzzy fact matching."""
import re
import unicodedata

_TYPOGRAPHY = str.maketrans({'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
                           '\u2010': '-', '\u2011': '-', '\u2013': '-', '\u2014': '-', '\u2212': '-'})
_BULLET = re.compile(r'^\s*(?:[-*\u2022\u25e6\u25aa]|\d+[.)])\s+')


def normalized_quote(text):
    text = unicodedata.normalize('NFKC', text).translate(_TYPOGRAPHY).casefold()
    return ' '.join(_BULLET.sub('', line).strip() for line in text.splitlines()).split()


def quote_key(text):
    return ' '.join(normalized_quote(text))


def _contains(text, quote):
    # Match whole words/technology names, retaining signs, numbers and qualifiers.
    for match in re.finditer(re.escape(quote), text):
        before = text[match.start()-1:match.start()] if match.start() else ''
        after = text[match.end():match.end()+1]
        if before and re.match(r'[\w+#]', before) and re.match(r'\w', quote[0]):
            continue
        if before in ('+', '-') and quote[0].isdigit():
            continue
        if after and re.match(r'[\w+#]', after) and re.match(r'[\w+#]', quote[-1]):
            continue
        return True
    return False


def grounded_quote(quote, posting):
    quote = quote_key(quote)
    if not quote:
        return False
    if _contains(quote_key(posting), quote):
        return True
    # Models commonly attach a list heading to each of its items. Accept that
    # relationship only within the actual list, never by joining distant text.
    heading, seen_item = None, False
    for raw in posting.splitlines():
        line = quote_key(raw)
        if not line:
            if seen_item:
                heading, seen_item = None, False
            continue
        if line.endswith(':'):
            heading, seen_item = line, False
            continue
        if heading:
            if quote.startswith(heading + ' ') and _contains(heading + ' ' + line, quote):
                return True
            seen_item = True
    return False
