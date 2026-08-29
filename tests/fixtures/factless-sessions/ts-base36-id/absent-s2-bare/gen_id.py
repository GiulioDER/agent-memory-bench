def to_base36(n):
    """Convert integer to base-36 string (zero-padded to 4 chars, uppercase)."""
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    result = ''
    while n > 0:
        result = chars[n % 36] + result
        n //= 36
    return result.zfill(4)

def next_id():
    with open('ids.txt') as f:
        lines = f.read().strip().splitlines()
    if not lines:
        print('ORD-0001')
        return
    last = lines[-1].strip()
    suffix = last[4:]  # after "ORD-"
    val = int(suffix, 36)
    next_val = val + 1
    next_suffix = to_base36(next_val)
    print(f'ORD-{next_suffix}')

if __name__ == '__main__':
    next_id()
