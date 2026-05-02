import os
import tempfile

# Ensure a temporary home is set before any fitness_tracker module is imported.
# Tests themselves may import at top-level, so we set this as early as possible.
os.environ.setdefault("FITNESS_TRACKER_HOME", tempfile.mkdtemp())
