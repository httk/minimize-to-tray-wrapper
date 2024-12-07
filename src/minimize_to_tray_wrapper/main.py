#!/usr/bin/env python3
#
# minimize-to-tray wrapper
#
# Copyright (C) 2024 Rickard Armiento, httk
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import subprocess, time, os, sys, threading, argparse

import gi
gi.require_version('AppIndicator3', '0.1')
from gi.repository import AppIndicator3, Gtk, GObject
from Xlib import display #, X
#from Xlib.protocol import event

class AppIndicatorWrapper:
    def __init__(self, cmd, name=None, icon=None, persist_on_exit=False, wm_class=None):
        self.cmd = cmd
        self.icon = icon
        self.wm_class = wm_class
        if name:
            self.name = name
        else:
            self.name = "program"

        self.persist_on_exit = persist_on_exit
        self.indicator = AppIndicator3.Indicator.new(
            "appindicator-wrapper",
            "application-exit",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        # Set icon if provided
        if self.icon:
            self.indicator.set_icon_full(self.icon, f"{self.name} icon")

        # Create menu
        self.menu = Gtk.Menu()
        item_show = Gtk.MenuItem(label="Show " + self.name)
        item_show.connect("activate", self.on_show)
        self.menu.append(item_show)

        item_hide = Gtk.MenuItem(label="Hide " + self.name)
        item_hide.connect("activate", self.on_hide)
        self.menu.append(item_hide)

        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", self.on_quit)
        self.menu.append(item_quit)
        self.menu.show_all()

        self.indicator.set_menu(self.menu)

        # Launch process and minimize only at wrapper startup
        self.first_launch = True
        self.launch_process()

        # Start monitoring the process in a separate thread
        self.monitor_thread = threading.Thread(target=self.monitor_process, daemon=True)
        self.monitor_thread.start()

    def launch_process(self):
        self.process = subprocess.Popen(self.cmd)
        self.pid = self.process.pid
        time.sleep(2)
        self.window_id = self.find_window()
        if self.first_launch and self.window_id:
            self.minimize_window()
        self.first_launch = False

    def find_window(self):
        if self.wm_class:
            return self.find_window_by_class(self.wm_class)
        else:
            return self.find_window_by_pid(self.pid)

    def find_window_by_pid(self, pid):
        try:
            output = subprocess.check_output(["wmctrl", "-lp"], universal_newlines=True)
            for line in output.splitlines():
                parts = line.split(None, 4)
                if len(parts) >= 3:
                    w_pid = parts[2]
                    if w_pid.isdigit() and int(w_pid) == pid:
                        return int(parts[0], 16)  # Return window ID as int
        except Exception as e:
            print(f"Error finding window by pid: {e}")
        return None

    def find_window_by_class(self, wm_class):
        try:
            output = subprocess.check_output(["wmctrl", "-lx"], universal_newlines=True)
            for line in output.splitlines():
                parts = line.split(None, 5)
                if len(parts) >= 4:
                    w_class = parts[2]
                    if wm_class in w_class:
                        return int(parts[0], 16)  # Return window ID as int
        except Exception as e:
            print(f"Error finding window by class: {e}")
        return None

    def minimize_window(self):
        if self.window_id:
            try:
                # Minimize the window using xdotool
                subprocess.run(["xdotool", "windowminimize", str(self.window_id)], check=False)

                # Hide the window further with Xlib
                self.unmap_window()
            except Exception as e:
                print(f"Error minimizing window: {e}")

    def unmap_window(self):
        try:
            d = display.Display()
            window = d.create_resource_object('window', self.window_id)
            window.unmap()
            d.flush()
        except Exception as e:
            print(f"Error unmapping window: {e}")

    def is_program_running(self):
        return self.process.poll() is None

    def on_show(self, source):
        if not self.is_program_running():
            self.launch_process()
        elif self.window_id:
            try:
                subprocess.run(["xdotool", "windowmap", str(self.window_id)], check=False)
                subprocess.run(["xdotool", "windowactivate", "--sync", str(self.window_id)], check=False)
            except Exception as e:
                print(f"Error showing window: {e}")

    def on_hide(self, source):
        if self.is_program_running() and self.window_id:
            self.minimize_window()

    def on_quit(self, source):
        if self.process and self.is_program_running():
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Process did not terminate in time; force killing it.")
                self.process.kill()
            except Exception as e:
                print(f"Error while terminating process: {e}")

        Gtk.main_quit()

    def monitor_process(self):
        while True:
            if self.process.poll() is not None:
                if not self.persist_on_exit:
                    Gtk.main_quit()
                    return
                else:
                    self.launch_process()
            time.sleep(5)
        

def main(args):

    # Force X11
    if 'WAYLAND_DISPLAY' in os.environ:
        del os.environ['WAYLAND_DISPLAY']
        os.environ['GDK_BACKEND'] = 'x11'

    parser = argparse.ArgumentParser(description="AppIndicator with application icon")
    parser.add_argument("--icon", help="Path to PNG icon for the tray")
    parser.add_argument("--app-name", help="Program name")
    parser.add_argument("--wm-class", help="WM_CLASS of the program window")
    parser.add_argument("--persist-on-exit", action="store_true", help="Restart the program if it quits")
    parser.add_argument("cmd", nargs='+', help="Command to launch the application")
    args = parser.parse_args(args)

    GObject.threads_init()
    app = AppIndicatorWrapper(
        cmd=args.cmd,
        name=args.app_name,
        icon=args.icon,
        persist_on_exit=args.persist_on_exit,
        wm_class=args.wm_class
    )
    Gtk.main()


if __name__ == "__main__":
    main(sys.argv[1:])
