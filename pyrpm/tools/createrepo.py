import gzip
import hashlib
import os
import os.path
from xml.etree import ElementTree

# try to import the best StringIO
from StringIO import StringIO

from pyrpm.yum import YumPackage

class YumRepository(object):

    def __init__(self, repodir):
        self.repodir = repodir
        self.primary_data = {}
        self.filelists_data = {}
        self.other_data = {}

    def read(self):
        # open repomd to find xml files
        with self._retr_file('repodata/repomd.xml') as file:
            repomd_tree = ElementTree.parse(file)

        # read XML files
        for type, dictionary, node_filter, id_func in [
            ('primary', self.primary_data, "{http://linux.duke.edu/metadata/common}package", lambda x: x.find('{http://linux.duke.edu/metadata/common}checksum[@pkgid="YES"]').text),
            ('filelists', self.filelists_data, "{http://linux.duke.edu/metadata/filelists}package", lambda x: x.attrib['pkgid']),
            ('other', self.other_data,"{http://linux.duke.edu/metadata/other}package", lambda x: x.attrib['pkgid'])]:

            # find location
            node = repomd_tree.find("{http://linux.duke.edu/metadata/repo}data[@type='" + type + "']")
            if node is None:
                continue

            # parse file
            self._read_meta(node.find('{http://linux.duke.edu/metadata/repo}location').get('href', None), dictionary, node_filter, id_func)

    def save(self):
        # create XML files
        primary_file, primary_file_gz       = self._create_meta(self.primary_data, '{http://linux.duke.edu/metadata/common}metadata', 'http://linux.duke.edu/metadata/common')
        filelists_file, filelists_file_gz   = self._create_meta(self.filelists_data, '{http://linux.duke.edu/metadata/filelists}filelists', 'http://linux.duke.edu/metadata/filelists')
        other_file, other_file_gz           = self._create_meta(self.other_data, '{http://linux.duke.edu/metadata/other}otherdata', 'http://linux.duke.edu/metadata/other')

        # create repomd
        tree = ElementTree.ElementTree(ElementTree.Element("{http://linux.duke.edu/metadata/repo}repomd"))

        # compute file-stuff
        for type, file, file_gz, filename in [
            ('primary', primary_file, primary_file_gz, 'repodata/primary.xml.gz'),
            ('filelists', filelists_file, filelists_file_gz, 'repodata/filelists.xml.gz'),
            ('other', other_file, other_file_gz, 'repodata/other.xml.gz')]:

            # compute file numbers (size, checksum)
            open_size = file.tell()
            open_checksum = self._hash(file)
            normal_size = file_gz.tell()
            normal_checksum = self._hash(file_gz)

            # create XML
            e = ElementTree.Element("{http://linux.duke.edu/metadata/repo}data", {'type': type})
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}checksum", {'type': 'sha256'}, text=normal_checksum)
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}size", text=str(normal_size))
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}open-checksum", {'type': 'sha256'}, text=open_checksum)
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}open-size", text=str(open_size))
            self._add_node(e, "{http://linux.duke.edu/metadata/repo}location", {'href': filename})
            tree.getroot().append(e)

            # write files
            self._store_file(file_gz, filename)

            # close files
            file.close()
            file_gz.close()

        # map namespaces
        ElementTree.register_namespace('rpm', 'http://linux.duke.edu/metadata/rpm')
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/repo')

        # write everything out
        file = StringIO()
        tree.write(file, encoding='utf-8', xml_declaration=True, method='xml')
        self._store_file(file, 'repodata/repomd.xml')
        file.close()

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

    def _read_meta(self, location, dictionary, search_str, id_func):
        if not location:
            return

        # parse primary XML
        with self._retr_file(location) as file:
            with gzip.GzipFile(fileobj=file) as file_gz:
                tree = ElementTree.parse(file_gz)

        # read package nodes
        for pkg_node in tree.findall(search_str):
            dictionary[id_func(pkg_node)] = pkg_node


    def _create_meta(self, list, root_tag, local_namespace):
        # create complete document
        tree = ElementTree.ElementTree(ElementTree.Element(root_tag))
        tree.getroot().set('packages', str(len(list)))
        for pkg_node in list.items():
            tree.getroot().append(pkg_node[1])

        # map namespaces
        ElementTree.register_namespace('rpm', 'http://linux.duke.edu/metadata/rpm')
        ElementTree.register_namespace('', local_namespace)

        # write it out
        output = StringIO()
        output_gz = StringIO()
        with gzip.GzipFile(fileobj=output_gz, mode='w') as primary_file:
            tree.write(output, 'utf-8', True)
            tree.write(primary_file, 'utf-8', True)

        return output, output_gz

    def _retr_file(self, filename):
        return open(os.path.join(self.repodir, filename), 'rb')

    def _store_file(self, file, filename):
        # check for folder
        if not os.path.exists(os.path.dirname(os.path.join(self.repodir, filename))):
            os.mkdir(os.path.dirname(os.path.join(self.repodir, filename)))

        # store file
        file.seek(0)
        with open(os.path.join(self.repodir, filename), 'wb') as fs_file:
            data = file.read()
            while data:
                fs_file.write(data)
                data = file.read()

    def _hash(self, file):
        file.seek(0)
        m = hashlib.sha256()
        data = file.read()
        while data:
            m.update(data)
            data = file.read()
        return m.hexdigest()

    def _add_node(self, parent, tag, attrib={}, text=None):
            a = ElementTree.Element(tag, attrib)
            if text is not None:
                a.text = text
            parent.append(a)

if __name__ == '__main__':
    from pprint import pprint
    from pyrpm.yum import YumPackage

    repo = YumRepository("D:\\Projekte\\pyrpm\\temprepo")

    # read existing repo
    #repo.read()

    # add package
    repo.add_package(YumPackage(file(os.path.join(repo.repodir, 'tcl-devel-8.5.7-6.el6.x86_64.rpm'), 'rb')))

    # delete package
    #repo.remove_package('4d9c71201f9c0d11164772600d7dadc2cad0a01ac4e472210641e242ad231b3a')

    repo.save()