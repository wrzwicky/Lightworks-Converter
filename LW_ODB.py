#!/usr/bin/python3

import csv, logging, os, pprint
import ed5decode
import EDL


# *.odb file from LightWorks
# Plain text, structure is pretty self evident.
class LW_ODB:

    def __init__(self, filename):
        self.filename = filename
        self.metadata = {}
        self.flens = None
        """list of field lengths"""
        self.ftypes = None
        """list of field types"""
        self.fnames = None
        """list of field names"""
        self.fnum = None
        """map from field name to field index"""
        self.items = {}
        """rows = map from Cookie to dict of fname/value"""

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

    def makeEDL(self):
        for cookie in self.items:
            item = self.items[cookie]
            if item["Type"] == "edit":
                itemdata = item['.ed5'].EHP
                e = EDL.EDL()
                e.title = self.metadata['PROJECT_NAME']

                edits = item['.ed5'].edit_cells
                num = 1
                for c in edits:
                    b = EDL.EDLBlock()
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



class LW_Item:
    ## temp class to hunt for something better
    #self.cookie
    #self.data #dict key->value
    #self.ed5  #ed5decode.ED5 object

    def __init__(self, data, filename):
        self.filename = filename

        self.data = data
        self.cookie = data['Cookie']

        seg_file = os.path.join(directory, '%s.ed5' % cookie)
        self.ed5 = ed5decode.ED5(seg_file)


if __name__ == '__main__':
    odb = LW_ODB("Ep6_Sc3-Archive.Archive\summary.odb")
    edl = odb.makeEDL()
    e.savePremiere()


##    for cookie in odb.items:
##        item = odb.items[cookie]
##        if item["Type"] == "shot":
##            itemdata = item['.ed5'].EHP
##            keys = itemdata.keys()
##            files = set()
##            for k in keys:
##                if k.startswith("ORIGINAL_FILE_"):
##                    files.add(itemdata[k])
##            if len(files) == 0:
##                print(cookie, " => NOTHING!")
##            elif len(files) > 1:
##                print("ERROR: ", cookie, " => ", files)
##            else:
##                f = next(iter(files))
##                print(cookie, " => ", f)
##        else:
##            print("edit ", cookie)
