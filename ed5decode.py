#!/usr/bin/env python3

"""
"ed5decode" -- access to lightworks logging database
    
Copyright (C) 2014  Martin Schitter <ms+lwks@mur.at>

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

import sys, struct, re, logging, os, glob, argparse, time, ntpath
import xml.etree.ElementTree as ET
from xml.dom import minidom

VERSION = '0.2'

class ED5:

    def __init__(self, filename):

        self.childs = [] # a list of segments
        self.filename = filename
        self.edit_cells = []
        self.EHP = {}
        self.title = None
        self.fps = 0 
        
        f = open(filename, 'rb')
        data = f.read()
        f.close()
        
        self.childs = Segment.segments_from_data(data, self)

    def proj_info(self):
        "read framerate and title from project ed5 file"
        
        proj_c = self.EHP['PROJECT_COOKIE']
        directory = os.path.dirname(os.path.abspath(self.filename))
        proj_file = os.path.join(directory, 'O%s.odb' % proj_c[1:])
        if not os.access(proj_file, os.F_OK):
            logging.error('can not read project info (%s)' % proj_file)
            self.title = 'unknown'
        else:
            p_f = open(proj_file)
            for l in p_f.readlines():
                l.strip()
                if l.find('PROJECT_NAME') != -1:
                    self.title = l[14:-2]
                if l.find('PROJECT_RATE') != -1:
                    self.fps = int(l[14:-2])
                    break
            p_f.close()

    def export_preparation(self):
        "preprocessing that is common for any export format"

        if not self.title:
            self.proj_info()
            
        
        if not self.edit_cells:
            logging.error('no edit data found')
            return 0

        # merge pair of cells
        num =  len(self.edit_cells)
        if num % 2:
            logging.error('odd number of edit cells')
            return 0
        else:
            for n in range(num-1, 0, -2):
                self.edit_cells[n-1]['src_out'] = self.edit_cells[n]['src_out']
                self.edit_cells[n-1]['rec_out'] = self.edit_cells[n]['rec_out']
                del self.edit_cells[n]
        return num
            
    def mlt(self, mlt_filename):
        "dump the edit as MLT XML"

        if not self.export_preparation():
            return

        et = ET.Element('mlt')
                
        #find all producers
        producers={}
        for c in self.edit_cells:
            if c['reel'] in ['BL', 'dissolve']:
                continue
            if c['reel'] not in producers.keys():
                    d = os.path.dirname(os.path.abspath(self.filename))
                    e = ED5(os.path.join(d, '%s.ed5' % c['reel']))
                    match = list(filter(lambda x: x.startswith(
                        'ORIGINAL_FILE'), e.EHP.keys()))
                    if match:
                        path = e.EHP[match[0]]
                        if path.startswith('\\'):
                            base = ntpath.basename(path)
                        else:
                            base = os.path.basename(path)
                        #if search_dir:
                        #    path = os.path.join(search_dir, base)
                        if not os.access(path, os.F_OK):
                            patern = os.path.join(d, '[SV]%s.*' % c['reel'][1:])
                            arch_fallback = glob.glob(patern)
                            if len(arch_fallback) == 1:
                                path = arch_fallback[0]
                                logging.warning(
                                    'using shot from archive (%s = %s)'
                                    % (base, os.path.basename(path)))
                            else:
                                logging.warning('clip not found %s' %
                                                path)

                        producers[c['reel']] = path
                        et_prod = ET.SubElement(et, 'producer',
                                                id=c['reel'])
                        et_prop = ET.SubElement(et_prod, 'property',
                                                name='resource')
                        et_prop.text = path
                    else:
                        logging.error('did not find path for "%s"',
                                      c['reel'])
                        producers[c['reel']] = None
                        
        # merge related cuts
        [ a != b 
        and a['reel']    == b['reel']    
        and a['src_in']  == b['src_in']  
        and a['src_out'] == b['src_out'] 
        and a['rec_in']  == b['rec_in']  
        and a['rec_out'] == b['rec_out'] 
        
        and not a.update(track=a['track']+' '+b['track'])
        and not self.edit_cells.remove(b)
        
        for a in self.edit_cells
        for b in self.edit_cells]
            

        # add to channel
        channels= {}
        for c in self.edit_cells:
            v_tracks = re.findall('V[0-9]', c['track'])
            a_tracks = re.findall('A[0-9]', c['track'])
                             
            if v_tracks:
                if v_tracks[0] not in channels.keys():
                    channels[v_tracks[0]] = [c]
                else:
                    channels[v_tracks[0]].append(c)

        # add to xml
        for channel in channels.keys():
            et_pl = ET.SubElement(et, 'playlist', id=channel)
            for c in channels[channel]:
                 et_ent = ET.SubElement(et_pl, 'entry', {
                                       'producer': c['reel'],
                                       'in': "%d"%round(c['src_in']*self.fps),
                                       'out':"%d"%round(c['src_out']*self.fps)
                                       })
                
        # write xml
        raw = ET.tostring(et, encoding="unicode")
        reparsed = minidom.parseString(raw)
        pretty = reparsed.toprettyxml(indent="  ")
        
        if mlt_filename == '-':
            print(pretty)
        else:
            f = open(mlt_filename, 'w')
            f.write(pretty)
            f.close()
                    
        
    def edl(self, edl_filename, filename_as_reel , gvg_format=False):
        "dump the edit information as EDL"
 
        # EDL format specifications:
        # http://www.editware.com/Editware-DOCs/EDLformat.PDF
        # http://xmil.biz/EDL-X/CMX3600.pdf
        
        if not self.export_preparation():
            return

        # ignore out of bound channels
        err = {}
        for c in self.edit_cells[:]:
            if c['track'] not in 'V1 V2 A1 A2 A3 A4'.split():
                if c['track'] not in err.keys():
                    logging.error('channel %s invalid in EDL' % c['track'])
                self.edit_cells.remove(c)
                err[c['track']] = None
                
        # merge related cuts
        [ a != b 
        and a['reel']    == b['reel']    
        and a['src_in']  == b['src_in']  
        and a['src_out'] == b['src_out'] 
        and a['rec_in']  == b['rec_in']  
        and a['rec_out'] == b['rec_out'] 
        
        and not a.update(track=a['track']+' '+b['track'])
        and not self.edit_cells.remove(b)
        
        for a in self.edit_cells
        for b in self.edit_cells]

        # channel notation
        for c in self.edit_cells:
            c['aud'] = ''
            
            if gvg_format:
                if c['track'].find('V1') != -1:
                    c['track'] = c['track'].replace('V1','V')
                x = c['track'].split()
                x.sort()
                c['track'] = ''.join(x)
                c['track'] = c['track'][:1] + c['track'][1:].replace('A','')
                c['track'] = c['track'].ljust(6)
            else:
                tracks = set(c['track'].strip().split())
                if 'V2' in tracks:
                    tracks.remove('V2')
                    tracks.add('V1')
                
                tracks34 = tracks & {'A3', 'A4'}
                tracks12V = tracks & {'A1', 'A2', 'V1'}
                
                if tracks34 == {'A3'}:
                    c['aud'] = '\nAUD  3   '
                elif tracks34 == {'A4'}:
                    c['aud'] = '\nAUD  4   '
                elif tracks34 == {'A3', 'A4'}:
                    c['aud'] = '\nAUD  3  4'

                if not tracks12V:
                    c['track'] = 'NONE'
                elif tracks12V == {'A1'}:
                    c['track'] = 'A   '
                elif tracks12V == {'A1', 'V1'}:
                    c['track'] = 'B   '
                elif tracks12V == {'V1'}:
                    c['track'] = 'V   '
                elif tracks12V == {'A2'}:
                    c['track'] = 'A2  '
                elif tracks12V == {'A2', 'V1'}:
                    c['track'] = 'A2/V'
                elif tracks12V == {'A1', 'A2'}:
                    c['track'] = 'AA  '
                elif tracks12V == {'A1', 'A2', 'V1'}:
                    c['track'] = 'AA/V'

        # edl numbering and operation code
        num = 1
        for c in self.edit_cells:
            if not 'duration' in c.keys():
                c['duration'] = '   '
            if not 'operation' in c.keys():
                c['operation'] = 'C   '
            if gvg_format:
                c['number'] = '%04d' % num
            else:
                c['number'] = '%03d' % num
            if c['reel']  == 'dissolve':
                next_c = self.edit_cells[self.edit_cells.index(c) +1]
                next_c['duration'] = '%03d' % round(c['src_out'] * self.fps)
                next_c['rec_in'] = c['rec_in']
                next_c['operation'] = 'D   '
                if gvg_format:   
                    next_c['number'] = '%04d' % (num - 1)
                else:
                    next_c['number'] = '%03d' % (num - 1)
                self.edit_cells.remove(c)
            else:
                num += 1

        # a-mode sorting
        events = {}
        for c in self.edit_cells:
            if c['number'] not in events.keys():
                events[c['number']] = [c['number'],c['rec_in'],[c]]
            else:
                events[c['number']][2].append(c)
        sort_list = list(events.values())
        sort_list.sort(key=lambda x: x[1])
        new_cells = []
        for n, x in enumerate(sort_list):
            for c in x[2]:
                if gvg_format:
                    c['number'] = '%04d' % n
                else:
                    c['number'] = '%03d' % n
                new_cells.append(c)
        self.edit_cells = new_cells
        
                
                
        if 'name' in self.EHP:
            edit_name = self.EHP['name'].split(' ', 3)[-1]
        else:
            edit_name = 'unknown edit'

        output = []
        output.append('TITLE: %s -- %s (%s) FRAMERATE: %d' % (
            self.title, edit_name, os.path.basename(self.filename), self.fps))
        if gvg_format:
            output.append('GVG EDL [WARNING: ONLY 6 BYTES OF COOKIES USED]')
            output.append('SMPTE FRAME CODE')
        output.append('')

        reels = {}              
        for c in self.edit_cells[:]:
            for n in ['src_in', 'src_out', 'rec_in', 'rec_out']:
                if n in c.keys():
                    c[n+'_hmsf'] = t2hmsf(c[n], self.fps)
                    
            if c['reel'] == 'BL' and gvg_format:
                c['reel'] == 'BLK'
                    
            # clip names as reel
            if c['reel'] not in ['UNKNOWN', 'BLK', 'BL']:
                #if not c['reel'] in reels.keys():
                    d = os.path.dirname(os.path.abspath(self.filename))
                    e = ED5(os.path.join(d, '%s.ed5' % c['reel']))
                    match = list(filter(lambda x: x.startswith(
                        'ORIGINAL_FILE'), e.EHP.keys()))
                    if match:
                        name = e.EHP[match[0]]
                        if name.startswith('\\'):
                            base = ntpath.basename(name)
                        else:
                            base = os.path.basename(name)

                        base = os.path.basename(name.replace('\\','/'))
                        short = base.split('.',-1)[0].replace(' ', '_')
                        if filename_as_reel:
                            if gvg_format and len(short) > 6:
                                logging.warning('filename to long for EDL: %s'
                                                % base)
                                reels[c['reel']] = c['reel'][2:]
                            elif len(short) > 8:
                                logging.warning('filename to long for EDL: %s'
                                                % base)
                                reels[c['reel']] = c['reel']
                            else:
                                reels[c['reel']] = short
                        else:
                            if gvg_format:
                                reels[c['reel']] = c['reel'][2:]
                            else:
                                reels[c['reel']] = c['reel']
                        c['from_clip'] = '\n* FROM CLIP NAME: %s' % base
                        c['reel'] = 'AX'
            if not 'from_clip' in c.keys():
                c['from_clip'] =''
            if c['reel'] in reels.keys():
                c['reel'] = reels[c['reel']]
                
            if gvg_format:
                output.append(' '.join([
                    c['number'], c['reel'].ljust(6), c['track'],
                    c['operation'], c['duration'],
                    c['src_in_hmsf'], c['src_out_hmsf'],
                    c['rec_in_hmsf'], c['rec_out_hmsf'],
                    c['aud'], c['from_clip']
                    ]))
            else:
                output.append(' '.join([
                    c['number'],'', c['reel'].ljust(8),'', c['track'],'',
                    c['operation'], c['duration'],
                    c['src_in_hmsf'], c['src_out_hmsf'],
                    c['rec_in_hmsf'], c['rec_out_hmsf'],
                    c['aud'], c['from_clip']
                    ]))
                
        output.append('')
        if edl_filename == '-':
            sys.stdout.write('\n'.join(output))
        else:
            f = open(edl_filename, 'w')
            f.write('\n'.join(output))
            f.close()

    def fcpxml(self, fcp_filename):
        "dump the edit as Final Cut XML"
        pass

            
class Segment:

    def segments_from_data(data, parent):
        'return a list of Segments instances from raw data'

        segments = []
        while data:
            
            # catch alignment errors
            if not data.startswith(b'$\0'):
                logging.error("magic sequence not found")
                sys.exit(1)
                
            label, flags, a, b, head_len, tail = read_segment(data)
            
            dprint('-'*5, 'segment_nr:', len(segments), '-'*35)
            
            segments.append(Segment(data[:head_len+b], parent))
            data = data[head_len+b:]
        return segments
    
    def __init__(self, data, parent):

        self.parent = parent
        self.childs = []
        
        label, flags, a, b, head_len, tail = read_segment(data)

        if isdebug():
            print('segment label: %s\tflags: %s,\t(b=) len: %d' %
                (label, flags, b))
            hexdump(data, n=head_len)

            dprint('subsegment index len (a=): %d' % a )
            hexdump(tail, n=a)

        subsegment_data = tail[a:]
        self.childs = Subsegment.subsegments_from_data(subsegment_data, self) 
        
        
class Subsegment:

    def subsegments_from_data(data, parent):
        'return a list of Subsegments instances from raw data'

        subsegments = []
        
        while data:
            label, flags, a, b, head_len, tail = read_segment(data)
            subsegments.append(Subsegment(data[:head_len+a], parent))          
            data = data[head_len+a:]
        return subsegments

    def __init__(self, data, parent):

        self.parent = parent
        self.childs = []
        
        label, flags, a, b, head_len, tail = read_segment(data)
        self.label = label
        
        if isdebug():
            print ('subsegment -- label: %s, flags %s, (a=) len: %d, b: %d'
                    % (label, flags, a, b))
            hexdump(data, n=head_len)
        if label == b'EHP':
            self.label_EHP(tail)
        elif label == b'T':
            self.T = tail[1:-1]
            dprint('T -- %s' % self.T)
        elif label == b'A':
            self.label_A(tail)
        elif label == b'C':
            self.label_C(tail)
        else:
            if isdebug():            
                print("unsupported segment:", label)
                hexdump(tail)

    def label_EHP(self, tail):
            unknown=tail[:2]
            count = struct.unpack('i', tail[2:6])[0]
            dprint('EHP -- unknown: %s, c: %d' % (unknown, count))
            parts=tail[6:].split(b'\0')
            idx = 0
            while idx+2 < len(parts):
                name = parts[idx]
                value = parts[idx+1]
                typ = parts[idx+2]
                idx += 3
                dprint(name, ':', value, ':', typ)
                self.parent.parent.EHP[name.decode()] = value.decode()
                  
    def label_A(self, tail):
            num_str = tail[:4]
            tail = tail[4:]
            num = struct.unpack('i', num_str)[0]
            dprint('A -- num:', num)
            while tail:
                t = struct.unpack('d', tail[:8])[0]
                unknown1 = ' '.join(map(lambda x: "%02x" % x, tail[8:11]))
                gain = struct.unpack('I', tail[11:15])[0]
                unknown2 = ' '.join(map(lambda x: "%02x" % x, tail[15:21]))
                tail = tail[21:]
                dprint('t=%03.2f\t[%s] gain=%3.1f\t [%s]'
                      % (t, unknown1, int2db(gain), unknown2))

                
    def label_C(self, tail):

        first_byte=tail[:1] # allways 2 (?)
        ref, track,sub, sub2, tail = tail[1:].split(b'\0', 4)
        if isdebug():
            print('first_byte:', first_byte)
            print('ref:', ref)
            print('track:', track)
            print('sub:', sub)
            print('sub2:', sub2)
            hexdump(tail[:12])
        t, num = struct.unpack('dI', tail[:12])
        dprint('t:', t, 'num:', num)
        tail = (tail[12:])
        #hexdump(tail)
        while tail:
            if isdebug():
                print('jump over offset: ', 17)
                hexdump(tail[:17])
            a, b = struct.unpack('II', tail[:8])
            dprint('a:', a, 'b:', b, '(a+b == num)')
            if b == 0xf0000000:
                if isdebug():
                    print('no usual edit...')
                    hexdump(tail)
                tail = b''
            #### 17 bytes unknown 
            tail = tail[17:]
            
            # num times edit information of 64 byte length
            while tail:
                dprint('--------------------------------------')
                data = tail[:0x40]
                tail = tail[0x40:]

                edit = { 'track': track.decode()}
                
                # unknown floats
                x, speed = struct.unpack('ff',data[8:16])
                edit['speed'] = speed
                if isdebug():
                    print('x: %f\tspeed: %f' % (x, speed))
                    hexdump(data[:16])

                t1, t2 = struct.unpack('dd', data[16:32])
                # 1 or 4 at byte 28-32 denote in/out time 
                t_sel = struct.unpack('i', data[44:48])[0]
                if t_sel == 1:
                    edit['rec_in'] = t1
                    edit['src_in'] = t2
                    dprint('Rec IN: %.2f   Src IN: %.2f' % (t1, t2))
                elif t_sel == 4:
                    edit['rec_out'] = t1
                    edit['src_out'] = t2
                    dprint('Rec OUT: %.2f  Src OUT: %.2f' % (t1, t2))
                else:
                    logging.error('time selector "0x%x" unknown' % t_sel)
                if isdebug():
                    hexdump(data[16:])

                #reel 
                r = struct.unpack('i', data[32:36])[0]
                if r == 1:
                    reel = 'BL'
                elif r == 0xb655:
                    reel = 'dissolve'
                else:
                    directory = os.path.dirname(os.path.abspath(
                        self.parent.parent.filename))
                    reel = int2reel(r, directory)
                edit['reel'] = reel
                    
                #type of edit
                scope = chr(data[42])
                edit['scope'] = scope 
                                
                dprint('Reel: %s\tType of Edit: %c' % (reel, scope)) 

                #EDL IDs
                id1, id2 = struct.unpack('ii', data[52:60])
                edit['id1'] = id1
                edit['id2'] = id2
                dprint('ID-1: %d\t ID-2: %d' % (id1, id2))

                self.parent.parent.edit_cells.append(edit)
                    

def read_segment(data):
    'read one segment out of a list'
    label, tail = data.split(b'\0', 1)
    flags = tail[:2]
    a, b = struct.unpack('ii', tail[2:10])
    tail = tail[10:]
    head_len = len(label) + 11
    return label, flags, a, b, head_len, tail

def t2hmsf(t, fps):
    "get string from seconds for EDL"
    
    sec, frac = divmod(t,1)
    ff=round(frac*fps)
    t_str = time.strftime('%H:%M:%S', time.gmtime(sec))
    t_str += ':%02d' % ff
    return t_str
            
def int2reel(num, directory):
    'find existing cookie for numeric ID'
    
    b36 = base36(num)
    b36 = '0' * (4 - len(b36)) + b36
    p = os.path.join(directory, '*%s.ed5' % b36)
    match = glob.glob(p)
    if len(match) != 1:
        logging.error('did not find uniq cookie "*%s" in %s' %
                      (b36, directory))
        return 'UNKNOWN'
    else:
        return os.path.basename(match[0])[:-4]

    
def base36(num):
    'translate number to base36 string'

    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    base36 = '' 
    while num:
        num, i = divmod(num, 36)
        base36 = alphabet[i] + base36
    return base36 or '0'
        
    
def int2db(num):
    # does not work very well... :(
    return (num - 0xf0000000)/10240000.0

def isdebug():
    'return true if debugging is enabled' 
    return logging.getLogger().isEnabledFor(logging.DEBUG)

def dprint(*args):
    'print if debugging is enabled'

    if isdebug():
        print(*args)
    
def hexdump(data, offset=0, n=None):

    if len(data) < offset:
        return
    data = data[offset:]
    if n:
        data = data[:n]
    while data:
        line = data[:16]
        data = data[16:]

        str2 = ' '.join(map(lambda x: "%02x" % x, line))
        str3 = ''.join(map(lambda x: chr(x).isprintable()
                           and chr(x) or '.', line))
        print('%04x  %s %s' % (offset, str2.ljust(50), str3.encode('utf8')))
        offset += 16
    
def main():
    parser = argparse.ArgumentParser(description='analyze .ed5 files')
    parser.add_argument('--version', action='version',
                         version='%(prog)s: ' + VERSION)
    parser.add_argument('-d', '--debug', action='store_true' )
    parser.add_argument('files', metavar='FILE', nargs='+' )

    parser.add_argument('-m', '--mlt', metavar='FILE',
                        help='export as MLT XML (use "-" for stdout)')
    parser.add_argument('-e', '--edl', metavar='FILE',
                        help='export as EDL (use "-" for stdout)')
    parser.add_argument('-x', '--fcpxml', metavar='FILE',
                        help='export as Final Cut XML (use "-" for stdout)')

    parser.add_argument('-c', '--clipnames', action='store_true',
                        help='use clipname as reel in EDL')
    parser.add_argument('-g', '--gvg-edl', action='store_true',
                        help='grass valley group EDL format')

    args = parser. parse_args()
    #print('ARGS:', args)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

##    if args.edl and args.mlt and args.fcpxml:
##        logging.error('you can use only one export format')
##        sys.exit(0)
    
    for f in args.files:
        ed5 = ED5(f)

        if args.edl:
            ed5.edl(args.edl, args.clipnames, args.gvg_edl)
        if args.mlt:
            ed5.mlt(args.mlt)
        if args.fcpxml:
            ed5.fcpxml(args.fcpxml)
    
if __name__ == '__main__':
    main()
