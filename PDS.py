#!/usr/bin/python3

import xml.etree.ElementTree as ET

"""
CyberLink PowerDirector format.
"""

class PDS:
    pass

tree = ET.parse('test-file(powerdirector).xml')
root = tree.getroot()
e = root.find('Aurora/Playable/TimelineChunk/Buffer')

tltree = ET.fromstring(e.text)

# Project
## Aurora
### OutputProfile
### MenuPlayable
### Playable
#### OutputProfile
#### VideoProfile
#### Chapter
#### Thumbnail
#### TimelineChunk
##### Buffer
#   -> XML file

#(which contains)

# PROJECT
## INFORMATION
## LIBRARY
## TITLE
