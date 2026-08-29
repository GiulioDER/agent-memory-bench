"""Reads ids.txt and prints the next order id."""

import string

BASE36 = string.digits + string.ascii_uppercase


def to_base36(n: int) -> str:
    """Convert an integer to a base-36 string."""
    if n == 0:
        return "0"
    digits = []
    while n:
        digits.append(BASE36[n % 36])
        n //= 36
    return "".join(reversed(digits))


def from_base36(s: str) -> int:
    """Convert a base-36 string to an integer."""
    return int(s, 36)


def main() -> None:
    with open("ids.txt") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        print("ORD-0000")
        return

    last_id = lines[-1]
    suffix = last_id.split("-", 1)[1]
    num = from_base36(suffix)
    next_num = num + 1
    next_suffix = to_base36(next_num).zfill(4).upper()
    print(f"ORD-{next_suffix}")


if __name__ == "__main__":
    main()
