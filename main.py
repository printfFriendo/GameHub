import os
import sys
import re
import json
import base64
import threading
import webbrowser
import multiprocessing
import shutil
from io import BytesIO
from urllib.parse import urljoin, quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import customtkinter as ctk
from tkinter import messagebox

from scrapers.anti_bot_scraper import create_dlps_roms_scraper, classify_download_link

# Configuração Visual do CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
SITES_CONFIG_FILE = os.path.join(APP_DIR, "sites_config.json")

# Se for executável congelado e ainda não existir sites_config.json na pasta do .exe, copia do bundle
if getattr(sys, "frozen", False) and not os.path.exists(SITES_CONFIG_FILE):
    bundled_cfg = os.path.join(getattr(sys, "_MEIPASS", ""), "sites_config.json")
    if os.path.exists(bundled_cfg):
        try:
            shutil.copyfile(bundled_cfg, SITES_CONFIG_FILE)
        except Exception:
            pass

# Cabeçalho padrão para simular um navegador real e evitar bloqueios simples
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Configuração inicial de sites (Criada automaticamente se sites_config.json não existir)
DEFAULT_SITES_CONFIG = [
    {
        "name": "Archive.org (Jogos Clássicos & ROMs)",
        "enabled": True,
        "platform": "Retro / Multi",
        "mode": "archive_api",
        "base_url": "https://archive.org",
        "search_url": "",
        "item_selector": "",
        "title_selector": "",
        "link_selector": "",
        "image_selector": "",
        "download_link_pattern": r"\.(zip|7z|iso|chd|exe|rom)$"
    },
    {
        "name": "DLPSGame (Anti-Bot Scraper)",
        "enabled": True,
        "platform": "PlayStation / Switch / PC",
        "mode": "dlpsgame",
        "base_url": "https://dlpsgame.com/",
        "search_url": "https://dlpsgame.com/?s={query}",
        "item_selector": "",
        "title_selector": "",
        "link_selector": "",
        "image_selector": "",
        "download_link_pattern": r"(mega\.nz|mediafire\.com|drive\.google\.com|1fichier\.com|gofile\.io|qiwi|datanodes\.to|filekeeper\.net|pixeldrain\.com|filecrypt\.cc|downloadgameps3\.(net|com)/archives/|\.pkg|\.zip|\.7z|\.rar|\.nsp|\.xci)"
    },
    {
        "name": "ROMSLab (Anti-Bot Scraper)",
        "enabled": True,
        "platform": "Switch / PC / PS5",
        "mode": "romslab",
        "base_url": "https://romslab.com/",
        "search_url": "https://romslab.com/?s={query}",
        "item_selector": "",
        "title_selector": "",
        "link_selector": "",
        "image_selector": "",
        "download_link_pattern": r"(mega\.nz|mediafire\.com|drive\.google\.com|1fichier\.com|gofile\.io|qiwi|datanodes\.to|filekeeper\.net|pixeldrain\.com|filecrypt\.cc|downloadgameps3\.(net|com)/archives/|\.pkg|\.zip|\.7z|\.rar|\.nsp|\.xci)"
    },
    {
        "name": "ROMSFun (ROMs & Retrô)",
        "enabled": True,
        "platform": "Multi-Console / Retrô",
        "mode": "romsfun",
        "base_url": "https://romsfun.com/roms/",
        "search_url": "https://romsfun.com/browse-all-roms/?q={query}",
        "item_selector": "",
        "title_selector": "",
        "link_selector": "",
        "image_selector": "",
        "download_link_pattern": r"(romsfun\.com|romsfast\.com|mega\.nz|mediafire\.com|1fichier\.com|drive\.google\.com|\.zip|\.7z|\.iso|\.rar|\.rom|\.nes|\.sfc|\.bin)"
    },
    {
        "name": "FitGirl Repacks (PC Games)",
        "enabled": True,
        "platform": "PC / Repack",
        "mode": "fitgirl",
        "base_url": "https://fitgirl-repacks.site/",
        "search_url": "https://fitgirl-repacks.site/?s={query}",
        "item_selector": "",
        "title_selector": "",
        "link_selector": "",
        "image_selector": "",
        "download_link_pattern": r"(magnet:\?|1337x|rutor|tapochek|datanodes\.to|fuckingfast\.co|filekeeper\.net|paste\.fitgirl|gofile\.io|pixeldrain\.com|multiup|1fichier|mediafire|drive\.google|\.torrent|\.rar|\.bin|\.zip)"
    }
]


# =====================================================================
# MOTOR MODULAR DE BUSCA E EXTRAÇÃO (SCRAPER ENGINE)
# =====================================================================
class ModularScraperEngine:
    """
    Motor flexível que lê as configurações do sites_config.json
    e executa buscas em múltiplos sites simultaneamente.
    """

    @staticmethod
    def search_all_sites(sites_config, query):
        """Busca o termo em todos os sites ativos em paralelo."""
        active_sites = [s for s in sites_config if s.get("enabled", True)]
        all_results = []

        if not active_sites:
            return all_results

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_site = {
                executor.submit(ModularScraperEngine.search_single_site, site, query): site
                for site in active_sites
            }
            for future in as_completed(future_to_site):
                try:
                    site_results = future.result()
                    all_results.extend(site_results)
                except Exception:
                    # Isola falhas: se 1 site cair, os outros continuam funcionando
                    pass

        return all_results

    @staticmethod
    def search_single_site(site_cfg, query):
        mode = site_cfg.get("mode", "html_custom")
        if mode == "archive_api":
            return ModularScraperEngine._search_archive_org(site_cfg, query)
        elif mode == "wp_rest_api":
            return ModularScraperEngine._search_wp_rest_api(site_cfg, query)
        elif mode in ["anti_bot_scraper", "dlpsgame", "romslab", "romsfun", "fitgirl"]:
            return ModularScraperEngine._search_anti_bot_scraper(site_cfg, query)
        else:
            return ModularScraperEngine._search_html_custom(site_cfg, query)

    @staticmethod
    def _search_archive_org(site_cfg, query):
        """Busca na API pública do Internet Archive (Software / ROMs)."""
        results = []
        encoded_q = quote_plus(f"{query} AND mediatype:(software)")
        api_url = (
            f"https://archive.org/advancedsearch.php?q={encoded_q}"
            f"&fl[]=identifier,title&rows=12&page=1&output=json"
        )
        try:
            resp = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=8)
            resp.raise_for_status()
            docs = resp.json().get("response", {}).get("docs", [])
            for doc in docs:
                ident = doc.get("identifier")
                title = doc.get("title", ident)
                if not ident:
                    continue
                results.append({
                    "title": title,
                    "platform": site_cfg.get("platform", "Retro"),
                    "source_name": site_cfg.get("name", "Archive.org"),
                    "cover_url": f"https://archive.org/services/img/{ident}",
                    "page_url": f"https://archive.org/details/{ident}",
                    "direct_download": f"https://archive.org/compress/{ident}",
                    "download_pattern": site_cfg.get("download_link_pattern", "")
                })
        except Exception:
            pass
        return results
    @staticmethod
    def _search_wp_rest_api(site_cfg, query):
        """
        Conecta na API REST nativa de qualquer site WordPress (/wp-json/wp/v2/posts).
        Dispensa configuração de seletores CSS!
        """
        results = []
        base_url = site_cfg.get("base_url", "").rstrip("/")
        if not base_url:
            return results

        api_url = f"{base_url}/wp-json/wp/v2/posts?search={quote_plus(query)}&_embed&per_page=12"
        try:
            resp = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=10)
            resp.raise_for_status()
            posts = resp.json()

            for post in posts:
                # 1. Título limpo de entidades HTML
                raw_title = post.get("title", {}).get("rendered", "Sem Título")
                clean_title = BeautifulSoup(raw_title, "html.parser").get_text().strip()

                # 2. Link do Post
                page_url = post.get("link", "")

                # 3. Capa destacada via _embedded
                cover_url = ""
                embedded = post.get("_embedded", {})
                media_list = embedded.get("wp:featuredmedia", [])
                if media_list and isinstance(media_list, list):
                    cover_url = media_list[0].get("source_url", "")

                # 4. Tenta extrair links de download já presentes no conteúdo do post
                content_html = post.get("content", {}).get("rendered", "")
                direct_dl = ModularScraperEngine._find_download_in_html(
                    content_html, base_url, site_cfg.get("download_link_pattern", "")
                )

                results.append({
                    "title": clean_title,
                    "platform": site_cfg.get("platform", "Geral"),
                    "source_name": site_cfg.get("name", "WordPress"),
                    "cover_url": cover_url,
                    "page_url": page_url,
                    "direct_download": direct_dl,
                    "download_pattern": site_cfg.get("download_link_pattern", "")
                })
        except Exception:
            pass
        return results

    @staticmethod
    def _search_anti_bot_scraper(site_cfg, query):
        """
        Usa o AntiBotScraper module para buscar jogos em DLPSGame, ROMSLab, ROMSFun e FitGirl.
        Extrai capas e links de download automaticamente.
        """
        results = []
        scraper = None
        try:
            from scrapers.anti_bot_scraper import create_dlps_roms_scraper
            scraper = create_dlps_roms_scraper()
            mode = site_cfg.get("mode", "anti_bot_scraper")
            games = scraper.search_by_mode(mode, query, max_results=20)
            for game in games:
                result = {
                    "title": game.get("title", "Sem título"),
                    "url": game.get("url", ""),
                    "cover_url": game.get("cover_url", ""),
                    "platform": game.get("platform", site_cfg.get("platform", "Multi")),
                    "source_name": game.get("source_name", site_cfg.get("name", "Site Scraper")),
                    "page_url": game.get("url", ""),
                    "download_pattern": site_cfg.get(
                        "download_link_pattern",
                        r"(mega\.nz|mediafire\.com|drive\.google\.com|1fichier\.com|gofile\.io|qiwi|datanodes\.to|filekeeper\.net|pixeldrain\.com|filecrypt\.cc|downloadgameps3\.(net|com)/archives/|magnet:\?|1337x|rutor|tapochek|romsfast\.com|\.pkg|\.zip|\.7z|\.rar|\.nsp|\.xci|\.bin|\.torrent)"
                    )
                }
                if "download_links" in game:
                    result["download_links"] = game["download_links"]
                results.append(result)
        except Exception as e:
            print(f"[AntiBotScraper Error] {e}")
        finally:
            if scraper and hasattr(scraper, "close"):
                scraper.close()
        
        return results

    @staticmethod
    def _search_html_custom(site_cfg, query):
        """
        Motor HTML universal baseado em seletores CSS configuráveis.
        Funciona em praticamente qualquer site de catálogo de jogos/ROMs.
        """
        results = []
        base_url = site_cfg.get("base_url", "").rstrip("/")
        search_url_tpl = site_cfg.get("search_url", "")
        if not search_url_tpl:
            return results

        target_url = search_url_tpl.replace("{query}", quote_plus(query))

        try:
            resp = requests.get(target_url, headers=DEFAULT_HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            item_sel = site_cfg.get("item_selector", "article")
            title_sel = site_cfg.get("title_selector", "h2, h3, .title")
            link_sel = site_cfg.get("link_selector", "a")
            img_sel = site_cfg.get("image_selector", "img")

            items = soup.select(item_sel)[:16]  # Limita a 16 por site para rapidez

            for item in items:
                # Extrair Título
                title_el = item.select_one(title_sel)
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                # Extrair Link
                link_el = item.select_one(link_sel)
                href = link_el.get("href", "") if link_el else ""
                if not href and title_el and title_el.name == "a":
                    href = title_el.get("href", "")
                page_url = urljoin(base_url, href) if href else ""

                # Extrair Capa (Suporta Lazy Loading: data-src, data-lazy-src, src)
                img_el = item.select_one(img_sel)
                cover_url = ""
                if img_el:
                    for attr in ["data-src", "data-lazy-src", "data-original", "src"]:
                        val = img_el.get(attr, "")
                        if val and not val.startswith("data:image"):
                            cover_url = urljoin(base_url, val)
                            break

                results.append({
                    "title": title,
                    "platform": site_cfg.get("platform", "Geral"),
                    "source_name": site_cfg.get("name", "Site Custom"),
                    "cover_url": cover_url,
                    "page_url": page_url,
                    "direct_download": "",
                    "download_pattern": site_cfg.get("download_link_pattern", "")
                })
        except Exception:
            pass

        return results
    @staticmethod
    def resolve_download_links_from_post(page_url, pattern_regex):
        """
        Entra na página do jogo e extrai todos os links diretos e espelhos,
        classificando cada link por categoria (Base, Update, DLC, Torrent)
        e provedor (Mediafire, Mega, Google Drive, DataNodes, etc.).
        """
        raw_matches = []
        if not page_url:
            return []

        try:
            # 1. Caso específico: ROMSFun (navega na subpágina /download/ e recupera as opções)
            if "romsfun.com" in page_url:
                resp = requests.get(page_url, headers=DEFAULT_HEADERS, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    dl_a = soup.find("a", href=lambda h: h and "/download/" in h)
                    if dl_a:
                        dl_page_url = dl_a["href"]
                        r2 = requests.get(dl_page_url, headers=DEFAULT_HEADERS, timeout=10)
                        if r2.status_code == 200:
                            s2 = BeautifulSoup(r2.text, "html.parser")
                            seen_dl = set()
                            for a in s2.find_all("a", href=True):
                                hr = a["href"].strip()
                                txt = a.get_text(strip=True)
                                if "/download/" in hr and hr != dl_page_url and hr not in seen_dl:
                                    seen_dl.add(hr)
                                    final_url = hr
                                    try:
                                        r3 = requests.get(hr, headers=DEFAULT_HEADERS, timeout=6)
                                        if r3.status_code == 200:
                                            s3 = BeautifulSoup(r3.text, "html.parser")
                                            sto = s3.find("a", href=lambda h: h and ("romsfast.com" in h or ".zip" in h or ".7z" in h))
                                            if sto:
                                                final_url = sto["href"]
                                    except Exception:
                                        pass
                                    raw_matches.append({"label": txt or "Download ROM", "url": final_url})

            # 2. Caso específico: FitGirl Repacks (extrai magnets, torrents, filehosters e partes)
            elif "fitgirl-repacks.site" in page_url:
                resp = requests.get(page_url, headers=DEFAULT_HEADERS, timeout=12)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    entry = soup.select_one(".entry-content")
                    if entry:
                        seen_fg = set()
                        for a in entry.find_all("a", href=True):
                            hr = a["href"].strip()
                            txt = a.get_text(strip=True)
                            if hr in seen_fg or any(j in hr for j in ["wp-login", "comments", "xmlrpc", "gravatar", "riotpixels.net"]):
                                continue
                            if (
                                hr.startswith("magnet:") or
                                any(d in hr for d in ["1337x", "rutor", "tapochek", "paste.fitgirl", "datanodes", "fuckingfast", "filecrypt", "gofile", "pixeldrain", "multiup", "1fichier", "mediafire", "drive.google"]) or
                                any(ext in hr.lower() for ext in [".torrent", ".rar", ".bin", ".zip", ".iso"])
                            ):
                                seen_fg.add(hr)
                                raw_matches.append({"label": txt or hr.split("/")[-1], "url": hr})

            # 3. Padrão universal (DLPSGame com base64 payload, ROMSLab e outros)
            if not raw_matches:
                resp = requests.get(page_url, headers=DEFAULT_HEADERS, timeout=12)
                if resp.status_code == 200:
                    raw_matches = ModularScraperEngine._find_all_downloads_in_html(
                        resp.text, page_url, pattern_regex
                    )
        except Exception as e:
            print(f"[Link Resolution Error] {e}")

        # Enriquecimento com o classificador de links
        classified_links = []
        for item in raw_matches:
            c = classify_download_link(item.get("label", ""), item.get("url", ""))
            classified_links.append(c)

        return classified_links

    @staticmethod
    def _find_download_in_html(html_text, base_url, pattern_regex):
        links = ModularScraperEngine._find_all_downloads_in_html(html_text, base_url, pattern_regex)
        return links[0]["url"] if links else ""

    @staticmethod
    def _find_all_downloads_in_html(html_text, base_url, pattern_regex):
        if not html_text:
            return []
        default_pattern = (
            r"(mega\.nz|mediafire\.com|drive\.google\.com|1fichier\.com|gofile\.io|qiwi|"
            r"datanodes\.to|filekeeper\.net|pixeldrain\.com|filecrypt\.cc|"
            r"downloadgameps3\.(net|com)/archives/|magnet:\?|\.zip|\.7z|\.iso|\.rar|\.pkg|\.nsp|\.xci|\.chd|\.bin)"
        )
        if not pattern_regex:
            pattern_regex = default_pattern
        else:
            if "filecrypt" not in pattern_regex:
                pattern_regex += r"|(filecrypt\.cc|datanodes\.to|filekeeper\.net|pixeldrain\.com|qiwi|downloadgameps3\.(net|com)/archives/)"

        soup = BeautifulSoup(html_text, "html.parser")
        regex = re.compile(pattern_regex, re.IGNORECASE)
        matches = []
        seen_urls = set()

        # 1. Decodifica payloads protegidos em Base64 (ex: DLPSGame .secure-data / data-payload)
        for el in soup.select("[data-payload], .secure-data"):
            payload = el.get("data-payload")
            if not payload:
                continue
            try:
                dec = base64.b64decode(payload).decode("utf-8", errors="ignore")
                psoup = BeautifulSoup(dec, "html.parser")
                for a_tag in psoup.find_all("a", href=True):
                    href = a_tag["href"].strip()
                    full_url = urljoin(base_url, href)
                    if full_url in seen_urls or any(j in full_url for j in ["guide-download", "tool-download"]):
                        continue
                    if regex.search(full_url):
                        seen_urls.add(full_url)
                        label = a_tag.get_text(strip=True) or "Download Mirror"
                        matches.append({"label": label[:45], "url": full_url})
            except Exception:
                pass

        # 2. Varre links normais da página HTML
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue

            # Filtra links de navegação/menus que não sejam de download
            if any(j in full_url for j in ["guide-download", "wp-login", "list-all-game", "intent/post", "/category/", "/tag/"]):
                continue

            btn_text = a_tag.get_text(strip=True) or "Link de Download"
            if regex.search(full_url):
                seen_urls.add(full_url)
                matches.append({"label": btn_text[:45], "url": full_url})

        return matches


# =====================================================================
# JANELA DE GERENCIAMENTO DE SITES (ADICIONAR / EDITAR FONTES)
# =====================================================================
class SiteManagerModal(ctk.CTkToplevel):
    """Permite ativar/desativar e adicionar novos sites pela própria interface."""

    def __init__(self, parent, sites_config, on_save_callback):
        super().__init__(parent)
        self.title("⚙ Gerenciar Sites e Fontes de Busca")
        self.geometry("700x560")
        self.sites_config = sites_config
        self.on_save_callback = on_save_callback
        self.grab_set()

        ctk.CTkLabel(
            self, text="Fontes de Busca Configuradas (sites_config.json)",
            font=("Segoe UI", 18, "bold")
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            self,
            text="Ative/desative os sites abaixo ou cadastre um novo site WordPress / HTML:",
            font=("Segoe UI", 12), text_color="gray"
        ).pack(pady=(0, 10))

        # Lista de sites atuais
        self.list_frame = ctk.CTkScrollableFrame(self, height=180)
        self.list_frame.pack(fill="x", padx=20, pady=5)
        self.check_vars = []
        self._render_site_list()

        # Formulário para adicionar novo site rapidamente
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            form_frame, text="➕ Adicionar Novo Site Rapidamente",
            font=("Segoe UI", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, pady=8, padx=10, sticky="w")

        self.entry_name = self._add_field(form_frame, "Nome do Site:", "Ex: Meu Portal PS4/Switch", 1, 0)
        self.entry_plat = self._add_field(form_frame, "Plataforma:", "Ex: Switch / PS4 / PC", 1, 1)
        self.entry_base = self._add_field(form_frame, "URL Base do Site:", "Ex: https://meusite.com", 2, 0)
        self.entry_search = self._add_field(
            form_frame, "URL de Busca (use {query}):",
            "Ex: https://meusite.com/?s={query}", 2, 1
        )

        ctk.CTkLabel(form_frame, text="Modo de Leitura:", font=("Segoe UI", 12)).grid(
            row=3, column=0, padx=10, pady=(6, 0), sticky="w"
        )
        self.mode_var = ctk.StringVar(value="html_custom")
        mode_menu = ctk.CTkOptionMenu(
            form_frame, variable=self.mode_var,
            values=["html_custom", "wp_rest_api"]
        )
        mode_menu.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="ew")

        btn_add_site = ctk.CTkButton(
            form_frame, text="+ Incluir Site na Lista", fg_color="#28a745", hover_color="#218838",
            command=self.add_new_site
        )
        btn_add_site.grid(row=4, column=1, padx=10, pady=(0, 10), sticky="ew")

        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)

        # Botão Salvar Alterações
        ctk.CTkButton(
            self, text="💾 Salvar e Aplicar Configurações", height=40,
            font=("Segoe UI", 14, "bold"), command=self.save_all
        ).pack(fill="x", padx=20, pady=(0, 15))
    def _add_field(self, parent, label, placeholder, row, col):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=row, column=col, padx=10, pady=4, sticky="ew")
        ctk.CTkLabel(container, text=label, font=("Segoe UI", 12)).pack(anchor="w")
        entry = ctk.CTkEntry(container, placeholder_text=placeholder)
        entry.pack(fill="x")
        return entry

    def _render_site_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.check_vars.clear()

        for idx, site in enumerate(self.sites_config):
            row_f = ctk.CTkFrame(self.list_frame, fg_color="#252535")
            row_f.pack(fill="x", pady=3, padx=5)

            var = ctk.BooleanVar(value=site.get("enabled", True))
            self.check_vars.append((var, site))

            chk = ctk.CTkCheckBox(
                row_f, text=f"{site.get('name')}  [{site.get('platform')}] — Modo: {site.get('mode')}",
                variable=var, font=("Segoe UI", 12, "bold")
            )
            chk.pack(side="left", padx=10, pady=8)

            btn_del = ctk.CTkButton(
                row_f, text="Remover", width=70, height=26, fg_color="#dc3545", hover_color="#b02a37",
                command=lambda i=idx: self.remove_site(i)
            )
            btn_del.pack(side="right", padx=10, pady=6)

    def remove_site(self, index):
        del self.sites_config[index]
        self._render_site_list()

    def add_new_site(self):
        name = self.entry_name.get().strip()
        plat = self.entry_plat.get().strip() or "Geral"
        base = self.entry_base.get().strip().rstrip("/")
        search = self.entry_search.get().strip()
        mode = self.mode_var.get()

        if not name or not base:
            messagebox.showwarning("Atenção", "Preencha pelo menos o Nome e a URL Base do site!")
            return

        if not search:
            search = f"{base}/?s={{query}}"

        new_site = {
            "name": name,
            "enabled": True,
            "platform": plat,
            "mode": mode,
            "base_url": base,
            "search_url": search,
            "item_selector": "article, .post, .type-post, .result-item",
            "title_selector": "h2.entry-title, h2.post-title, h3.entry-title, h2 a, h3 a",
            "link_selector": "h2 a, h3 a, a.post-thumbnail, a",
            "image_selector": "img.wp-post-image, .post-thumbnail img, img",
            "download_link_pattern": r"(mega\.nz|mediafire\.com|1fichier\.com|drive\.google\.com|magnet:\?|\.zip|\.rar|\.7z|\.iso|\.pkg|\.nsp)"
        }
        self.sites_config.append(new_site)
        self._render_site_list()

        self.entry_name.delete(0, "end")
        self.entry_base.delete(0, "end")
        self.entry_search.delete(0, "end")

    def save_all(self):
        for var, site in self.check_vars:
            site["enabled"] = var.get()
        self.on_save_callback(self.sites_config)
        self.destroy()


# =====================================================================
# JANELA DE SELEÇÃO E ORGANIZAÇÃO DE LINKS (CATEGORIAS E SERVIDORES)
# =====================================================================
class LinksSelectorModal(ctk.CTkToplevel):
    """Exibe os links organizados por categoria (Jogo Base, Updates, DLCs, Torrents) e por Servidor."""

    def __init__(self, parent, game_title, page_url, found_links, launch_callback):
        super().__init__(parent)
        self.title(f"Downloads & Espelhos — {game_title}")
        self.geometry("820x600")
        self.minsize(720, 500)
        self.grab_set()

        self.game_title = game_title
        self.page_url = page_url
        self.all_links = found_links
        self.launch_callback = launch_callback
        self.current_filter = "all"

        self._setup_ui()

    def _setup_ui(self):
        # Cabeçalho Superior
        top_frame = ctk.CTkFrame(self, fg_color="#181822", corner_radius=0)
        top_frame.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            top_frame, text=self.game_title, font=("Segoe UI", 16, "bold"),
            text_color="#60a5fa", wraplength=760, justify="left"
        ).pack(anchor="w", padx=20, pady=(15, 4))

        count_text = (
            f"Encontrados {len(self.all_links)} links organizados por tipo e provedor"
            if self.all_links else "Nenhum link direto encontrado automaticamente"
        )
        ctk.CTkLabel(
            top_frame, text=count_text, font=("Segoe UI", 12), text_color="#94a3b8"
        ).pack(anchor="w", padx=20, pady=(0, 10))

        if not self.all_links:
            empty_frame = ctk.CTkFrame(self, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, padx=20, pady=20)
            ctk.CTkLabel(
                empty_frame,
                text="O site utiliza links protegidos ou botões dinâmicos na página.\n"
                     "Clique abaixo para abrir a página original diretamente no navegador:",
                font=("Segoe UI", 13), text_color="gray", justify="center"
            ).pack(expand=True)
            self._setup_footer()
            return

        # Barra de Filtros por Categoria
        filter_frame = ctk.CTkFrame(self, fg_color="#1e1e2d", corner_radius=8)
        filter_frame.pack(fill="x", padx=15, pady=(10, 5))

        cats = {}
        for l in self.all_links:
            c = l.get("category", "base")
            cats[c] = cats.get(c, 0) + 1

        filter_options = [("all", f"Todos ({len(self.all_links)})")]
        if cats.get("base"): filter_options.append(("base", f"🎮 Jogo Base ({cats['base']})"))
        if cats.get("update"): filter_options.append(("update", f"🔄 Updates ({cats['update']})"))
        if cats.get("dlc"): filter_options.append(("dlc", f"🎁 DLCs ({cats['dlc']})"))
        if cats.get("torrent"): filter_options.append(("torrent", f"🧲 Torrents ({cats['torrent']})"))
        if cats.get("mirror"): filter_options.append(("mirror", f"🔗 Espelhos ({cats['mirror']})"))
        if cats.get("mod"): filter_options.append(("mod", f"🛠️ Mods ({cats['mod']})"))

        self.filter_buttons = {}
        btn_box = ctk.CTkFrame(filter_frame, fg_color="transparent")
        btn_box.pack(anchor="w", padx=10, pady=8)

        for key, text in filter_options:
            b = ctk.CTkButton(
                btn_box, text=text, height=30, font=("Segoe UI", 11, "bold"),
                fg_color="#2563eb" if key == "all" else "#27273a",
                hover_color="#1d4ed8",
                command=lambda k=key: self._set_filter(k)
            )
            b.pack(side="left", padx=4)
            self.filter_buttons[key] = b

        # Área de Rolagem dos Links
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#12121a", corner_radius=8)
        self.scroll.pack(fill="both", expand=True, padx=15, pady=8)

        self._render_links()
        self._setup_footer()

    def _set_filter(self, category):
        self.current_filter = category
        for k, b in self.filter_buttons.items():
            b.configure(fg_color="#2563eb" if k == category else "#27273a")
        self._render_links()

    def _render_links(self):
        for widget in self.scroll.winfo_children():
            widget.destroy()

        filtered = [
            l for l in self.all_links
            if self.current_filter == "all" or l.get("category") == self.current_filter
        ]

        if not filtered:
            ctk.CTkLabel(
                self.scroll, text="Nenhum link encontrado nesta categoria.",
                font=("Segoe UI", 12), text_color="gray"
            ).pack(pady=30)
            return

        for item in filtered:
            card = ctk.CTkFrame(self.scroll, fg_color="#1c1c28", corner_radius=8, border_width=1, border_color="#2a2a3c")
            card.pack(fill="x", pady=4, padx=6)

            info_col = ctk.CTkFrame(card, fg_color="transparent")
            info_col.pack(side="left", fill="both", expand=True, padx=12, pady=8)

            badge_row = ctk.CTkFrame(info_col, fg_color="transparent")
            badge_row.pack(anchor="w")

            # Badge da categoria
            cat_label = item.get("category_label", "🎮 Jogo Base")
            ctk.CTkLabel(
                badge_row, text=cat_label, font=("Segoe UI", 10, "bold"),
                fg_color="#2c2c3e", text_color="#cbd5e1", corner_radius=4, padx=6, pady=2
            ).pack(side="left", padx=(0, 6))

            # Badge do provedor / servidor
            prov_text = f"{item.get('provider_icon', '🌐')} {item.get('provider', 'Direto')}"
            ctk.CTkLabel(
                badge_row, text=prov_text, font=("Segoe UI", 10, "bold"),
                fg_color=item.get("provider_color", "#3b82f6"), text_color="#ffffff",
                corner_radius=4, padx=6, pady=2
            ).pack(side="left", padx=(0, 6))

            # Badge de Parte (se houver)
            if item.get("part_text"):
                ctk.CTkLabel(
                    badge_row, text=item.get("part_text"), font=("Segoe UI", 10, "bold"),
                    fg_color="#eab308", text_color="#000000",
                    corner_radius=4, padx=6, pady=2
                ).pack(side="left")

            # Nome/Label do link
            ctk.CTkLabel(
                info_col, text=item.get("label", "Download"), font=("Segoe UI", 12, "bold"),
                text_color="#f1f5f9", anchor="w", wraplength=520, justify="left"
            ).pack(anchor="w", pady=(4, 2))

            # URL snippet
            url_display = item.get("url", "")
            if len(url_display) > 75:
                url_display = url_display[:72] + "..."
            ctk.CTkLabel(
                info_col, text=url_display, font=("Segoe UI", 10),
                text_color="#64748b", anchor="w"
            ).pack(anchor="w")

            # Botões de Ação na Direita
            btn_col = ctk.CTkFrame(card, fg_color="transparent")
            btn_col.pack(side="right", padx=10, pady=8)

            dl_btn = ctk.CTkButton(
                btn_col, text="⬇ Baixar", width=90, height=32,
                font=("Segoe UI", 11, "bold"), fg_color="#16a34a", hover_color="#15803d",
                command=lambda u=item["url"]: self.launch_callback(u)
            )
            dl_btn.pack(side="top", pady=2)

            copy_btn = ctk.CTkButton(
                btn_col, text="📋 Copiar", width=90, height=26,
                font=("Segoe UI", 10), fg_color="#334155", hover_color="#475569"
            )
            copy_btn.configure(command=lambda u=item["url"], b=copy_btn: self._copy_link(u, b))
            copy_btn.pack(side="top", pady=2)

    def _copy_link(self, url, button):
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()
            button.configure(text="✓ Copiado!", fg_color="#059669")
            self.after(1500, lambda: button.configure(text="📋 Copiar", fg_color="#334155"))
        except Exception:
            pass

    def _setup_footer(self):
        footer = ctk.CTkFrame(self, fg_color="#181822", corner_radius=0, height=55)
        footer.pack(fill="x", side="bottom")

        ctk.CTkButton(
            footer, text="🌐 Abrir Post Original no Navegador", height=36,
            font=("Segoe UI", 12, "bold"), fg_color="#0284c7", hover_color="#0369a1",
            command=lambda: self.launch_callback(self.page_url)
        ).pack(side="left", padx=20, pady=10)

        ctk.CTkButton(
            footer, text="✕ Fechar", height=36, width=90,
            font=("Segoe UI", 12), fg_color="#475569", hover_color="#334155",
            command=self.destroy
        ).pack(side="right", padx=20, pady=10)
# =====================================================================
# APLICAÇÃO PRINCIPAL (INTERFACE GRÁFICA)
# =====================================================================
class GameHubApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Game & ROM Hub — Buscador Multi-Sites Modular")
        self.geometry("1060x720")
        self.minsize(920, 600)

        self.image_cache = {}
        self.placeholder_image = self._create_placeholder_image()
        self.sites_config = self.load_sites_config()
        self.all_search_results = []
        self.current_query = ""

        self.setup_ui()

    def _create_placeholder_image(self):
        img = Image.new("RGB", (170, 220), color=(40, 40, 52))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 160, 210], outline=(75, 75, 95), width=2)
        draw.text((48, 100), "SEM CAPA", fill=(150, 150, 170))
        return ctk.CTkImage(light_image=img, dark_image=img, size=(170, 220))

    def load_sites_config(self):
        if not os.path.exists(SITES_CONFIG_FILE):
            with open(SITES_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SITES_CONFIG, f, indent=4, ensure_ascii=False)
            return DEFAULT_SITES_CONFIG
        try:
            with open(SITES_CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                if isinstance(data, dict) and "value" in data:
                    data = data["value"]
                return data if isinstance(data, list) else DEFAULT_SITES_CONFIG
        except Exception as e:
            messagebox.showerror("Erro no JSON", f"Falha ao ler {SITES_CONFIG_FILE}:\n{e}")
            return DEFAULT_SITES_CONFIG

    def save_sites_config(self, updated_config):
        self.sites_config = updated_config
        try:
            with open(SITES_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.sites_config, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Configuração Salva", "A lista de sites foi atualizada com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar: {e}")

    def setup_ui(self):
        # --- BARRA SUPERIOR ---
        top_bar = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color="#181822")
        top_bar.pack(fill="x", side="top")

        ctk.CTkLabel(
            top_bar, text="🎮 GAME HUB", font=("Segoe UI", 22, "bold"), text_color="#4da6ff"
        ).pack(side="left", padx=25, pady=20)

        self.search_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="🔍 Digite o nome do jogo e pressione Enter (ex: Mario, Sonic, Doom, Zelda)...",
            height=42, font=("Segoe UI", 14)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(5, 10), pady=20)
        self.search_entry.bind("<Return>", lambda event: self.trigger_search())

        self.btn_search = ctk.CTkButton(
            top_bar, text="Pesquisar", width=120, height=42,
            font=("Segoe UI", 14, "bold"), command=self.trigger_search
        )
        self.btn_search.pack(side="left", padx=5, pady=20)

        btn_sites = ctk.CTkButton(
            top_bar, text="⚙ Gerenciar Sites", width=150, height=42,
            fg_color="#3a3a4e", hover_color="#4e4e68", font=("Segoe UI", 13, "bold"),
            command=lambda: SiteManagerModal(self, self.sites_config, self.save_sites_config)
        )
        btn_sites.pack(side="right", padx=25, pady=20)

        # --- BARRA DE FILTROS ---
        filter_bar = ctk.CTkFrame(self, height=46, corner_radius=8, fg_color="#1a1a26")
        filter_bar.pack(fill="x", padx=15, pady=(8, 4))

        ctk.CTkLabel(
            filter_bar, text="🎯 Filtros:", font=("Segoe UI", 12, "bold"), text_color="#4da6ff"
        ).pack(side="left", padx=(15, 8), pady=8)

        ctk.CTkLabel(
            filter_bar, text="🕹️ Plataforma:", font=("Segoe UI", 11), text_color="#a0a0b5"
        ).pack(side="left", padx=(4, 4), pady=8)

        self.platform_filter_menu = ctk.CTkOptionMenu(
            filter_bar, values=["Todas"], width=170, height=28,
            font=("Segoe UI", 11), dropdown_font=("Segoe UI", 11),
            fg_color="#272738", button_color="#36364d",
            command=lambda val: self._apply_display_filters()
        )
        self.platform_filter_menu.pack(side="left", padx=(2, 15), pady=8)

        ctk.CTkLabel(
            filter_bar, text="🌐 Site / Origem:", font=("Segoe UI", 11), text_color="#a0a0b5"
        ).pack(side="left", padx=(4, 4), pady=8)

        self.site_filter_menu = ctk.CTkOptionMenu(
            filter_bar, values=["Todos"], width=180, height=28,
            font=("Segoe UI", 11), dropdown_font=("Segoe UI", 11),
            fg_color="#272738", button_color="#36364d",
            command=lambda val: self._apply_display_filters()
        )
        self.site_filter_menu.pack(side="left", padx=(2, 12), pady=8)

        self.btn_clear_filters = ctk.CTkButton(
            filter_bar, text="✖ Limpar Filtros", width=105, height=28,
            fg_color="#35354a", hover_color="#454560", font=("Segoe UI", 11, "bold"),
            command=self._reset_filters
        )
        self.btn_clear_filters.pack(side="left", padx=4, pady=8)

        self.count_badge = ctk.CTkLabel(
            filter_bar, text="", font=("Segoe UI", 11, "bold"), text_color="#38bdf8"
        )
        self.count_badge.pack(side="right", padx=15, pady=8)

        # --- BARRA DE STATUS ---
        self.status_label = ctk.CTkLabel(
            self,
            text="Digite o nome de um jogo acima e clique em 'Pesquisar' para consultar todos os sites ativos.",
            font=("Segoe UI", 13), text_color="#a0a0b5"
        )
        self.status_label.pack(anchor="w", padx=25, pady=(4, 4))

        # --- GRADE DE RESULTADOS ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=6)

        for col in range(4):
            self.scroll_frame.grid_columnconfigure(col, weight=1)

    def _reset_filters(self):
        self.platform_filter_menu.set("Todas")
        self.site_filter_menu.set("Todos")
        self._apply_display_filters()

    def trigger_search(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Busca Vazia", "Digite o nome de um jogo para pesquisar!")
            return

        # Limpa resultados anteriores
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        active_count = sum(1 for s in self.sites_config if s.get("enabled", True))
        self.status_label.configure(
            text=f"⏳ Buscando '{query}' em {active_count} site(s) ativo(s)... Aguarde..."
        )
        self.count_badge.configure(text="")
        self.btn_search.configure(state="disabled", text="Buscando...")

        # Executa a busca em uma Thread separada para não congelar a interface
        threading.Thread(target=self._run_search_thread, args=(query,), daemon=True).start()

    def _run_search_thread(self, query):
        results = ModularScraperEngine.search_all_sites(self.sites_config, query)
        self.after(0, lambda: self._render_search_results(query, results))

    def _render_search_results(self, query, results):
        self.btn_search.configure(state="normal", text="Pesquisar")
        self.current_query = query
        self.all_search_results = results or []

        if not results:
            self.platform_filter_menu.configure(values=["Todas"])
            self.platform_filter_menu.set("Todas")
            self.site_filter_menu.configure(values=["Todos"])
            self.site_filter_menu.set("Todos")
            self.count_badge.configure(text="")
            self.status_label.configure(
                text=f"Nenhum resultado encontrado para '{query}'. Verifique os sites ativos em '⚙ Gerenciar Sites'."
            )
            return

        # Coleta plataformas e sites únicos para alimentar os filtros
        plat_set = sorted(list({str(g.get("platform", "Outros")).strip() for g in results if g.get("platform")}))
        self.platform_filter_menu.configure(values=["Todas"] + plat_set)
        self.platform_filter_menu.set("Todas")

        site_set = sorted(list({str(g.get("source_name", "Outro")).strip() for g in results if g.get("source_name")}))
        self.site_filter_menu.configure(values=["Todos"] + site_set)
        self.site_filter_menu.set("Todos")

        self._apply_display_filters()

    def _apply_display_filters(self):
        # Limpa cards na grade
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not self.all_search_results:
            return

        selected_plat = self.platform_filter_menu.get().strip()
        selected_site = self.site_filter_menu.get().strip()

        filtered = []
        for g in self.all_search_results:
            p = str(g.get("platform", "")).strip()
            s = str(g.get("source_name", "")).strip()
            if selected_plat != "Todas" and p != selected_plat:
                continue
            if selected_site != "Todos" and s != selected_site:
                continue
            filtered.append(g)

        total_all = len(self.all_search_results)
        total_filtered = len(filtered)
        self.count_badge.configure(text=f"Exibindo: {total_filtered} de {total_all}")

        if not filtered:
            self.status_label.configure(
                text=f"Nenhum resultado corresponde aos filtros selecionados (Plataforma: '{selected_plat}', Site: '{selected_site}')."
            )
            empty_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="Nenhum jogo corresponde aos filtros selecionados.\nExperimente selecionar 'Todas' as plataformas ou 'Todos' os sites.",
                font=("Segoe UI", 14), text_color="#8c8ca5"
            )
            empty_lbl.pack(pady=40)
            return

        self.status_label.configure(
            text=f"✅ Exibindo {total_filtered} de {total_all} resultado(s) para '{self.current_query}'."
        )

        columns = 4
        for idx, game in enumerate(filtered[:48]):
            row = idx // columns
            col = idx % columns
            self.create_game_card(game, row, col)
    def create_game_card(self, game, row, col):
        card = ctk.CTkFrame(
            self.scroll_frame, corner_radius=12, fg_color="#222230",
            border_width=1, border_color="#34344a"
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        # 1. Capa
        cover_lbl = ctk.CTkLabel(card, text="", image=self.placeholder_image)
        cover_lbl.pack(pady=(15, 8), padx=15)

        cover_url = game.get("cover_url", "")
        if cover_url:
            if cover_url in self.image_cache:
                cover_lbl.configure(image=self.image_cache[cover_url])
            else:
                threading.Thread(
                    target=self.load_cover_async, args=(cover_url, cover_lbl), daemon=True
                ).start()

        # 2. Título do Jogo
        title_str = game.get("title", "Sem Título")
        display_title = title_str if len(title_str) <= 32 else title_str[:30] + "..."
        ctk.CTkLabel(
            card, text=display_title, font=("Segoe UI", 13, "bold"), wraplength=190
        ).pack(padx=10, pady=(2, 2))

        # 3. Fonte e Plataforma
        meta_text = f"🌐 {game.get('source_name')}  •  🕹️ {game.get('platform')}"
        ctk.CTkLabel(
            card, text=meta_text, font=("Segoe UI", 11), text_color="#8c8ca5", wraplength=190
        ).pack(padx=10, pady=(0, 10))

        # 4. Botão de Ação / Download
        btn_dl = ctk.CTkButton(
            card, text="⬇ Baixar / Obter Link", font=("Segoe UI", 13, "bold"),
            fg_color="#0066cc", hover_color="#0052a3", height=36, corner_radius=8,
            command=lambda g=game: self.handle_game_download(g)
        )
        btn_dl.pack(fill="x", padx=15, pady=(0, 15))

    def load_cover_async(self, url, label_widget):
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=7)
            resp.raise_for_status()
            img_data = Image.open(BytesIO(resp.content)).convert("RGB")
            img_data = img_data.resize((170, 220), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(170, 220))
            self.image_cache[url] = ctk_img

            if label_widget.winfo_exists():
                self.after(0, lambda: label_widget.configure(image=ctk_img))
        except Exception:
            pass

    def handle_game_download(self, game):
        """
        Verifica se já temos um link direto de download.
        Se não tiver, inspeciona a página do post em busca de links ou abre no navegador.
        """
        direct_url = game.get("direct_download", "")
        page_url = game.get("page_url", "")
        pattern = game.get("download_pattern", "")
        title = game.get("title", "Jogo")

        if direct_url:
            self.launch_in_windows(direct_url)
            return

        if not page_url:
            messagebox.showwarning("Sem Link", "Este item não possui uma URL válida associada.")
            return

        # Inspeciona a página do post em background para extrair links de servidores
        self.status_label.configure(text=f"🔍 Extraindo links de download da página de '{title}'...")

        def inspect_task():
            found = ModularScraperEngine.resolve_download_links_from_post(page_url, pattern)
            self.after(
                0,
                lambda: self._present_resolved_links(title, page_url, found)
            )

        threading.Thread(target=inspect_task, daemon=True).start()

    def _present_resolved_links(self, title, page_url, found_links):
        self.status_label.configure(text=f"Pronto. Links processados para '{title}'.")
        LinksSelectorModal(self, title, page_url, found_links, self.launch_in_windows)

    def launch_in_windows(self, url):
        """Aciona o gerenciador de downloads padrão do Windows / Navegador."""
        if not url:
            return
        try:
            if os.name == "nt":
                os.startfile(url)
            else:
                webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Erro ao Abrir Link", f"Não foi possível iniciar:\n{e}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = GameHubApp()
    app.mainloop()

