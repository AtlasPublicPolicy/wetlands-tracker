import pandas as pd
import feedparser
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime



def get_web_published_date(soup):
    """
    Get the public notice published date
    """
    
    if soup.find("meta", {"itemprop":"datePublished"}) is None:
        published_date = None
    else:
        try:
            published_date_origin = soup.find("meta", {"itemprop":"datePublished"}).get("content")
            parsed_date = datetime.strptime(published_date_origin.split('T')[0], '%Y-%m-%d')
            published_date = parsed_date.strftime("%m/%d/%Y")
        except Exception as e:
            published_date = "ERROR: " + str(e)
    return published_date
            
    
    
    
def get_web_expire_date(soup):
    """
    Get the public notice expiration date
    """
    
    if soup.find("div", "expire") is None:
        web_expire_date = None
    else:
        try:
            web_expire_date = re.search(r'(?<=:\s).+', soup.find_all("div", "expire")[0].get_text()).group()
        except Exception as e:
            web_expire_date  = "ERROR: " + str(e)
    return web_expire_date



def get_web_pdf_url(soup, web_url):
    """
    Get the pdf url for the public notice pdf
    """
    
    try:
        pdf_end = soup.findAll('a', {"class": "link"})[2]['href']
    except:
        try:
            web_href = soup.find("div", {"itemprop":"articleBody"}).find_all("a", href=True)
            pdf_end = [a.get("href") for a in web_href if "pdf" in a.get("href").lower()][0]
        except Exception as e:
            pdf_end = "ERROR: " + str(e)
    finally:
        if any(word in pdf_end for word in ["ERROR", "http"]):
            pdf_url = pdf_end
        else:
            pdf_url = web_url[:30]  + pdf_end
    return pdf_url

    
    
    
def get_web_text(soup):
    """
    Get all web texts
    """
    
    try:
        body = soup.find_all("div", {"itemprop": "articleBody"})[0]
        if body.find("p") is None:
            web_text = body.get_text()
        else:
            web_text = body.get_text().replace(u'\xa0', u'').replace("\n", "")
    except:
        web_text = "Error"
    finally:
        return web_text

    
    
    
def get_web_applicant(web_text, district):
    """
    Get all info in "NAME OF APPLICANT"
    """
    
    if district == "mvn":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', web_text)) != 0:
            
            # Applicant full info
            try:
                web_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]\s?:?(.+)(?=L\s?[Oo]\s?[Cc]\s?[Aa]\s?[Tt]\s?[Ii]\s?[Oo]\s?[Nn])', web_text).group(1).strip()
                web_applicant_contents = re.sub(r'\s{2,}', "", web_applicant_contents)

            except:
                web_applicant_contents = "ERROR"
        else:
            web_applicant_contents = "unknown"
    
    
    
    if district == "sam":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', web_text)) != 0:
            
            # Applicant full info
            try:
                web_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt].+(?=(W\s?A\s?T\s?E\s?R\s?W\s?A\s?Y|L\s?O\s?C\s?A\s?T\s?I\s?O\s?N))', web_text).group().strip()
                web_applicant_contents = re.sub(r'\s{2,}', "", web_applicant_contents)
            except:
                web_applicant_contents = "ERROR"
        else:
            web_applicant_contents = "unknown"
            
            
            
    if district == "saj":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', web_text)) != 0:
                
            # Applicant full info
            try:
                web_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt].+(?=(W\s?A\s?T\s?E\s?R\s?W\s?A\s?Y|L\s?O\s?C\s?A\s?T\s?I\s?O\s?N))', web_text).group().strip()
                web_applicant_contents = re.sub(r'\s{2,}', "", web_applicant_contents)

            except:
                web_applicant_contents = "ERROR"
        else:
            web_applicant_contents = "unknown"
            
            
        
    if district == "swg":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', web_text)) != 0:
            
            # Applicant full info
            try:
                web_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt].+(?=(L\s?O\s?C\s?A\s?T\s?I\s?O\s?N|P\s?R\s?O\s?J\s?E\s?C\s?T))', web_text).group().strip()
                web_applicant_contents = re.sub(r'\s{2,}', "", web_applicant_contents)
            except:
                web_applicant_contents = "ERROR"
        else:
            web_applicant_contents = "unknown"
        
    return web_applicant_contents




def get_web_location(web_text, district):
    """
    Get all info in "LOCATION OF WORK"
    """
    
    if re.findall(r'L\s?[Oo]\s?[Cc]\s?[Aa]\s?[Tt]\s?[Ii]\s?[Oo]\s?[Nn]', web_text) != 0:
        
        if district == "mvn":
            try:
                web_location = re.search(r'L\s?[Oo]\s?[Cc]\s?[Aa]\s?[Tt]\s?[Ii]\s?[Oo]\s?[Nn]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk]\s?:?(.*)(?=C\s?[Hh]\s?[Aa]\s?[Rr]\s?[Aa]\s?[Cc]\s?[Tt]\s?[Ee]\s?[Rr]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk])', web_text).group(1).replace("  ", " ").strip()
            except:
                web_location = "ERROR"
                
        if district  == "sam":
            try:
                web_location = re.search(r'(L\s?O\s?C\s?A\s?T\s?I\s?O\s?N|W\s?A\s?T\s?E\s?R\s?W\s?A\s?Y)\s?:?(.*)(?=(P\s?R\s?O\s?J\s?E\s?C\s?T|P\s?R\s?O\s?P\s?O\s?S\s?E\s?D|A\s?P\s?P\s?L\s?I\s?C\s?A\s?N\s?T|W\s?O\s?R\s?K))', web_text).group(2).replace("  ", " ").strip()
            except:
                web_location = "ERROR"
                
        if district == "saj":
            try:
                web_location = re.search(r'L\s?O\s?C\s?A\s?T\s?I\s?O\s?N\s?:?(.*)(?=(D\s?i\s?r\s?e\s?c\s?t\s?i\s?o\s?n\s?s|A\s?P\s?P\s?R\s?O\s?X\s?I\s?M\s?A\s?T\s?E|P\s?R\s?O\s?J\s?E\s?C\s?T))', web_text).group(1).replace("  ", " ").strip()
            except:
                web_location = "ERROR"
                
        if district == "swg":
            try:
                web_location = re.search(r'L\s?O\s?C\s?A\s?T\s?I\s?O\s?N\s?:?(.*)(?=(L\s?A\s?T\s?I\s?T\s?U\s?D\s?E|A\s?G\s?E\s?N\s?D\s?A|P\s?R\s?O\s?J\s?E\s?C\s?T|A\s?V\s?O\s?I\s?D\s?A\s?N\s?C\s?E))', web_text).group(1).replace("  ", "").strip()
            except:
                web_location = "ERROR"
                
    else:
        web_location = "unknown"
        
    return web_location




def get_web_character(web_text, district):
    """
    Get all info in "CHRACATER OF WORK"
    """
    
    if district == "mvn":
        if len(re.findall(r'C\s?[Hh]\s?[Aa]\s?[Rr]\s?[Aa]\s?[Cc]\s?[Tt]\s?[Ee]\s?[Rr]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk]', web_text)) != 0:
            try:
                web_character = re.search(r'C\s?[Hh]\s?[Aa]\s?[Rr]\s?[Aa]\s?[Cc]\s?[Tt]\s?[Ee]\s?[Rr]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk](.*?)(?=(M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N|T\s?h\s?e\s{0,2}c\s?o\s?m\s?m\s?e\s?n\s?t\s{0,2}p\s?e\s?r\s?i\s?o\s?d|$))', web_text).group(1).strip()
                web_character = re.sub(r'\s{2,}', "", web_character)
            except:
                web_character = "ERROR"
        else:
            web_character = "unknown"
            
    if district in ("sam", "saj"):
        if len(re.findall(r'W\s?O\s?R\s?K', web_text)) != 0:
            try:
                web_character = re.search(
                r'(P\s?R\s?O\s?P\s?O\s?S\s?E\s?D\s{0,2}W\s?O\s?R\s?K|W\s?O\s?R\s?K\s{0,2}D\s?E\s?S\s?C\s?R\s?I\s?P\s?T\s?I\s?O\s?N|W\s?O\s?R\s?K)\s?:?(.*?)(?=(A\s?V\s?O\s?I\s?D\s?A\s?N\s?C\s?E|C\s?O\s?A\s?S\s?T\s?A\s?L|T\s?h\s?e\s{0,2}a\s?p\s?p\s?l\s?i\s?c\s?a\s?n\s?t\s{0,2}h\s?a\s?s\s{0,2}a\s?p\s?p\s?l\s?i\s?e\s?d|$))',
                web_text).group(2).strip()
                web_character = re.sub(r'\s{2,}', "", web_character)
            except:
                web_character = "ERROR"
        else:
            web_character = "unknown"
            
    if district == "swg":
        if len(re.findall(r'P\s?R\s?O\s?J\s?E\s?C\s?T\s{0,2}D\s?E\s?S\s?C\s?R\s?I\s?P\s?T\s?I\s?O\s?N', web_text)) != 0:
            try:
                web_character = re.search(r'P\s?R\s?O\s?J\s?E\s?C\s?T\s{0,2}D\s?E\s?S\s?C\s?R\s?I\s?P\s?T\s?I\s?O\s?N(.*?)(?=([A-Z\s]+:|$))', web_text).group(1).strip()
                web_character = re.sub(r'\s{2,}', "", web_character)
            except:
                web_character = "ERROR"
        else:
            web_character = "unknown"
                        
    return web_character       




def get_web_mitigation(web_text, district):
    """
    Get all info in "MITIGATION"
    """
    
    if district == "mvn":
        if len(re.findall(r'M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N', web_text)) != 0:
            try:
                web_mitigation = re.search(r'M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N(.*?)(?=T\s?h\s?e\s{0,2}c\s?o\s?m\s?m\s?e\s?n\s?t\s{0,2}p\s?e\s?r\s?i\s?o\s?d|$)', web_text).group(1).strip()
                web_mitigation = re.sub(r'\s{2,}', "", web_mitigation)
            except:
                web_mitigation = "ERROR"
        else:
            web_mitigation = "unknown"
    
    if district in ["sam", "saj", "swg"]:
        if len(re.findall(r'(A\s?V\s?O\s?I\s?D\s?A\s?N\s?C\s?E\s?(&|A\s?N\s?D)\s?M\s?I\s?N\s?I\s?M\s?I\s?Z\s?A\s?T\s?I\s?O\s?N|C?\s?O?\s?M?\s?P?\s?E?\s?N?\s?S?\s?A?\s?T?\s?O?\s?R?\s?Y?\s{0,2}M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N|$)', web_text)) != 0:
                # web_mitigation = re.search(r'(AVOIDANCE|COMPENSATORY|MITIGATION).*?(?=WATER|The applicant will apply|The applicant has applied|CULTURAL)', web_text).group().strip()
            try:
                web_avio_mini = re.search(r'M\s?I\s?N\s?I\s?M\s?I\s?Z\s?A\s?T\s?I\s?O\s?N\s{0,2}I?\s?N?\s?F?\s?O?\s?R?\s?M?\s?A?\s?T?\s?I?\s?O?\s?N?.+?(?=[A-Z\s]+:)', web_text).group().strip()
            except:
                web_avio_mini = "ERROR: AVOIDANCE AND MINIMIZATION"
            try:
                web_comp_miti = re.search(r'M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N.+?(?=[A-Z\s]+:)', 
                                     web_text).group().strip()
            except:
                web_comp_miti = "ERROR: COMPENSATORY MITIGATION"
            if "ERROR" not in web_avio_mini and "ERROR" not in web_comp_miti:
                web_mitigation = web_avio_mini + " " + web_comp_miti
                web_mitigation = re.sub(r'\s{2,}', "", web_mitigation)
            else:
                web_mitigation = "ERROR"
        else:
            web_mitigation = "unknown"
            
    return web_mitigation
    




def web_extraction(web_url, update):
    """
    This function consists of all the components above to extract fields from the public notice website.
    
    update can take two values: 1 and 0; 
    1 means running this function for the updating purpose; 
    0 means running this function for the first time to scrape all public notices
    """
    
    district = re.search(r'www\.(.*?)\.usace', web_url).group(1)
    
    req = requests.get(web_url)
    content = req.text
    soup = BeautifulSoup(content, 'html.parser')
    
    # Get published date, expiration date, and PDF url from webpages only when updating from rss feed
    if update == 1:
        web_published_date = get_web_published_date(soup)
        web_expire_date = get_web_expire_date(soup)
        pdf_url = get_web_pdf_url(soup, web_url)

    # Extract webpage body
    web_text = get_web_text(soup)

    if web_text != "Error":

        web_applicant = get_web_applicant(web_text, district)
        web_location = get_web_location(web_text, district)
        web_character = get_web_character(web_text, district)
        web_mitigation = get_web_mitigation(web_text, district)
        
    else:
        # Assign "Error" to all fields inside of website body.
        web_applicant = "ERROR"
        web_location = "ERROR"
        web_character = "ERROR"
        web_mitigation = "ERROR"
    
    if update == 1:
        return {"datePublished":web_published_date, 
                "dateExpiry":web_expire_date, 
                "PdfUrl":pdf_url,
                "web_applicant":web_applicant, 
                "web_location":web_location, 
                "web_character":web_character, 
                "web_mitigation":web_mitigation,
                "web_text": web_text}
    else:
        return {"web_applicant":web_applicant, 
                "web_location":web_location, 
                "web_character":web_character, 
                "web_mitigation":web_mitigation,
                "web_text": web_text}





def update_weblist_from_rss(district, n_days):
    """
    Scrape the RSS feeder for new notice webpage links and titles

    dist_rss: District for which to scrape RSS feed

    n_days = No. of days in the past (from current day to count)

    """

    dist_rss = {"Galveston": "https://www.swg.usace.army.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=4&Site=437&isdashboardselected=0&max=500",
                "New Orleans":"https://www.mvn.usace.army.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=4&Site=417&isdashboardselected=0&max=500",
                "Jacksonville":"https://www.saj.usace.army.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=4&Site=435&isdashboardselected=0&max=500",
                "Mobile":"https://www.sam.usace.army.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=4&Site=460&isdashboardselected=0&max=500"}
    
    if district != "all":
        # Parse the RSS feed to a dataframe
        rss_parsed = feedparser.parse(dist_rss[district])
        rss_df = pd.DataFrame(rss_parsed.entries)
        
    else:
        rss_df_list = [pd.DataFrame(feedparser.parse(dist_rss_url).entries) for dist_rss_url in list(dist_rss.values())]
        rss_df = pd.concat(rss_df_list, ignore_index=True)

    # Clean the df to include information needed only
    rss_df = rss_df[["title", "link", "published"]].rename(
        columns = {"title": "web_title", "link": "usaceWebUrl"}, 
        copy = False)

    # Filter rss to the most recent month:
    rss_df['published'] = pd.to_datetime(rss_df['published'], format = "%a, %d %b %Y %H:%M:%S %Z")
    last_n_days = pd.Timestamp.now(tz = rss_df['published'].dt.tz) - pd.DateOffset(days=n_days)
    rss_df = rss_df[rss_df["published"] >= last_n_days]

    # change the formatting of date time so we can include those later than the last date in redivis
    # rss_df['published'] = rss_df['published'].dt.strftime("%Y-%m-%d")
    rss_df = rss_df.drop(["published"], axis = 1)
    
    return rss_df
    

