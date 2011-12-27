from rpm import RPM

#################
# Helper Methods
#################

__cached_saxutils = None
def to_xml(item, attrib=False):
    global __cached_saxutils
    if __cached_saxutils is None:
        import xml.sax.saxutils
        __cached_saxutils = xml.sax.saxutils
    
    item = item.rstrip()
    if attrib:
        item = __cached_saxutils.escape(item, entities={'"':"&quot;"})
    else:
        item = __cached_saxutils.escape(item)
    return item

##################
# Real classes
#################
class YumPackage(RPM):  
    def _dump_base_items(self):
        return u"""
\t<name>%(name)s</name>
\t<arch>%(arch)s</arch>
\t<version epoch="%(epoch)s" ver="%(ver)s" rel="%(rel)s"/>
\t<checksum type="%(csum_type)s" pkgid="YES">%(csum)s</checksum>
\t<summary>%(summary)s</summary>
\t<description>%(description)s</description>
\t<packager>%(packager)s</packager>
\t<url>%(url)s</url>
\t<time file="%(filetime)s" build="%(buildtime)s"/>
\t<size package="%(packagesize)s" installed="%(installedsize)s" archive="%(archivesize)s"/>
\t<location xml:base="%(location_base)s" href="%(location_href)s"/>
""" % { 'name': self.header.name,
        'arch': self.header.architecture,
        'epoch': self.header.epoch,
        'ver': self.header.version,
        'rel': self.header.release,
        'csum_type': 'sha256',
        'csum': self.checksum,
        'summary': to_xml(self.header.summary),
        'description': to_xml(self.header.description),
        'packager': self.header.packager,
        'url': self.header.url,
        'filetime': 0,
        'buildtime': self.header.build_time,
        'packagesize': self.header.size,
        'installedsize': sum([file.size for file in self.filelist]),
        'archivesize': self.header.archive_size,
        'location_base': "",
        'location_href': ""}

    def _dump_format_items(self):
        msg = """\t<format>
\t\t<rpm:license>%(license)s</rpm:license>
\t\t<rpm:vendor>%(vendor)s</rpm:vendor>
\t\t<rpm:group>%(group)s</rpm:group>
\t\t<rpm:buildhost>%(buildhost)s</rpm:buildhost>
\t\t<rpm:sourcerpm>%(sourcerpm)s</rpm:sourcerpm>
""" % {
        'license': to_xml(self.header.license),
        'vendor': to_xml(self.header.vendor),
        'group': to_xml(self.header.group),
        'buildhost': to_xml(self.header.build_host),
        'sourcerpm': to_xml(self.header.source_rpm)}
        
        msg += self._dump_pco('provides')
        msg += self._dump_requires()
        msg += self._dump_pco('conflicts')         
        msg += self._dump_pco('obsoletes')         
        msg += self._dump_files(True)
        msg += """\t</format>"""
        
        return msg

    def _dump_pco(self, pcotype):
        msg = ""
        mylist = getattr(self, pcotype)
        if mylist: msg = "\n\t\t<rpm:%s>\n" % pcotype
        for prco in sorted(mylist):
            pcostring = '''\t\t\t<rpm:entry name="%s"''' % to_xml(prco.name, attrib=True)
            if prco.str_flags:
                pcostring += ''' flags="%s"''' % to_xml(prco.str_flags, attrib=True)
                e,v,r = prco.version
                if e:
                    pcostring += ''' epoch="%s"''' % to_xml(e, attrib=True)
                if v:
                    pcostring += ''' ver="%s"''' % to_xml(v, attrib=True)
                if r:
                    pcostring += ''' rel="%s"''' % to_xml(r, attrib=True)
            pcostring += "/>\n"
            msg += pcostring
            
        if mylist: msg += "\t\t</rpm:%s>\n" % pcotype
        return msg
    
    
    def _dump_files(self, primary=False):
        # sort files
        files = {'file': [], 'dir': [], 'ghost': []}
        for file in self.filelist:
            if primary and not file.primary:
                continue
            files[file.type].append(file)
        
        # create output
        msg = ""
        msg += "\n".join(["""\t<file>%s</file>""" % to_xml(fn.name) for fn in sorted(files['file'])])
        msg += "\n".join(["""\t<file type="dir">%s</file>""" % to_xml(fn.name) for fn in sorted(files['dir'])])
        msg += "\n".join(["""\t<file type="ghost">%s</file>""" % to_xml(fn.name) for fn in sorted(files['ghost'])])
        return msg


    def _dump_requires(self):
        """returns deps in XML format"""
        msg = ""
        if self.requires: msg = "\n\t\t<rpm:requires>\n"
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
            
            prcostring = '''\t\t\t<rpm:entry name="%s"''' % to_xml(prco.name, attrib=True)
            if prco.str_flags:
                prcostring += ''' flags="%s"''' % to_xml(prco.str_flags, attrib=True)
                
                e,v,r = prco.version
                if e:
                    prcostring += ''' epoch="%s"''' % to_xml(e, attrib=True)
                if v:
                    prcostring += ''' ver="%s"''' % to_xml(v, attrib=True)
                if r:
                    prcostring += ''' rel="%s"''' % to_xml(r, attrib=True)
            if prco.flags & 1600:
                prcostring += ''' pre="1"'''

            prcostring += "/>\n"
            msg += prcostring
            used += 1
            
        if self.requires: msg += "\t\t</rpm:requires>\n"
        
        return "" if used == 0 else msg


    def _dump_changelog(self, clog_limit=0):
        if not self.changelog:
            return ""
        
        # We need to output them "backwards", so the oldest is first
        clogs = self.changelog[:clog_limit] if clog_limit else self.changelog
        return "\n".join(["""\t<changelog author="%s" date="%d">%s</changelog>""" % (to_xml(changelog.name), changelog.time, to_xml(changelog.text)) for changelog in clogs])


    def xml_dump_primary_metadata(self):
        msg =  u"""<package type="rpm">"""
        msg += self._dump_base_items()
        msg += self._dump_format_items()
        msg += u"""\n</package>"""
        return msg
    
    def xml_dump_filelists_metadata(self):
        return u"""
<package pkgid="%(pkgid)s" name="%(name)s" arch="%(arch)s">
\t<version epoch="%(epoch)s" ver="%(ver)s" rel="%(rel)s"/>
%(files)s
</package>
""" % {
        'pkgid': self.checksum,
        'name': self.header.name,
        'arch': self.header.architecture,
        'epoch': self.header.epoch,
        'ver': self.header.version,
        'rel': self.header.release,
        'files': self._dump_files()
}

    def xml_dump_other_metadata(self, clog_limit=0):
        return u"""
<package pkgid="%(pkgid)s" name="%(name)s" arch="%(arch)s">
\t<version epoch="%(epoch)d" ver="%(ver)s" rel="%(rel)s"/>
%(changelog)s
</package>
""" % {
        'pkgid': self.checksum,
        'name': self.header.name,
        'arch': self.header.architecture,
        'epoch': self.header.epoch,
        'ver': self.header.version,
        'rel': self.header.release,
        'changelog': self._dump_changelog(clog_limit)}