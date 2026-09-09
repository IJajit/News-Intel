import os
import sys

# Add the root directory to path to import server.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import NewsBriefingHandler, seed_briefs

# Ensure briefings are seeded in /tmp on Vercel cold starts
seed_briefs()

class handler(NewsBriefingHandler):
    pass
