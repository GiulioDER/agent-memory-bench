# Bucket the cache

Address each entry by `len(resource_id) % 16`. The directory then holds at most
sixteen files whatever the resource count, which is the property we need.
