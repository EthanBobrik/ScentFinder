import os, re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from seleniumbase import SB
from selenium_stealth import stealth
import requests
from dotenv import load_dotenv
from lxml import html
import time, random
from database.db import session
from database.models import Cologne, Note, CologneNote, NoteType

MAX_REQUESTS = 25
BASE_URL = "https://www.fragrantica.com"
global num_requests
cooldown_until = 0

load_dotenv()

def get_scraperapi_response(url):
    API_KEY = os.getenv("SCRAPERAPI_KEY")
    scraperapi_url = f"http://api.scraperapi.com/?api_key={API_KEY}&url={url}&render=true"
    return requests.get(scraperapi_url, timeout=20)

def get_note_urls():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--start-maximized")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)

    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

    driver.get(BASE_URL + "/notes/")
    # Scroll down to trigger dynamic content
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(5)  # give time for JS to load after scrolling
    tree = html.fromstring(driver.page_source)
    note_urls = tree.xpath("//div[contains(@class, 'notebox')]//a/@href")
    print("Found", len(note_urls), "note URLs")

    with open("../../data/raw/notes.txt", "w", encoding="utf-8") as f:
        for url in note_urls:
            f.write(url + "\n")
            print(url)

    driver.quit()

def clean_name(text):
    # Replace spaces and these characters: / \ , . ' " &
    cleaned = re.sub(r"[ /\\,.\'\"&®]+", "-", text)
    # Remove double dashes if they appear
    cleaned = re.sub(r"-+", "-", cleaned)
    # Remove accents
    cleaned = re.sub(r"[é]+", "e", cleaned)
    cleaned = re.sub(r"[ô]+", "o", cleaned)
    cleaned = re.sub(r"[á]+", "a", cleaned)
    # Strip leading/trailing dashes
    return cleaned.strip("-")

def get_cologne_urls():
    global num_requests
    num_requests = 0
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
    ]

    with SB(uc=True, headless=False) as driver:
        # Random user-agent
        driver.driver.execute_cdp_cmd(
            'Network.setUserAgentOverride',
            {"userAgent": random.choice(USER_AGENTS)}
        )

        designer_url = BASE_URL + "/designers/"
        driver.open(designer_url)
        driver.uc_gui_click_captcha()
        driver.sleep(random.uniform(1, 3))
        driver.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        driver.sleep(random.uniform(2, 5))

        driver.wait_for_element("div.designerlist")
        tree = html.fromstring(driver.get_page_source())

        names_raw = tree.xpath("//div[contains(@class,'designerlist')]//a/text()")
        urls_raw = tree.xpath("//div[contains(@class,'designerlist')]//a/@href")
        names_cleaned = [clean_name(name.strip()) for name in names_raw]

        assert len(names_cleaned) == len(urls_raw), "Mismatch in number of names and URLs"

        brand_map = dict(zip(names_cleaned, urls_raw))

        # Get brands already scraped
        try:
            with open("../../data/raw/colognes.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        brands_scraped = set()
        for line in lines:
            url = line.strip()
            if "/perfume/" in url:
                parts = url.split("/perfume/")[1].split("/")
                if len(parts) >= 1:
                    brand = parts[0]
                    brands_scraped.add(brand)

        # Use dictionary keys for difference
        all_brands = set(brand_map.keys())
        brands_not_scraped = all_brands - brands_scraped

        print(f"Brands not yet scraped: {len(brands_not_scraped)}")

        with open("../../data/raw/colognes.txt", "a", encoding="utf-8") as f:
            for brand in brands_not_scraped:
                if num_requests > MAX_REQUESTS:
                    print("Too many requests")
                    time.sleep(600)
                    num_requests = 0

                # Lookup path in brand_map
                brand_path = brand_map[brand]
                brand_full_url = BASE_URL + brand_path

                time.sleep(random.uniform(5, 15))

                driver.driver.execute_script("window.scrollBy(0, window.innerHeight/2);")
                driver.sleep(random.uniform(1, 3))

                try:
                    driver.open(brand_full_url)
                    driver.uc_gui_click_captcha()
                    driver.sleep(random.uniform(1, 3))

                    last_height = driver.driver.execute_script("return document.body.scrollHeight")
                    while True:
                        driver.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                        time.sleep(random.uniform(1, 2))
                        new_height = driver.driver.execute_script("return document.body.scrollHeight")
                        if new_height == last_height:
                            break
                        last_height = new_height

                    driver.wait_for_element("div.flex-child-auto")
                    tree2 = html.fromstring(driver.get_page_source())
                    cologne_urls = tree2.xpath("//div[contains(@class, 'flex-child-auto')]//a/@href")

                    for cologne_url in cologne_urls:
                        url = f"{BASE_URL}{cologne_url}\n"
                        f.write(url)
                        print(url)
                        num_requests += 1

                except Exception as e:
                    print(f"Skipping {brand} due to: {e}")
                    continue

def represents_int(s):
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False

def note_scraper():
    with open("../../data/raw/notes.txt", "r", encoding="utf-8") as f:
        note_urls = f.readlines()

    num_notes = len(note_urls)
    num_records = session.query(Note).count()

    for idx in range(num_records, num_notes):
        url = note_urls[idx].strip()
        try:
            page = get_scraperapi_response(url)
            tree = html.fromstring(page.content)

            note_title_elements = tree.xpath("//h1//text()")
            if not note_title_elements:
                continue
            note_title = note_title_elements[0].strip()

            note_group_elements = tree.xpath("//h3//b")
            note_group = note_group_elements[0].text.strip() if note_group_elements else ""

            note_description_elements = tree.xpath("//div[@class='cell callout']//p//text()")
            note_description = note_description_elements[0].strip() if note_description_elements else ""

            note = Note(name=note_title, group=note_group, description=note_description)
            existing = session.query(Note).filter_by(name=note.name).first()
            if not existing:
                session.add(note)
                session.commit()
                print(f"[+] Added note: {note_title}")
            else:
                print(f"[=] Note already exists: {note_title}")
        except Exception as e:
            print(f"[!] Error processing {url}: {e}")
            continue

def cologne_scraper():
    with open("../../data/raw/colognes.txt", "r", encoding="utf-8") as f:
        cologne_urls = f.readlines()

    num_colognes = len(cologne_urls)
    num_records = session.query(Cologne).count()

    for idx in range(num_records, num_colognes):
        url = cologne_urls[idx].strip()
        try:
            page = get_scraperapi_response(url)
            tree = html.fromstring(page.content)

            url_parts = url.replace(BASE_URL, "").strip("/").split("/")
            if len(url_parts) < 3 or url_parts[0] != "perfume":
                continue

            brand = url_parts[1].replace("-", " ")
            perfume_name_parts = url_parts[2].split("-")
            perfume_title = " ".join(perfume_name_parts[:-1]) if len(perfume_name_parts) > 1 else perfume_name_parts[0]

            page_title_elements = tree.xpath("//head//title//text()")
            launch_year = None
            if page_title_elements:
                page_title = page_title_elements[0]
                potential_year = page_title[-4:].strip()
                if represents_int(potential_year):
                    launch_year = int(potential_year)

            main_accords = [text.strip() for text in tree.xpath("//div[@class='cell accord-bar']//text()") if text.strip()]

            notes_captions = tree.xpath("//div[@class='strike-title']//text()")
            notes = {}
            if "Fragrance Notes" in notes_captions:
                notes["general"] = tree.xpath("//div[@class='text-center notes-box']/following-sibling::div[1]//div[a]//text()")
            elif "Perfume Pyramid" in notes_captions:
                notes["top"] = tree.xpath("//h4[normalize-space()='Top Notes']/following-sibling::div[1]//div[a]//text()")
                notes["middle"] = tree.xpath("//h4[normalize-space()='Middle Notes']/following-sibling::div[1]//div[a]//text()")
                notes["base"] = tree.xpath("//h4[normalize-space()='Bottom Notes']/following-sibling::div[1]//div[a]//text()")

            votes = tree.xpath("//div[@class = 'cell small-1 medium-1 large-1']//text()")
            if len(votes) < 19:
                print(f"[!] Not enough vote data for {url}")
                continue

            def safe_int(val):
                return int(val) if represents_int(val) else 0

            cologne = Cologne(
                name=perfume_title,
                brand=brand,
                launch_year=launch_year,
                main_accords=main_accords,
                top_notes=notes.get("top", []),
                middle_notes=notes.get("middle", []),
                base_notes=notes.get("base", []),
                general_notes=notes.get("general", []),
                longevity_very_weak=safe_int(votes[0]),
                longevity_weak=safe_int(votes[1]),
                longevity_moderate=safe_int(votes[2]),
                longevity_long_lasting=safe_int(votes[3]),
                longevity_eternal=safe_int(votes[4]),
                sillage_intimate=safe_int(votes[5]),
                sillage_moderate=safe_int(votes[6]),
                sillage_strong=safe_int(votes[7]),
                sillage_enormous=safe_int(votes[8]),
                gender_female=safe_int(votes[9]),
                gender_more_female=safe_int(votes[10]),
                gender_unisex=safe_int(votes[11]),
                gender_more_male=safe_int(votes[12]),
                gender_male=safe_int(votes[13]),
                price_way_overpriced=safe_int(votes[14]),
                price_overpriced=safe_int(votes[15]),
                price_ok=safe_int(votes[16]),
                price_good_value=safe_int(votes[17]),
                price_great_value=safe_int(votes[18]),
                url=url
            )

            session.add(cologne)
            session.commit()

            # Link notes
            for note_type_key, note_type_enum in {
                "top": NoteType.TOP,
                "middle": NoteType.MIDDLE,
                "base": NoteType.BASE,
                "general": NoteType.GENERAL
            }.items():
                for note_name in notes.get(note_type_key, []):
                    note = session.query(Note).filter_by(name=note_name).first()
                    if note:
                        link = CologneNote(cologne_id=cologne.id, note_id=note.id, note_type=note_type_enum)
                        session.add(link)

            session.commit()
            print(f"[+] Added cologne: {brand} - {perfume_title}")

        except Exception as e:
            print(f"[!] Error processing {url}: {e}")
            continue

def main():
    # get_note_urls()
    get_cologne_urls()
    # note_scraper()
    # cologne_scraper()


if __name__ == "__main__":
    main()