"""General-purpose functions to help with testing"""

import os
import subprocess

def check_call_suppress_output(args):
    """Make a check_call call with the given args, suppressing all output"""
    with open(os.devnull, 'w') as devnull:
        subprocess.check_call(args, stdout=devnull)
