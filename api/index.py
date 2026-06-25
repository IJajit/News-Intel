import os
import sys

# Add the root directory to path to import server.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import NewsBriefingHandler

class handler(NewsBriefingHandler):
    pass
