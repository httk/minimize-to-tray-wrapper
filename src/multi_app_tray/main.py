#!/usr/bin/env python3
#
# multi-app-tray
#
# Copyright (C) 2024-2025 Rickard Armiento, httk
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

import subprocess
import time
import os
import sys
import threading
import argparse

import gi
gi.require_version('AppIndicator3', '0.1')
from gi.repository import AppIndicator3, Gtk, GObject
from Xlib import display

def force_x11():
    """
    Force running on X11 (disable Wayland), since we need X11-based tools.
    """
    if 'WAYLAND_DISPLAY' in os.environ:
        del os.environ['WAYLAND_DISPLAY']
    os.environ['GDK_BACKEND'] = 'x11'


class MultiAppIndicator:
    def __init__(self, apps, icon=None):
        """
        apps is a list of dicts, each with:
          {
            'name': <string>,       # Display name
            'wm_class': <string>,   # If you want to identify by WM_CLASS
            'cmd': <list>,          # Command to run, e.g. ["gnome-calculator"]
            'process': None,        # Will be set at runtime
            'window_id': None       # Will be set at runtime
          }
        icon is an optional path to a PNG icon.
        """
        self.apps = apps
        self.indicator = AppIndicator3.Indicator.new(
            "multi-appindicator-wrapper",
            "application-exit",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        if icon:
            if os.path.isfile(icon):
                self.indicator.set_icon_full(icon,"multi-tray icon")
            else:
                print("SETTING?",icon,icon)
                self.indicator.set_icon_full(icon,icon)
        else:
            self.indicator.set_icon("application-exit")
        
        # Build the tray menu
        self.menu = Gtk.Menu()

        # For each application, add "Show <name>" and "Hide <name>" items
        for app in self.apps:
            # Initialize runtime data
            app['process'] = None
            app['window_id'] = None

            item_show = Gtk.MenuItem(label=f"Show {app['name']}")
            item_show.connect("activate", self.on_show_app, app)
            self.menu.append(item_show)

            item_hide = Gtk.MenuItem(label=f"Hide {app['name']}")
            item_hide.connect("activate", self.on_hide_app, app)
            self.menu.append(item_hide)

            self.menu.append(Gtk.SeparatorMenuItem())

        # Quit item
        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", self.on_quit)
        self.menu.append(item_quit)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

    def on_show_app(self, menuitem, app):
        """
        Show (unminimize / activate) the window for the given app.
        If it’s not running, launch it.
        """
        #if not self.is_app_running(app):
        #    self.launch_app(app)

        if 'window_id' in app:
            try:
                subprocess.run(["xdotool", "windowmap", str(app['window_id'])], check=True)
                subprocess.run(["xdotool", "windowactivate", "--sync", str(app['window_id'])], check=True)
                return
            except subprocess.CalledProcessError:
                pass

        app['window_id'] = self.find_window(app)
        if app['window_id']:
            # Unminimize/map the window
            subprocess.run(["xdotool", "windowmap", str(app['window_id'])], check=False)
            # Bring to front / focus
            subprocess.run(["xdotool", "windowactivate", "--sync", str(app['window_id'])], check=False)
        else:
            self.launch_app(app)


    def try_remap_and_focus(self, window_id):
        """
        Attempt to remap (unminimize) and focus a cached window_id.
        Return True on success, False if something went wrong (e.g., invalid ID).
        """

    
            
    def on_hide_app(self, menuitem, app):
        """
        Hide (minimize / unmap) the window for the given app.
        If the window isn’t found or the app isn’t running, do nothing.
        """
        #if not self.is_app_running(app):
        #    return

        app['window_id'] = self.find_window(app)
        if app['window_id']:
            subprocess.run(["xdotool", "windowminimize", str(app['window_id'])], check=False)
            self.unmap_window(app['window_id'])

    def launch_app(self, app):
        """
        Launch the app's command, store the process handle.
        """
        try:
            proc = subprocess.Popen(app['cmd'])
            app['process'] = proc
            # Give the window a little time to appear
            time.sleep(1.5)
        except Exception as e:
            print(f"Error launching {app['name']}: {e}")

    #def is_app_running(self, app):
    #    """
    #    Check if the app's process is alive (not None and not exited).
    #    """
    #    proc = app.get('process')
    #    if proc is None:
    #        return False
    #    return (proc.poll() is None)

    def on_quit(self, menuitem):
        """
        Clean up all running processes (if desired), then quit.
        """
        for app in self.apps:
            proc = app.get('process')
            if proc and proc.poll() is None:
                # Terminate gracefully
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print(f"Process {app['name']} did not terminate in time; killing it.")
                    proc.kill()
                except Exception as e:
                    print(f"Error while terminating {app['name']}: {e}")

        Gtk.main_quit()

    def find_window(self, app):
        """
        Finds the window via wmctrl by either WM_CLASS or by PID.
        """
        if 'wm_class' in app and app['wm_class']:
            return self.find_window_by_class(app['wm_class'])
        #else:
        #    proc = app.get('process')
        #    if proc and proc.poll() is None:
        #        return self.find_window_by_pid(proc.pid)
        return None

    #def find_window_by_pid(self, pid):
    #    try:
    #        output = subprocess.check_output(["wmctrl", "-lp"], universal_newlines=True)
    #        for line in output.splitlines():
    #            parts = line.split(None, 4)
    #            if len(parts) >= 3:
    #                w_pid = parts[2]
    #                if w_pid.isdigit() and int(w_pid) == pid:
    #                    return int(parts[0], 16)  # Convert hex WID to int
    #    except Exception as e:
    #        print(f"Error finding window by pid: {e}")
    #    return None

    def find_window_by_class(self, wm_class):
        try:
            output = subprocess.check_output(["wmctrl", "-lx"], universal_newlines=True)
            for line in output.splitlines():
                parts = line.split(None, 5)
                if len(parts) >= 3:
                    w_class = parts[2]
                    # e.g. w_class might look like: "gnome-calculator.Gnome-calculator"
                    if wm_class in w_class:
                        return int(parts[0], 16)
        except Exception as e:
            print(f"Error finding window by class: {e}")
        return None

    def unmap_window(self, window_id):
        """
        Additional step to hide/unmap the window at the X11 level.
        """
        try:
            d = display.Display()
            w = d.create_resource_object('window', window_id)
            w.unmap()
            d.flush()
        except Exception as e:
            print(f"Error unmapping window: {e}")


def main(argv):
    parser = argparse.ArgumentParser(description="Multi-App Tray Example")
    parser.add_argument("--icon", help="Path to PNG icon for the tray", default=None)
    parser.add_argument(
        "--app", 
        nargs=3, 
        action="append", 
        metavar=("NAME", "WM_CLASS", "CMD"),
        help="Define an app entry: --app <name> <wm_class> <command>"
    )

    args = parser.parse_args(argv)

    apps = []
    if args.app:
        for (app_name, wm_class, cmd) in args.app:
            apps.append({
                "name": app_name,
                "wm_class": wm_class,
                "cmd": [cmd]
            })

    GObject.threads_init()
    indicator = MultiAppIndicator(apps=apps, icon=args.icon)
    Gtk.main()
