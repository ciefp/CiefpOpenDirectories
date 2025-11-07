from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Screens.MessageBox import MessageBox
from Components.ScrollLabel import ScrollLabel
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap
from enigma import eDVBDB
from enigma import eTimer
import urllib.request
import urllib.parse
import re
import os
from datetime import datetime
from Screens.Console import Console


PLUGIN_VERSION = "1.1" 
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/CiefpOpenDirectories/"
TMP_PATH = "/tmp/CiefpOpenDirectories/"
os.makedirs(TMP_PATH, exist_ok=True)


class MainScreen(Screen):
    skin = """
    <screen name="MainScreen" position="center,center" size="1200,800" title="..:: CiefpOpenDirectories v{} - First Screen ::..">
        <widget name="list" position="0,0" size="800,650" scrollbarMode="showOnDemand" />

        <!-- STATUS PORUKA -->
        <widget name="status_label" position="50,660" size="700,40" font="Regular;26" 
                halign="left" valign="center" foregroundColor="#00ff00" backgroundColor="#10000000" 
                transparent="1" />

        <ePixmap pixmap="%sbackground.png" position="800,0" size="400,800" alphatest="on" />

        <!-- Dugmad -->
        <ePixmap pixmap="buttons/red.png" position="50,720" size="35,35" alphatest="blend" />
        <eLabel text="Exit" position="100,710" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#800000" halign="center" valign="center" transparent="0" />
        <ePixmap pixmap="buttons/green.png" position="500,720" size="35,35" alphatest="blend" />
        <eLabel text="Select" position="550,710" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#008000" halign="center" valign="center" transparent="0" />
    </screen>""" % (PLUGIN_VERSION, PLUGIN_PATH)

    def __init__(self, session):
        Screen.__init__(self, session)
        self["list"] = MenuList([], enableWrapAround=True)
        self["list"].selectionEnabled(1)
        self["status_label"] = Label("")  # Prazno na početku
        self["status_label"].setText("")  # Sigurnost
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "WizardActions", "ListboxActions"],
                            {
                                "ok": self.select,
                                "cancel": self.exit,
                                "red": self.exit,
                                "green": self.select
                            }, -2)

        # poveži navigaciju direktno na listuself.update_timer = eTimer()
        self.update_timer.callback.append(self.check_for_updates)
        self.update_timer.start(1500, True)  # 1.5s nakon starta
        self["list"].moveUp = self["list"].up
        self["list"].moveDown = self["list"].down
        self["list"].selectionEnabled(1)

        self.loadAddresses()

    def moveUp(self):
        self["list"].up()
        
    def moveDown(self):
        self["list"].down()

    def loadAddresses(self):
        try:
            with open(PLUGIN_PATH + "opendirectories.txt", "r") as f:
                addresses = [line.strip() for line in f.readlines() if line.strip()]
            self["list"].setList(addresses)
            if not addresses:
                self.session.open(MessageBox, "No addresses in opendirectories.txt!", MessageBox.TYPE_INFO)
        except Exception as e:
            self["list"].setList([])
            print("[CiefpOpenDirectories] Error loading txt:", e)
            
    def select(self):
        url = self["list"].getCurrent()
        if url:
            if not url.endswith('/'):
                url += '/'
            self.session.open(ContentScreen, url)

    def exit(self):
        self.close()

class ContentScreen(Screen):
    skin = """
    <screen name="ContentScreen" position="center,center" size="1800,800" title="..:: Directory Content v{} - Second Screen ::..">
        <widget name="content_list" position="0,0" size="700,700" font="Regular;22" scrollbarMode="showOnDemand" />
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
def check_for_updates(self):
    self["status_label"].setText("Checking for updates...")
    try:
        self.container = Console()
        self.container.ePopen("wget -q --no-check-certificate -O /tmp/version.txt '%s' && echo SUCCESS" % VERSION_URL, self.update_check_finished)
    except Exception as e:
        self["status_label"].setText("Update check failed.")
        print("[CiefpOpenDirectories] Update error:", e)

def update_check_finished(self, result, retval, extra_args):
    if "SUCCESS" in result:
        try:
            with open("/tmp/version.txt", "r") as f:
                remote_version = f.read().strip()
            os.remove("/tmp/version.txt")

            if remote_version != PLUGIN_VERSION and remote_version:
                self["status_label"].setText(f"Update available: v{remote_version}")
                self.session.openWithCallback(
                    self.start_update,
                    MessageBox,
                    f"New version: v{remote_version}\n"
                    f"Current: v{PLUGIN_VERSION}\n\n"
                    f"Install now?",
                    MessageBox.TYPE_YESNO
                )
            else:
                self["status_label"].setText("Up to date.")
        except Exception as e:
            self["status_label"].setText("Version check failed.")
    else:
        self["status_label"].setText("Failed to check update.")

def start_update(self, answer):
    if answer:
        self["status_label"].setText("Updating...")
        # ... pokreni installer.sh ...
    else:
        self["status_label"].setText("Update cancelled.")

def update_finished(self, *args, **kwargs):
    self.session.open(MessageBox,
        "Update completed!\n"
        "Enigma2 will restart in 3 seconds...",
        MessageBox.TYPE_INFO, timeout=3)

def main(session, **kwargs):
    session.open(MainScreen)
    
def Plugins(**kwargs):
    return PluginDescriptor(
        name="CiefpOpenDirectories",
        description=f"Open Directories Browser & Playlist Creator (Version {PLUGIN_VERSION})",
        icon="plugin.png",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        fnc=main
    )