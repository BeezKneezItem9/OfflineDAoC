"""Send unittest output to stdout (Windows PowerShell 5.1 treats stderr as errors).
Emit actionable GitHub annotations on failure without publishing any fixture data.
"""
import sys
import unittest
from pathlib import Path

suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_*.py')
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
for case, traceback in result.failures + result.errors:
    message = (str(case) + '\n' + traceback)[-12000:]
    message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print('::error::' + message, flush=True)
if result.wasSuccessful():
    print('::notice::%s tool tests passed; %s skipped' % (result.testsRun-len(result.skipped), len(result.skipped)))
sys.exit(0 if result.wasSuccessful() else 1)
