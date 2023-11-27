import pandas as pd
import numpy as np
import feedparser
from bs4 import BeautifulSoup
import requests
import PyPDF2 as pdf
import re




def get_item(soup, item_i):
    """
    Extract each items in each page of district website
    """
    
    # Get the info in the box for each notice
    item = soup.find_all("div", class_="desc")[item_i]
    web_url = item.find("a", class_="title").get("href")
    web_title = item.find("a", class_="title").get_text()
    publish_date = item.time.get("datetime")
    try:
        expire_date = item.find("p", class_="standout").get_text().replace("Expiration date: ", "")
    except Exception as e:
        expire_date = None
        #print(page_p, item_i, str(e))
        
    # Get the notice PDF url
    try:
        # directly pull from each box on the main website
        pdf_end = item.find("div", class_="attachment").a.get("href")
    except:
        try:
            # for those do not have pdf url in the main website, pull from each webpage of notice
            req = requests.get(web_url)
            content = req.text
            soup = BeautifulSoup(content, 'html.parser')
            try:
                web_href = soup.find("div", {"itemprop":"articleBody"}).find_all("a", href=True)
                pdf_end = [a.get("href") for a in web_href if "pdf" in a.get("href").lower()][0]
            except:
                pdf_end = "ERROR: cannot pull pdf url"
        except:
            pdf_end = "ERROR: cannot read web url"
    finally:
        if any(word in pdf_end for word in ["ERROR", "http"]):
            pdf_url = pdf_end
        else:
            pdf_url = web_url[:30]  + pdf_end
        
    return [web_url, web_title, publish_date, expire_date, pdf_url]

    


def get_page(url, page_p):
    """
    Scrape the main public notice website by page
    """
    main_url = url + "?page=" + str(page_p)
    content = requests.get(main_url).text
    soup = BeautifulSoup(content, 'html.parser')
    item_num = len(soup.find_all("div", class_="desc"))
    
    # Scrape all the public notices item in one district website page
    web_singlepage_df = pd.DataFrame([get_item(soup, i) for i in range(0, item_num)], 
                                 columns = ["usaceWebUrl", "web_title", "datePublished", "dateExpiry", "PdfUrl"])
    return web_singlepage_df  

    

    
def get_weblist(district = "all"):
    """
    Scrape the list of public notice webpages for one district USACE website.
    """
    
    dist_website = {"Galveston": "https://www.swg.usace.army.mil/Media/Public-Notices/",
                "New Orleans":"https://www.mvn.usace.army.mil/Missions/Regulatory/Public-Notices/",
                "Jacksonville":"https://www.saj.usace.army.mil/Missions/Regulatory/Public-Notices/",
                "Mobile":"https://www.sam.usace.army.mil/Missions/Regulatory/Public-Notices/"}
    
    if district != "all":
        # Check how many pages there are in the website
        check_content = requests.get(dist_website[district]).text
        check_soup = BeautifulSoup(check_content, 'html.parser')
        page_num = int(check_soup.find_all("a", class_="page-link")[-1].string)

        # Get a list of public notice pages of all pages
        allpage_list = [get_page(dist_website[district], p) for p in range(1, page_num + 1)]

        # Convert the list to a dataframe
        web_df = pd.concat(allpage_list, axis = 0, ignore_index = True)
        
    else:
        allpage_alldist_list = []
        
        for dist_weblink in list(dist_website.values()):
            
            # Check how many pages there are in the website
            check_content = requests.get(dist_weblink).text
            check_soup = BeautifulSoup(check_content, 'html.parser')
            page_num = int(check_soup.find_all("a", class_="page-link")[-1].string)

            # Get a list of public notice pages of all pages
            allpage_list = [get_page(dist_weblink, p) for p in range(1, page_num + 1)]
            
            allpage_alldist_list += allpage_list

        # Convert the list to a dataframe
        web_df = pd.concat(allpage_alldist_list, axis = 0, ignore_index = True)

    return web_df