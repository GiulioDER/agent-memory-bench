import sys


ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
BASE = len(ALPHABET)  # 36
WIDTH = 4


def to_base36(n: int) -> str:
    """Convert integer to base-36 string."""
    if n == 0:
        return '0'
    digits = []
    while n > 0:
        n, rem = divmod(n, BASE)
        digits.append(ALPHABET[rem])
    return ''.join(reversed(digits))


def from_base36(s: str) -> int:
    """Convert base-36 string to integer."""
    n = 0
    for ch in s:
        n = n * BASE + ALPHABET.index(ch)
    return n


def next_id(last_id: str) -> str:
    """Given an id like ORD-243C, return the next in sequence."""
    prefix, suffix = last_id.split('-')
    n = from_base36(suffix)
    n += 1
    new_suffix = to_base36(n).zfill(WIDTH)
    return f'{prefix}-{new_suffix}'


def main():
    try:
        with open('ids.txt') as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print('ORD-0000')
        return

    if not lines:
        print('ORD-0000')
        return

    last = lines[-1]
    print(next_id(last))


if __name__ == '__main__':
    main()
