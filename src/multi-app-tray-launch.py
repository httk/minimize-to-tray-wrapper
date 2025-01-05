#!/usr/bin/env python3

import sys

from multi_app_tray import main
sys.argv[0]="multi-app-tray-wrapper"
sys.exit(main(sys.argv[1:]))
