# Lightworks-Converter
Converts project files from the Lightworks video editor app over to other formats.

## Project Notes

 * LW_ODB.py - The current Lightwave -> Final Cut 7 program. Does NOT take args; you need to edit the bottom of the file.
 * edl.py - EDL class used by LW_ODB.
 * PDS.py - very early peek at the Cyberlink PowerDirector file format.
 * ed5decode.py - Original program found online.  Can be used directly to create EDL or MLT files.

---

### Lightworks File Format

http://www.lwks.com/index.php?option=com_kunena&func=view&catid=23&id=62779&Itemid=81

Looks like the .ed5 files contain the extracted meta-data. This includes the time-code. These files are binary records (correction: they're string records in a binary file) so using a hex editor I changed the time code at the record:

    LABEL_REV:1 ntsc_drop_label 00:00:00;00 113 0.0333666667 1 MediumRollId 24,2

I changed the hour from 00 to 01 then opened the project and the timecode in the viewer now reflected my change. Looks like the key is to parse the ed5 files as binary records, make the change to the timecode record and re-write the ed5 file. Records are separated by nul bytes (0x00).

-----

### Docs for ed5decode

For very simple examples (like the LWKS tutorials) it should do it's job:

    python3 ed5decode.py  -m /tmp/test.mlt doc/Coffee\ Demo.Archive/E706013R.ed5

you can view the result in 'melt'

    melt /tmp/test.mlt

or render it to some file (most of ffmpegs options are available)

    melt -consumer avformat:/tmp/file.mp4 vcodec=libx264 vb=8M /tmp/test.mlt

-----

### Convert 'melt' files to EDL

https://eyeframeconverter.wordpress.com/mlt2edl/
