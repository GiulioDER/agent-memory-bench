import sys

BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base36_decode(s: str) -> int:
    """Decode a base-36 string to an integer."""
    return int(s, 36)


def base36_encode(n: int) -> str:
    """Encode an integer to a base-36 string (uppercase)."""
    if n == 0:
        return "0"
    digits = []
    while n > 0:
        digits.append(BASE36[n % 36])
        n //= 36
    return "".join(reversed(digits))


def next_id(last_id: str) -> str:
    """Given an order ID like ORD-243G, return the next one like ORD-243H."""
    prefix, suffix = last_id.rsplit("-", 1)
    num = base36_decode(suffix)
    next_num = num + 1
    next_suffix = base36_encode(next_num).rjust(4, "0")
    return f"{prefix}-{next_suffix}"


def main():
    try:
        with open("ids.txt") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("ids.txt not found", file=sys.stderr)
        sys.exit(1)

    # Find the last non-empty line
    last_line = None
    for line in reversed(lines):
        stripped = line.strip()
        if stripped:
            last_line = stripped
            break

    if last_line is None:
        # No IDs yet; start from the first
        print("ORD-0001")
        return

    print(next_id(last_line))


if __name__ == "__main__":
    main()
