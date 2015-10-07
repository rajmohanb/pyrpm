try:
    from xml.etree.cElementTree import Element
except:
    from xml.etree.ElementTree import Element

from rpm import RPM


def element(tag, attrib={}, text=None):
    """Helper function for Element creation"""
    ele = Element(tag, attrib)
    if text:
        ele.text = text
    return ele


class YumPackage(RPM):
    def _xml_base_items(self, ele):
        ele.append(element('{http://linux.duke.edu/metadata/common}name', text=self.header.name))
        ele.append(element('{http://linux.duke.edu/metadata/common}arch', text=self.header.architecture))
        ele.append(element("{http://linux.duke.edu/metadata/common}version", {'epoch': str(self.header.epoch), 'ver': unicode(self.header.version), 'rel': unicode(self.header.release)}))
        ele.append(element('{http://linux.duke.edu/metadata/common}checksum', {'type': 'sha256', 'pkgid': 'YES'}, text=self.checksum))
        ele.append(element('{http://linux.duke.edu/metadata/common}summary', text=self.header.summary))
        ele.append(element('{http://linux.duke.edu/metadata/common}description', text=self.header.description))
        ele.append(element('{http://linux.duke.edu/metadata/common}packager', text=self.header.packager))
        ele.append(element('{http://linux.duke.edu/metadata/common}url', text=self.header.url))
        ele.append(element('{http://linux.duke.edu/metadata/common}time', {'file': str(self.header.build_time), 'build': str(self.header.build_time)}))
        ele.append(element('{http://linux.duke.edu/metadata/common}size', {'package': str(self.filesize), 'installed': str(sum([file.size for file in self.filelist])), 'archive': str(self.header.archive_size)}))
        ele.append(element('{http://linux.duke.edu/metadata/common}location', {'href': self.canonical_filename}))

    def _xml_format_items(self, ele):
        ef = element('{http://linux.duke.edu/metadata/common}format')
        ef.append(element('{http://linux.duke.edu/metadata/rpm}license', text=self.header.license))
        ef.append(element('{http://linux.duke.edu/metadata/rpm}vendor', text=self.header.vendor))
        ef.append(element('{http://linux.duke.edu/metadata/rpm}group', text=self.header.group))
        ef.append(element('{http://linux.duke.edu/metadata/rpm}buildhost', text=self.header.build_host))
        ef.append(element('{http://linux.duke.edu/metadata/rpm}sourcerpm', text=self.header.source_rpm))

        self._xml_pco(ef, 'provides')
        self._xml_requires(ef)
        self._xml_pco(ef, 'conflicts')
        self._xml_pco(ef, 'obsoletes')
        self._xml_files(ef, True)

        ele.append(ef)

    def _xml_pco(self, ele, pcotype):
        # get right pco
        mylist = getattr(self, pcotype)
        if not mylist:
            return

        ef = element('{http://linux.duke.edu/metadata/rpm}' + pcotype)
        for prco in sorted(mylist):
            entry = element('{http://linux.duke.edu/metadata/rpm}entry', {'name': prco.name})
            if prco.str_flags:
                entry.set('flags', prco.str_flags)
                e, v, r = prco.version
                if e:
                    entry.set('epoch', str(e))
                if v:
                    entry.set('ver', v)
                if r:
                    entry.set('rel', r)
            ef.append(entry)
        ele.append(ef)

    def _xml_files(self, ele, primary=False):
        # sort files
        files = {'file': [], 'dir': [], 'ghost': []}
        for file in self.filelist:
            if primary and not file.primary:
                continue
            files[file.type].append(file)

        # create output
        for file in sorted(files['file']):
            ele.append(element("{http://linux.duke.edu/metadata/filelists}file", text=file.name))

        for type in ['dir', 'ghost']:
            for file in sorted(files[type]):
                ele.append(element("{http://linux.duke.edu/metadata/filelists}file", {'type': type}, text=file.name))

    def _xml_requires(self, ele):
        """returns deps in XML format"""
        ef = element('{http://linux.duke.edu/metadata/rpm}requires')
        used = 0

        for prco in sorted(self.requires):
            if prco.name.startswith('rpmlib('):
                continue

            # this drops out requires that the pkg provides for itself.
            if prco.name in [p.name for p in self.provides] or (prco.name.startswith('/') and (prco.name in [file.name for file in self.filelist])):
                if not prco.flags:
                    continue
                else:
                    if prco in self.provides:
                        continue

            entry = element('{http://linux.duke.edu/metadata/rpm}entry', {'name': prco.name})
            if prco.str_flags:
                entry.set('flags', prco.str_flags)
                e, v, r = prco.version
                if e:
                    entry.set('epoch', str(e))
                if v:
                    entry.set('ver', v)
                if r:
                    entry.set('rel', r)
            if prco.flags & 1600:
                entry.set('pre', '1')

            ef.append(entry)
            used += 1

        if used != 0:
            ele.append(ef)

    def _xml_changelog(self, ele, clog_limit=0):
        if not self.changelog:
            return ""

        # We need to output them "backwards", so the oldest is first
        clogs = self.changelog[:clog_limit] if clog_limit else self.changelog
        for changelog in clogs:
            ele.append(element('{http://linux.duke.edu/metadata/other}changelog', {'author': changelog.name, 'date': str(changelog.time)}, text=changelog.text))

    def xml_primary_metadata(self):
        ele = element("{http://linux.duke.edu/metadata/common}package", {'type': 'rpm'})
        self._xml_base_items(ele)
        self._xml_format_items(ele)
        return ele

    def xml_filelists_metadata(self):
        ele = element("{http://linux.duke.edu/metadata/filelists}package", {'pkgid': self.checksum, 'name': self.header.name, 'arch': self.header.architecture})
        ele.append(element("{http://linux.duke.edu/metadata/filelists}version", {'epoch': str(self.header.epoch), 'ver': unicode(self.header.version), 'rel': unicode(self.header.release)}))
        self._xml_files(ele)
        return ele

    def xml_other_metadata(self, clog_limit=0):
        ele = element("{http://linux.duke.edu/metadata/other}package", {'pkgid': self.checksum, 'name': self.header.name, 'arch': self.header.architecture})
        ele.append(element("{http://linux.duke.edu/metadata/other}version", {'epoch': str(self.header.epoch), 'ver': unicode(self.header.version), 'rel': unicode(self.header.release)}))
        self._xml_changelog(ele, clog_limit)
        return ele
