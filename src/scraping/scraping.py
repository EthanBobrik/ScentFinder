import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from seleniumbase import SB
from selenium_stealth import stealth
from urllib import request, error
import requests
from dotenv import load_dotenv
from lxml import html
from pymongo.mongo_client import MongoClient
import time

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

    driver.get("https://www.fragrantica.com/notes/")
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

def get_cologne_urls():
    with SB(uc=True, headless=True) as driver:
        countries = ["United States", "France", "Italy", "United Kingdom", "Germany", "Spain",
                     "United Arab Emirates", "Russia", "Switzerland", "Netherlands", "Japan",
                     "England", "Canada", "Brazil", "Poland", "Australia"]

        with open("../../data/raw/colognes.txt", "w", encoding="utf-8") as f:
            for country in countries:
                try:
                    country_url = f"https://www.fragrantica.com/country/{country}.html"
                    driver.open(country_url)

                    # Attempt to solve CAPTCHA after country page
                    driver.uc_gui_click_captcha()

                    last_height = driver.driver.execute_script("return document.body.scrollHeight")
                    while True:
                        driver.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                        time.sleep(1)
                        new_height = driver.driver.execute_script("return document.body.scrollHeight")
                        if new_height == last_height:
                            break
                        last_height = new_height

                    driver.wait_for_element("div.designerlist")
                    tree1 = html.fromstring(driver.get_page_source())
                    brand_urls = tree1.xpath("//div[contains(@class,'designerlist')]//a/@href")

                    for brand_url in brand_urls:
                        brand_full_url = f"https://www.fragrantica.com{brand_url}"
                        driver.open(brand_full_url)

                        # Attempt to solve CAPTCHA after brand page
                        driver.uc_gui_click_captcha()

                        last_height = driver.driver.execute_script("return document.body.scrollHeight")
                        while True:
                            driver.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                            time.sleep(1)
                            new_height = driver.driver.execute_script("return document.body.scrollHeight")
                            if new_height == last_height:
                                break
                            last_height = new_height

                        driver.wait_for_element("div.flex-child-auto")
                        tree2 = html.fromstring(driver.get_page_source())
                        cologne_urls = tree2.xpath("//div[contains(@class, 'flex-child-auto')]//a/@href")

                        for cologne_url in cologne_urls:
                            url = f"https://www.fragrantica.com{cologne_url}\n"
                            f.write(url)
                            print(url)

                except Exception as e:
                    print(f"Skipping {country} due to: {e}")
                    continue

def note_scraper():
    with open("../../data/raw/notes.txt", "r",encoding="utf-8") as f:
        note_urls = f.readlines()
    num_notes = len(note_urls)
    num_records = get_collection().count_documents({})
    for idx in range(num_records,num_notes):
        try:
            url = note_urls[idx][:-1]
            page = requests.get(url)
            tree = html.fromstring(page.content)
            note_title = tree.xpath("//h1//text()")[0].trim()
            note_group = tree.xpath("//h3//b")[0].trim()
            note_description = tree.xpath("//div[@class='cell callout']//p//text()")[0].trim()
            note_data = {
                "name": note_title,
                "group": note_group.text,
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
    with open("../../data/raw/colognes.txt", "r",encoding="utf-8") as f:
        cologne_urls = f.readlines()
    num_colognes = len(cologne_urls)
    num_records = get_collection().count_documents({})
    for idx in range(num_records,num_colognes):
        try:
            url = cologne_urls[idx][:-1]
            page = requests.get(url)
            tree = html.fromstring(page.content)
            brand_and_perfume = url[35:-6].split("/")
            brand = brand_and_perfume[0].replace("-"," ")
            perfume_title = brand_and_perfume[1].split("-")
            perfume_title = " ".join(perfume_title[:-1])
            page_title = tree.xpath("//head//title//text()")[0]
            if not page_title:
                launch_year = None
            else:
                launch_year = page_title[-4:].trim()
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
    #get_note_urls()
    get_cologne_urls()
    #note_scraper()
    #cologne_scraper()

if __name__ == "__main__":
    main()
