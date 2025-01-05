# tray-utils

Two small utilities written in Python:

- tray-wrapper: wrap a process that opens an x11 window in a wrapper that opens a tray icon that allows the window to be mimimized to tray (as an appindicator) to support this feature when it is missing in the software.

- multi-app-tray: sets up a tray icon that allows multiple programs to be independently launched and their window controlled.

For program options do:
```
bin/tray-wrapper --help
```
and
```
bin/multi-app-tray --help
```
