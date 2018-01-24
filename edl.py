#!/usr/bin/python3

"""
edl.py -- Classes to help create Edit Description List ("EDL") files.

Copyright (C) 2015 William R. Zwicky <wrzwicky@pobox.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

class EDLBlock:
    def __init__(self):
        self.id = 0
        """Num, 3 digits, officially 001-999. Non-num makes row a comment."""
        self.reel = None
        """Reference to media file or tape.
           Officially: 3-digit num 001-253, optionally followed by B;
           or BL for black,
           or AX for aux source.
           Unofficially: any string."""
        self.channels = None
        """The channels involved in the edit.
           A = audio1,
           V = video1,
           B = A+V,
           A2 = audio2,
           A2/V = A2+V,
           AA = A1+A2,
           AA/V = A1+A2+V"""
        self.transition = None
        """Type of edit statment.
           C=cut,
           D=dissolve,
           Wxxx=wipe type xxx,
           KB = key background (background clip for matching K or KO line),
           K=key foreground (foreground clip for matching KB line),
           KO=key foreground mask ('this material being removed from the foreground' for matching KB line)"""
        self.transDur = None
        """Duration of transition.
           3-digit int 001-255, in frames,
           or lone F to 'indicate a fade condition'"""
        self.srcIn = None
        """timecode (hh:mm:ss:ff)
           'play source in-time' (start of clip in source file)"""
        self.srcOut = None
        """timecode (hh:mm:ss:ff)
           'play source out-time' (end of clip in source file)"""
        self.recIn = None
        """timecode (hh:mm:ss:ff)
           'record in-time' (where to place start of clip in output stream)"""
        self.recOut = None
        """timecode (hh:mm:ss:ff). Either out-time or duration.
           Ignored on read; clip length is srcOut-srcIn."""

class EDL(list):
    def __init__(self):
        self.title = None      #str 'title' field in file
        self.dropframe = True  #bool whether drop-frame (may want to hide this in timecode string instead)
        #self.fps   = 23.97  #float frames per second
        self.reels = {}        #str->str mapping from EDLBlock.reel to file path
        #self.edits = []

    def load(self, filename):
        # auto-detect dialect: Premiere, Final Cut, Sony, CMX, etc.
        pass

    def savePremiere(self):
        # CMX 3600:
        #   111^^222^^3333^^4444^555^666666666666^777777777777^888888888888^999999999999^
        # Old Lightworks converter:
        #   003  E00706EU  V     D    030 00:00:26:29 00:00:32:10 00:00:01:02 00:00:07:13
        #   111^^22222222^^3333^^4444^555^66666666666^77777777777^88888888888^99999999999
        # Export from Premiere:
        #   003  AX       AA    C        00:00:00:10 00:02:03:24 00:00:53:25 00:02:57:09
        #   * FROM CLIP NAME: Ep6_Sc2 - Elliot tries again with Tiff.mp4

        if not not self.title:
            print("TITLE: ", self.title)
        if self.dropframe:
            print("FCM: DROP FRAME")
        else:
            print("FCM: NON DROP FRAME")
        print()
        
        for block in self:
            s = "%03d  %-8s  %-4s  %-4s %03s %-11s %-11s %-11s %-11s" \
                % (block.id, block.reel, block.channels,
                   block.transition, block.transDur,
                   block.srcIn, block.srcOut, block.recIn, block.recOut)
            print(s)


# TITLE: title
# FCM: DROP FRAME | NON DROP FRAME

if __name__ == '__main__':
    e = EDL()
    e.title = "Test script"
    b = EDLBlock()
    b.id = 2
    b.reel = "7x432"
    b.channels = "B"
    e.append(b)
    b = EDLBlock()
    b.id = 3
    b.reel = "9b777"
    b.channels = "AA/V"
    e.append(b)

    e.savePremiere()
