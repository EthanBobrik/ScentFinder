import os, re
from seleniumbase import SB
import requests
from dotenv import load_dotenv
from lxml import html
import time, random
from database.db import session
from database.models import Cologne, Note, CologneNote, NoteType
from bs4 import BeautifulSoup

MAX_REQUESTS = 25
BASE_URL = "https://www.fragrantica.com"
global num_requests
cooldown_until = 0

load_dotenv()

def get_scraperapi_response(url):
    API_KEY = os.getenv("SCRAPERAPI_KEY")
    if not API_KEY:
        print("[!] SCRAPERAPI_KEY not found in environment variables")
        return None

    scraperapi_url = f"http://api.scraperapi.com/?api_key={API_KEY}&url={url}&render=true"
    try:
        response = requests.get(scraperapi_url, timeout=20)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"[!] Error with ScraperAPI request: {e}")
        return None

def notes_scraper(db_session):
    """
    Fetches all notes from /notes/ page, extracting name, url, and group for each note,
    and inserts each unique note into the database if it does not already exist.
    """
    print("[+] Starting notes scraper...")

    with SB(uc=True, headless=False) as driver:
        try:
            driver.open(BASE_URL + "/notes/")
            driver.uc_gui_click_captcha()
            driver.sleep(random.uniform(1, 3))
            driver.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            driver.sleep(random.uniform(2, 5))
            driver.wait_for_element("div.notebox", timeout=10)
            response = driver.get_page_source()
            if not response:
                print("[!] No response from the page. Exiting notes scraper.")
                return
            print("[+] Page loaded successfully, processing content...")

            # Use BeautifulSoup to parse the content
            soup = BeautifulSoup(response, "html.parser")
            print(f"[+] Page content length: {len(response)}")

            # Debug: Check if we have the expected structure
            noteboxes = soup.find_all("div", class_="notebox")
            print(f"[+] Found {len(noteboxes)} noteboxes")

            if len(noteboxes) == 0:
                # Try alternative selectors
                noteboxes = soup.find_all("div", class_=lambda x: x and "notebox" in x)
                print(f"[+] Found {len(noteboxes)} noteboxes with alternative selector")

            tree = html.fromstring(str(soup))

            # Try multiple XPath patterns
            xpath_patterns = [
                "//div[contains(@class, 'notebox')]/a",
                "//div[@class='notebox']/a",
                "//a[contains(@href, '/notes/')]"
            ]

            note_links = []
            for pattern in xpath_patterns:
                note_links = tree.xpath(pattern)
                print(f"[+] XPath pattern '{pattern}' found {len(note_links)} links")
                if note_links:
                    break

            if not note_links:
                print("[!] No note links found. Let's examine the page structure...")
                # Print first 1000 characters to debug
                print("Page content preview:")
                print(response.text[:1000])
                return

            notes_added = 0
            notes_skipped = 0

            for i, a in enumerate(note_links):
                try:
                    name = a.xpath(".//text()")
                    name = name[0].strip() if name else None

                    note_url = a.xpath(".//@href")
                    note_url = note_url[0] if note_url else None

                    # Find the nearest preceding group header
                    group = a.xpath("(.//preceding::div[@class='text-center']//h2/text())[last()]")
                    if not group:
                        # Try alternative group finding
                        group = a.xpath(".//preceding::h2/text()[1]")
                    group = group[0].strip() if group else "Unknown"

                    if name and note_url:
                        # Check if note already exists
                        exists = db_session.query(Note).filter_by(name=name).first()
                        if not exists:
                            note = Note(name=name, group=group, url=note_url)
                            db_session.add(note)
                            notes_added += 1
                            if notes_added % 50 == 0:  # Progress indicator
                                print(f"[+] Processed {notes_added} notes so far...")
                        else:
                            notes_skipped += 1
                    else:
                        print(f"[!] Missing data for note {i}: name='{name}', url='{note_url}'")

                except Exception as e:
                    print(f"[!] Error processing note {i}: {e}")
                    continue

            # Commit all changes
            db_session.commit()
            print(f"[+] Notes scraping completed! Added: {notes_added}, Skipped: {notes_skipped}")

            # Verify the data was saved
            try:
                total_notes = db_session.query(Note).count()
                print(f"[+] Total notes in database: {total_notes}")
            except Exception as e:
                print(f"[!] Could not count notes: {e}")

        except Exception as e:
            print(f"[!] Error in notes_scraper: {e}")
            db_session.rollback()
            import traceback
            traceback.print_exc()

def clean_name(text):
    if not text:
        return ""
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

    print("[+] Starting cologne URL collection...")

    # Create data directory if it doesn't exist
    os.makedirs("../../data/raw", exist_ok=True)

    with SB(uc=True, headless=False) as driver:
        # Random user-agent
        driver.driver.execute_cdp_cmd(
            'Network.setUserAgentOverride',
            {"userAgent": random.choice(USER_AGENTS)}
        )

        designer_url = BASE_URL + "/designers/"
        print(f"[+] Opening designers page: {designer_url}")

        driver.open(designer_url)
        driver.uc_gui_click_captcha()
        driver.sleep(random.uniform(1, 3))
        driver.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        driver.sleep(random.uniform(2, 5))

        try:
            driver.wait_for_element("div.designerlist", timeout=10)
        except Exception as e:
            print(f"[!] Could not find designerlist element: {e}")
            return

        tree = html.fromstring(driver.get_page_source())

        names_raw = tree.xpath("//div[contains(@class,'designerlist')]//a/text()")
        urls_raw = tree.xpath("//div[contains(@class,'designerlist')]//a/@href")

        print(f"[+] Found {len(names_raw)} brand names and {len(urls_raw)} URLs")

        if len(names_raw) != len(urls_raw):
            print(f"[!] Mismatch in names and URLs. Taking minimum length.")
            min_len = min(len(names_raw), len(urls_raw))
            names_raw = names_raw[:min_len]
            urls_raw = urls_raw[:min_len]

        names_cleaned = [clean_name(name.strip()) for name in names_raw]
        brand_map = dict(zip(names_cleaned, urls_raw))

        # Get brands already scraped
        try:
            with open("../../data/raw/colognes.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []
            print("[+] No existing cologne URLs file found, starting fresh")

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

        print(f"[+] Total brands: {len(all_brands)}")
        print(f"[+] Already scraped: {len(brands_scraped)}")
        print(f"[+] Brands not yet scraped: {len(brands_not_scraped)}")

        with open("../../data/raw/colognes.txt", "a", encoding="utf-8") as f:
            for brand in brands_not_scraped:
                if num_requests > MAX_REQUESTS:
                    print("[+] Rate limit reached, sleeping for 10 minutes...")
                    time.sleep(600)
                    num_requests = 0

                # Lookup path in brand_map
                brand_path = brand_map[brand]
                brand_full_url = BASE_URL + brand_path

                print(f"[+] Scraping brand: {brand}")
                time.sleep(random.uniform(5, 15))

                driver.driver.execute_script("window.scrollBy(0, window.innerHeight/2);")
                driver.sleep(random.uniform(1, 3))

                try:
                    driver.open(brand_full_url)
                    driver.uc_gui_click_captcha()
                    driver.sleep(random.uniform(1, 3))

                    # Infinite scroll to load all colognes
                    last_height = driver.driver.execute_script("return document.body.scrollHeight")
                    while True:
                        driver.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                        time.sleep(random.uniform(1, 2))
                        new_height = driver.driver.execute_script("return document.body.scrollHeight")
                        if new_height == last_height:
                            break
                        last_height = new_height

                    driver.wait_for_element("div.flex-child-auto", timeout=10)
                    tree2 = html.fromstring(driver.get_page_source())
                    cologne_urls = tree2.xpath("//div[contains(@class, 'flex-child-auto')]//a/@href")

                    urls_added = 0
                    for cologne_url in cologne_urls:
                        url = f"{BASE_URL}{cologne_url}\n"
                        f.write(url)
                        urls_added += 1
                        num_requests += 1

                    print(f"[+] Added {urls_added} URLs for brand {brand}")

                except Exception as e:
                    print(f"[!] Skipping {brand} due to: {e}")
                    continue

def represents_int(s):
    try:
        int(s)
        return True
    except (ValueError, TypeError):
        return False

def cologne_scraper():
    print("[+] Starting cologne scraper...")

    try:
        with open("../../data/raw/colognes.txt", "r", encoding="utf-8") as f:
            cologne_urls = f.readlines()
    except FileNotFoundError:
        print("[!] No colognes.txt file found. Run get_cologne_urls() first.")
        return

    num_colognes = len(cologne_urls)

    try:
        num_records = session.query(Cologne).count()
    except Exception as e:
        print(f"[!] Error counting existing records: {e}")
        num_records = 0

    print(f"[+] Total cologne URLs: {num_colognes}")
    print(f"[+] Already processed: {num_records}")
    print(f"[+] Remaining to process: {num_colognes - num_records}")

    for idx in range(num_records, num_colognes):
        url = cologne_urls[idx].strip()
        print(f"[+] Processing cologne {idx + 1}/{num_colognes}: {url}")

        try:
            page = get_scraperapi_response(url)
            if not page:
                print(f"[!] Failed to get page content for {url}")
                continue

            tree = html.fromstring(page.content)

            url_parts = url.replace(BASE_URL, "").strip("/").split("/")
            if len(url_parts) < 3 or url_parts[0] != "perfume":
                print(f"[!] Invalid URL format: {url}")
                continue

            brand = url_parts[1].replace("-", " ")
            perfume_name_parts = url_parts[2].split("-")
            perfume_title = " ".join(perfume_name_parts[:-1]) if len(perfume_name_parts) > 1 else perfume_name_parts[0]

            # Extract launch year
            page_title_elements = tree.xpath("//head//title//text()")
            launch_year = None
            if page_title_elements:
                page_title = page_title_elements[0]
                potential_year = page_title[-4:].strip()
                if represents_int(potential_year):
                    launch_year = int(potential_year)

            # Extract main accords
            main_accords = [text.strip() for text in tree.xpath("//div[@class='cell accord-bar']//text()") if
                            text.strip()]

            # Extract notes
            notes_captions = tree.xpath("//div[@class='strike-title']//text()")
            notes = {}
            if "Fragrance Notes" in notes_captions:
                notes["general"] = tree.xpath(
                    "//div[@class='text-center notes-box']/following-sibling::div[1]//div[a]//text()")
            elif "Perfume Pyramid" in notes_captions:
                notes["top"] = tree.xpath(
                    "//h4[normalize-space()='Top Notes']/following-sibling::div[1]//div[a]//text()")
                notes["middle"] = tree.xpath(
                    "//h4[normalize-space()='Middle Notes']/following-sibling::div[1]//div[a]//text()")
                notes["base"] = tree.xpath(
                    "//h4[normalize-space()='Bottom Notes']/following-sibling::div[1]//div[a]//text()")

            # Extract votes
            votes = tree.xpath("//div[@class = 'cell small-1 medium-1 large-1']//text()")
            if len(votes) < 19:
                print(f"[!] Not enough vote data for {url} (found {len(votes)}, need 19)")
                continue

            def safe_int(val):
                return int(val) if represents_int(val) else 0

            # Create cologne object
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

            # Link notes to cologne
            for note_type_key, note_type_enum in {
                "top": NoteType.TOP,
                "middle": NoteType.MIDDLE,
                "base": NoteType.BASE,
                "general": NoteType.GENERAL
            }.items():
                for note_name in notes.get(note_type_key, []):
                    try:
                        note = session.query(Note).filter_by(name=note_name).first()
                        if note:
                            # Check if link already exists
                            existing_link = session.query(CologneNote).filter_by(
                                cologne_id=cologne.id,
                                note_id=note.id,
                                note_type=note_type_enum
                            ).first()

                            if not existing_link:
                                link = CologneNote(cologne_id=cologne.id, note_id=note.id, note_type=note_type_enum)
                                session.add(link)
                    except Exception as e:
                        print(f"[!] Error linking note {note_name}: {e}")

            session.commit()
            print(f"[+] Added cologne: {brand} - {perfume_title}")

        except Exception as e:
            print(f"[!] Error processing {url}: {e}")
            session.rollback()
            import traceback
            traceback.print_exc()
            continue

def main():
    print("[+] Starting fragrance scraper...")

    # Uncomment the function you want to run:

    # 1. First run this to scrape all notes
    #notes_scraper(session)

    # 2. Then run this to collect cologne URLs (this takes a long time)
    # get_cologne_urls()

    # 3. Finally run this to scrape individual cologne data
    #cologne_scraper()

    session.close()
    print("[+] Scraper finished!")


if __name__ == "__main__":
    main()