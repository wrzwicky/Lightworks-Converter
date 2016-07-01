#!/usr/bin/python3

import csv, logging, os, pathlib, pprint, sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
from yattag import Doc

import ed5decode
import edl

"""
LW_ODB.py -- Classes to help read Lightworks *.odb files.

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

# *.odb file from LightWorks
# Plain text, structure is pretty self evident.
class LW_ODB:

    def __init__(self, filename):
        self.filename = filename
        self.metadata = {}
        """dict of misc values in the odb file"""
        self.flens = None
        """list of field lengths"""
        self.ftypes = None
        """list of field types"""
        self.fnames = None
        """list of field names"""
        self.fnum = None
        """map from field name to field index"""
        self.items = {}
        """rows = map from Cookie to dict of fname/value; special '.ed5' is parsed ed5 file"""

        self.loadProject()
        print(self.metadata['PROJECT_NAME'])
        #print(list(self.items.keys()))
        self.loadItems()

        any = next (iter (self.items.values()))['.ed5']
        print(any.filename, any.title, any.fps)
#        pprint.pprint(any.EHP)
#        pprint.pprint(any.edit_cells)

    def loadProject(self):
        """Load the main odb file. It's a plain text file, easy to read.
           Lists metadata at the top, then a list of resources (clips and edited sequences) below.
           The "cookie" from each row refers to an .ed5 file with details."""
        proj_file = self.filename
        if not os.access(proj_file, os.F_OK):
            logging.error('can not read project info (%s)' % proj_file)
            self.title = 'unknown'
        else:
            with open(proj_file) as csvfile:
                tablerow = 0
                for row in csv.reader(csvfile, delimiter=',', quotechar='"', skipinitialspace=True):
                    if len(row) == 1:
                        [k,s,v] = row[0].partition(':')
                        if not not v:
                            self.metadata[k] = v
                    else:
                        tablerow += 1
                        if tablerow == 1:
                            # field lengths
                            self.flens = row
                        elif tablerow == 2:
                            # field types
                            self.ftypes = row
                        elif tablerow == 3:
                            # field names
                            self.fnames = row
                            self.fnum = dict(zip(row, range(0,len(row))))
                        else:
                            # all the data rows
                            #self.items[row[0]] = row
                            self.items[row[0]] = dict(zip(self.fnames, row))

    def loadItems(self):
        """Load the items in project, attach as element '.ed5'."""
        directory = os.path.dirname(os.path.abspath(self.filename))
        for cookie in self.items:
            item = self.items[cookie]
            seg_file = os.path.join(directory, '%s.ed5' % cookie)
            item['.ed5'] = ed5decode.ED5(seg_file)

    def fixEdits(self, edit_cells):
        """Fix and clean list of edits."""
        
        # merge pairs of cells
        num =  len(edit_cells)
        if num % 2:
            raise ValueError('odd number of edit cells')
        else:
            for n in range(num-1, 0, -2):
                edit_cells[n-1]['src_out'] = edit_cells[n]['src_out']
                edit_cells[n-1]['rec_out'] = edit_cells[n]['rec_out']
                del edit_cells[n]
        
        # merge related cuts
        [ a != b 
        and a['reel']    == b['reel']    
        and a['src_in']  == b['src_in']  
        and a['src_out'] == b['src_out'] 
        and a['rec_in']  == b['rec_in']  
        and a['rec_out'] == b['rec_out'] 
        
        and not a.update(track=a['track']+' '+b['track'])
        and not edit_cells.remove(b)
        
        for a in edit_cells
        for b in edit_cells]

        return edit_cells


    def makeEDL(self):
        for cookie in self.items:
            item = self.items[cookie]
            if item["Type"] == "edit":
                itemdata = item['.ed5'].EHP
                e = edl.EDL()
                e.title = self.metadata['PROJECT_NAME']

                edits = item['.ed5'].edit_cells
                self.fixEdits(edits)
                num = 1
                for c in edits:
                    if c['reel'] == 'BL':
                        # black frame
                        pass
                    else:
                        b = edl.EDLBlock()
                        b.id = num
                        num += 1
                        b.reel = c['reel']
                        b.channels = c['track']
                        b.transition = 'C'
                        #b.transDur = ?
                        b.srcIn = c['src_in']
                        b.srcOut = c['src_out']
                        b.recIn = c['rec_in']
                        b.recOut = c['rec_out']
                        #c['aud'], c['from_clip']
                        e.append(b)
        return e

    def makeFcpxml(self):
        # minimal file for Premiere to accept:
        # condensed <element/> not allowed!
        # <?xml version="1.0"?>
        # <xmeml version="4">
	#   <project>
	#     <name>name</name>
	#     <children></children>
	#   </project>
	# </xmeml>

        uid = 1

        root = ET.Element('xmeml', {'version': '4'})
        project = ET.SubElement(root, 'project')
        name = ET.SubElement(project, 'name')
        name.text = self.metadata['PROJECT_NAME']
        children = ET.SubElement(project, 'children')
        children.tail = ' '  #prevent condensing

##        project_children_bin = ET.SubElement(children, 'bin')
##        name = ET.SubElement(project_children_bin, 'name')
##        name.text = 'Assets'
##        children = ET.SubElement(project_children_bin, 'children')
##        children.tail = ' '  #prevent condensing
        
        for cookie in self.items:
            item = self.items[cookie]

            if item["Type"] == "edit":
                # Describes an edited sequence.

                doc, tag, text = Doc().tagtext()

                with tag('sequence', id='sequence-%s' % uid):
                    uid += 1
                    with tag('rate'):
                        with tag('timebase'):
                            text('30')
                        with tag('ntsc'):
                            text('TRUE')
                    with tag('name'):
                        text(self.metadata['PROJECT_NAME'])
                    with tag('media'):
                        with tag('video'):
                            with tag('format'):
                                with tag('samplecharacteristics'):
                                    with tag('rate'):
                                        with tag('timebase'):
                                            text('30')
                                        with tag('ntsc'):
                                            text('TRUE')
                                    with tag('width'):
                                        text('1920')
                                    with tag('height'):
                                        text('1080')
                                    with tag('anamorphic'):
                                        text('FALSE')
                                    with tag('pixelaspectratio'):
                                        text('square')
                                    with tag('fielddominance'):
                                        text('none')
                                    with tag('colordepth'):
                                        text('24')

                            with tag('track'):
                                edits = item['.ed5'].edit_cells
                                self.fixEdits(edits)

                                for c in edits:
                                    if c['reel'] == 'BL':
                                        # black frame
                                        pass
                                    else:
                                        id_clipitem = 'clipitem-%s' % uid
                                        uid += 1
                                        with tag('clipitem', id=id_clipitem):
                                            with tag('start'):
                                                text('1')
                                            with tag('end'):
                                                text('11')
                                            with tag('in'):
                                                text('21')
                                            with tag('out'):
                                                text('31')
                                            doc.stag('file', id='file-%s' % c['reel'])
                                            with tag('link'):
                                                with tag('linkclipref'):
                                                    text(id_clipitem)
                                                with tag('mediatype'):
                                                    text('video')
                                                with tag('trackindex'):
                                                    text('1')
                                                with tag('clipindex'):
                                                    text('1')

##                                            b.reel = c['reel']
##                                            b.channels = c['track']
##                                            b.transition = 'C'
##                                            #b.transDur = ?
##                                            b.srcIn = c['src_in']
##                                            b.srcOut = c['src_out']
##                                            b.recIn = c['rec_in']
##                                            b.recOut = c['rec_out']
##                                            #c['aud'], c['from_clip']

                children.append( ET.fromstring(doc.getvalue()) )

            elif item["Type"] == "shot":
                # Describes a video clip.
                # Tested by importing into Premiere CS6.
                # Elements and values below are required; Pre will crash or
                #  simply fail to see the clip otherwise.
                # P requires certain elements, even if empty.
                # P requires 'id' attribute on some elements, but not all.
                
                doc, tag, text = Doc().tagtext()

                ed5 = item['.ed5'].EHP
                keys = ed5.keys()
                files = set()
                for k in keys:
                    if k.startswith("ORIGINAL_FILE_"):
                        files.add(ed5[k])
                if len(files) == 0:
                    logging.error('cookie has zero files: %s' % item["Cookie"])
                    filepath = ""
                elif len(files) > 1:
                    logging.error('cookie has many files: %s => %s' % [item["Cookie"], files])
                    filepath = next(iter(files))
                else:
                    filepath = next(iter(files))

                if len(filepath) > 0:
                    filepath = pathlib.Path(filepath).as_uri()

                with tag('clip', id=item['Cookie']):
                    with tag('ismasterclip'):
                        text('TRUE')
                    with tag('rate'):
                        with tag('timebase'):
                            text('30')
                        with tag('ntsc'):
                            text('TRUE')
                    with tag('name'):
                        text(item['Cookie'])

                    with tag('media'):
                        with tag('video'):
                            with tag('track'):
                                with tag('clipitem', id='clipitem-%s' % uid):
                                    uid += 1
                                    with tag('file', id='file-%s' % item['Cookie']):
                                        with tag('pathurl'):
                                            text(filepath)
                                        with tag('media'):
                                            with tag('video'):
                                                text(' ')
                                            with tag('audio'):
                                                text(' ')

                children.append( ET.fromstring(doc.getvalue()) )

            else:
                logging.error('unknown asset type %s' % item["Type"])
        
        return ET.ElementTree(root)


class LW_Item:
    """quickie class to hunt for a better way to wrap things together"""

    def __init__(self, data, filename):
        self.filename = filename

        self.data = data
        """dict key->value"""
        self.cookie = data['Cookie']
        """What LightWorks calls this thing."""

        seg_file = os.path.join(directory, '%s.ed5' % cookie)
        self.ed5 = ed5decode.ED5(seg_file)
        """ed5decode.ED5 object, decoded from filename"""


if __name__ == '__main__':
    odb = LW_ODB(".ignore\Ep6_Sc3-Archive.Archive\summary.odb")
##    edl = odb.makeEDL()
##    edl.savePremiere()

    et = odb.makeFcpxml()
    xmlstr = minidom.parseString(ET.tostring(et.getroot())).toprettyxml(indent="  ")
    with open("output.xml", "wt") as f:
        f.write(xmlstr)
