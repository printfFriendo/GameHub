import base64
import random
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, quote_plus
import requests
from bs4 import BeautifulSoup

REALISTIC_HEADERS_TEMPLATE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

def classify_download_link(label, url):
    """
    Classifica um link de download quanto ao:
    - category: "base", "update", "dlc", "torrent", "mirror"
    - category_label: "🎮 Jogo Base", "🔄 Atualização", "🎁 DLC/Extra", "🧲 Torrent", "🔗 Espelho"
    - provider: "Mediafire", "Mega", "Google Drive", "DataNodes", "Torrent (Magnet)", etc.
    - provider_color: cor em hex para a tag visual
    - part_text: "Parte 1", "Parte 2", etc.
    """
    label_str = str(label or "").strip()
    url_str = str(url or "").strip()
    low_text = (label_str + " " + url_str).lower()

    # 1. Provedor / Servidor
    provider = "Servidor Direto"
    provider_color = "#3b82f6"
    provider_icon = "🌐"

    if url_str.startswith("magnet:"):
        provider = "Torrent (Magnet)"
        provider_color = "#7c3aed"
        provider_icon = "🧲"
    elif "1337x" in url_str:
        provider = "1337x (Torrent)"
        provider_color = "#dc2626"
        provider_icon = "🏴‍☠️"
    elif "rutor" in url_str:
        provider = "RuTor (Torrent)"
        provider_color = "#b45309"
        provider_icon = "🏴‍☠️"
    elif "tapochek" in url_str:
        provider = "Tapochek"
        provider_color = "#475569"
        provider_icon = "🏴‍☠️"
    elif "mediafire.com" in url_str:
        provider = "Mediafire"
        provider_color = "#0284c7"
        provider_icon = "📦"
    elif "mega.nz" in url_str or "mega.co.nz" in url_str:
        provider = "Mega"
        provider_color = "#ef4444"
        provider_icon = "☁️"
    elif "1fichier.com" in url_str:
        provider = "1Fichier"
        provider_color = "#f59e0b"
        provider_icon = "📁"
    elif "drive.google.com" in url_str:
        provider = "Google Drive"
        provider_color = "#10b981"
        provider_icon = "🌐"
    elif "datanodes.to" in url_str:
        provider = "DataNodes"
        provider_color = "#f97316"
        provider_icon = "⚡"
    elif "fuckingfast.co" in url_str:
        provider = "FuckingFast"
        provider_color = "#06b6d4"
        provider_icon = "⚡"
    elif "filekeeper.net" in url_str:
        provider = "FileKeeper"
        provider_color = "#64748b"
        provider_icon = "💾"
    elif "filecrypt.cc" in url_str:
        provider = "FileCrypt"
        provider_color = "#0891b2"
        provider_icon = "🔒"
    elif "gofile.io" in url_str:
        provider = "Gofile"
        provider_color = "#6366f1"
        provider_icon = "🚀"
    elif "pixeldrain.com" in url_str:
        provider = "Pixeldrain"
        provider_color = "#059669"
        provider_icon = "💧"
    elif "qiwi.gg" in url_str:
        provider = "Qiwi"
        provider_color = "#84cc16"
        provider_icon = "🥝"
    elif "downloadgameps3" in url_str:
        provider = "DownloadGamePS"
        provider_color = "#2563eb"
        provider_icon = "🛡️"
    elif "romsfast.com" in url_str or "romsfun" in url_str:
        provider = "ROMSFast"
        provider_color = "#f43f5e"
        provider_icon = "⚡"
    elif "paste.fitgirl" in url_str:
        provider = "FitGirl Paste"
        provider_color = "#a855f7"
        provider_icon = "📋"

    # 2. Categoria do Conteúdo
    category = "base"
    category_label = "Jogo Base"
    category_icon = "🎮"

    if url_str.startswith("magnet:") or ".torrent" in url_str or "1337x" in url_str or "rutor" in url_str:
        category = "torrent"
        category_label = "Torrent / P2P"
        category_icon = "🧲"
    elif re.search(r'\b(update|atualizacao|patch|hotfix|v[0-9]+\.[0-9]+|backport|fix)\b', low_text):
        category = "update"
        category_label = "Atualização / Patch"
        category_icon = "🔄"
    elif re.search(r'\b(dlc|bonus|extra|addon|expansion|soundtrack|ost)\b', low_text):
        category = "dlc"
        category_label = "DLC & Bônus"
        category_icon = "🎁"
    elif re.search(r'\b(mod|hack|cheat|dublado|traducao|legendado)\b', low_text):
        category = "mod"
        category_label = "Mod / Tradução"
        category_icon = "🛠️"
    elif re.search(r'\b(mirror|espelho|container)\b', low_text):
        category = "mirror"
        category_label = "Espelho / Mirror"
        category_icon = "🔗"

    # 3. Extração de Parte (ex: Parte 01, Part 2)
    part_match = re.search(r'(?:part|pt|parte)[\._\s-]*0*([0-9]+)', low_text)
    part_text = f"Parte {part_match.group(1)}" if part_match else ""

    # 4. Rótulo amigável
    clean_label = label_str
    if not clean_label or clean_label.lower().startswith("http") or len(clean_label) < 3:
        filename = url_str.split("?")[0].split("#")[0].rstrip("/").split("/")[-1]
        clean_label = urllib.parse.unquote(filename) if filename else f"{provider} Download"

    return {
        "url": url_str,
        "label": clean_label,
        "category": category,
        "category_label": category_label,
        "category_icon": category_icon,
        "provider": provider,
        "provider_icon": provider_icon,
        "provider_color": provider_color,
        "part_text": part_text,
    }


class AntiBotScraper:
    def __init__(self, site_name="Multi-Scraper", site_url="https://dlpsgame.com"):
        self.site_name = site_name
        self.site_url = site_url
        self.session = requests.Session()
        self.session.headers.update(REALISTIC_HEADERS_TEMPLATE)

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def _infer_platform(self, text):
        t = text.lower()
        if "switch 2" in t or "nup" in t:
            return "Switch 2"
        if "switch" in t or "nsp" in t or "xci" in t:
            return "Switch"
        if "ps5" in t:
            return "PS5"
        if "ps4" in t or "pkg" in t:
            return "PS4"
        if "ps3" in t:
            return "PS3"
        if "ps2" in t:
            return "PS2"
        if "psp" in t:
            return "PSP"
        if "repack" in t or "pc" in t or "windows" in t:
            return "PC"
        if "snes" in t or "super nintendo" in t:
            return "SNES"
        if "nes" in t:
            return "NES"
        if "gba" in t or "game boy advance" in t:
            return "GBA"
        if "gamecube" in t:
            return "GameCube"
        if "wii" in t:
            return "Wii"
        if "n64" in t or "nintendo 64" in t:
            return "N64"
        return "Multi"

    def search_dlps(self, query, max_results=15):
        results = []
        if not query:
            return results
        url = f"https://dlpsgame.com/?s={quote_plus(query)}"
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for h2 in soup.select("h2"):
                    a = h2.find("a")
                    if not a or not a.get("href"):
                        continue
                    title = a.get_text(strip=True)
                    page_url = a["href"].strip()
                    if title == "LABELS" or "category" in page_url:
                        continue

                    container = h2.find_parent("div") or h2.find_parent("article")
                    cover_url = ""
                    if container:
                        img = container.find("img")
                        if img:
                            cover_url = img.get("src") or img.get("data-src") or ""

                    results.append({
                        "title": title,
                        "url": page_url,
                        "page_url": page_url,
                        "cover_url": cover_url,
                        "platform": self._infer_platform(title + " " + page_url),
                        "source_name": "DLPSGame",
                    })
                    if len(results) >= max_results:
                        break
        except Exception as e:
            print(f"[DLPSScraper Error] {e}")
        return results

    def search_romslab(self, query, max_results=15):
        results = []
        if not query:
            return results
        url = f"https://romslab.com/?s={quote_plus(query)}"
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for h2 in soup.select("h2"):
                    a = h2.find("a")
                    if not a or not a.get("href"):
                        continue
                    title = a.get_text(strip=True)
                    page_url = a["href"].strip()
                    if "category" in page_url:
                        continue

                    container = h2.find_parent("li") or h2.find_parent("article") or h2.find_parent("div")
                    cover_url = ""
                    if container:
                        img = container.find("img")
                        if img:
                            c_cand = img.get("data-src") or img.get("src") or ""
                            if "placeholder" not in c_cand:
                                cover_url = c_cand

                    results.append({
                        "title": title,
                        "url": page_url,
                        "page_url": page_url,
                        "cover_url": cover_url,
                        "platform": self._infer_platform(title + " " + page_url),
                        "source_name": "ROMSLab",
                    })
                    if len(results) >= max_results:
                        break
        except Exception as e:
            print(f"[ROMSLabScraper Error] {e}")
        return results

    def search_romsfun(self, query, max_results=15):
        results = []
        if not query:
            return results
        url = f"https://romsfun.com/browse-all-roms/?q={quote_plus(query)}"
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for div in soup.select("div.rf-li"):
                    a_title = div.select_one("h3.rf-li-title a")
                    if not a_title:
                        continue
                    title = a_title.get_text(strip=True)
                    link = a_title.get("href", "").strip()
                    if not link:
                        continue

                    img = div.select_one(".rf-li-th img")
                    img_src = img.get("src") or img.get("data-src") or "" if img else ""

                    platform = "ROM / Retrô"
                    match = re.search(r'/roms/([^/]+)/', link)
                    if match:
                        platform = match.group(1).replace("-", " ").upper()

                    results.append({
                        "title": title,
                        "url": link,
                        "page_url": link,
                        "cover_url": img_src,
                        "platform": platform,
                        "source_name": "ROMSFun",
                    })
                    if len(results) >= max_results:
                        break
        except Exception as e:
            print(f"[ROMSFunScraper Error] {e}")
        return results

    def search_fitgirl(self, query, max_results=15):
        results = []
        if not query:
            return results
        url = f"https://fitgirl-repacks.site/?s={quote_plus(query)}"
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for art in soup.select("article.post"):
                    h = art.select_one("h1.entry-title a, h2.entry-title a")
                    if not h:
                        continue
                    title = h.get_text(strip=True)
                    link = h.get("href", "").strip()
                    if "updates digest" in title.lower() or not link:
                        continue

                    # Tenta capturar capa se houver imagem no snippet
                    img = art.select_one(".entry-content img, img")
                    img_src = img.get("src") or "" if img else ""

                    results.append({
                        "title": title,
                        "url": link,
                        "page_url": link,
                        "cover_url": img_src,
                        "platform": "PC (Repack)",
                        "source_name": "FitGirl Repacks",
                    })
                    if len(results) >= max_results:
                        break

                # Busca capas reais em paralelo nas páginas individuais para os que não têm capa
                to_fetch = [r for r in results if not r.get("cover_url") and r.get("page_url")]
                if to_fetch:
                    def _fetch_post_cover(item):
                        try:
                            r_post = self.session.get(item["page_url"], timeout=6)
                            if r_post.status_code == 200:
                                s_post = BeautifulSoup(r_post.text, "html.parser")
                                entry = s_post.select_one(".entry-content")
                                if entry:
                                    for im in entry.select("img"):
                                        src = im.get("src") or ""
                                        if src and not any(x in src.lower() for x in ["donate", "bitcoin", "hitcounter", "flag", "paypal"]):
                                            item["cover_url"] = src.strip()
                                            break
                        except Exception:
                            pass

                    with ThreadPoolExecutor(max_workers=min(len(to_fetch), 6)) as executor:
                        list(executor.map(_fetch_post_cover, to_fetch))
        except Exception as e:
            print(f"[FitGirlScraper Error] {e}")
        return results

    def search_by_mode(self, mode, query, max_results=20):
        m = str(mode).lower()
        if m in ["romsfun", "romfun"]:
            return self.search_romsfun(query, max_results)
        elif m in ["fitgirl", "fitgirl_repacks"]:
            return self.search_fitgirl(query, max_results)
        elif m in ["dlps", "dlpsgame"]:
            return self.search_dlps(query, max_results)
        elif m in ["romslab"]:
            return self.search_romslab(query, max_results)
        else:
            # anti_bot_scraper unificado (busca em DLPS + ROMSLab)
            return self.search_category(query, max_results)

    def search_category(self, query, max_results=30):
        dlps_res = self.search_dlps(query, max_results=max_results // 2)
        roms_res = self.search_romslab(query, max_results=max_results // 2)
        return dlps_res + roms_res

    def search(self, query, max_results=30):
        return self.search_category(query, max_results)


def create_dlps_roms_scraper():
    return AntiBotScraper("Multi-Scraper", "https://dlpsgame.com")
