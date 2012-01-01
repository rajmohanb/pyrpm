import gzip
import hashlib
import os
from xml.etree import ElementTree

from pyrpm.yum import YumPackage

class YumRepository(object):
    
    def __init__(self, repodir):
        self.repodir = repodir
        self.primary_data = {}
        self.filelists_data = {}
        self.other_data = {}
        
        # read repo
        self._read_repomd()
    
    def save(self):
        # write XML files
        self._write_primary()
        self._write_filelists()
        self._write_other()

        # write repomd to find xml files
        self._write_repomd()
    
    
    def packages(self):
        for key, value in self.primary_data.iteritems():
            yield (key, value, self.filelists_data[key], self.other_data[key])
    
    
    def add_package(self, package, clog_limit=0):
        pkgid = package.checksum
        
        self.primary_data[pkgid] = package.xml_primary_metadata()
        self.filelists_data[pkgid] = package.xml_filelists_metadata()
        self.other_data[pkgid] = package.xml_other_metadata(clog_limit)
    
    
    def remove_package(self, pkgid):
        for part in (self.primary_data, self.filelists_data, self.other_data):
            if pkgid in part:
                del part[pkgid]
    
    
    def _read_repomd(self):
        # open repomd to find xml files
        repomd_tree = ElementTree.parse(os.path.join(self.repodir, 'repodata/repomd.xml'))
        
        # read XML files
        for type, func in [('primary', self._read_primary), ('filelists', self._read_filelists), ('other', self._read_other)]:
            node = repomd_tree.find("{http://linux.duke.edu/metadata/repo}data[@type='" + type + "']")
            if node is not None:
                func(node.find('{http://linux.duke.edu/metadata/repo}location').get('href', None))
    
    
    def _read_primary(self, location):
        if not location:
            return
        
        # parse primary XML
        with gzip.GzipFile(os.path.join(self.repodir, location)) as primary_file:
            primary_tree = ElementTree.parse(primary_file)
        
        # read package nodes
        for pkg_node in primary_tree.findall("{http://linux.duke.edu/metadata/common}package"):
            # extract pkgid
            pkgid = pkg_node.find('{http://linux.duke.edu/metadata/common}checksum[@pkgid="YES"]').text
            self.primary_data[pkgid] = pkg_node
    
    
    def _read_filelists(self, location):
        if not location:
            return
        
        # parse primary XML
        with gzip.GzipFile(os.path.join(self.repodir, location)) as filelists_file:
            filelists_tree = ElementTree.parse(filelists_file)
        
        # read package nodes
        for pkg_node in filelists_tree.findall("{http://linux.duke.edu/metadata/filelists}package"):
            self.filelists_data[pkg_node.attrib['pkgid']] = pkg_node
    
    
    def _read_other(self, location):
        if not location:
            return
        
        # parse primary XML
        with gzip.GzipFile(os.path.join(self.repodir, location)) as other_file:
            other_tree = ElementTree.parse(other_file)
        
        # read package nodes
        for pkg_node in other_tree.findall("{http://linux.duke.edu/metadata/other}package"):
            self.other_data[pkg_node.attrib['pkgid']] = pkg_node
    

    def _write_primary(self):
        # create complete document
        tree = ElementTree.ElementTree(ElementTree.Element('{http://linux.duke.edu/metadata/common}metadata'))
        tree.getroot().set('packages', str(len(self.primary_data)))
        for pkg_node in self.primary_data.items():
            tree.getroot().append(pkg_node[1])
        
        # map namespaces
        ElementTree.register_namespace('rpm', 'http://linux.duke.edu/metadata/rpm')
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/common')
        
        # write it out
        with gzip.GzipFile(os.path.join(self.repodir, 'repodata/primary.xml.gz'), 'w') as primary_file:
            tree.write(primary_file, 'utf-8', True)
    
    
    def _write_filelists(self):
        # create complete document
        tree = ElementTree.ElementTree(ElementTree.Element('{http://linux.duke.edu/metadata/filelists}filelists'))
        tree.getroot().set('packages', str(len(self.filelists_data)))
        for pkg_node in self.filelists_data.items():
            tree.getroot().append(pkg_node[1])
        
        # map namespaces
        ElementTree.register_namespace('rpm', 'http://linux.duke.edu/metadata/rpm')
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/filelists')
        
        # write it out
        with gzip.GzipFile(os.path.join(self.repodir, 'repodata/filelists.xml.gz'), 'w') as primary_file:
            tree.write(primary_file, 'utf-8', True)
    
    
    def _write_other(self):
        # create complete document
        tree = ElementTree.ElementTree(ElementTree.Element('{http://linux.duke.edu/metadata/other}otherdata'))
        tree.getroot().set('packages', str(len(self.other_data)))
        for pkg_node in self.other_data.items():
            tree.getroot().append(pkg_node[1])
        
        # map namespaces
        ElementTree.register_namespace('rpm', 'http://linux.duke.edu/metadata/rpm')
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/other')
        
        # write it out
        with gzip.GzipFile(os.path.join(self.repodir, 'repodata/other.xml.gz'), 'w') as primary_file:
            tree.write(primary_file, 'utf-8', True)


    def _write_repomd(self):
        tree = ElementTree.ElementTree(ElementTree.Element("{http://linux.duke.edu/metadata/repo}repomd"))
        
        # compute file-stuff
        for type, filename in [('primary', 'repodata/primary.xml.gz'), ('filelists', 'repodata/filelists.xml.gz'), ('other', 'repodata/other.xml.gz')]:
            # compute open numbers (size, checksum)
            with gzip.GzipFile(os.path.join(self.repodir, filename)) as open_file:
                m = hashlib.sha256()
                open_size = 0
                data = open_file.read()
                while data:
                    open_size += len(data)
                    m.update(data)
                    data = open_file.read()
                open_checksum = m.hexdigest()
            
            # compute normal numbers
            with open(os.path.join(self.repodir, filename), 'rb') as normal_file:
                m = hashlib.sha256()
                normal_size = 0
                
                data = normal_file.read()
                while data:
                    normal_size += len(data)
                    m.update(data)
                    data = normal_file.read()
                normal_checksum = m.hexdigest()
            
            e = ElementTree.Element("{http://linux.duke.edu/metadata/repo}data", {'type': type})
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}checksum", {'type': 'sha256'}, text=normal_checksum)
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}size", text=str(normal_size))
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}open-checksum", {'type': 'sha256'}, text=open_checksum)
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}open-size", text=str(open_size))
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}location", {'href': filename})
            tree.getroot().append(e)
        
        # map namespaces
        ElementTree.register_namespace('rpm', 'http://linux.duke.edu/metadata/rpm')
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/repo')
        
        # write it out
        tree.write(open(os.path.join(self.repodir, 'repodata/repomd.xml'), 'wt'), encoding='utf-8', xml_declaration=True, method='xml')
    
    
    def _add_node(self, parent, tag, attrib={}, text=None):
            a = ElementTree.Element(tag, attrib)
            if text is not None:
                a.text = text
            parent.append(a)

if __name__ == '__main__':
    from pprint import pprint
    from pyrpm.yum import YumPackage
    
    repo = YumRepository("D:\\Projekte\\pyrpm\\temprepo")
    
    # add package
    repo.add_package(YumPackage(file(os.path.join(repo.repodir, 'tcl-devel-8.5.7-6.el6.x86_64.rpm'), 'rb')))
    
    # delete package
    #repo.remove_package('4d9c71201f9c0d11164772600d7dadc2cad0a01ac4e472210641e242ad231b3a')
    
    repo.save()