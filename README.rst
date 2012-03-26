=====
PyRPM
=====

:authors: Stefan Richter, Mário Morgado
:license: BSD

PyRPM is a pure python module to extract information from a RPM package and to create YUM metadata. Supports generation/editing YUM repositories.

Usage
-----

        >>> from pyrpm.rpm import RPM
        >>> rpm = RPM(file('package-1.0-r1.i586.rpm')
        >>> rpm.binary # this means that the package is a rpm and not a src.rpm
        True
        >>> rpm.header.name
        'package'
        >>> rpm.header.architecture
        'i586'
        >>> rpm.header.description
        'package description'

