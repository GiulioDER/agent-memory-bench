#!/usr/bin/env python3
"""Read ids.txt and print the next order id."""

def next_id(current: str) -> str:
    """Increment a 4-character base-36 id."""
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    val = 0
    for ch in current:
        val = val * 36 + digits.index(ch)
    val += 1
    result = ""
    for _ in range(4):
        result = digits[val % 36] + result
        val //= 36
    return result

def main():
    with open("ids.txt") as f:
        lines = [line.strip() for line in f if line.strip()]
    last_id = lines[-1]
    suffix = last_id.split("-")[1]
    print(f"ORD-{next_id(suffix)}")

if __name__ == "__main__":
    main()
