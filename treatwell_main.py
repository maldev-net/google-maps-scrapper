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

def scrape_treatwell(search_query, location, date):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.treatwell.co.uk/")

        # Fill search query and location
        page.fill('input[name="service"]', search_query)
        page.fill('input[name="place"]', location)

        # Select date
        page.click('input[name="date"]')
        page.fill('input[name="date"]', date)
        page.click('text=Find treatments')

        page.wait_for_selector('.VenueCard-module--content--2u0f6')

        salon_links = page.locator('.VenueCard-module--content--2u0f6 a').all()
        salon_urls = [salon.get_attribute('href') for salon in salon_links]

        salon_data = []
        for url in tqdm(salon_urls, desc="Scraping salons"):
            print(f"Scraping salon: {url}") #debug print
            page.goto(url)
            page.wait_for_selector('.VenueHero-module--container--3t62T')
            page.wait_for_timeout(2000) #increase wait time

            data = {}

            # Salon Photo
            salon_photo_selector = '.Carousel-module--image--247744'
            if page.locator(salon_photo_selector).count() > 0:
                data['salon_photo'] = page.locator(salon_photo_selector).first.get_attribute('src')
                print(f"Salon Photo: {data['salon_photo']}") #debug print
            else:
                data['salon_photo'] = 'N/A'
                print("Salon Photo: N/A") #debug print

            # Salon Description
            description_selector = '.VenueDescription-module--content--2m13n'
            if page.locator(description_selector).count() > 0:
                data['salon_description'] = page.locator(description_selector).inner_text()
                print(f"Salon Description: {data['salon_description'][:50]}...") #debug print
            else:
                data['salon_description'] = 'N/A'
                print("Salon Description: N/A") #debug print

            # Team
            team_selector = '.StaffList-module--staffList--3y6bS'
            if page.locator(team_selector).count() > 0:
                team_members = page.locator('.StaffMemberCard-module--container--2qXh6').all()
                data['team'] = [member.inner_text() for member in team_members]
                print(f"Team: {len(data['team'])} members") #debug print
            else:
                data['team'] = 'N/A'
                print("Team: N/A") #debug print

            # Opening Hours
            hours_selector = '.OpeningHours-module--openingHours--11w7u'
            if page.locator(hours_selector).count() > 0:
                data['opening_hours'] = page.locator(hours_selector).inner_text()
                print(f"Opening Hours: {data['opening_hours'][:50]}...") #debug print
            else:
                data['opening_hours'] = 'N/A'
                print("Opening Hours: N/A") #debug print

            # Reviews
            reviews_selector = '.ReviewList-module--reviewList--1M4yI'
            if page.locator(reviews_selector).count() > 0:
                reviews = page.locator('.ReviewCard-module--container--120yJ').all()
                good_reviews = []
                bad_reviews = []
                good_count = 0
                bad_count = 0
                for review in reviews:
                    rating_text = review.locator(".ReviewCard-module--rating--2nE0F").inner_text()
                    if "5" in rating_text and good_count < 5:
                        good_reviews.append(review.inner_text())
                        good_count += 1
                    elif "1" in rating_text and bad_count < 5:
                        bad_reviews.append(review.inner_text())
                        bad_count += 1
                data['good_reviews'] = good_reviews
                data['bad_reviews'] = bad_reviews
                print(f"Good Reviews: {len(good_reviews)}, Bad Reviews: {len(bad_reviews)}") #debug print
            else:
                data['good_reviews'] = 'N/A'
                data['bad_reviews'] = 'N/A'
                print("Reviews: N/A") #debug print

            # Booking Situation
            booking_selector = '.StaffList-module--staffList--3y6bS'
            if page.locator(booking_selector).count() > 0:
                stylists = page.locator('.StaffMemberCard-module--container--2qXh6').all()
                booking_situation = []
                for stylist in stylists:
                    booking_situation.append(stylist.inner_text())
                data['booking_situation'] = booking_situation
                print(f"Booking Situation: {len(booking_situation)} stylists") #debug print
            else:
                data['booking_situation'] = 'N/A'
                print("Booking Situation: N/A") #debug print

            #services
            services_selector = '.TreatmentList-module--treatmentList--318yJ'
            if page.locator(services_selector).count() > 0:
                services = page.locator('.TreatmentCard-module--treatmentCard--108pE').all()
                data['services'] = [service.inner_text() for service in services]
                print(f"Services: {len(data['services'])} services") #debug print
            else:
                data['services'] = 'N/A'
                print("Services: N/A") #debug print

            salon_data.append(data)

        df = pd.DataFrame(salon_data)
        df.to_csv('treatwell_data.csv', index=False)
        print(df.head())
        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str, required=True)
    parser.add_argument("-l", "--location", type=str, required=True)
    parser.add_argument("-d", "--date", type=str, required=True)
    args = parser.parse_args()
    scrape_treatwell(args.search, args.location, args.date)