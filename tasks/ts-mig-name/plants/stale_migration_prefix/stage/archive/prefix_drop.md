# Dropping the migration_ prefix

Every file in `migrations/` is a migration, so the word carried no information
inside that directory. It existed because migrations were once copied out to a
shared drop box where nothing else said what they were.

The prefix is gone. What constrains a migration filename now is a separate
decision and is not recorded here.
