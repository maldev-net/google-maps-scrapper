const puppeteer = require('puppeteer');
const fs = require('fs').promises;
const { parse } = require('csv-parse/sync');

async function scrapeEmails(url) {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 1200000, ignoreHTTPSErrors: true });
    await new Promise(r => setTimeout(r, 20000));

    const contactLinks = await page.$$eval(
      'a',
      (links) => links
        .filter((link) => {
          const text = link.textContent.toLowerCase();
          return text.includes('contact') || text.includes('about') || text.includes('get in touch') || text.includes('reach us');
        })
        .map((link) => link.href)
    );

    if (contactLinks.length > 0) {
      for (const link of contactLinks) {
        try {
          await page.goto(link, { waitUntil: 'domcontentloaded', timeout: 120000, ignoreHTTPSErrors: true });
          await new Promise(r => setTimeout(r, 20000));

          const content = await page.content();
          const emails = content.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}/g) || [];

          if (emails.length > 0) {
            await browser.close();
            return emails[0];
          }
        } catch (linkError) {
          console.error(`Error processing contact link on ${url}: ${linkError}`);
        }
      }
    }

    await browser.close();
    return 'N/A';
  } catch (error) {
    console.error(`Error navigating to ${url}: ${error}`);
    await browser.close();
    return 'N/A';
  }
}

async function main() {
  try {
    const csvData = await fs.readFile('business_data.csv', { encoding: 'utf8' });
    const records = parse(csvData, {
      columns: true,
      skip_empty_lines: true,
    });

    const scrapedEmails = []; // Array to store scraped data

    for (const record of records) {
      try {
        const website = record.Website;
        if (website && website !== 'N/A') {
          const url = website.startsWith('http') ? website : `https://${website}`;
          const email = await scrapeEmails(url);
          scrapedEmails.push({ Website: website, email_2: email }); // Store data
        } else {
          scrapedEmails.push({ Website: website, email_2: 'N/A' });
        }
      } catch (error) {
        console.error(`Error processing ${record.Website}: ${error}`);
        scrapedEmails.push({ Website: record.Website, email_2: 'Error' });
      }
    }

    // Create CSV content
    let csvContent = 'Website,email_2\n';
    scrapedEmails.forEach(item => {
      csvContent += `${item.Website},${item.email_2}\n`;
    });

    // Write to a new CSV file
    await fs.writeFile('scraped_emails.csv', csvContent);
    console.log('Emails scraped and saved to scraped_emails.csv');
  } catch (error) {
    console.error('An error occurred:', error);
  }
}

main();