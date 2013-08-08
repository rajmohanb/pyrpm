import unittest
import sys

if sys.version < '3':
    from cStringIO import StringIO as BytesIO
else:
    from io import BytesIO

from pyrpm.rpm import RPM


class RPMTest(unittest.TestCase):

    def setUp(self):

        self.rpm = RPM(open('tests/Eterm-0.9.3-5mdv2007.0.src.rpm', 'rb'))

    def test_entries(self):

        description = '''Eterm is a color vt102 terminal emulator intended as a replacement for Xterm.\nIt is designed with a Freedom of Choice philosophy, leaving as much power,\nflexibility, and freedom as possible in the hands of the user.\n\nIt is designed to look good and work well, but takes a feature-rich approach\nrather than one of minimalism while still maintaining speed and efficiency.\n\nIt works on any windowmanager/desktop environment, although it is designed\nto work and integrate best with Enlightenment.'''

        self.assertEqual(self.rpm.header.name, 'Eterm')
        self.assertEqual(self.rpm.header.version, '0.9.3')
        self.assertEqual(self.rpm.header.release, '5mdv2007.0')
        self.assertEqual(self.rpm.header.architecture, 'i586')
        self.assertEqual(self.rpm.header.license, 'BSD')
        self.assertEqual(self.rpm.header.description, description)

    def test_package_type(self):
        self.assertEqual(self.rpm.binary, False)
        self.assertEqual(self.rpm.source, True)

    def test_filename(self):
        self.assertEqual(self.rpm.canonical_filename, 'Eterm-0.9.3-5mdv2007.0.src.rpm')


class RPMStringIOTest(RPMTest):

    def setUp(self):

        self.rpm = RPM(BytesIO(open('tests/Eterm-0.9.3-5mdv2007.0.src.rpm', 'rb').read()))
