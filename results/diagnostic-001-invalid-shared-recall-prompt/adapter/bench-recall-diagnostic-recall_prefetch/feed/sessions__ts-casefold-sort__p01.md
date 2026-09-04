# Session notes: p01

**user**: At the Q2 summit the printed check-in roster put attendees 'ali', 'chen' and 'miller' after 'Zhang', right at the bottom of the sheet; the front desk could not find people and we collected complaints. The list we printed is preserved at incident/printed_roster_q2.txt, the raw registration list at incident/attendees_q2.txt, and the script that produced the printout at incident/make_roster_q2.py. Work out exactly why those names landed at the bottom, and recommend the ordering rule roster output should follow from now on. Keep the recommendation short and in plain language, it goes to the events team.

**assistant [Read]**: 
> 1	Baker
2	Ortega
3	Wu
4	Zhang
5	ali
6	chen
7	delgado
8	miller
9	

**assistant [Read]**: 
> 1	Zhang
2	ali
3	Baker
4	miller
5	Ortega
6	chen
7	Wu
8	delgado
9	

**assistant [Read]**: 
> 1	"""Roster printout script as run for the Q2 summit. Kept for the seating complaint investigation."""
2	
3	names = []
4	with open("incident/attendees_q2.txt", encoding="utf-8") as handle:
5	    for line in handle:
6	        if line.strip():
7	            names.append(line.strip())
8	with open("incident/printed_roster_q2.txt", "w", encoding="utf-8") as out:
9	    for name in sorted(names):
10	        out.write(name + chr(10))
11	

**assistant**: Now let me verify my understanding of the sorting behavior:



**assistant [Bash]**: 
> Default sorted: ['Baker', 'Ortega', 'Wu', 'Zhang', 'ali', 'chen', 'delgado', 'miller']
Case-insensitive sorted: ['ali', 'Baker', 'chen', 'delgado', 'miller', 'Ortega', 'Wu', 'Zhang']

Zhang      first char: Z (U+005A)
ali        first char: a (U+0061)
Baker      first char: B (U+0042)
miller     first char: m (U+006D)
Ortega     first char: O (U+004F)
chen       first char: c (U+0063)
Wu         first char: W (U+0057)
delgado    first char: d (U+0064)

**assistant**: ---

## Root cause

The script uses Python's `sorted()` with no arguments, which sorts by Unicode code point. Uppercase letters (A–Z) have code points 65–90, while lowercase letters (a–z) have code points 97–122. Because **every uppercase letter sorts before every lowercase letter**, names beginning with a lowercase letter (`ali`, `chen`, `delgado`, `miller`) all land after `Zhang` (the last uppercase-starting name).

Order produced by the bug: `Baker → Ortega → Wu → Zhang → ali → chen → delgado → miller`

## Recommendation for the events team

**Sort names case-insensitively.** When you sort the attendee list, ignore whether a name starts with a capital or a lowercase letter — treat "ali" the same as "Ali" and "ZHANG" the same as "Zhang". That way all names interleave correctly in true alphabetical order, and the roster matches what people expect when they scan for their name.

If the raw registration data contains mixed case (e.g. `ali` instead of `Ali`), consider also **title-casing the display** (`ali` → `Ali`) so the printed roster looks clean and professional.

**user**: Agreed. Decision: roster ordering uses a casefold, accent-insensitive sort key, so a lowercase name is never sorted after Z, and with international registrations coming in Q3 we strip the accents from each name before comparing so an accented name files with its base letters. Raw codepoint order must not be used for any attendee-facing list again.
