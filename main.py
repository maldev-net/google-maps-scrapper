from playwright.sync_api import sync_playwright
import pandas as pd
import argparse
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from typing import Dict, List, Optional
import time
from tqdm import tqdm

class WebsiteDataExtractor:
    def __init__(self):
        self.patterns = {
            'email': r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}',
            'phone': r'(\+\d{1,3}[-.]?)?\s*\(?\d{3}\)?[-.]?\s*\d{3}[-.]?\s*\d{4}',
            'social_media': {
                'facebook': r'facebook\.com/[A-Za-z0-9.]+',
                'instagram': r'instagram\.com/[A-Za-z0-9_]+',
                'twitter': r'twitter\.com/[A-Za-z0-9_]+',
                'linkedin': r'linkedin\.com/[A-Za-z0-9_]+',
                'youtube': r'youtube\.com/[A-Za-z0-9_]+',
            }
        }

    def extract_structured_data(self, url: str) -> Dict:
        if not url or url == "N/A":
            return self._get_empty_result()
        try:
            session = self._create_session()
            soup = self._get_page_content(url, session)
            data = {
                'url': url,
                'structured_data': self._extract_schema_data(soup),
                'meta_data': self._extract_meta_data(soup),
                'contact_info': self._extract_contact_info(soup, url, session),
                'social_media': self._extract_social_media(soup),
                'business_hours': self._extract_business_hours(soup),
                'additional_info': self._extract_additional_info(soup)
            }
            return data
        except Exception as e:
            print(f"Error extracting data from {url}: {str(e)}")
            return self._get_empty_result()

    def _create_session(self):
        session = requests.Session()
        session.verify = False
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        return session

    def _get_page_content(self, url: str, session) -> BeautifulSoup:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        for attempt in range(3):
            try:
                response = session.get(url, timeout=20)
                return BeautifulSoup(response.text, 'html.parser')
            except:
                if attempt == 2:
                    raise
                time.sleep(1)

    def _extract_schema_data(self, soup: BeautifulSoup) -> Dict:
        schema_data = {}
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    schema_data.update(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            schema_data.update(item)
            except:
                continue
        return schema_data

    def _extract_meta_data(self, soup: BeautifulSoup) -> Dict:
        meta_data = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name', meta.get('property', ''))
            content = meta.get('content', '')
            if name and content:
                meta_data[name] = content
        return meta_data

    def _extract_contact_info(self, soup: BeautifulSoup, url: str, session) -> Dict:
        contact_info = {'emails': [], 'phones': [], 'address': None}
        text = soup.get_text()
        contact_info['emails'] = self._extract_emails(text)
        contact_info['phones'] = self._extract_phones(text)
        contact_links = soup.find_all('a', href=re.compile(r'contact|about|get-in-touch|reach-us', re.I))
        for link in contact_links[:2]:
            try:
                contact_url = urljoin(url, link['href'])
                response = session.get(contact_url, timeout=10)
                contact_soup = BeautifulSoup(response.text, 'html.parser')
                contact_text = contact_soup.get_text()
                contact_info['emails'].extend(self._extract_emails(contact_text))
                contact_info['phones'].extend(self._extract_phones(contact_text))
            except:
                continue
        contact_info['emails'] = list(set(contact_info['emails']))
        contact_info['phones'] = list(set(contact_info['phones']))
        return contact_info

    def _extract_social_media(self, soup: BeautifulSoup) -> Dict:
        social_media = {}
        for platform, pattern in self.patterns['social_media'].items():
            links = soup.find_all('a', href=re.compile(pattern, re.I))
            if links:
                social_media[platform] = list(set([link['href'] for link in links]))
        return social_media

    def _extract_business_hours(self, soup: BeautifulSoup) -> Optional[Dict]:
        schema_data = self._extract_schema_data(soup)
        if 'openingHours' in schema_data:
            return schema_data['openingHours']
        hours_div = soup.find('div', class_=re.compile(r'hours|schedule|timing', re.I))
        if hours_div:
            return {'raw': hours_div.get_text(strip=True)}
        return {}

    def _extract_additional_info(self, soup: BeautifulSoup) -> Dict:
        info = {}
        price_range = soup.find(class_=re.compile(r'price-range|pricing', re.I))
        if price_range:
            info['price_range'] = price_range.get_text(strip=True)
        cuisine = soup.find(class_=re.compile(r'cuisine|food-type', re.I))
        if cuisine:
            info['cuisine'] = cuisine.get_text(strip=True)
        return info

    def _extract_emails(self, text: str) -> List[str]:
        emails = re.findall(self.patterns['email'], text)
        return [email for email in emails if not email.endswith(('.png', '.jpg', '.gif', '.jpeg')) and len(email) < 100]

    def _extract_phones(self, text: str) -> List[str]:
        return re.findall(self.patterns['phone'], text)

    def _get_empty_result(self) -> Dict:
        return {'url': None, 'structured_data': {}, 'meta_data': {}, 'contact_info': {'emails': [], 'phones': [], 'address': None}, 'social_media': {}, 'business_hours': {}, 'additional_info': {}}

def main(search_for, total):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})

        name_xpath = '//div[@class="TIHn2 "]//h1[@class="DUwDvf lfPIob"]'
        address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
        website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
        phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
        reviews_count_xpath = '//div[@class="TIHn2 "]//div[@class="fontBodyMedium dmRWX"]//div//span//span//span[@aria-label]'
        reviews_average_xpath = '//div[@class="TIHn2 "]//div[@class="fontBodyMedium dmRWX"]//div//span[@aria-hidden]'
        intro_xpath = '//div[@class="WeS02d fontBodyMedium"]//div[@class="PYvSYb "]'
        info1 = '//div[@class="LTs0Rc"][1]'
        info2 = '//div[@class="LTs0Rc"][2]'
        info3 = '//div[@class="LTs0Rc"][3]'
        opens_at_xpath = '//button[contains(@data-item-id, "oh")]//div[contains(@class, "fontBodyMedium")]'
        opens_at_xpath2 = '//div[@class="MkV9"]//span[@class="ZDu9vd"]//span[2]'
        place_type_xpath = '//div[@class="LBgpqf"]//button[@class="DkEaL "]'

        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(3000)

        search_box = page.locator('//input[@id="searchboxinput"]')
        search_box.click()
        search_box.fill(search_for)
        page.keyboard.press("Enter")

        page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]')
        page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')

        listings = []
        last_height = 0

        while len(listings) < total:
            page.mouse.wheel(0, 10000)
            page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]')
            time.sleep(14)  # Wait for content to load

            new_listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
            new_listings = [listing.locator("xpath=..") for listing in new_listings]
            if len(new_listings) > len(listings):
                listings = new_listings
                print(f"Currently Found: {len(listings)}")
            else:
                current_height = page.evaluate("window.scrollY")
                if current_height == last_height:
                    print(f"No new results found, stopping scroll. Found {len(listings)} results.")
                    break
                last_height = current_height

        listings = listings[:total]

        scraped_data = []
        for listing in listings:
            try:
                listing.click()
                page.wait_for_selector(name_xpath)
                page.wait_for_timeout(4000)

                name = page.locator(name_xpath).inner_text() if page.locator(name_xpath).count() > 0 else ""
                address = page.locator(address_xpath).inner_text() if page.locator(address_xpath).count() > 0 else ""
                website = page.locator(website_xpath).inner_text() if page.locator(website_xpath).count() > 0 else ""
                phone = page.locator(phone_number_xpath).inner_text() if page.locator(phone_number_xpath).count() > 0 else ""
                place_type = page.locator(place_type_xpath).inner_text() if page.locator(place_type_xpath).count() > 0 else ""
                introduction = page.locator(intro_xpath).inner_text() if page.locator(intro_xpath).count() > 0 else "None Found"

                reviews_count = 0
                if page.locator(reviews_count_xpath).count() > 0:
                    temp = page.locator(reviews_count_xpath).inner_text()
                    temp = temp.replace('(', '').replace(')', '').replace(',', '')
                    reviews_count = int(temp)

                reviews_average = 0.0
                if page.locator(reviews_average_xpath).count() > 0:
                    temp = page.locator(reviews_average_xpath).inner_text()
                    temp = temp.replace(' ', '').replace(',', '.')
                    reviews_average = float(temp)

                store_shopping = "No"
                in_store_pickup = "No"
                store_delivery = "No"

                if page.locator(info1).count() > 0:
                    temp = page.locator(info1).inner_text()
                    temp = temp.split('·')
                    if len(temp) > 1:
                        check = temp[1].replace("\n", "")
                        if 'shop' in check.lower():
                            store_shopping = "Yes"
                        elif 'pickup' in check.lower():
                            in_store_pickup = "Yes"
                        elif 'delivery' in check.lower():
                            store_delivery = "Yes"

                if page.locator(info2).count() > 0:
                    temp = page.locator(info2).inner_text()
                    temp = temp.split('·')
                    if len(temp) > 1:
                        check = temp[1].replace("\n", "")
                        if 'pickup' in check.lower():
                            in_store_pickup = "Yes"
                        elif 'shop' in check.lower():
                            store_shopping = "Yes"
                        elif 'delivery' in check.lower():
                            store_delivery = "Yes"

                if page.locator(info3).count() > 0:
                    temp = page.locator(info3).inner_text()
                    temp = temp.split('·')
                    if len(temp) > 1:
                        check = temp[1].replace("\n", "")
                        if 'delivery' in check.lower():
                            store_delivery = "Yes"
                        elif 'pickup' in check.lower():
                            in_store_pickup = "Yes"
                        elif 'shop' in check.lower():
                            store_shopping = "Yes"

                opens_at = ""
                if page.locator(opens_at_xpath).count() > 0:
                    opens = page.locator(opens_at_xpath).inner_text()
                    opens = opens.split('⋅')
                    if len(opens) != 1:
                        opens = opens[1]
                    opens = opens.replace("\u202f", "")
                    opens_at = opens
                elif page.locator(opens_at_xpath2).count() > 0:
                    opens = page.locator(opens_at_xpath2).inner_text()
                    opens = opens.split('⋅')
                    opens = opens[1]
                    opens = opens.replace("\u202f", "")
                    opens_at = opens

                scraped_data.append({
                    'Names': name,
                    'Website': website,
                    'Introduction': introduction,
                    'Phone Number': phone,
                    'Address': address,
                    'Review Count': reviews_count,
                    'Average Review Count': reviews_average,
                    'Store Shopping': store_shopping,
                    'In Store Pickup': in_store_pickup,
                    'Delivery': store_delivery,
                    'Type': place_type,
                    'Opens At': opens_at
                })

                page.wait_for_timeout(1000)

            except Exception as e:
                print(f"Null scraping listing: {str(e)}")
                scraped_data.append({
                    'Names': "Null",
                    'Website': "Null",
                    'Introduction': "Null",
                    'Phone Number': "Null",
                    'Address': "Null",
                    'Review Count': 0,
                    'Average Review Count': 0.0,
                    'Store Shopping': "No",
                    'In Store Pickup': "No",
                    'Delivery': "No",
                    'Type': "Null",
                    'Opens At': "Null"
                })

        df = pd.DataFrame(scraped_data)
        df = df.drop_duplicates(subset=['Names'], keep='first')
        for column in df.columns:
            if df[column].nunique() == 1:
                df.drop(column, axis=1, inplace=True)

        print("\nExtracting detailed website data...")
        extractor = WebsiteDataExtractor()
        website_data = []

        for website in tqdm(df['Website'].tolist(), desc="Processing websites"):
            data = extractor.extract_structured_data(website)
            website_data.append(data)
            time.sleep(1)

        df['Email'] = [data['contact_info']['emails'][0] if data['contact_info']['emails'] else 'N/A' for data in website_data]
        df['Additional_Phones'] = [', '.join(data['contact_info']['phones']) if data['contact_info']['phones'] else 'N/A' for data in website_data]
        df['Facebook'] = [', '.join(data['social_media'].get('facebook', [])) if data['social_media'].get('facebook') else 'N/A' for data in website_data]
        df['Instagram'] = [', '.join(data['social_media'].get('instagram', [])) if data['social_media'].get('instagram') else 'N/A' for data in website_data]
        df['Twitter'] = [', '.join(data['social_media'].get('twitter', [])) if data['social_media'].get('twitter') else 'N/A' for data in website_data]
        df['Linkedin'] = [', '.join(data['social_media'].get('linkedin', [])) if data['social_media'].get('linkedin') else 'N/A' for data in website_data]
        df['Youtube'] = [', '.join(data['social_media'].get('youtube', [])) if data['social_media'].get('youtube') else 'N/A' for data in website_data]
        df['Business_Hours'] = [str(data['business_hours']) if data['business_hours'] else 'N/A' for data in website_data]

        def extract_address_components(address):
            if not address:
                return None, None, None, None
            parts = address.split(', ')
            street = parts[0] if parts else None
            city = parts[1] if len(parts) > 1 else None
            state = parts[2].split(' ')[0] if len(parts) > 2 else None
            postal_code = parts[2].split(' ')[1] if len(parts) > 2 and len(parts[2].split(' ')) > 1 else None
            return street, city, state, postal_code

        df[['Street', 'City', 'State', 'Postal Code']] = df['Address'].apply(lambda x: pd.Series(extract_address_components(x)))

        for website in tqdm(df['Website'].tolist(), desc="Processing websites"):
            data = extractor.extract_structured_data(website)
            website_data.append(data)
            time.sleep(1)

        df['email_1'] = 'N/A'
        for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="Extracting Facebook Emails"):
            facebook_links = row['Facebook'].split(', ')
            for link in facebook_links:
                if link != 'N/A':
                    try:
                        temp_page = browser.new_page()
                        temp_page.goto(link, timeout=60000)
                        temp_page.wait_for_timeout(5000)

                        if temp_page.locator('div[role="dialog"]').count() > 0:
                            try:
                                close_button = temp_page.locator('div[role="dialog"] button[aria-label="Close"]')
                                if close_button.count() > 0:
                                    close_button.hover()
                                    close_button.click()
                                    temp_page.wait_for_timeout(2000)
                                else:
                                    print(f"Close button not found on {link}")
                            except Exception as popup_error:
                                print(f"Error closing popup on {link}: {popup_error}")

                        content = temp_page.content()
                        try:
                            emails = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}', content)
                            if emails:
                                df.at[index, 'email_1'] = emails[0]
                            else:
                                print(f"No email found on {link}")
                        except Exception as re_error:
                            print(f"Error finding emails on {link}: {re_error}")

                        temp_page.close()

                    except Exception as e:
                        print(f"Error navigating to {link}: {e}")

        # Add search query column with dynamic values
        if not df.empty:  # Check if DataFrame is not empty
            df['search_query'] = df.apply(
                lambda row: f"{search_for.split('in')[0].strip()}, {row['Postal Code']}, {row['City']}, {row['State']}, US",
                axis=1
            )
        else:
            df['search_query'] = "N/A"  # If DataFrame is empty, search_query is "N/A"

        # Email Validation and Cleaning
        def clean_email(email):
            if pd.isna(email) or email == 'N/A':
                return 'N/A'
            email = email.lower()
            cleaned_email = re.sub(r'[^a-z@.]', '', email)
            return cleaned_email

        df['Email'] = df['Email'].apply(clean_email)
        df['email_1'] = df['email_1'].apply(clean_email)

        with open('detailed_business_data.json', 'w') as f:
            json.dump(website_data, f, indent=2)

        df.to_csv('business_data.csv', index=False)
        print("\nFirst few records:")
        print(df.head())
        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()

    if args.search:
        search_for = args.search
    else:
        search_for = "turkish stores in toronto Canada"  # Default search query
    if args.total:
        total = args.total
    else:
        total = 100  # Set the default total to 100

    main(search_for, total)