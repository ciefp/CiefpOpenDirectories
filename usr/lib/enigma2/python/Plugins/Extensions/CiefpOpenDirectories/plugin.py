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



PLUGIN_VERSION = "1.0" 
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/CiefpOpenDirectories/"
TMP_PATH = "/tmp/CiefpOpenDirectories/"
os.makedirs(TMP_PATH, exist_ok=True)


class MainScreen(Screen):
    skin = """
    <screen name="MainScreen" position="center,center" size="1200,800" title="..:: CiefpOpenDirectories - First Screen ::..">
        <widget name="list" position="0,0" size="800,700" scrollbarMode="showOnDemand" />
        <ePixmap pixmap="%sbackground.png" position="800,0" size="400,800" alphatest="on" />
        <!-- Dugmad za MainScreen -->
        <ePixmap pixmap="buttons/red.png" position="50,720" size="35,35" alphatest="blend" />
        <eLabel text="Exit" position="100,710" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#800000" halign="center" valign="center" transparent="0" />

        <ePixmap pixmap="buttons/green.png" position="500,720" size="35,35" alphatest="blend" />
        <eLabel text="Select" position="550,710" size="200,50" font="Regular;28" foregroundColor="white" backgroundColor="#008000" halign="center" valign="center" transparent="0" />
    </screen>""" % PLUGIN_PATH

    def __init__(self, session):
        Screen.__init__(self, session)
        self["list"] = MenuList([], enableWrapAround=True)
        self["list"].selectionEnabled(1)
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "WizardActions", "ListboxActions"],
                            {
                                "ok": self.select,
                                "cancel": self.exit,
                                "red": self.exit,
                                "green": self.select
                            }, -2)

        # poveži navigaciju direktno na listu
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
    <screen name="ContentScreen" position="center,center" size="1800,800" title="..:: Directory Content - Second Screen ::..">
        <widget name="content_list" position="0,0" size="600,700" scrollbarMode="showOnDemand" />
        <widget name="selected_list" position="600,0" size="800,700" font="Regular;22" scrollbarMode="showOnDemand" />
        <ePixmap pixmap="%sbackground.png" position="1400,0" size="400,800" alphatest="on" />
        <!-- Dugmad za ContentScreen -->
        <ePixmap pixmap="buttons/red.png" position="50,720" size="35,35" alphatest="blend" />
        <eLabel text="Back" position="100,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#800000" halign="center" valign="center" transparent="0" />

        <ePixmap pixmap="buttons/green.png" position="320,720" size="35,35" alphatest="blend" />
        <eLabel text="Select" position="370,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#008000" halign="center" valign="center" transparent="0" />

        <ePixmap pixmap="buttons/yellow.png" position="590,720" size="35,35" alphatest="blend" />
        <eLabel text="Create" position="640,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#808000" halign="center" valign="center" transparent="0" />

        <ePixmap pixmap="buttons/blue.png" position="860,720" size="35,35" alphatest="blend" />
        <eLabel text="All" position="910,710" size="180,50" font="Regular;28" foregroundColor="white" backgroundColor="#000080" halign="center" valign="center" transparent="0" />
    </screen>""" % PLUGIN_PATH

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
                                        "ok": self.selectItem,
                                        "cancel": self.goBack,
                                        "red": self.goBack,
                                        "green": self.selectItem,
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

    def loadContent(self):
        self["content_list"].setList([])
        self.content_items = []
        self.load_error = None

        try:
            req = urllib.request.Request(self.current_url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            html = response.read().decode('utf-8', errors='ignore')
            links = re.findall(r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', html)
            items = []
            for href, name in links:
                href = href.split('?')[0].strip()
                name = name.strip()
                if href in ('../', './') or name.startswith('?') or 'Parent Directory' in name:
                    continue
                full_url = urllib.parse.urljoin(self.current_url, href)
                if href.endswith('/'):
                    display_name = name.rstrip('/') if name.endswith('/') else name
                    items.append((display_name, full_url, 'folder'))
                elif name.lower().endswith(('.mp4', '.mkv', '.mp3', '.flac', '.avi', '.ts')):  # dodaj još ekstenzija po želji
                    items.append((name, full_url, 'file'))
            items.sort(key=lambda x: (x[2] != 'folder', x[0].lower()))
            self.content_items = items
            self["content_list"].setList(
                [f"{'[FOLDER]' if item[2] == 'folder' else '[FILE]'} {item[0]}" for item in items]
            )
            if not items:
                self["content_list"].setList(["[INFO] The directory is empty."])

        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, 'reason') else str(e)
            if 'timed out' in reason.lower():
                self.load_error = "Timeout: Server is not responding."
            else:
                self.load_error = f"URL error: {reason}"
            print("[CiefpOpenDirectories] Load error:", e)
        except Exception as e:
            self.load_error = f"Unexpected error: {str(e)}"
            print("[CiefpOpenDirectories] Load error:", e)

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

        # Podrazumevani naziv
        now = datetime.now()
        dt_str = now.strftime("%d.%m.%Y_%H:%M")
        default_name = f"IPTV OPD {dt_str}"

        # Otvori virtuelnu tastaturu za unos naziva
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

        counter = len([f for f in os.listdir(TMP_PATH) if f.endswith('.m3u')]) + 1
        now = datetime.now()
        dt_str = now.strftime("%d.%m.%Y_%H:%M")

        if typ == "m3u":
            # Kreiraj bezbedan naziv fajla
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            filename = f"{TMP_PATH}{safe_name}_{counter}.m3u"

            with open(filename, "w") as f:
                f.write("#EXTM3U\n")
                for item in self.selected:
                    f.write(f"#EXTINF:-1,{item[0]}\n{item[1]}\n")
            self.session.open(MessageBox,
                              f"M3U created: {os.path.basename(filename)}\nYou can run it in Media Player.",
                              MessageBox.TYPE_INFO)

        elif typ == "bouquet":
            # Kreiraj bezbedan naziv fajla
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            safe_dt = dt_str.replace(':', '')
            filename = f"userbouquet.{safe_name}_{safe_dt}_{counter}.tv"
            path = "/etc/enigma2/" + filename

            with open(path, "w") as f:
                f.write(f"#NAME {name}\n")
                for item in self.selected:
                    url = item[1]
                    name = item[0]
                    lower_name = name.lower()
                    is_audio = lower_name.endswith(('.mp3', '.flac'))
                    service_type = "2" if is_audio else "1"
                    # Uvek koristi http prefix u enkodingu
                    if url.startswith('https://'):
                        prefix = 'https%3a//'
                        url_part = url[8:]
                    else:
                        prefix = 'http%3a//'
                        url_part = url[7:] if url.startswith('http://') else url
                    encoded_url = prefix + url_part.replace('/', '%2f').replace(':', '%3a').replace('?', '%3f').replace('&', '%26')
                    f.write(f"#SERVICE 4097:0:{service_type}:0:0:0:0:0:0:0:{encoded_url}:{name}\n")
                    f.write(f"#DESCRIPTION {name}\n")

            with open("/etc/enigma2/bouquets.tv", "a") as f:
                f.write(f'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{filename}" ORDER BY bouquet\n')

            eDVBDB.getInstance().reloadBouquets()
            eDVBDB.getInstance().reloadServicelist()
            self.session.open(MessageBox, f"Userbouquet created:{name}\nBouquets.tv reloaded!", MessageBox.TYPE_INFO)


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