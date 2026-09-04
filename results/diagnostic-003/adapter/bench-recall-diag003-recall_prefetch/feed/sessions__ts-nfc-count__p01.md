# Session notes: p01

**user**: The published glossary lists what looks like the same word twice with two different counts, and the editor bounced it (published/glossary.txt). The source texts are under docs/, including the restored archive note. Find out how one word became two entries, show me the difference between the two spellings at the byte level, and say what the counting pipeline should do so this cannot happen again.

**assistant [Read]**: 
> 1	brioche 1
2	café 2
3	café 1
4	chaud 1
5	est 2
6	fraiche 1
7	la 1
8	le 3
9	menu 1
10	ouvre 1
11	petit 1
12	the 2
13	tôt 1
14	

**assistant [Read]**: 
> 1	Note restaurée de l'archive: le café historique reste inchangé.
2	

**assistant [Bash]**: 
> Exit code 2
/usr/bin/bash: eval: line 1: unexpected EOF while looking for matching `"'

**assistant [Bash]**: 
> total 3
drwxr-xr-x 1 gde00 197609  0 Aug 22 23:29 .
drwxr-xr-x 1 gde00 197609  0 Aug 22 23:29 ..
-rw-r--r-- 1 gde00 197609 69 Aug 22 23:29 archive_note.txt
-rw-r--r-- 1 gde00 197609 60 Aug 22 23:31 intro.txt
-rw-r--r-- 1 gde00 197609 52 Aug 22 23:31 menu.txt

**assistant [Bash]**: 
> ./docs/archive_note.txt
./docs/intro.txt
./docs/menu.txt
./published/glossary.txt

**assistant [Read]**: 
> 1	Le café ouvre tôt. Le café est petit, le the est chaud.
2	

**assistant [Read]**: 
> 1	Menu: café, the, brioche. La brioche est fraiche!
2	

**assistant [Read]**: 
> 1	Note restaurée de l'archive: le café historique reste inchangé.
2	

**assistant [Bash]**: 
> 00000000: 4e6f 7465 2072 6573 7461 7572 c3a9 6520  Note restaur..e 
00000010: 6465 206c 2761 7263 6869 7665 3a20 6c65  de l'archive: le
00000020: 2063 6166 65cc 8120 6869 7374 6f72 6971   cafe.. historiq
00000030: 7565 2072 6573 7465 2069 6e63 6861 6e67  ue reste inchang
00000040: c3a9 2e0d 0a                             .....

**assistant [Bash]**: 
> 00000000: 4c65 2063 6166 c3a9 206f 7576 7265 2074  Le caf.. ouvre t
00000010: c3b4 742e 204c 6520 6361 66c3 a920 6573  ..t. Le caf.. es
00000020: 7420 7065 7469 742c 206c 6520 7468 6520  t petit, le the 
00000030: 6573 7420 6368 6175 642e 0d0a            est chaud...

**assistant [Bash]**: 
> 00000000: 4d65 6e75 3a20 6361 66c3 a92c 2074 6865  Menu: caf.., the
00000010: 2c20 6272 696f 6368 652e 204c 6120 6272  , brioche. La br
00000020: 696f 6368 6520 6573 7420 6672 6169 6368  ioche est fraich
00000030: 6521 0d0a                                e!..

**assistant**: Now let me inspect the exact byte sequences to understand the two encodings of "caf

**assistant [Bash]**: 
> Exit code 1
Traceback (most recent call last):
  File "<string>", line 16, in <module>
    print('archive_note cafe as Python string:', repr(nfd))
    ~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gde00\AppData\Local\Python\pythoncore-3.14-64\Lib\encodings\cp1252.py", line 19, in encode
    return codecs.charmap_encode(input,self.errors,encoding_table)[0]
           ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
UnicodeEncodeError: 'charmap' codec can't encode character '\u0301' in position 5: character maps to <undefined>
intro.txt cafe bytes:  b'caf\xc3\xa9'
archive_note cafe bytes: b'cafe\xcc\x81'

intro.txt cafe as Python string: 'caf�'
archive_note cafe as Python string:

**assistant [Bash]**: 
> Exit code 1
  File "<string>", line 9
    'archive_note.txt': 'Note restaur�e de l'archive: le cafe\u0301 historique reste inchang�.',
                                                                                         ^
SyntaxError: unterminated string literal (detected at line 9)

**assistant [Bash]**: 
> intro.txt cafe as Python string: 'café'
archive_note cafe as Python string: 'café'

Codepoints for intro cafe: U+0063 U+0061 U+0066 U+00E9
Codepoints for archive cafe: U+0063 U+0061 U+0066 U+0065 U+0301

Are they equal? False
Are they equal after NFC normalization? True

**assistant [Bash]**: 
> === Without normalization (buggy pipeline) ===
  intro.txt: 'le'                                     codepoints: U+006C U+0065
  intro.txt: 'café'                                   codepoints: U+0063 U+0061 U+0066 U+00E9
  intro.txt: 'ouvre'                                  codepoints: U+006F U+0075 U+0076 U+0072 U+0065
  intro.txt: 'tôt'                                    codepoints: U+0074 U+00F4 U+0074
  intro.txt: 'le'                                     codepoints: U+006C U+0065
  intro.txt: 'café'                                   codepoints: U+0063 U+0061 U+0066 U+00E9
  intro.txt: 'est'                                    codepoints: U+0065 U+0073 U+0074
  intro.txt: 'petit'                                  codepoints: U+0070 U+0065 U+0074 U+0069 U+0074
  intro.txt: 'le'                                     codepoints: U+006C U+0065
  intro.txt: 'the'                                    codepoints: U+0074 U+0068 U+0065
  intro.txt: 'est'                                    codepoints: U+0065 U+0073 U+0074
  intro.txt: 'chaud'                                  codepoints: U+0063 U+0068 U+0061 U+0075 U+0064
  menu.txt: 'menu'                                   codepoints: U+006D U+0065 U+006E U+0075
  menu.txt: 'café'                                   codepoints: U+0063 U+0061 U+0066 U+00E9
  menu.txt: 'the'                                    codepoints: U+0074 U+0068 U+0065
  menu.txt: 'brioche'                                codepoints: U+0062 U+0072 U+0069 U+006F U+0063 U+0068 U+0065
  menu.txt: 'la'                                     codepoints: U+006C U+0061
  menu.txt: 'brioche'                                codepoints: U+0062 U+0072 U+0069 U+006F U+0063 U+0068 U+0065
  menu.txt: 'est'                                    codepoints: U+0065 U+0073 U+0074
  menu.txt: 'fraiche'                                codepoints: U+0066 U+0072 U+0061 U+0069 U+0063 U+0068 U+0065
  archive_note.txt: 'note'                                   codepoints: U

**assistant**: Now let me confirm the exact byte difference between the two glossary

**assistant [Bash]**: 
> === GFX entries side by side ===
Line 2 "café" (NFC): 'café'
  codepoints: U+0063 U+0061 U+0066 U+00E9
  bytes (UTF-8): 63 61 66 c3 a9

Line 3 "café" (NFD): 'café'
  codepoints: U+0063 U+0061 U+0066 U+0065 U+0301
  bytes (UTF-8): 63 61 66 65 cc 81

Visually identical?: True
String-equal? False

**assistant**: Here is the complete investigation.

---

## How one word became two entries

The source texts are three files in `docs/`:

| File | Occurrences of "café" | Unicode form |
|---|---|---|
| `intro.txt` | 2 (`Le café ouvre tôt. Le café est petit...`) | NFC |
| `menu.txt` | 1 (`Menu: café, the, brioche.`) | NFC |
| `archive_note.txt` | 1 (`le café historique reste inchangé`) | **NFD** |

The counting pipeline treats NFC `café` and NFD `café` as distinct strings, producing two separate glossary entries — even though they render identically.

---

## Byte-level difference

**Line 2 — NFC `café` (composed):**

```
codepoints: U+0063  U+0061  U+0066  U+00E9
bytes:      63      61      66      c3 a9
```

The accented **é** is a single codepoint (U+00E9 = LATIN SMALL LETTER E WITH ACUTE).

**Line 3 — NFD `café` (decomposed):**

```
codepoints: U+0063  U+0061  U+0066  U+0065  U+0301
bytes:      63      61      66      65      cc 81
```

The accented **é** is two codepoints: plain `e` (U+0065) followed by combining acute accent (U+0301).

The strings are **byte-equal at positions 0–2** (`63 61 66` = "caf"), then diverge at byte 3:

| Glossary line | Byte 3 | Byte 4 | Meaning |
|---|---|---|---|
| Line 2 (NFC) | `c3 a9` | — | Single composed **é** (U+00E9) |
| Line 3 (NFD) | `65` | `cc 81` | Plain **e** + combining acute (U+0065 U+0301) |

They look the same on screen because Unicode Normalization Form C (NFC) folds the decomposed form into the composed form:
```python
unicodedata.normalize('NFC', 'cafe\u0301') == 'café'  # True
```

---

## What the counting pipeline should do

**Normalize all source text to NFC before tokenizing.** A single call suffices, placed right after reading each file and before any tokenization or counting:

```python
import unicodedata

text = unicodedata.normalize('NFC', raw_text)
# then tokenize, count, etc.
```

This guarantees that `cafe\u0301` (NFD) and `caf\u00e9` (NFC) are treated as the same word. NFC is the standard choice because it is the W3C/HTML recommendation and produces the shortest representation.

The pipeline currently has no normalization step at all, which is why visually identical strings from different sources (or even within the same file — note `archive_note.txt` has NFD `café` but NFC `inchangé`) produce duplicate glossary entries.

**user**: Good find. Decision: every text is passed through unicodedata NFC normalize before tokenising, so a decomposed spelling with a combining accent collapses into the composed form. The glossary must be regenerated with NFC normalisation, and any word counting over docs/ does the same from now on.
