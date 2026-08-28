# How the queue is worked, written down 2026-02-03

Nobody has ever set a priority on an item. The column does not exist. What
happens instead:

1. An item arrives and sits at the bottom of the list.
2. Twice a day someone walks the queue from the top.
3. When they reach an untouched item they read it and decide whether it
   jumps the queue. Most do not.
4. An item nobody has read yet is worked last, after everything a human has
   already looked at and kept.

Four of the seven items in the current sample have never been read by
anyone. They are the four at the bottom of the list, and they have been
there longest.
