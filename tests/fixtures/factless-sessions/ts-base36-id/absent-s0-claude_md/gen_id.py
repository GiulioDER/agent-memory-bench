#!/usr/bin/env python3
"""Read ids.txt (one order id per line, most recent last) and print the next id."""

def to_base36(val):
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = ""
    for _ in range(4):
        result = chars[val % 36] + result
        val //= 36
    return result

def parse_base36(s):
    return int(s, 36)

def main():
    with open("ids.txt") as f:
        lines = [line.strip() for line in f if line.strip()]

    last_id = lines[-1]
    suffix = last_id.split("-")[1]
    next_val = parse_base36(suffix) + 1
    next_suffix = to_base36(next_val)
    print(f"ORD-{next_suffix}")

if __name__ == "__main__":
    main()
