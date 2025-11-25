# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.MessageBox import MessageBox
from Components.ScrollLabel import ScrollLabel
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ConfigList import ConfigListScreen
from Components.ProgressBar import ProgressBar  # <-- DODATO!
from Components.config import config, ConfigSubsection, ConfigText, ConfigYesNo, ConfigSelection, configfile
from enigma import eDVBDB, eTimer, eConsoleAppContainer
from skin import parseColor
import re
import os
import shutil
from datetime import datetime
import urllib.parse
import urllib.request
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# === KONFIGURACIJA ===
PLUGIN_VERSION = "1.3"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/CiefpOpenDirectories/"
TMP_PATH = "/tmp/CiefpOpenDirectories/"
OPENDIRECTORIES_FILE = PLUGIN_PATH + "opendirectories.txt"
BACKUP_FILE = "/tmp/opendirectories_backup.txt"
CONFIG_FILE = "/etc/enigma2/ciefp_opendirectories.cfg"

os.makedirs(TMP_PATH, exist_ok=True)
os.makedirs(PLUGIN_PATH, exist_ok=True)

# === CONFIG SETUP ===
config.ciefp = ConfigSubsection()
config.ciefp.default_name = ConfigText(default="IPTV OPD", fixed_size=False)
config.ciefp.include_date = ConfigYesNo(default=True)
config.ciefp.include_time = ConfigYesNo(default=True)
config.ciefp.scrape_depth = ConfigSelection(
    choices=[("1", "1 level"), ("2", "2 levels"), ("3", "3 levels"), ("0", "Unlimited")],
    default="2"
)
config.ciefp.scrape_filter = ConfigSelection(
    choices=[("all", "All Files"), ("video", "Video Only"), ("audio", "Audio Only")],
    default="video"
)

# Učitaj konfiguraciju
try:
    configfile.load(CONFIG_FILE)
except:
    pass

# === UPDATE URL-OVI ===
VERSION_URL = "https://raw.githubusercontent.com/ciefp/CiefpOpenDirectories/main/version.txt"
UPDATE_COMMAND = "wget -q --no-check-certificate https://raw.githubusercontent.com/ciefp/CiefpOpenDirectories/main/installer.sh -O - | /bin/sh"

# =================================== MAIN SCREEN ===================================
class MainScreen(Screen):
    skin = """
    <screen name="MainScreen" position="center,center" size="1800,900" title="..:: CiefpOpenDirectories v{} - Main Menu ::..">
        <widget name="list" position="0,0" size="1400,800" scrollbarMode="showOnDemand" itemHeight="33" font="Regular;28"  />
        <widget name="status_label" position="1250,820" size="400,40" font="Regular;26" halign="left" valign="center" foregroundColor="#00ff00" backgroundColor="#10000000" transparent="1" />
        <ePixmap pixmap="{}background.png" position="1400,0" size="400,800" alphatest="on" />
        <!-- Dugmad -->
        <ePixmap pixmap="buttons/red.png" position="50,830" size="35,35" alphatest="blend" />
        <eLabel text="Exit" position="100,820" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#800000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/green.png" position="350,830" size="35,35" alphatest="blend" />
        <eLabel text="Add URL" position="400,820" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#008000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/yellow.png" position="650,830" size="35,35" alphatest="blend" />
        <eLabel text="Settings" position="700,820" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#808000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/blue.png" position="950,830" size="35,35" alphatest="blend" />
        <eLabel text="Scrape" position="1000,820" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#000080" halign="center" valign="center" transparent="0" />
    </screen>""".format(PLUGIN_VERSION, PLUGIN_PATH)

    def __init__(self, session):
        Screen.__init__(self, session)
        self["list"] = MenuList([], enableWrapAround=True)
        self["list"].selectionEnabled(1)
        self["status_label"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
                                    {"ok": self.openContent, "cancel": self.exit,
                                     "red": self.exit, "green": self.addUrl,
                                     "yellow": self.openSettings, "blue": self.startScrape}, -2)

        self.container = eConsoleAppContainer()
        self.container.appClosed.append(self.command_finished)
        self.container.dataAvail.append(self.version_data_avail)
        self.version_check_in_progress = False
        self.version_buffer = b''

        self.loadAddresses()
        self.check_for_updates()

    def loadAddresses(self):
        try:
            if not os.path.exists(OPENDIRECTORIES_FILE):
                open(OPENDIRECTORIES_FILE, 'a').close()
            with open(OPENDIRECTORIES_FILE, "r") as f:
                addresses = [line.strip() for line in f.readlines() if line.strip() and line.strip().startswith(('http://', 'https://'))]
            self["list"].setList(addresses)
            if not addresses:
                self["status_label"].setText("No URLs. Use GREEN to add.")
        except Exception as e:
            self["list"].setList([])
            print("[CiefpOpenDirectories] Load error:", e)

    def openContent(self):
        url = self["list"].getCurrent()
        if url:
            self.session.open(ContentScreen, url)

    def addUrl(self):
        self.session.openWithCallback(self.urlEntered, VirtualKeyBoard, title="Enter Open Directory URL:", text="http://")

    def urlEntered(self, url):
        if not url or not url.strip():
            return
        url = url.strip().rstrip('/') + '/'
        if not url.startswith(('http://', 'https://')):
            self.session.open(MessageBox, "Invalid URL! Must start with http:// or https://", MessageBox.TYPE_ERROR)
            return
        current = self["list"].getList() or []
        if url not in current:
            current.append(url)
            self["list"].setList(current)
            # DODAJ NOVI RED!
            with open(OPENDIRECTORIES_FILE, "a", encoding="utf-8") as f:
                f.write(url + "\n")
            self["status_label"].setText(f"Added: {url}")
        else:
            self["status_label"].setText("URL already exists.")

    def openSettings(self):
        self.session.open(SettingsScreen)

    def startScrape(self):
        url = self["list"].getCurrent()
        if not url:
            self.session.open(MessageBox, "Select a URL first!", MessageBox.TYPE_WARNING)
            return
        self.session.open(ScrapeScreen, url)

    def exit(self):
        self.close()

    # === UPDATE LOGIKA ===
    def check_for_updates(self):
        if self.version_check_in_progress: return
        self.version_check_in_progress = True
        self["status_label"].setText("Checking for updates...")
        try:
            self.container.execute(f"wget -q --timeout=10 -O - {VERSION_URL}")
        except Exception as e:
            self.version_check_in_progress = False
            self["status_label"].setText("Update check failed.")
            print("[CiefpOpenDirectories] Update error:", e)

    def version_data_avail(self, data):
        self.version_buffer += data

    def command_finished(self, retval):
        if self.version_check_in_progress:
            self.version_check_closed(retval)
        else:
            self.update_completed(retval)

    def version_check_closed(self, retval):
        self.version_check_in_progress = False
        if retval == 0:
            try:
                remote_version = self.version_buffer.decode().strip()
                self.version_buffer = b''
                if remote_version != PLUGIN_VERSION:
                    self.session.openWithCallback(self.start_update, MessageBox,
                        f"New version: v{remote_version}\nInstall now?", MessageBox.TYPE_YESNO)
                else:
                    self["status_label"].setText("Up to date.")
            except Exception as e:
                self["status_label"].setText("Version check failed.")
        else:
            self["status_label"].setText("Update check failed.")

    def start_update(self, answer):
        if not answer: 
            self["status_label"].setText("Update cancelled.")
            return
        if os.path.exists(OPENDIRECTORIES_FILE):
            shutil.copy2(OPENDIRECTORIES_FILE, BACKUP_FILE)
        self["status_label"].setText("Updating...")
        self.container.execute(UPDATE_COMMAND)

    def update_completed(self, retval):
        if os.path.exists(BACKUP_FILE):
            shutil.move(BACKUP_FILE, OPENDIRECTORIES_FILE)
        if retval == 0:
            self["status_label"].setText("Update OK! Restarting...")
            self.container.execute("sleep 2 && killall -9 enigma2")
        else:
            self["status_label"].setText("Update failed.")

# =================================== SETTINGS ===================================
class SettingsScreen(ConfigListScreen, Screen):
    skin = """
    <screen position="center,center" size="1200,800" title="..:: CiefpOpenDirectories - Settings ::..">
        <widget name="config" position="20,20" size="750,650" itemHeight="33" font="Regular;28"  scrollbarMode="showOnDemand" />
        <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/CiefpOpenDirectories/settings.png" position="800,0" size="400,800" alphatest="on" />
        <ePixmap pixmap="buttons/red.png" position="50,720" size="35,35" alphatest="blend" />
        <eLabel text="Exit" position="100,710" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#800000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/green.png" position="500,720" size="35,35" alphatest="blend" />
        <eLabel text="Save" position="550,710" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#008000" halign="center" valign="center" transparent="0" />
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        list = []
        list.append(("Default Playlist Name", config.ciefp.default_name))
        list.append(("Include Date in Filename", config.ciefp.include_date))
        list.append(("Include Time in Filename", config.ciefp.include_time))
        list.append(("Scrape Depth", config.ciefp.scrape_depth))
        list.append(("Scrape File Filter", config.ciefp.scrape_filter))
        ConfigListScreen.__init__(self, list, session=session)
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
                                    {"ok": self.keyOK, "cancel": self.keyCancel, 
                                     "red": self.exit, "green": self.save}, -2)

    def keyOK(self):
        current = self["config"].getCurrent()
        if current and len(current) > 1:
            cfg = current[1]
            # Ako je ovo "Default Playlist Name", otvori virtualnu tastaturu
            if cfg == config.ciefp.default_name:
                self.session.openWithCallback(
                    lambda result: self.vkbCallback(result, cfg),
                    VirtualKeyBoard,
                    title="Enter Default Playlist Name:",
                    text=cfg.value
                )
            else:
                # Za ostale postavke, koristi standardni OK
                ConfigListScreen.keyOK(self)

    def vkbCallback(self, result, cfg):
        if result is not None:
            cfg.value = result
            self["config"].invalidateCurrent()

    def save(self):
        # Sačuvaj sve postavke
        for x in self["config"].list:
            x[1].save()
        
        # ISPRAVKA: configfile.save() ne prima argumente
        try:
            configfile.save()
        except Exception as e:
            print(f"[CiefpOpenDirectories] Error saving config: {e}")
            # Pokušaj sa alternativnim načinom čuvanja
            try:
                with open(CONFIG_FILE, 'w') as f:
                    config.ciefp.save(f)
            except Exception as e2:
                print(f"[CiefpOpenDirectories] Alternative save also failed: {e2}")
        
        self.session.open(MessageBox, "Settings saved successfully!", MessageBox.TYPE_INFO, timeout=3)
        self.close()

    def exit(self):
        self.close()
# =================================== SCRAPE SCREEN ===================================
class ScrapeScreen(Screen):
    skin = """
    <screen position="center,center" size="1800,800" title="Scrape in Progress...">
        <widget name="progress" position="50,50" size="1700,30" />
        <widget name="progress_text" position="50,90" size="1700,40" font="Regular;28" halign="center" />
        <widget name="current_folder" position="50,140" size="1700,30" font="Regular;22" halign="center" foregroundColor="#00ff00" />
        <widget name="depth_info" position="50,180" size="1700,30" font="Regular;22" halign="center" foregroundColor="#ffff00" />
        <widget name="stats" position="50,220" size="1700,500" font="Regular;22" scrollbarMode="showOnDemand" />
        <widget name="footer_label" position="50,700" size="1700,40" halign="center" font="Regular;28" foregroundColor="#ff0000" />
    </screen>"""

    def __init__(self, session, base_url):
        Screen.__init__(self, session)
        self.base_url = base_url.rstrip('/') + '/'
        self.found_files = []
        self.scanned_folders = 0
        self.scanned_files = 0
        self.current_folder = ""
        self.current_depth = 0
        self.max_depth = 0
        self.stop = False
        self.folders_to_scan = []
        self.is_scanning = False

        self["progress"] = ProgressBar()
        self["progress_text"] = Label("Starting...")
        self["current_folder"] = Label("")
        self["depth_info"] = Label("")
        self["stats"] = ScrollLabel("")
        self["footer_label"] = Label("CANCEL to stop")

        self["actions"] = ActionMap(["OkCancelActions"], {"cancel": self.cancelScrape})

        self.timer = eTimer()
        self.timer.callback.append(self.runScrape)
        self.timer.start(100, True)

    def runScrape(self):
        """Pokreće inicijalno skeniranje"""
        self.max_depth = int(config.ciefp.scrape_depth.value) if config.ciefp.scrape_depth.value != "0" else 5
        filter_mode = config.ciefp.scrape_filter.value
        self.found_files = []
        self.scanned_folders = 0
        self.scanned_files = 0
        self.stop = False
        self.is_scanning = True
        self.folders_to_scan = [(self.base_url, 0)]

        self["progress_text"].setText("Starting scan...")
        self["progress"].setValue(0)
        self["current_folder"].setText(f"Base URL: {self.base_url}")
        self["depth_info"].setText(f"Max depth: {self.max_depth} | Filter: {filter_mode}")
        self["footer_label"].setText("CANCEL to stop")
        self["footer_label"].instance.setForegroundColor(parseColor("#ff0000"))

        # Pokreni ciklus skeniranja
        self.timer.stop()
        try:
            self.timer.callback.clear()
        except:
            self.timer.callback = []
        self.timer.callback.append(self.scan_next_folder)
        self.timer.start(200, True)

    def scan_next_folder(self):
        """Skenira sledeći folder u redu"""
        if self.stop:
            self.finalize_scan()
            return

        if not self.folders_to_scan:
            self.finalize_scan()
            return

        try:
            url, depth = self.folders_to_scan.pop(0)
            self.current_folder = url
            self.current_depth = depth

            total_done = self.scanned_folders + 1
            total_queued = len(self.folders_to_scan)
            progress = min(99, int((total_done / (total_done + total_queued + 1)) * 100))
            self["progress"].setValue(progress)
            self["progress_text"].setText(f"Progress: {progress}% - Scanning depth {depth}")
            self["current_folder"].setText(f"Scanning: {url}")
            self["depth_info"].setText(f"Depth: {depth}/{self.max_depth} | Folders left: {len(self.folders_to_scan)}")

            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context

            items = self._parse_directory_fast(url)
            self.scanned_folders += 1
            new_folders = 0
            new_files = 0

            for item in items:
                if self.stop:
                    break
                if item[2] == 'folder' and depth < self.max_depth:
                    self.folders_to_scan.append((item[1], depth + 1))
                    new_folders += 1
                elif item[2] == 'file' and self.filter_file(item[0], config.ciefp.scrape_filter.value):
                    if item not in self.found_files:
                        self.found_files.append(item)
                        new_files += 1

            self.updateStats(new_folders, new_files)

        except Exception as e:
            print(f"[Scrape] Error scanning {self.current_folder}: {e}")

        if not self.stop and hasattr(self, "timer"):
            if self.folders_to_scan:
                self.timer.stop()
                try:
                    self.timer.callback.clear()
                except:
                    self.timer.callback = []
                self.timer.callback.append(self.scan_next_folder)
                self.timer.start(200, True)
            else:
                self.finalize_scan()

    def _parse_directory_fast(self, directory_url):
        """Brzo parsiranje direktorijuma"""
        items = []
        try:
            req = urllib.request.Request(directory_url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            })

            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

                links = re.findall(r'<a\s+href="([^"]*?)"[^>]*>(.*?)</a>', html, re.IGNORECASE)

                for href, name in links:
                    if self.stop:
                        break

                    href = href.strip()
                    if not href or href in ('../', './') or href.startswith(('?', '#')):
                        continue

                    clean_name = re.sub(r'<[^>]+>', '', name).strip()

                    # Ako je skraćeno ("..&gt;"), koristi ime iz href
                    if '&gt;' in clean_name or '..' in clean_name:
                        clean_name = urllib.parse.unquote(os.path.basename(href))

                    if not clean_name:
                        clean_name = urllib.parse.unquote(os.path.basename(href))

                    full_url = urllib.parse.urljoin(directory_url, href.split('?')[0].split('#')[0])

                    if href.endswith('/') or full_url.endswith('/'):
                        folder_name = clean_name.rstrip('/')
                        if folder_name and folder_name not in ('.', '..'):
                            items.append((folder_name, full_url, 'folder'))
                    else:
                        if self.is_supported_format(clean_name):
                            items.append((clean_name, full_url, 'file'))

        except urllib.error.URLError as e:
            print(f"[Parse] URL Error: {e}")
        except Exception as e:
            print(f"[Parse] General Error: {e}")

        return items

    def is_supported_format(self, filename):
        filename_lower = filename.lower()
        video_formats = ('.mp4', '.mkv', '.avi', '.ts')
        audio_formats = ('.mp3', '.flac')
        return filename_lower.endswith(video_formats + audio_formats)

    def filter_file(self, filename, filter_mode):
        filename_lower = filename.lower()
        if filter_mode == "all":
            return self.is_supported_format(filename)
        elif filter_mode == "video":
            return filename_lower.endswith(('.mp4', '.mkv', '.avi', '.ts'))
        elif filter_mode == "audio":
            return filename_lower.endswith(('.mp3', '.flac'))
        return False

    def updateStats(self, new_folders=0, new_files=0):
        text = f"Base URL: {self.base_url}\n"
        text += f"Max depth: {self.max_depth} | Current depth: {self.current_depth}\n"
        text += f"Scanned folders: {self.scanned_folders}\n"
        text += f"Found compatible files: {len(self.found_files)}\n"
        text += f"Total files checked: {self.scanned_files}\n"
        text += f"Folders in queue: {len(self.folders_to_scan)}\n"
        text += f"New folders found: {new_folders}\n"
        text += f"New files found: {new_files}\n"

        if self.current_folder:
            text += f"\nCurrent folder: {self.current_folder}\n"

        if self.found_files:
            text += f"\nLast files found:\n"
            for file in self.found_files[-5:]:
                text += f"- {file[0]}\n"

        self["stats"].setText(text)

    def finalize_scan(self):
        """Završi skeniranje i prikaži rezultate"""
        self.is_scanning = False
        self.timer.stop()
        self["progress"].setValue(100)
        self["progress_text"].setText("Scrape complete!")
        self["depth_info"].setText("")
        self["current_folder"].setText("")
        self["stats"].setText(self["stats"].getText() + "\n\n[INFO] Scrape finished successfully.")

        # Promeni footer
        self["footer_label"].setText("OK to return to Main Menu")
        self["footer_label"].instance.setForegroundColor(parseColor("#00ff00"))

        # PROMJENA: Postavi ActionMap koji direktno zatvara screen
        self["actions"] = ActionMap(["OkCancelActions"],
                                    {"ok": self.exitAfterComplete,
                                     "cancel": self.exitAfterComplete})

        # Automatski pitaj za kreiranje playliste
        self.session.openWithCallback(self.createFromScrape,
                                      MessageBox,
                                      f"Scan complete! Found {len(self.found_files)} compatible files.\nCreate playlist?",
                                      MessageBox.TYPE_YESNO)

    def askToCreate(self):
        """Ova metoda više nije potrebna nakon finalize_scan"""
        # Možete je ukloniti ili ostaviti praznu
        pass

    def exitAfterComplete(self):
        """Bezbedno zatvaranje nakon završetka"""
        try:
            self.timer.stop()
        except:
            pass
        self.close()

    def cancelScrape(self):
        """Prekid skeniranja"""
        if not self.is_scanning:
            self.exitAfterComplete()
            return
        self.stop = True
        try:
            self.timer.stop()
        except:
            pass
        self["progress_text"].setText("Cancelling...")
        self["progress"].setValue(0)
        self.session.open(MessageBox,
                          f"Scan cancelled.\nFound {len(self.found_files)} files so far.",
                          MessageBox.TYPE_INFO, timeout=3)
        self.close()

    def createFromScrape(self, answer):
        """Poziva ekran za kreiranje liste"""
        if answer and self.found_files:
            self.session.open(CreatePlaylistScreen, self.found_files)
        else:
            self.close()

# =================================== CONTENT SCREEN (v1.1) ===================================

class ContentScreen(Screen):
    skin = """
    <screen name="ContentScreen" position="center,center" size="1800,800" title="..:: Directory Content v{} - Second Screen ::..">
        <widget name="content_list" position="0,0" size="700,700" itemHeight="33" font="Regular;28"  scrollbarMode="showOnDemand" />
        <widget name="selected_list" position="750,0" size="650,700" font="Regular;20" scrollbarMode="showOnDemand" />
        <ePixmap pixmap="{}background.png" position="1400,0" size="400,800" alphatest="on" />
        <!-- Dugmad -->
        <ePixmap pixmap="buttons/red.png" position="50,720" size="35,35" alphatest="blend" />
        <eLabel text="Back" position="100,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#800000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/green.png" position="320,720" size="35,35" alphatest="blend" />
        <eLabel text="Select Folder" position="370,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#008000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/yellow.png" position="590,720" size="35,35" alphatest="blend" />
        <eLabel text="Create" position="640,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#808000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/blue.png" position="860,720" size="35,35" alphatest="blend" />
        <eLabel text="All" position="910,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#000080" halign="center" valign="center" transparent="0" />
    </screen>""".format(PLUGIN_VERSION, PLUGIN_PATH)

    def __init__(self, session, base_url):
        Screen.__init__(self, session)
        self.base_url = base_url.rstrip('/') + '/'
        self.current_url = self.base_url
        self.history = [self.current_url]
        self.content_items = []
        self.selected = []
        self.load_error = None  # Za čuvanje greške

        self["content_list"] = MenuList([], enableWrapAround=True)
        self["content_list"].selectionEnabled(1)
        self["selected_list"] = ScrollLabel("")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "WizardActions", "ListboxActions"],
                                    {
                                        "ok": self.selectItem,  # OK: navigacija ili selekcija fajla
                                        "cancel": self.goBack,
                                        "red": self.goBack,
                                        "green": self.selectFolder,  # Novo: zeleno za selekciju cijelog foldera
                                        "yellow": self.createFile,
                                        "blue": self.selectAll
                                    }, -2)

        # Timer za odloženo učitavanje i prikaz greške
        self.loadTimer = eTimer()
        self.loadTimer.callback.append(self.delayedLoad)
        self.onLayoutFinish.append(self.startLoadTimer)

    def startLoadTimer(self):
        self.loadTimer.start(500, True)  # 500ms, singleshot=True

    def delayedLoad(self):
        self.loadContent()
        if self.load_error:
            self.session.openWithCallback(self.errorCallback, MessageBox,
                                          f"Address not available or timed out:\n{self.load_error}\n\nPlease try again later or check the URL.",
                                          MessageBox.TYPE_ERROR, timeout=10)

    def errorCallback(self, ret=None):
        self.goBack()  # Automatski se vrati nazad ako je greška

    def _parse_directory(self, directory_url):
        """Parsira direktorij i vraća listu (name, full_url, 'file') ili 'folder'"""
        items = []
        try:
            req = urllib.request.Request(directory_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response = urllib.request.urlopen(req, timeout=30)
            html = response.read().decode('utf-8', errors='ignore')

            links = re.findall(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', html)

            for href, raw_name in links:
                href = href.strip()
                raw_name = raw_name.strip()

                if href.startswith('?'):
                    continue

                href_clean = href.split('?')[0].split('#')[0]
                if not href_clean or href_clean in ('../', './'):
                    continue

                try:
                    decoded_href = urllib.parse.unquote(href_clean)
                except:
                    decoded_href = href_clean

                full_url = urllib.parse.urljoin(directory_url, href_clean)

                # Očisti prikazani naziv
                display_name = raw_name
                if '&gt;' in display_name:
                    display_name = display_name.replace('&gt;', '') + '...'

                # Folder
                if href_clean.endswith('/'):
                    folder_name = display_name.rstrip('/') if display_name.endswith('/') else display_name
                    items.append((folder_name, full_url, 'folder'))
                # Fajl
                elif decoded_href.lower().endswith(('.mp4', '.mkv', '.mp3', '.flac', '.avi', '.ts')):
                    # Ako je naziv prekratak → koristi puni iz href-a
                    if '...' in display_name or len(display_name) < len(decoded_href) - 10:
                        display_name = urllib.parse.unquote(os.path.basename(href_clean))
                    items.append((display_name, full_url, 'file'))

        except Exception as e:
            print(f"[CiefpOpenDirectories] _parse_directory error: {e}")

        return items

    def loadContent(self):
        self["content_list"].setList([])
        self.content_items = []
        self.load_error = None

        items = self._parse_directory(self.current_url)

        file_count = len([i for i in items if i[2] == 'file'])
        print(f"[CiefpOpenDirectories] loadContent - Files: {file_count}, Folders: {len(items) - file_count}")

        items.sort(key=lambda x: (x[2] != 'folder', x[0].lower()))
        self.content_items = items
        self["content_list"].setList(
            [f"{'[FOLDER]' if item[2] == 'folder' else '[FILE]'} {item[0]}" for item in items]
        )
        if not items:
            self["content_list"].setList(["[INFO] The directory is empty."])

    def selectFolder(self):
        idx = self["content_list"].getSelectedIndex()
        if idx is None or idx >= len(self.content_items):
            return
        item = self.content_items[idx]
        if item[2] != 'folder':
            self.session.open(MessageBox, "This is not a folder! Use OK to select files.", MessageBox.TYPE_WARNING,
                              timeout=3)
            return

        import time
        start_time = time.time()  # Počni mjerenje vremena
        folder_count = [0]  # Koristimo listu jer Python ne dozvoljava promjenu int u closure-u

        # Počni rekurziju
        added_files = self._recursive_select_folder(item[1], folder_count)

        elapsed = time.time() - start_time  # Završi mjerenje

        self.updateSelectedList()

        if added_files:
            self.session.open(MessageBox,
                              f"Successfully added {len(added_files)} files!\n"
                              f"From {folder_count[0]} folders in {elapsed:.1f} seconds.",
                              MessageBox.TYPE_INFO, timeout=6)
        else:
            self.session.open(MessageBox, "No files found in this folder.", MessageBox.TYPE_INFO, timeout=3)

    def _recursive_select_folder(self, folder_url, folder_count, added=None):
        if added is None:
            added = []

        # Povećaj brojač foldera
        folder_count[0] += 1

        items = self._parse_directory(folder_url)
        for item in items:
            if item[2] == 'folder':
                self._recursive_select_folder(item[1], folder_count, added)
            elif item[2] == 'file' and item not in self.selected:
                self.selected.append(item)
                added.append(item)

        return added

    def selectItem(self):
        idx = self["content_list"].getSelectedIndex()
        if idx is None or idx >= len(self.content_items):
            return
        item = self.content_items[idx]
        if item[2] == 'folder':
            self.current_url = item[1]
            self.history.append(self.current_url)
            self.loadContent()
        elif item[2] == 'file':
            if item not in self.selected:
                self.selected.append(item)
                self.updateSelectedList()
                self.session.open(MessageBox, f"Selected: {item[0]}", MessageBox.TYPE_INFO, timeout=2)

    def selectAll(self):
        added = 0
        for item in self.content_items:
            if item[2] == 'file' and item not in self.selected:
                self.selected.append(item)
                added += 1
        self.updateSelectedList()
        if added:
            self.session.open(MessageBox, f"All {added} files selected!", MessageBox.TYPE_INFO, timeout=2)

    def updateSelectedList(self):
        text = "\n".join([f"[SELECTED] {s[0]}" for s in self.selected])
        self["selected_list"].setText(text)

    def goBack(self):
        if len(self.history) > 1:
            self.history.pop()
            self.current_url = self.history[-1]
            self.loadContent()
        else:
            self.close()

    def createFile(self):
        if not self.selected:
            self.session.open(MessageBox, "No files selected!", MessageBox.TYPE_WARNING)
            return
        choices = [("m3u", "Create M3U Playlist"), ("bouquet", "Create a Userbouquet")]
        self.session.openWithCallback(self.createCallback, ChoiceBox, title="Select file type", list=choices)

    def createCallback(self, choice):
        if not choice:
            return
        typ, _ = choice

        # Čist default naziv — korisnik može dodati datum ako želi
        default_name = "IPTV OPD"

        self.session.openWithCallback(
            lambda new_name: self.finalizeCreation(typ, new_name or default_name),
            VirtualKeyBoard,
            title="Unesite naziv playliste/bouqueta:",
            text=default_name
        )

    def finalizeCreation(self, typ, name):
        """Finalizira kreiranje fajla sa zadatim nazivom"""
        if not self.selected:
            self.session.open(MessageBox, "No files selected!", MessageBox.TYPE_WARNING)
            return

        # Generiši jedinstveni brojač (samo za M3U, ali koristimo isti pristup)
        counter = len([f for f in os.listdir(TMP_PATH) if f.endswith('.m3u')]) + 1

        # Format datuma: 07112025_1815 (bez . i :)
        now = datetime.now()
        dt_str = now.strftime("%d%m%Y_%H%M")

        # Očisti naziv za fajl sistem
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_').strip('_')

        if typ == "m3u":
            filename = f"{TMP_PATH}{safe_name}_{dt_str}_{counter}.m3u"
            with open(filename, "w") as f:
                f.write("#EXTM3U\n")
                for item in self.selected:
                    f.write(f"#EXTINF:-1,{item[0]}\n{item[1]}\n")
            self.session.open(MessageBox,
                              f"M3U created: {os.path.basename(filename)}\nYou can run it in Media Player.",
                              MessageBox.TYPE_INFO)

        elif typ == "bouquet":
            # Kreiraj naziv fajla
            filename = f"userbouquet.{safe_name}_{dt_str}_{counter}.tv"
            path = "/etc/enigma2/" + filename

            with open(path, "w") as f:
                f.write(f"#NAME {name}\n")  # Pravi naziv bouqueta
                for item in self.selected:
                    url = item[1]
                    item_name = item[0]
                    lower_name = item_name.lower()
                    is_audio = lower_name.endswith(('.mp3', '.flac'))
                    service_type = "2" if is_audio else "1"

                    # Enkodiranje URL-a
                    if url.startswith('https://'):
                        prefix = 'https%3a//'
                        url_part = url[8:]
                    else:
                        prefix = 'http%3a//'
                        url_part = url[7:] if url.startswith('http://') else url

                    encoded_url = prefix + url_part.replace('/', '%2f').replace(':', '%3a').replace('?', '%3f').replace(
                        '&', '%26')
                    f.write(f"#SERVICE 4097:0:{service_type}:0:0:0:0:0:0:0:{encoded_url}:{item_name}\n")
                    f.write(f"#DESCRIPTION {item_name}\n")

            # Dodaj u bouquets.tv
            with open("/etc/enigma2/bouquets.tv", "a") as f:
                f.write(f'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{filename}" ORDER BY bouquet\n')

            # Reload bouqueta
            eDVBDB.getInstance().reloadBouquets()
            eDVBDB.getInstance().reloadServicelist()

            # PRAVI naziv bouqueta u poruci
            self.session.open(MessageBox,
                              f"Userbouquet created: {name}\nBouquets.tv reloaded!",
                              MessageBox.TYPE_INFO)


# =================================== CREATE PLAYLIST SCREEN ===================================
class CreatePlaylistScreen(Screen):
    skin = """
    <screen position="center,center" size="900,450" title="Create Playlist">
        <eLabel text="Name:" position="50,60" size="150,40" font="Regular;26" />
        <widget name="name" position="200,60" size="650,40" font="Regular;26" halign="left" />
        <eLabel text="Type will be chosen after confirming." position="50,120" size="800,40" font="Regular;22" foregroundColor="#aaaaaa"/>

        <ePixmap pixmap="buttons/red.png" position="80,370" size="35,35" alphatest="blend" />
        <eLabel text="Cancel" position="130,360" size="180,50" font="Regular;28"
                foregroundColor="white" backgroundColor="#800000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/green.png" position="350,370" size="35,35" alphatest="blend" />
        <eLabel text="Edit Name" position="400,360" size="200,50" font="Regular;28"
                foregroundColor="white" backgroundColor="#008000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/blue.png" position="650,370" size="35,35" alphatest="blend" />
        <eLabel text="Create" position="700,360" size="180,50" font="Regular;28"
                foregroundColor="white" backgroundColor="#000080" halign="center" valign="center" transparent="0" />
    </screen>"""

    def __init__(self, session, files):
        Screen.__init__(self, session)
        self.files = files

        # Kreiraj početni naziv kao i ranije
        default_name = config.ciefp.default_name.value
        dt = ""
        if config.ciefp.include_date.value:
            dt += datetime.now().strftime("%d%m%Y")
        if config.ciefp.include_time.value:
            dt += "_" + datetime.now().strftime("%H%M")
        if dt:
            dt = "_" + dt.lstrip("_")
        self.final_name = f"{default_name}{dt}"

        # UI elementi
        self["name"] = Label(self.final_name)
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"],
                                    {
                                        "ok": self.chooseType,       # OK = napravi
                                        "cancel": self.exit,         # Cancel
                                        "red": self.exit,            # Crveno = Cancel
                                        "green": self.editName,      # Zeleno = izmena naziva
                                        "blue": self.chooseType      # Plavo = Create (isti efekat kao OK)
                                    }, -2)

    def editName(self):
        """Omogućava korisniku da promeni naziv fajla"""
        self.session.openWithCallback(self.nameChanged, VirtualKeyBoard,
                                      title="Enter new playlist name:",
                                      text=self.final_name)

    def nameChanged(self, new_name):
        if new_name and new_name.strip():
            safe = "".join(c for c in new_name if c.isalnum() or c in " _-").replace(" ", "_")
            self.final_name = safe.strip("_")
            self["name"].setText(self.final_name)

    def chooseType(self):
        """Korisnik bira tip fajla (m3u/bouquet)"""
        # Mali delay da se izbegne dupli OK signal posle tastature
        try:
            from enigma import eTimer
            t = eTimer()
            def delayed_open():
                try:
                    t.stop()
                except:
                    pass
                choices = [("m3u", "M3U Playlist"), ("bouquet", "Enigma2 Bouquet")]
                self.session.openWithCallback(self.createConfirmed, ChoiceBox, "Select type:", choices)
            t.callback.append(delayed_open)
            t.start(400, True)  # 400 ms je dovoljno da "proguta" stari OK event
        except Exception as e:
            print(f"[CreatePlaylistScreen] Timer error: {e}")
            # fallback bez tajmera ako nešto pođe po zlu
            choices = [("m3u", "M3U Playlist"), ("bouquet", "Enigma2 Bouquet")]
            self.session.openWithCallback(self.createConfirmed, ChoiceBox, "Select type:", choices)

    def createConfirmed(self, choice):
        if not choice:
            return
        typ = choice[0]
        self.createFile(typ)

    def createFile(self, typ):
        """Kreira fajl prema tipu"""
        name = "".join(c for c in self.final_name if c.isalnum() or c in " _-").replace(" ", "_")
        counter = len([f for f in os.listdir(TMP_PATH) if f.endswith('.m3u')]) + 1
        now = datetime.now().strftime("%d%m%Y_%H%M")
        safe_name = f"{name}_{now}_{counter}"

        if typ == "m3u":
            path = f"{TMP_PATH}{safe_name}.m3u"
            with open(path, "w") as f:
                f.write("#EXTM3U\n")
                for item in self.files:
                    f.write(f"#EXTINF:-1,{item[0]}\n{item[1]}\n")
            self.session.open(MessageBox,
                              f"M3U created:\n{os.path.basename(path)}",
                              MessageBox.TYPE_INFO, timeout=5)

        elif typ == "bouquet":
            path = f"/etc/enigma2/userbouquet.{safe_name}.tv"
            with open(path, "w") as f:
                f.write(f"#NAME {self.final_name}\n")
                for item in self.files:
                    url, title = item[1], item[0]
                    is_audio = title.lower().endswith(('.mp3', '.flac'))
                    stype = "2" if is_audio else "1"
                    enc = 'https%3a//' if url.startswith('https://') else 'http%3a//'
                    enc += url.split('://', 1)[1].replace('/', '%2f').replace(':', '%3a')\
                             .replace('?', '%3f').replace('&', '%26')
                    f.write(f"#SERVICE 4097:0:{stype}:0:0:0:0:0:0:0:{enc}:{title}\n")
                    f.write(f"#DESCRIPTION {title}\n")
            with open("/etc/enigma2/bouquets.tv", "a") as f:
                f.write(f'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.{safe_name}.tv" ORDER BY bouquet\n')
            eDVBDB.getInstance().reloadBouquets()
            self.session.open(MessageBox,
                              f"Bouquet created:\n{self.final_name}",
                              MessageBox.TYPE_INFO, timeout=5)

        self.close()

    def exit(self):
        self.close()

# =================================== PLUGIN ENTRY ===================================
def main(session, **kwargs):
    session.open(MainScreen)

def Plugins(**kwargs):
    return PluginDescriptor(
        name="CiefpOpenDirectories",
        description=f"Open Directories Browser & Playlist Creator v{PLUGIN_VERSION}",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon="plugin.png",
        fnc=main
    )