import re
from dataclasses import dataclass
from csv import DictWriter
from pathlib import Path

from bs4 import BeautifulSoup, Tag

# SOURCE_PATH = r'E:\alexa\Code\proj\Scrape_FB_Car_Ads\data\2024-08-07_Melb_20km_hiace.html'
SOURCE_PATH = r'data\2024-08-07_Melb_500km_hiace.html'
OUT_DIR = r"data\out"

out_file_name = Path(SOURCE_PATH).stem
OUT_FILE = f"{out_file_name}.csv"

MIN_PRICE = 1500

def get_text_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

source_text = get_text_from_file(SOURCE_PATH)

# print(source_text[:1000])

soup = BeautifulSoup(source_text, 'html.parser')

description_tags = soup.find_all(
    "span", 
    "x1lliihq x6ikm8r x10wlt62 x1n2onr6"
)

TILE_CLASS = 'x78zum5 xdt5ytf x1n2onr6'
TILE_DESCRIPTION_CLASS = "x1lliihq x6ikm8r x10wlt62 x1n2onr6"
LOCATION_CLASS = "x1lliihq x6ikm8r x10wlt62 x1n2onr6 xlyipyv xuxw1ft x1j85h84"
PRICE_CLASS = "x193iq5w xeuugli x13faqbe x1vvkbs x1xmvt09 x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x xudqn12 x676frb x1lkfr7t x1lbecb7 x1s688f xzsf02u"
MILEAGE_CLASS = "x1lliihq x6ikm8r x10wlt62 x1n2onr6 xlyipyv xuxw1ft x1j85h84"
IMAGE_CLASS = "xt7dq6l xl1xv1r x6ikm8r x10wlt62 xh8yej3"

TARGET_MODEL = 'hiace'

def price_text_to_number(price_text: str) -> str:
    price_text = re.sub(r'[^\d]', '', price_text)
    return price_text

def cull_whitespace(text) -> str:
    text = re.sub(r' +', ' ', text).strip()
    text = re.sub(r'\n', ' -', text).strip()
    return text

def clean_mileage(mileage: str) -> str:
    return re.sub(r'[^\d]', '', mileage)

def clean_fb_url(url: str) -> str:
    '''
    This https://www.facebook.com/marketplace/item/768406558758480/?ref=search&referral_code=null&referral_story_type=post&tracking=browse_serp%3A2fa8531b-3b46-4bc3-b1f0-c88bf7d07a4c
    becomes https://www.facebook.com/marketplace/item/768406558758480'''
    i = url.find("/?ref=")
    return url[0:i]
    # return url

@dataclass
class TileTitle:
    """
    Assumes the following format
    2008 Toyota hiace - turbo diesel with rwc and rego and 1 year warranty
    """
    year: str
    make: str
    model: str
    description: str

    @staticmethod
    def _split_description(tile_title: str):
        parts = tile_title.split(' ')
        year = parts[0]
        try:
            make = parts[1]
        except IndexError:
            make = ''
        try:
            model = parts[2]
        except IndexError:
            model = ''
        description = ' '.join(parts[3:])
        return year, make, model, cull_whitespace(description)

    @classmethod
    def from_string(cls, tile_title: str):
        year, make, model, description = cls._split_description(tile_title)
        return cls(year, make, model, description)


class Tile:

    def __init__(self, tile_html: BeautifulSoup):
        self.tile = tile_html

        try:
            title_html = self._get_title_html()
            assert title_html is not None, f"Title html is None"
        except AssertionError:
            raise ValueError(f"Invalid title_html: {title_html}")
        
        self.tile_title = TileTitle.from_string(title_html)

        self.year = self.tile_title.year
        self.make = self.tile_title.make
        self.model = self.tile_title.model
        self.description = self.tile_title.description
        self.price = self._get_price()

        self.mileage = self._get_mileage()

        self.location = self._get_location()

        self.is_valid = self._is_valid_tile()

        self.ad_url = self._get_ad_url()
        self.img_url = self._get_image_url()

    def _get_location(self):
        location_element = self.tile.find("span", LOCATION_CLASS)
        if location_element:
            return location_element.text
        return None

    def _get_title_html(self):
        title_html = self.tile.find("span", TILE_DESCRIPTION_CLASS)
        if title_html:
            return title_html.text
        return None
    
    def _get_price(self):
        price_element = self.tile.find("span", PRICE_CLASS)
        if price_element:
            return price_text_to_number(price_element.text)
        return None

    def _get_mileage(self):
        candidate_mileage_elements = self.tile.find_all("span", MILEAGE_CLASS)
        if not candidate_mileage_elements:
            return None
        for el in candidate_mileage_elements:
            if isinstance(el, Tag):
                if not re.match(r'^\d+', el.text):
                    continue
                if len(el.text) > 8:
                    continue
                return clean_mileage(el.text)              
        return None
    
    def _get_ad_url(self):
        base_url = 'https://www.facebook.com'
        # a_element = self.tile.find('a')
        a_element = self.tile.parent
        if not a_element:
            return None
        assert isinstance(a_element, Tag), f"{a_element=} is not a Tag"
        rel_url = a_element.get('href')
        if not rel_url:
            return None
        assert isinstance(rel_url, str), f"{rel_url=} is not a string"
        return clean_fb_url(f"{base_url}{rel_url}")
    
    def _get_image_url(self):
        image_element = self.tile.find("img", IMAGE_CLASS)
        if image_element:
            assert isinstance(image_element, Tag), f"{image_element=} is not a Tag"
            return image_element.get('src')
        return None

    def _is_valid_tile(self):
        if not self._is_year_valid():
            return False
        if self.price is None or int(self.price) < MIN_PRICE:
            return False
        if self.model.lower() != TARGET_MODEL.lower():
            return False
        
        return True
    
    def _is_year_valid(self):
        return re.match(r'^\d{4}$', self.tile_title.year)
    
    def to_dict(self):
        return {
            'year': self.year,
            'make': self.make,
            'model': self.model,
            'description': self.description,
            'price': self.price,
            'mileage': self.mileage,
            'location': self.location,
            'ad_url': self.ad_url,
            'img_url': self.img_url,
        }
    



def get_tiles() -> list:
    r_list = []
    tile_elements = soup.find_all("div", TILE_CLASS)
    for tile in tile_elements:
        try:
            r_list.append(Tile(tile))
        except ValueError as e:
            print(f"Error: {e}")
            continue
        except Exception as e:
            print(f"Error: {e}")
    return r_list

tiles = get_tiles()

valid_tiles = [tile for tile in tiles if tile.is_valid]

with open(f"{OUT_DIR}/{OUT_FILE}", 'w', newline='') as file:
    writer = DictWriter(file, fieldnames=valid_tiles[0].to_dict().keys())
    writer.writeheader()
    for tile in valid_tiles:
        writer.writerow(tile.to_dict())
        