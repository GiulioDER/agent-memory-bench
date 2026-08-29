#!/usr/bin/env python3
import sys

BASE36 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def base36_increment(s: str) -> str:
    """Increment a base-36 string by 1."""
    chars = list(s)
    for i in range(len(chars) - 1, -1, -1):
        idx = BASE36.index(chars[i])
        if idx < 35:
            chars[i] = BASE36[idx + 1]
            return ''.join(chars)
        chars[i] = '0'
    # If we overflowed, prefix with '1'
    return '1' + ''.join(chars)


def main():
    with open('ids.txt') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        print('ORD-0000')
        return

    last_id = lines[-1]
    suffix = last_id.split('-')[1]
    next_suffix = base36_increment(suffix)
    print(f'ORD-{next_suffix}')


if __name__ == '__main__':
    main()
