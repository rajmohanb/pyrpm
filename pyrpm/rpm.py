# -*- coding: iso-8859-15 -*-
# -*- Mode: Python; py-ident-offset: 4 -*-
# vim:ts=4:sw=4:et
'''
PyRPM
=====

PyRPM is a pure python, simple to use, module to read information from a RPM file.

$Id$
'''
__revision__ = '$Rev$'[6:-2]

from StringIO import StringIO
from cStringIO import StringIO
import struct
from pyrpm import rpmdefs
import re

HEADER_MAGIC_NUMBER = re.compile('(\x8e\xad\xe8)')

def find_magic_number(regexp, data):
    ''' find a magic number in a buffer
    '''
    string = data.read(1)
    while True:
        match = regexp.search(string)
        if match:
            data.seek(-3, 1)
            return True
        byte = data.read(1)
        if not byte:
            return False
        else:
            string += byte
    return False

class Entry(object):
    ''' RPM Header Entry
    '''
    def __init__(self, entry, store):
        self.entry = entry
        self.store = store

        self.switch = { rpmdefs.RPM_DATA_TYPE_CHAR:            self.__readchar,
                        rpmdefs.RPM_DATA_TYPE_INT8:            self.__readint8,
                        rpmdefs.RPM_DATA_TYPE_INT16:           self.__readint16,
                        rpmdefs.RPM_DATA_TYPE_INT32:           self.__readint32,
                        rpmdefs.RPM_DATA_TYPE_INT64:           self.__readint64,
                        rpmdefs.RPM_DATA_TYPE_STRING:          self.__readstring,
                        rpmdefs.RPM_DATA_TYPE_BIN:             self.__readbin,
                        rpmdefs.RPM_DATA_TYPE_STRING_ARRAY:    self.__readstringarray,
                        rpmdefs.RPM_DATA_TYPE_I18NSTRING_TYPE: self.__readstring}

        self.store.seek(entry[2])
        self.value = self.switch[entry[1]](entry[3])
        self.tag = entry[0]

    def __str__(self):
        return "(%s, %s)" % (self.tag, self.value, )

    def __repr__(self):
        return "(%s, %s)" % (self.tag, self.value, )

    def __readfmt(self, fmt):
        size = struct.calcsize(fmt)
        data = self.store.read(size)
        return struct.unpack(fmt, data)

    def __readchar(self, data_count):
        ''' store is a pointer to the store offset
        where the char should be read
        '''
        return self.__readfmt('!{0:d}c'.format(data_count))

    def __readint8(self, data_count):
        ''' int8 = 1byte
        '''
        return self.__readchar(data_count)

    def __readint16(self, data_count):
        ''' int16 = 2bytes
        '''
        return self.__readfmt('!{0:d}h'.format(data_count))

    def __readint32(self, data_count):
        ''' int32 = 4bytes
        '''
        return self.__readfmt('!{0:d}i'.format(data_count))

    def __readint64(self, data_count):
        ''' int64 = 8bytes
        '''
        return self.__readfmt('!{0:d}q'.format(data_count))

    def __readstring(self, data_count):
        ''' read a string entry
        '''
        string = ''
        while True:
            char = self.__readchar(1)
            if char[0] == '\x00': # read until '\0'
                break
            string += char[0]
        return string
    
    def __readstringarray(self, data_count):
        ''' read a array of string entries
        '''
        array = []
        for i in range(0, data_count):
            array.append(self.__readstring(1))
        return array

    def __readbin(self, data_count):
        ''' read a binary entry
        '''
        return self.__readfmt('!{0:d}s'.format(data_count))


class Header(object):
    ''' RPM Header Structure
    '''
    def __init__(self, header, entries , store):
        '''
        '''
        self.header = header
        self.entries = entries
        self.store = store
        self.pentries = []
        self.rentries = []

        self.__readentries()


    def __readentry(self, entry):
        ''' [4bytes][4bytes][4bytes][4bytes]
               TAG    TYPE   OFFSET  COUNT
        '''
        return struct.unpack("!4l", entry)

    def __readentries(self):
        ''' read a rpm entry
        '''
        for entry in self.entries:
            entry = self.__readentry(entry)
            #if (entry[0] >= rpmdefs.RPMTAG_MIN_NUMBER and entry[0] <= rpmdefs.RPMTAG_MAX_NUMBER) or \
            #    (entry[0] >= rpmdefs.RPMTAGEX_MIN_NUMBER and entry[0] <= rpmdefs.RPMTAGEX_MAX_NUMBER):
            self.pentries.append(entry)

        for pentry in self.pentries:
            entry = Entry(pentry, self.store)
            if entry:
                self.rentries.append(entry)

class RPMError(BaseException):
    pass

class RPM(object):

    def __init__(self, rpm):
        ''' rpm - StringIO.StringIO | file
        '''
        if hasattr(rpm, 'read'): # if it walk like a duck..
            self.rpmfile = rpm
        else:
            raise ValueError('invalid initialization: '
                             'StringIO or file expected received %s'
                                 % (type(rpm), ))
        self.binary = None
        self.source = None
        self.header = None
        self.signature = None
        
        self.__readlead()
        self.__read_signature()
        self.__read_header()

    def __readlead(self):
        ''' reads the rpm lead section

            struct rpmlead {
               unsigned char magic[4];
               unsigned char major, minor;
               short type;
               short archnum;
               char name[66];
               short osnum;
               short signature_type;
               char reserved[16];
               } ;
        '''
        lead_fmt = '!4sBBhh66shh16s'
        data = self.rpmfile.read(96)
        value = struct.unpack(lead_fmt, data)

        magic_num = value[0]
        ptype = value[3]

        if magic_num != rpmdefs.RPM_LEAD_MAGIC_NUMBER:
            raise RPMError('wrong magic number this is not a RPM file')

        if ptype == 1:
            self.binary = False
            self.source = True
        elif ptype == 0:
            self.binary = True
            self.source = False
        else:
            raise RPMError('wrong package type this is not a RPM file')


    def __read_signature(self):
        ''' read signature header
        '''
        found = find_magic_number(HEADER_MAGIC_NUMBER, self.rpmfile)
        if not found:
            raise RPMError('invalid RPM file, signature area not found')
        
        # consume signature area
        header = self.__read_header_structure()
        sigs = [self.rpmfile.read(16) for i in range(header[3])]
        sigs_store = StringIO(self.rpmfile.read(header[4]))
        self.signature = Header(header, sigs, sigs_store)

    def __read_header(self):
        ''' read information headers
        '''
        # lets find the start of the header
        found = find_magic_number(HEADER_MAGIC_NUMBER, self.rpmfile)
        if not found:
            raise RPMError('invalid RPM file, header not found')
        
        # consume header area
        header = self.__read_header_structure()
        entries = [self.rpmfile.read(16) for i in range(header[3])]
        entries_store = StringIO(self.rpmfile.read(header[4]))
        self.header = Header(header, entries, entries_store)


    def __read_header_structure(self):
        ''' reads the header-header section
        [3bytes][1byte][4bytes][4bytes][4bytes]
          MN      VER   UNUSED  IDXNUM  STSIZE
        '''
        header = struct.unpack('!3sc4sll', self.rpmfile.read(16))
        if header[0] != rpmdefs.RPM_HEADER_MAGIC_NUMBER:
            raise RPMError('invalid RPM header')
        return header
    

    def __iter__(self):
        for entry in self.header.rentries:
            yield entry

    def __getitem__(self, item):
        for entry in self:
            if entry.tag == item:
                if entry.value and isinstance(entry.value, str):
                    return entry.value

    def name(self):
        return self[rpmdefs.RPMTAG_NAME]

    def package(self):
        name = self[rpmdefs.RPMTAG_NAME]
        version = self[rpmdefs.RPMTAG_VERSION]
        return '-'.join([name, version, ])

    def filename(self):
        package = self.package()
        release = self[rpmdefs.RPMTAG_RELEASE]
        name = '-'.join([package, release, ])
        arch = self[rpmdefs.RPMTAG_ARCH]
        if self.binary:
            return '.'.join([name, arch, 'rpm', ])
        else:
            return '.'.join([name, arch, 'src.rpm', ])
