import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from seleniumbase import SB
from selenium_stealth import stealth
from urllib import request, error
import requests
from dotenv import load_dotenv
from lxml import html
from pymongo.mongo_client import MongoClient
import time, random

BASE_URL = "https://www.fragrantica.com"
global num_requests
MAX_REQUESTS = 25

load_dotenv()

def get_mongo_client():
    uri = os.getenv("MONGO_URI")
    return MongoClient(uri)

def get_collection(db_name="scentfinder", collection_name="colognes"):
    client = get_mongo_client()
    db = client[db_name]
    return db[collection_name]

def insert_data(data, collection_name="colognes"):
    collection = get_collection(collection_name)
    collection.insert_one(data)

def get_data_by_name(name, collection_name="colognes"):
    collection = get_collection(collection_name)
    return collection.find_one({"name": name})

def get_scraperapi_response(url):
    API_KEY = os.getenv("SCRAPERAPI_KEY")
    scraperapi_url = f"http://api.scraperapi.com/?api_key={API_KEY}&url={url}&render=true"
    return requests.get(scraperapi_url, timeout=20)


def get_note_urls():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)

    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    driver.get(BASE_URL+"/notes/")
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
    cleaned = re.sub(r"[é]+","e",cleaned)
    cleaned = re.sub(r"[ô]+","o",cleaned)
    cleaned = re.sub(r"[á]+","a",cleaned)
    # Strip leading/trailing dashes
    return cleaned.strip("-")

def get_cologne_urls():
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
        with open("../../data/raw/colognes.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()

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

                except Exception as e:
                    print(f"Skipping {brand} due to: {e}")
                    continue

def note_scraper():
    global num_requests
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36"
    ]

    # Get URLs from file
    with open("../../data/raw/notes.txt", "r",encoding="utf-8") as f:
        note_urls = f.readlines()
    num_notes = len(note_urls)
    num_records = get_collection().count_documents({})

    with SB(uc=True, headless=False) as driver:
        # Random user-agent
        driver.driver.execute_cdp_cmd(
            'Network.setUserAgentOverride',
            {"userAgent": random.choice(USER_AGENTS)}
        )

        for idx in range(num_records,num_notes):
            try:
                url = note_urls[idx][:-1]
                driver.open(url)
                driver.uc_gui_click_captcha()
                driver.sleep(random.uniform(1, 3))
                driver.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                driver.sleep(random.uniform(2, 5))
                num_requests += 1

                tree = html.fromstring(driver.get_page_source())
                note_title = tree.xpath("//h1//text()")[0].strip()
                note_group = tree.xpath("//h3//b")[0].text.strip()
                note_description = tree.xpath("//div[@class='cell callout']//p//text()")[0].strip()
                note_data = {
                    "name": note_title,
                    "group": note_group,
                    "description": note_description,
                    "url": url
                }
                if get_data_by_name(note_title) is None:
                    insert_data(note_data,"notes")
                else:
                    continue
            except requests.exceptions.ConnectionError as e:
                continue

def represents_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def cologne_scraper():
    global num_requests
    with open("../../data/raw/colognes.txt", "r",encoding="utf-8") as f:
        cologne_urls = f.readlines()
    num_colognes = len(cologne_urls)
    num_records = get_collection().count_documents({})
    for idx in range(num_records,num_colognes):
        try:
            url = cologne_urls[idx][:-1]
            if num_requests % 25 == 0:
                page = get_scraperapi_response(url)
            else:
                try:
                    page = requests.get(url, timeout=20)
                except Exception:
                    page = get_scraperapi_response(url)
            num_requests += 1
            tree = html.fromstring(page.content)
            brand_and_perfume = url[35:-6].split("/")
            brand = brand_and_perfume[0].replace("-"," ")
            perfume_title = brand_and_perfume[1].split("-")
            perfume_title = " ".join(perfume_title[:-1])
            page_title = tree.xpath("//head//title//text()")[0]
            if not page_title:
                launch_year = None
            else:
                launch_year = page_title[-4:].strip()
                if not represents_int(launch_year):
                    launch_year = None
            main_accords = [text.strip() for text in tree.xpath("//div[@class='cell accord-bar']//text()") if text.strip()]
            notes_captions = tree.xpath("//div[@class='strike-title']//text()")
            notes={}
            if "Fragrance Notes" in notes_captions:
                notes["general"] = tree.xpath("//div[@class='text-center notes-box']/following-sibling::div[1]//div[a]//text()")
            elif "Perfume Pyramid" in notes_captions:
                top_notes = tree.xpath("//h4[normalize-space()='Top Notes']/following-sibling::div[1]//div[a]//text()")
                middle_notes = tree.xpath("//h4[normalize-space()='Middle Notes']/following-sibling::div[1]//div[a]//text()")
                base_notes = tree.xpath("//h4[normalize-space()='Bottom Notes']/following-sibling::div[1]//div[a]//text()")
                if top_notes:
                    notes["top"] = top_notes
                else:
                    notes["top"] = None
                if middle_notes:
                    notes["middle"] = middle_notes
                else:
                    notes["middle"] = None
                if base_notes:
                    notes["base"] = base_notes
                else:
                    notes["base"] = None
            else:
                notes = None
            votes = tree.xpath("//div[@class = 'cell small-1 medium-1 large-1']//text()")
            longevity = {"very weak": represents_int(votes[0]), "weak": represents_int(votes[1]), "moderate": represents_int(votes[2]), "long lasting": represents_int(votes[3]), "eternal": represents_int(votes[4])}
            sillage = {"intimate": represents_int(votes[5]), "moderate": represents_int(votes[6]), "strong": represents_int(votes[7]), "enormous": represents_int(votes[8])}
            gender = {"female": represents_int(votes[9]), "more female": represents_int(votes[10]), "unisex": represents_int(votes[11]), "more male": represents_int(votes[12]), "male": represents_int(votes[13])}
            price_value = {"way overpriced": represents_int(votes[14]), "overpriced": represents_int(votes[15]), "ok": represents_int(votes[16]), "good value": represents_int(votes[17]), "great value": represents_int(votes[18])}
            perfume = {
                "title":perfume_title,
                "brand":brand,
                "launch year":launch_year,
                "main accords":main_accords,
                "notes":notes,
                "longevity":longevity,
                "sillage":sillage,
                "gender":gender,
                "price value":price_value}
            if get_data_by_name(perfume) is None:
                insert_data(perfume,"colognes")
            else:
                continue
        except error.HTTPError:
            continue

def main():
    get_note_urls()
    #get_cologne_urls()
    #note_scraper()
    #cologne_scraper()

if __name__ == "__main__":
    main()
