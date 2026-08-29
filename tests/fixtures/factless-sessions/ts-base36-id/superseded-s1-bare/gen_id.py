import sys


def next_id(ids_path: str = "ids.txt") -> str:
    """Read ids.txt and return the next order id in sequence."""
    with open(ids_path) as f:
        lines = f.readlines()

    # Find the last non-empty line
    last_id = None
    for line in reversed(lines):
        line = line.strip()
        if line:
            last_id = line
            break

    if last_id is None:
        raise ValueError("ids.txt is empty")

    # Parse the suffix (four base-36 characters after "ORD-")
    prefix = last_id[:4]  # "ORD-"
    suffix = last_id[4:]  # four base-36 chars

    # Convert to integer, increment, convert back
    val = int(suffix, 36)
    val += 1

    # Format back to 4 uppercase base-36 characters
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = []
    temp = val
    for _ in range(4):
        result.append(chars[temp % 36])
        temp //= 36
    next_suffix = "".join(reversed(result))

    return prefix + next_suffix


if __name__ == "__main__":
    print(next_id())
