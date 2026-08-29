#!/usr/bin/env python3

def base36_encode(n):
    """Encode an integer as a base-36 string (zero-padded to 4 chars)."""
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    result = []
    for _ in range(4):
        result.append(chars[n % 36])
        n //= 36
    return ''.join(reversed(result))

def base36_decode(s):
    """Decode a base-36 string to an integer."""
    return int(s, 36)

def main():
    with open('ids.txt', 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if not lines:
        print('ORD-0000')
        return
    
    last_id = lines[-1]
    suffix = last_id.split('-')[1]  # e.g., '243G'
    num = base36_decode(suffix)
    next_num = num + 1
    next_suffix = base36_encode(next_num)
    print(f'ORD-{next_suffix}')

if __name__ == '__main__':
    main()
