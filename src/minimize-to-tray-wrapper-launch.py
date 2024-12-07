#!/usr/bin/env python3

import sys

from minimize_to_tray_wrapper import main
sys.argv[0]="minimize-to-tray-wrapper"
sys.exit(main(sys.argv[1:]))
