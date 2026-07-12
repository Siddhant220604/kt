import os

# Test-only defaults so the suite is self-contained and doesn't silently depend on a
# local backend/.env existing (that file is git-ignored and won't exist in CI). Real
# values from an actual .env still win if one is present, since setdefault never
# overrides an already-set variable.
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('JWT_SECRET', 'test-secret-do-not-use-in-production-xxxxxxxxxxxxxxxxxxxxxxxx')
