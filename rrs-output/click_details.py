import asyncio
import aiohttp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import pandas as pd
import logging
import concurrent.futures
from functools import partial
import re
import traceback
import sys
import os
import nest_asyncio

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MAX_CONCURRENT_MODALS = 3  # Adjust based on your system's capabilities
WAIT_TIME = 2  # Default wait time in seconds

class USACENoticesScraper:
    def __init__(self, headless=False):
        self.setup_driver(headless)
        self.data = []
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_MODALS)
    
    def setup_driver(self, headless):
        """Initialize the webdriver with appropriate options"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--disable-extensions")
        if headless:
            chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.maximize_window()
    
    async def initialize(self):
        """Load the initial page and handle consent popup"""
        logger.info("Loading initial page...")
        self.driver.get("https://rrs.usace.army.mil/rrs/public-notices")
        await asyncio.sleep(5)
        
        # Accept consent pop-up if present
        try:
            accept_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'I Accept')]"))
            )
            accept_button.click()
            logger.info("Clicked 'I Accept'")
            await asyncio.sleep(2)
        except Exception as e:
            logger.info(f"No consent popup or error: {str(e)}")
        
        # Click "Table View"
        try:
            table_view_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Table View')]"))
            )
            table_view_button.click()
            logger.info("Switched to 'Table View'")
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Could not click 'Table View': {str(e)}")
        
        # Determine total pages
        self.total_pages = await self.get_total_pages()
        logger.info(f"Detected {self.total_pages} total pages")
    
    async def get_total_pages(self):
        """Get the total number of pages to scrape"""
        pagination_buttons = self.driver.find_elements(By.XPATH, "//button[@data-testid='pagination-page-number']")
        if not pagination_buttons:
            logger.info("No pagination buttons found. Processing single page.")
            return 1
        else:
            last_label = pagination_buttons[-1].get_attribute('aria-label')
            return int(last_label.replace("Page ", ""))
    
    def get_field_value(self, parent_element, field_name):
        """Enhanced function to extract field value using multiple methods for robustness"""
        try:
            value = ""
            
            # Method 1: Direct XPath with exact matching
            xpath = f".//div[contains(@class, 'pn-label-value')]/b[text()='{field_name}:']/following-sibling::div"
            elements = parent_element.find_elements(By.XPATH, xpath)
            
            # Method 2: More flexible XPath with contains
            if not elements or not elements[0].text.strip():
                xpath = f".//div[contains(@class, 'pn-label-value')]/b[contains(text(), '{field_name}')]/following-sibling::div"
                elements = parent_element.find_elements(By.XPATH, xpath)
            
            # Method 3: Try a different HTML structure variation
            if not elements or not elements[0].text.strip():
                xpath = f".//*[contains(text(), '{field_name}')]/parent::*/following-sibling::div"
                elements = parent_element.find_elements(By.XPATH, xpath)
            
            # Method 4: Look for a label and its adjacent element
            if not elements or not elements[0].text.strip():
                xpath = f".//*[contains(text(), '{field_name}')]/following-sibling::*"
                elements = parent_element.find_elements(By.XPATH, xpath)
            
            # Method 5: Try to find by regex matching in the text
            if not elements or not elements[0].text.strip():
                all_divs = parent_element.find_elements(By.TAG_NAME, "div")
                for div in all_divs:
                    div_text = div.text.strip()
                    match = re.search(f"{field_name}[:\\s]+(.*?)(?:\\n|$)", div_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        return value
            
            # Extract and sanitize the value from elements if found
            if elements and elements[0].text.strip():
                value = elements[0].text.strip()
                
                # Special case for Zip Code: make sure we only get the digits
                if field_name == 'Zip Code' and value:
                    # If it contains digits, extract just the 5-digit ZIP
                    zip_match = re.search(r'(\d{5}(?:-\d{4})?)', value)
                    if zip_match:
                        value = zip_match.group(1).split('-')[0]  # Get just the 5-digit part if it's a ZIP+4
            
            # Log successful extraction
            if value:
                logger.info(f"Successfully extracted {field_name}: {value}")
                return value
            
            # If we get here, we couldn't find the value
            logger.warning(f"Could not extract value for {field_name}")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting '{field_name}': {str(e)}")
            logger.error(traceback.format_exc())
            return ""
    
    async def navigate_to_page(self, page_num):
        """Navigate to a specific page"""
        if page_num > 1:
            try:
                page_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//button[@data-testid='pagination-page-number' and @aria-label='Page {page_num}']"))
                )
                page_btn.click()
                logger.info(f"Navigated to page {page_num}")
                await asyncio.sleep(3)
                return True
            except Exception as e:
                logger.error(f"Could not navigate to page {page_num}: {str(e)}")
                return False
        return True
    
    async def get_page_elements(self):
        """Get table rows and eye buttons on the current page"""
        try:
            table_rows = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.usa-table tbody tr"))
            )
            eye_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.view-notice")
            return table_rows, eye_buttons
        except Exception as e:
            logger.error(f"Error getting page elements: {str(e)}")
            return [], []
    
    async def process_modal(self, index, row, btn):
        """Process a single modal dialog with notice details"""
        async with self.semaphore:  # Limit concurrent modal processing
            row_data = {}
            
            # Extract basic table data first
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 6:
                    row_data['DA_Number'] = cells[0].text.strip()
                    row_data['Project_Name'] = cells[1].text.strip()
                    row_data['State'] = cells[2].text.strip()
                    row_data['County'] = cells[3].text.strip() 
                    row_data['Public_Notice_Date'] = cells[4].text.strip()
                    row_data['Comment_Period_End'] = cells[5].text.strip()
                    logger.info(f"Table data: DA={row_data['DA_Number']}, Project={row_data['Project_Name']}")
            except Exception as e:
                logger.error(f"Error extracting table data: {str(e)}")
            
            # Click the eye button
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                await asyncio.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", btn)
                logger.info(f"Clicked 'eye' button for item {index+1}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Could not click eye button: {str(e)}")
                return None
            
            # Extract modal data
            try:
                # Wait for modal to appear
                modal = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".usa-modal"))
                )
                info_container = modal.find_element(By.CSS_SELECTOR, ".pn-info-container")
                
                # Extract data from flex containers
                flex_containers = info_container.find_elements(By.CSS_SELECTOR, ".pn-flex-container")
                for container in flex_containers:
                    fields_to_extract = [
                        ('DA Number', 'DA_Number'),
                        ('Project Name', 'Project_Name'),
                        ('Action Type', 'Action_Type'),
                        ('Date of Public Notice', 'Public_Notice_Date'),
                        ('Comment Period Ends', 'Comment_Period_End'),
                        ('Keyword(s)', 'Keywords')
                    ]
                    
                    for display_name, field_name in fields_to_extract:
                        value = self.get_field_value(container, display_name)
                        if value:
                            row_data[field_name] = value
                
                # Get Description
                description = self.get_field_value(info_container, 'Description')
                if description:
                    row_data['Description'] = description
                
                # Find Applicant section
                try:
                    applicant_section = info_container.find_element(By.XPATH, ".//section[.//h3[text()='Applicant']]")
                    applicant_name = self.get_field_value(applicant_section, 'Applicant Name')
                    applicant_company = self.get_field_value(applicant_section, 'Applicant Company')
                    
                    if applicant_name:
                        row_data['Applicant_Name'] = applicant_name
                    
                    if applicant_company:
                        row_data['Applicant_Company'] = applicant_company
                except Exception as e:
                    logger.error(f"Error extracting applicant data: {str(e)}")
                
                # ENHANCED: Find Location section with multiple methods for zip code extraction
                try:
                    # First try to find the Location section by h3 text
                    location_sections = info_container.find_elements(By.XPATH, ".//section[.//h3[text()='Location']]")
                    
                    # If that fails, try a more flexible search
                    if not location_sections:
                        location_sections = info_container.find_elements(By.XPATH, ".//section[contains(.//text(), 'Location')]")
                    
                    # If still no location section, search the entire info container
                    location_section = location_sections[0] if location_sections else info_container
                    
                    # Try standard field extraction first
                    location_fields = [
                        ('District', 'District'),
                        ('State', 'State'),
                        ('County', 'County'),
                        ('Zip Code', 'Zip_Code'),
                        ('Latitude', 'Latitude'),
                        ('Longitude', 'Longitude')
                    ]
                    
                    for display_name, field_name in location_fields:
                        value = self.get_field_value(location_section, display_name)
                        if value:
                            row_data[field_name] = value
                            logger.info(f"Found {field_name}: {value}")
                    
                    # ENHANCED: Multiple fallback methods for zip code extraction
                    if 'Zip_Code' not in row_data or not row_data['Zip_Code']:
                        logger.info("Zip code not found with standard method, trying fallbacks...")
                        
                        # Method 1: Look for any 5-digit number in the location section
                        all_divs = location_section.find_elements(By.TAG_NAME, "div")
                        for div in all_divs:
                            text = div.text.strip()
                            # Check if the text is a 5-digit number (US zip code format)
                            if text.isdigit() and len(text) == 5:
                                row_data['Zip_Code'] = text
                                logger.info(f"Found Zip_Code (fallback method 1): {text}")
                                break
                        
                        # Method 2: Look for patterns like "ZIP: 12345" or "Zip Code: 12345"
                        if 'Zip_Code' not in row_data or not row_data['Zip_Code']:
                            full_text = location_section.text
                            zip_matches = re.findall(r'(?:ZIP|Zip|zip)(?:\s*Code)?(?:\s*:|:?\s+)(\d{5}(?:-\d{4})?)', full_text)
                            if zip_matches:
                                # Take just the 5-digit part if it's a ZIP+4
                                zip_code = zip_matches[0].split('-')[0] if '-' in zip_matches[0] else zip_matches[0]
                                row_data['Zip_Code'] = zip_code
                                logger.info(f"Found Zip_Code (fallback method 2): {zip_code}")
                        
                        # Method 3: Search the entire modal text for zip code patterns
                        if 'Zip_Code' not in row_data or not row_data['Zip_Code']:
                            modal_text = modal.text
                            # Look for common state abbreviations followed by a 5-digit number
                            for state in ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                                         'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                                         'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                                         'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                                         'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']:
                                pattern = fr'{state}\s+(\d{{5}}(?:-\d{{4}})?)'
                                matches = re.findall(pattern, modal_text)
                                if matches:
                                    zip_code = matches[0].split('-')[0] if '-' in matches[0] else matches[0]
                                    row_data['Zip_Code'] = zip_code
                                    logger.info(f"Found Zip_Code (fallback method 3): {zip_code}")
                                    break
                
                except Exception as e:
                    logger.error(f"Error extracting location data: {str(e)}")
                    logger.error(traceback.format_exc())
                
                # Extract PDF and ContentDM URLs - Integrated version
              # Inside the process_modal method, replace the URL extraction section with this enhanced version:

# Extract PDF, ContentDM, and other website URLs
                try:
                    # First, try to find the Files section by h3 text
                    files_sections = info_container.find_elements(By.XPATH, ".//section[.//h3[text()='Files']]")
                    
                    # If that fails, try to find any section with links
                    if not files_sections:
                        files_sections = info_container.find_elements(By.XPATH, ".//section[.//a]")
                    
                    # If still no luck, look for divs with links
                    if not files_sections:
                        files_sections = [info_container]  # Search the entire info container
                    
                    pdf_urls = []
                    contentdm_urls = []
                    other_website_urls = []
                    all_links = []
                    
                    # Process each potential files section
                    for section in files_sections:
                        section_links = section.find_elements(By.TAG_NAME, "a")
                        all_links.extend(section_links)
                        
                        for link in section_links:
                            url = link.get_attribute("href")
                            if not url:
                                continue
                                
                            # Log URLs for debugging
                            logger.info(f"Found URL: {url[:100]}..." if len(url) > 100 else f"Found URL: {url}")
                            
                            # Check for PDF links
                            if url.lower().endswith('.pdf') or '.pdf' in url.lower() or '/pdf/' in url.lower() or 'application/pdf' in url.lower():
                                pdf_urls.append(url)
                                logger.info("Classified as PDF URL")
                                
                            # Check for ContentDM links - multiple patterns
                            elif any(pattern in url.lower() for pattern in [
                                'contentdm.oclc.org', 
                                'usace.contentdm',
                                'cdm.oclc.org',
                                'getfile/collection',
                                '/collection/p16021coll'
                            ]):
                                contentdm_urls.append(url)
                                logger.info("Classified as ContentDM URL")
                            
                            # Add other website URLs (like the one you shared)
                            elif url.startswith('http') and 'usace.army.mil' in url.lower():
                                other_website_urls.append(url)
                                logger.info("Classified as Other USACE Website URL")
                            
                            # Catch any remaining URLs
                            elif url.startswith('http'):
                                other_website_urls.append(url)
                                logger.info("Classified as Other Website URL")
                    
                    # Store the primary notice URL (first link of any type)
                    if all_links:
                        primary_url = all_links[0].get_attribute("href")
                        if primary_url:
                            row_data['Notice_URL'] = primary_url
                            logger.info(f"Primary Notice URL: {primary_url[:100]}..." if len(primary_url) > 100 else f"Primary Notice URL: {primary_url}")
                    
                    # Store PDF URLs
                    if pdf_urls:
                        row_data['PDF_URLs'] = '; '.join(pdf_urls)
                        logger.info(f"Found {len(pdf_urls)} PDF URL(s)")
                    
                    # Store ContentDM URLs
                    if contentdm_urls:
                        row_data['ContentDM_URLs'] = '; '.join(contentdm_urls)
                        logger.info(f"Found {len(contentdm_urls)} ContentDM URL(s)")
                    
                    # Store Other Website URLs (new)
                    if other_website_urls:
                        row_data['Other_Website_URLs'] = '; '.join(other_website_urls)
                        logger.info(f"Found {len(other_website_urls)} Other Website URL(s)")
                    
                    # Log a warning if no links were found
                    if not all_links:
                        logger.warning("No links found in any section")

                except Exception as e:
                    logger.error(f"Error extracting URLs: {str(e)}")
                    # Add traceback for better debugging
                    logger.error(traceback.format_exc())                
                # Close the modal
                try:
                    close_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.usa-modal__close"))
                    )
                    self.driver.execute_script("arguments[0].click();", close_button)
                except Exception as e:
                    logger.error(f"Error closing modal with button: {str(e)}")
                    try:
                        # Fallback: Press ESC key
                        actions = ActionChains(self.driver)
                        actions.send_keys(Keys.ESCAPE).perform()
                    except:
                        logger.error("Could not close modal")
                
                await asyncio.sleep(1)
                return row_data
                
            except Exception as e:
                logger.error(f"Error processing modal: {str(e)}")
                # Try to close modal if it's still open
                try:
                    actions = ActionChains(self.driver)
                    actions.send_keys(Keys.ESCAPE).perform()
                except:
                    pass
                await asyncio.sleep(1)
                return None
    
    async def process_page(self, page_num):
        """Process all notices on a page"""
        logger.info(f"Processing Page {page_num}/{self.total_pages}")
        
        # Navigate to the page
        if not await self.navigate_to_page(page_num):
            return []
        
        # Get page elements
        table_rows, eye_buttons = await self.get_page_elements()
        logger.info(f"Found {len(eye_buttons)} notices on page {page_num}")
        
        # Create tasks for processing each row
        page_data = []
        for index, (row, btn) in enumerate(zip(table_rows, eye_buttons)):
            try:
                row_data = await self.process_modal(index, row, btn)
                if row_data:
                    page_data.append(row_data)
                    logger.info(f"Successfully processed notice {index+1} on page {page_num}")
            except Exception as e:
                logger.error(f"Error processing notice {index+1} on page {page_num}: {str(e)}")
        
        # Save intermediate results
        if page_data:
            temp_df = pd.DataFrame(page_data)
            temp_df.to_csv(f"usace_notices_page_{page_num}.csv", index=False)
            logger.info(f"Saved intermediate data for page {page_num} ({len(page_data)} records)")
        
        return page_data
    
    async def run(self, pages_to_scrape=0):
        """Main method to run the scraper"""
        await self.initialize()
        
        # Determine number of pages to scrape
        if pages_to_scrape <= 0 or pages_to_scrape > self.total_pages:
            pages_to_scrape = self.total_pages
        
        all_data = []
        for page_num in range(1, pages_to_scrape + 1):
            page_data = await self.process_page(page_num)
            all_data.extend(page_data)
            logger.info(f"Completed page {page_num}/{pages_to_scrape}. Total records so far: {len(all_data)}")
        
        # Save final results
        if all_data:
            df = pd.DataFrame(all_data)
            
            # Reorder columns to have Notice_URL first, then organize other columns logically
            desired_column_order = [
                'Notice_URL',               # Primary notice URL first
                'DA_Number', 'Project_Name', 'Action_Type', 'Description', 'Keywords',  # Basic info
                'Public_Notice_Date', 'Comment_Period_End',  # Dates
                'Applicant_Name', 'Applicant_Company',  # Applicant info
                'District', 'State', 'County', 'Zip_Code', 'Latitude', 'Longitude',  # Location info
                'PDF_URLs', 'ContentDM_URLs'  # Additional URLs last
            ]
            
            # Ensure all columns exist (even if empty) and reorder
            for col in desired_column_order:
                if col not in df.columns:
                    df[col] = ""
            
            # Reorder columns while keeping any extra columns that might be present
            existing_cols = set(df.columns)
            final_cols = desired_column_order + [col for col in df.columns if col not in desired_column_order]
            df = df[final_cols]
            
            # Save the results
            output_file = "usace_public_notices_complete.csv"
            df.to_csv(output_file, index=False)
            logger.info(f"Final data saved to {output_file}. Total records: {len(df)}")
            logger.info(f"DataFrame columns: {df.columns.tolist()}")
            
            # Print URL capture statistics
            pdf_count = df['PDF_URLs'].apply(lambda x: 0 if pd.isna(x) or x == "" else len(x.split("; ")))
            contentdm_count = df['ContentDM_URLs'].apply(lambda x: 0 if pd.isna(x) or x == "" else len(x.split("; ")))
            logger.info(f"URL Statistics:")
            logger.info(f"  - Total PDF URLs: {pdf_count.sum()}")
            logger.info(f"  - Total ContentDM URLs: {contentdm_count.sum()}")
            logger.info(f"  - Records with PDF URLs: {(pdf_count > 0).sum()} ({(pdf_count > 0).sum()/len(df)*100:.1f}%)")
            logger.info(f"  - Records with ContentDM URLs: {(contentdm_count > 0).sum()} ({(contentdm_count > 0).sum()/len(df)*100:.1f}%)")
            
            # Print zip code statistics
            zip_count = df['Zip_Code'].apply(lambda x: 0 if pd.isna(x) or x == "" else 1)
            logger.info(f"Zip Code Statistics:")
            logger.info(f"  - Records with Zip Codes: {zip_count.sum()} ({zip_count.sum()/len(df)*100:.1f}%)")
            
            return df
        else:
            logger.warning("No data was scraped!")
            return pd.DataFrame()

# Main function to run the script directly
async def main():
    """Run the scraper with command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='USACE Public Notices Scraper')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--pages', type=int, default=0, help='Number of pages to scrape (0 for all)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Initialize and run the scraper
    logger.info("Starting USACE Public Notices Scraper")
    scraper = USACENoticesScraper(headless=args.headless)
    
    try:
        result_df = await scraper.run(pages_to_scrape=args.pages)
        logger.info(f"Scraper completed successfully with {len(result_df)} records")
    finally:
        # Always clean up WebDriver
        scraper.driver.quit()
    
    return result_df

# For Jupyter Notebook use
async def run_notebook(headless=False, pages=2, debug=True):
    """Run the scraper from a Jupyter notebook"""
    # Configure logging level
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Initialize and run the scraper
    logger.info("Starting USACE Public Notices Scraper")
    scraper = USACENoticesScraper(headless=headless)
    
    try:
        result_df = await scraper.run(pages_to_scrape=pages)
        logger.info(f"Scraper completed successfully with {len(result_df)} records")
    finally:
        # Always clean up WebDriver
        scraper.driver.quit()
    
    return result_df



if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="USACE Public Notices Scraper"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run Chrome in headless mode"
    )
    parser.add_argument(
        "--pages", type=int, default=0,
        help="Number of pages to scrape (0 = all pages)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable DEBUG‐level logging"
    )
    args = parser.parse_args()

    # set logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # run the main coroutine
    asyncio.run(main())


# # For command line execution    
# if __name__ == "__main__":
#     loop = asyncio.get_event_loop()
#     result_df = loop.run_until_complete(main())
#     logger.info(f"Scraper finished with {len(result_df)} records")



# try:
#     # Detect if running in a Jupyter Notebook
#     if 'ipykernel' in sys.modules:
#         result_df = loop.run_until_complete(run_notebook(headless=True, pages=2, debug=True))
#         display(result_df)  # Display the DataFrame in the notebook
#     else:
#         result_df = loop.run_until_complete(main())
#         logger.info(f"Scraper finished with {len(result_df)} records")
# finally:
#     loop.close()
