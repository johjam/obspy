# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from obspy.xseed.blockette import Blockette
from obspy.xseed.fields import Integer, VariableString, FixedString


class Blockette031(Blockette):
    """
    Blockette 031: Comment Description Blockette.

    Station operators, data collection centers, and data management centers
    can add descriptive comments to data to indicate problems encountered or
    special situations.

    Sample:
    03100720750Stime correction does not include leap second, (-1000ms).~000
    """
    id = 31
    name = "Comment Description"
    fields = [
        Integer(3, "Comment code key", 4),
        FixedString(4, "Comment class code", 1),
        VariableString(5, "Description of comment", 1, 70, 'UNLPS'),
        Integer(6, "Units of comment level", 3, ignore=True)
    ]
