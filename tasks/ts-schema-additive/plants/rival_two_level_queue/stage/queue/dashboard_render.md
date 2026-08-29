# What the queue board draws

Two lanes, side by side:

  LOW      everything the walker has read and dropped
  NORMAL   everything else

There has never been a third lane. The renderer takes the value and
maps anything it does not recognise into NORMAL, which is why nobody
has noticed the question until now.
