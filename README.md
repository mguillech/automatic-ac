# Automatic-AC

Automatic loading of time records onto an ActiveCollab service.

# Requirements:

## Python 2.7.x

+ Linux: Any decent distro comes with Python by default.
+ Windows: http://www.python.org/ftp/python/2.7.3/python-2.7.3.msi (x86)
+ OSX: http://www.python.org/ftp/python/2.7.3/python-2.7.3-macosx10.6.dmg (x86_64)

## PyYAML

+ Linux and OSX: pip install PyYAML
+ Windows: http://pyyaml.org/download/pyyaml/PyYAML-3.10.win32-py2.7.exe

## Requests

+ All the platforms: pip install requests

# Usage:

`python auto_ac.py [-a|--autodate] [-c|--commit] [-r|--random]`

Where:

+ -a or --autodate is used to use the current week as the week to load time records to.

+ -c or --commit is used to commit the records onto the ActiveCollab server (needs to be set explicitly!).

+ -r or --random is used to uniformly distribute time among the tickets across a day automatically.
