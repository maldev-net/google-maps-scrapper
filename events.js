const puppeteer = require('puppeteer');

(async () => {
  try {
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();

    // Navigate to Google Maps
    await page.goto('https://www.google.com/maps');

    // Wait for the search input field
    await page.waitForSelector('input[aria-label="Search Google Maps"]', { timeout: 15000 });
    await page.type('input[aria-label="Search Google Maps"]', 'restaurants in Lahore');
    await page.keyboard.press('Enter');

    // Wait for the results to load
    await page.waitForSelector('.section-result-title', { timeout: 15000 });

    // Extract data from the results
    const results = await page.evaluate(() => {
      const elements = document.querySelectorAll('.section-result');
      const data = [];
      elements.forEach((element) => {
        const name = element.querySelector('.section-result-title')?.textContent || 'N/A';
        const address = element.querySelector('.section-result-location')?.textContent || 'N/A';
        data.push({ name, address });
      });
      return data;
    });

    console.log('Scraped Results:', results);

    await browser.close();
  } catch (error) {
    console.error('Error scraping Google Maps:', error);
  }
})();
