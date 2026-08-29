import sys

def decode_base36(s):
    """Decode a base36 string to an integer."""
    return int(s, 36)

def encode_base36(n):
    """Encode an integer to a base36 string."""
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    if n == 0:
        return '0'
    result = []
    while n > 0:
        n, remainder = divmod(n, 36)
        result.append(chars[remainder])
    return ''.join(reversed(result))

def main():
    with open('ids.txt', 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    # Get the last ID (most recent last)
    last_id = lines[-1]
    
    # Extract the suffix after "ORD-"
    suffix = last_id[4:]
    
    # Decode, increment, encode
    num = decode_base36(suffix)
    next_num = num + 1
    next_suffix = encode_base36(next_num).zfill(4)
    
    print(f"ORD-{next_suffix}")

if __name__ == '__main__':
    main()
