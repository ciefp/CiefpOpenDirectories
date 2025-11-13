
# CiefpOpenDirectories v1.2  
**Open Directories Browser & Playlist Creator**  
*Enigma2 Plugin – Browse, Scrape & Generate M3U/Bouquet*

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/ciefp/CiefpOpenDirectories?label=Version)](https://github.com/ciefp/CiefpOpenDirectories/releases)  
[![Enigma2](https://img.shields.io/badge/Enigma2-Compatible-green)](https://enigma2.net)  
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

## Description

**CiefpOpenDirectories** is a powerful Enigma2 plugin for:
- **Browsing Open Directory** servers (HTTP-based file listings)
- **Recursive scraping** to user-defined depth
- **Selecting files and folders**
- **Creating M3U playlists** or **Enigma2 bouquets**

> Perfect for IPTV, movies, series, music – all from public open directories!

---

## What's New in v1.2 (vs v1.1)

| Feature | Description |
|--------|-------------|
| **Larger UI** | 1800x800 – modern, spacious layout |
| **4 Color Buttons** | Red (Exit), Green (Add URL), Yellow (Settings), Blue (Scrape) |
| **Settings Panel** | Default name, date/time, scrape depth, file filter |
| **Scrape Screen** | Progress bar, current folder, stats, depth info |
| **ContentScreen** | Fast, stable, recursive folder selection |
| **Create Screen** | Edit name, OK/Blue = Create |
| **Auto-Update** | With backup of `opendirectories.txt` |
| **Config File** | `/etc/enigma2/ciefp_opendirectories.cfg` |

---

## How to Use

### 1. **Main Menu**
| Button | Action |
|-------|--------|
| **OK** | Open selected directory |
| **Red** | Exit plugin |
| **Green** | Add URL (Virtual Keyboard) |
| **Yellow** | Settings |
| **Blue** | **Scrape** (auto-scan) |

---

### 2. **Directory Browser (ContentScreen)**
| Button | Action |
|-------|--------|
| **OK** | Enter folder / select file |
| **Red** | Go back |
| **Green** | Select **entire folder** (recursive) |
| **Yellow** | **Create** M3U/Bouquet |
| **Blue** | Select **all files** in current folder |

> Selected files appear in the right column `[SELECTED]`

---

### 3. **Scrape Screen**
- Displays:
  - Current folder
  - Depth level
  - Found files
  - Progress bar
- **CANCEL** → stop scan
- At the end → **"Create playlist?"**

---

### 4. **Create Playlist**
| Button | Action |
|-------|--------|
| **OK / Blue** | Choose M3U or Bouquet |
| **Green** | **Edit name** |
| **Red** | Cancel |

---

## Files & Locations

| File | Location | Purpose |
|------|----------|--------|
| `plugin.py` | `/usr/lib/enigma2/python/Plugins/Extensions/CiefpOpenDirectories/` | Main code |
| `plugin.png` | same | Menu icon |
| `background.png` | same | Background image |
| `settings.png` | same | (optional) |
| `opendirectories.txt` | same | URL list |
| `*.m3u` | `/tmp/CiefpOpenDirectories/` | Generated M3U files |
| `userbouquet.*.tv` | `/etc/enigma2/` | Generated bouquets |
| `ciefp_opendirectories.cfg` | `/etc/enigma2/` | Settings |

---

## Installation

```bash
# 1. Copy folder to:
scp -r CiefpOpenDirectories/ root@box:/usr/lib/enigma2/python/Plugins/Extensions/

# 2. Add icons:
#    plugin.png, background.png, settings.png (optional)

# 3. Restart Enigma2
reboot
```

> Or use `installer.sh` (if available)

---

## Screenshots

> *(https://github.com/ciefp/CiefpOpenDirectories/blob/main/screenshot1.jpg)*
> *(https://github.com/ciefp/CiefpOpenDirectories/blob/main/screenshot2.jpg)*
> *(https://github.com/ciefp/CiefpOpenDirectories/blob/main/screenshot3.jpg)*
> *(https://github.com/ciefp/CiefpOpenDirectories/blob/main/screenshot4.jpg)*


---

## Future Plans (v1.3+)

- [ ] Delete URLs from list  
- [ ] Sort by name/size/extension  
- [ ] Search by filename  
- [ ] Support for `.zip`, `.rar` (preview content)  
- [ ] IPTV export (PVR)  
- [ ] Accurate progress bar (estimated total)

---

## Credits

> **@ciefp** – author & visionary  
> Community – testing, feedback, ideas  

---

## License

```
GNU GPL v3.0
```

---

> **Happy Open Directory hunting!**  
> *If you like the plugin – leave a star on GitHub!*
```
