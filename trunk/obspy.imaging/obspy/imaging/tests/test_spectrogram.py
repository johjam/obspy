# -*- coding: utf-8 -*-
"""
The obspy.imaging.spectogram test suite.
"""

from obspy.core import UTCDateTime, Stream, Trace
import time
from obspy.imaging import spectrogram
import numpy as np
import os
import unittest
try:
    from unittest import skipIf
except ImportError:
    from obspy.core.util import skipIf


class SpectrogramTestCase(unittest.TestCase):
    """
    Test cases for spectrogram plotting.
    """
    def setUp(self):
        # directory where the test files are located
        self.path = os.path.join(os.path.dirname(__file__), 'output')

    @skipIf(__name__ != '__main__', 'test must be started manually')
    def test_Waveform(self):
        """
        Create waveform plotting examples in tests/output directory.
        """
        # Create dynamic test_files to avoid dependencies of other modules.
        # set specific seed value such that random numbers are reproduceable
        np.random.seed(815)
        head = {'network': 'BW', 'station': 'BGLD',
            'starttime': UTCDateTime(2007, 12, 31, 23, 59, 59, 915000),
            'sampling_rate': 200.0, 'channel': 'EHE'}
        tr = Trace(data=np.random.randint(0, 1000, 824), header=head)
        st = Stream([tr])
        outfile = os.path.join(self.path, 'spectogram.png')
        spectrogram.spectrogram(st[0].data, log=True, outfile=outfile,
                                samp_rate=st[0].stats.sampling_rate,
                                show=False)
        # check that outfile was modified
        stat = os.stat(outfile)
        self.assertTrue(abs(stat.st_mtime - time.time()) < 3)


def suite():
    return unittest.makeSuite(SpectrogramTestCase, 'test')


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
