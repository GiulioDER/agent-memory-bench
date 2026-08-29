#!/usr/bin/env python3
import sys

def base36_encode(n):
    chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    result = ''
    while n > 0:
        result = chars[n % 36] + result
        n //= 36
    return result.rjust(4, '0')

def base36_decode(s):
    return int(s, 36)

with open('ids.txt') as f:
    lines = [line.strip() for line in f if line.strip()]

last_id = lines[-1]
suffix = last_id.split('-')[1]
num = base36_decode(suffix)
next_num = num + 1
next_suffix = base36_encode(next_num)
next_id = f'ORD-{next_suffix}'
print(next_id)
