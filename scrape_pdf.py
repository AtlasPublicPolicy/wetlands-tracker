import pandas as pd
# import numpy as np
from bs4 import BeautifulSoup
import requests
import PyPDF2 as pdf
import io
import re
import nltk
import boto3
import time
import fitz
import pytesseract
from PIL import Image





def OCR(pdf_url, tesseract_path = "C:/Program Files/Tesseract-OCR/tesseract.exe"):
    """
    Convert scanned PDFs to selectable PDFs
    """
    
    # Specify the Tesseract executable path
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    # Download the PDF file
    pdf_content = requests.get(pdf_url).content
    
    # Open the PDF file from bytes
    pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

    pdf_text = ""
    for page_number in range(pdf_document.page_count):
        page = pdf_document.load_page(page_number)

        # Convert PDF page to an image
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Use Tesseract OCR to extract text from the image
        page_text = pytesseract.image_to_string(img)
        page_text = page_text.replace('\n', ' ').replace('\r', '')
        pdf_text += page_text

    pdf_document.close()

    return pdf_text




# Read pdf

def pdf_read(pdf_url, district):
    """
    Read pdf
    """
    
    try:
        # Download the PDF content as a bytes object
        pdf_bytes = requests.get(pdf_url).content

        # Create a PyPDF2 PdfFileReader object from the PDF content
        pdf_reader = pdf.PdfReader(io.BytesIO(pdf_bytes))

        # Extract text from all pages except appendix in the PDF file
        pdf_full = []
        for p in range(len(pdf_reader.pages)):
            pdf_p = pdf_reader.pages[p].extract_text().replace("\n", "")
            
            # Remove the footer for public notices from new_orleans District
            if district == "mvn" and p != 0:
                pdf_p = re.sub(r'-?' + str(p+1) + '-?', "", pdf_p)
            
            # Remove the header for public notices from Mobile District
            if district == "sam" and p != 0:
                try:
                    pdf_header = re.search(r'.*Page \d of \d', pdf_p).group()
                except:
                    try:
                        pdf_header = re.search(r'.*?\d{5}\s?-\s?[A-Z]{3}', pdf_p).group()
                    except:
                        pdf_header = "ERROR"
                if "ERROR" not in pdf_header:
                    pdf_p = pdf_p.replace(pdf_header, "")
            
            # Remove the footer for public notices from Galveston District
            if district == "swg" and p != 0:
                try:
                    pdf_header = re.search(r'.*?\s{5,}' + str(p+1), pdf_p).group()
                except:
                    try:
                        pdf_header = re.search(r'.*?#.*?[\d\s]{5,6}.*?\s{1,2}', pdf_p).group()
                    except:
                        pdf_header = "ERROR"
                if "ERROR" not in pdf_header:
                    pdf_p = pdf_p.replace(pdf_header, "")

            pdf_full.append(pdf_p)
            
            # Remove attachments(pictures) to speed up the reading process
            if district in ["mvn", "sam"]:
                break_signal = re.findall(r'(E\s?n\s?c\s?l\s?o?\s?s\s?u?\s?r?\s?e?|A\s?t\s?t\s?a\s?c\s?h\s?m\s?e\s?n\s?t|Y\s?o\s?u\s{0,2}a\s?r\s?e\s{0,2}i\s?n\s?v\s?i\s?t\s?e\s?d)', pdf_p)
                if len(break_signal) != 0:
                    break
            if district == "saj":
                break_signal = re.findall(r'R\s?E\s?Q\s?U\s?E\s?S\s?T\s?F\s?O\s?R\s?P\s?U\s?B\s?L\s?I\s?C\s?H\s?E\s?A\s?R\s?I\s?N\s?G', pdf_p)
                if len(break_signal) != 0:
                    break

        pdf_text = "".join(pdf_full)
        
    except:
        pdf_text = "ERROR"
        
    finally:
        return pdf_text
    
    
    
# Trim PDF text for Azure summarization

def trim_pdf(pdf_text, district):
    """
    Trim PDFs to resonable lengths for the cost management of Azure summarization
    """
    
    # Trim the letter heading of each PDFs which are identical
    try:
        trim_intro = re.search(r'(T\s?O\s?W\s?H\s?O\s?M\s?I\s?T\s?M\s?A\s?Y\s?C\s?O\s?N\s?C\s?E\s?R\s?N|P\s?U\s?R\s?P\s?O\s?S\s?E\s?O\s?F\s?P\s?U\s?B\s?L\s?I\s?C\s?N\s?O\s?T\s?I\s?C\s?E|I\s?n\s?t\s?e\s?r\s?e\s?s\s?t\s?e\s?d\s?p\s?a\s?r\s?t\s?i\s?e\s?s).*?(?=A\s?P\s?P\s?L\s?I\s?C\s?A\s?N\s?T|4\s?0\s?8\s?\))', pdf_text).group()
    except:
        trim_intro = ""
    
    if district == "mvn":
        # Trim everything after the "Corps of Engineers Permit Critria"
        try:
            trim_tail = re.search(r'C\s?o\s?r\s?p\s?s\s?o\s?f\s?E\s?n\s?g\s?i\s?n\s?e\s?e\s?r\s?s\s?P\s?e\s?r\s?m\s?i\s?t\s?C\s?r\s?i\s?t\s?e\s?r\s?i\s?a.*', pdf_text).group()
        except:
            trim_tail = ""
            
    if district == "sam":
        # Trim everyting between "COMMENTS" and "Environmental Protectioin Agency"
        try:
            trim_tail = re.search(r'C\s?O\s?M\s?M\s?E\s?N\s?T\s?S.*P\s?r\s?o\s?t\s?e\s?c\s?t\s?i\s?o\s?n\s{0,2}A\s?g\s?e\s?n\s?c\s?y', pdf_text).group()
        except:
            trim_tail = ""
            
    if district == "saj":
        # Trim everything after "IMPACT ON NATUREAL RESOURCES"
        try:
            trim_tail = re.search(r'I\s?M\s?P\s?A\s?C\s?T\s{0,2}O\s?N\s{0,2}N\s?A\s?T\s?U\s?R\s?A\s?L\s{0,2}R\s?E\s?S\s?O\s?U\s?R\s?C\s?E\s?S.*', pdf_text).group()
            # trim_tail = re.search(r'C\s?U\s?L\s?T\s?U\s?R\s?A\s?L\s{0,2}R\s?E\s?S\s?O\s?U\s?R\s?C\s?E\s?S.*', pdf_text).group()
        except:
            trim_tail = ""
            
        
    if district == "swg":
        # Trim everything between "PUBLIC INTEREST REVIEW FACTORS" and "COMMENT PERIOD"
        try:
            # trim_tail = re.search(r'P\s?U\s?B\s?L\s?I\s?C\s{0,2}I\s?N\s?T\s?E\s?R\s?E\s?S\s?T\s{0,2}R\s?E\s?V\s?I\s?E\s?W\s{0,2}F\s?A\s?C\s?T\s?O\s?R\s?S.*(?=C\s?O\s?M\s?M\s?E\s?N\s?T\s{0,2}P\s?E\s?R\s?I\s?O\s?D\s?:?)', pdf_text).group()
            trim_tail = re.search(r'C\s?U\s?R\s?R\s?E\s?N\s?T\s{0,2}S\s?I\s?T\s?E\s{0,2}C\s?O\s?N\s?D\s?I\s?T\s?I\s?O\s?N\s?S\s?:?.*(?=C\s?O\s?M\s?M\s?E\s?N\s?T\s{0,2}P\s?E\s?R\s?I\s?O\s?D\s?:?)', pdf_text).group()
        except:
            trim_tail = ""
    
    pdf_trimmed = pdf_text.replace(trim_intro, "").replace(trim_tail, "")
    pdf_trimmed = re.sub(r'\s{2,}', "", pdf_trimmed)
    
    # Trim texts when the characters exceed 10,000
    if len(pdf_trimmed) > 5000:
        pdf_trimmed = pdf_trimmed[:5000]
    
    return pdf_trimmed
    
    
    

# Seperate pdf texts into big chuncks:

def get_comment_window(pdf_text, district):
    """
    Get the comment window (days)
    """
    if "days" in pdf_text:
        try:
            if district == "mvn":
                comment_window = re.search(r'c\s?l\s?o\s?s\s?e\s?i?n?([\s\d]*)(?=d\s?a\s?y\s?s)', 
                                           pdf_text).group(1).strip().replace(" ", "")
            if district == "sam":
                comment_window = re.search(r'l\s?a\s?t\s?e\s?r\s?t\s?h\s?a\s?n([\s\d]*)(?=d\s?a\s?y\s?s)', 
                                           pdf_text).group(1).strip().replace(" ", "")
            if district == "saj":
                comment_window = re.search(r'w\s?i\s?t\s?h\s?i\s?n([\s\d]*)(?=d\s?a\s?y\s?s)', 
                                           pdf_text).group(1).strip().replace(" ", "")
            if district == "swg":
                comment_window = re.search(r'w\s?i\s?t\s?h\s?i\s?n([\s\d]*)(?=d\s?a\s?y\s?s)', 
                                           pdf_text).group(1).strip().replace(" ", "")
        except:
            comment_window = "ERROR"
    else:
        comment_window = "unknown"
        
    return comment_window




def get_pdf_app_num(pdf_text, district):
    """
    Get permit application # + district code + district Name
    """
    
    try:
        if district == "mvn":
            permit_application_number = re.search(r'(Application|[Ss][Uu][Bb][Jj][Ee][Cc][Tt])#?:?.*?([A-Z]{3}-?\d{4}-?\d{4,5}-?[A-Z]{2,3}).*?(WQC|PUBLICNOTICE|Interested|SPECIAL|New|\(Section)', pdf_text.replace(" ", "")).group(2).replace("PUBLICNOTICE", "").strip()
        if district == "sam":
            permit_application_number = re.search(r'(?<=NO\.).*(?=JOINT)', \
                                                  pdf_text).group().replace(" ", "")
        if district == "saj":
            permit_application_number = re.search(r'(?<=No\.).*?(?=T\s?O\s?W\s?H\s?O\s?M)', \
                                      pdf_text).group().replace(" ", "")
        if district == "swg":
            permit_application_number = re.search(r'(?<=No:).*?(?=Of)', \
                                      pdf_text).group().replace(" ", "")

    except:
        permit_application_number = "ERROR"
        
    finally:
        return permit_application_number

    
    

def get_pdf_manager(pdf_text, district):
    """
    Get manager name + phone + email
    """
    
    # MANAGER PHONE NUMBER ----------------------------------------------------------------------------------------

    if district == "mvn":
        # Typical formatting: "project_name" OR "zipcode" (xxx)-xxx-xxxx non-numeric characters
        try:
            manager_phone = re.search(r'[a-z\.|\d{4,5}](\(?\d{3}\)?-?\d{3}-?\d{4})[^\d]', # \(?\d{3}\)?-?\s{0,3}-?\d{3}\s?-?\s?\d{4}
                                      pdf_text.replace(" ", "")).group(1).strip()            
        except:
            manager_phone = "ERROR"
        
    if district == "sam":
        # Typical formatting: "concerning ..." (xxx)-xxx-xxxx non-numeric characters
        try:
            manager_phone = re.search(r'c\s?o\s?n\s?c\s?e\s?r\s?n\s?i\s?n\s?g.*?[a-z](\(?\d{3}\)?-?\d{3}-?\d{4})[^\d]',
                                  pdf_text.replace(" ", "")).group(1).strip()            
        except:
            manager_phone = "ERROR"
        
    if district == "saj":
        # Typical formatting: "phone" (xxx)-xxx-xxxx non-numeric characters
        try:
            manager_phone = re.search(r'p\s?h\s?o\s?n\s?e.*?(\(?\d{3}\)?-?\d{3}-?\d{4})[^\d]',
                                  pdf_text.replace(" ", "")).group(1).strip()            
        except:
            manager_phone = "ERROR"
        
    if district == "swg":
        # Typical formatting: English letter OR "zipcode" (xxx)-xxx-xxxx "Phone"

        try:
            manager_phone = re.search(r'[a-z|\d{4,5}](\(?\d{3}\)?-?\d{3}-?\d{4})\s{0,2}P\s?h\s?o\s?n\s?e',
                                      pdf_text.replace(" ", "")).group(1).strip()
        except:
            manager_phone = "ERROR"
        
        

    # MANAGER EMAIL ----------------------------------------------------------------------------------------
    
    if district == "mvn":
        # Typical formatting: xxx.xxx.xxx@usace.army.mil OR xxx-xxx-xxx@usace.army.mil
        try: 
            manager_email = re.search(r'[A-Za-z]+[\.\-][A-Za-z\s\d\.\-]+@\s?u\s?s\s?a\s?c\s?e\s?\.\s?a\s?r\s?m\s?y\s?\.\s?m\s?i\s?l',
                                      pdf_text).group().replace(" ", "")
            if "ElizabethHill" in manager_email:
                manager_email = re.sub(r'.*ElizabethHill', "", manager_email)
        except:
            manager_email = "ERROR"
    
    if district == "sam":
        # Typical formatting: xxx.xxx.xxx@usace.army.mil OR xxx-xxx-xxx@usace.army.mil
        try: 
            manager_email = re.search(r'[A-Za-z]+\.[A-Za-z\s\d\.]+;?@\.?\s?u\s?s\s?a\s?c\s?e\s?\.\s?a\s?r\s?m\s?y\s?\.\s?m\s?i\s?l',
                                      pdf_text).group()
            if "at" in manager_email:
                manager_email = re.sub(r'.*\sat\s', "", manager_email)
            manager_email = manager_email.replace(" ", "")
        except:
            manager_email = "ERROR"
            
    if district == "saj":
        # Typical formatting: "QUESTION" OR "question" ... xxx.xxx.xxx@usace.army.mil OR xxx-xxx-xxx@usace.army.mil
        try: 
            manager_email = re.search(r'[Qq]\s?[Uu]\s?[Ee]\s?[Ss]\s?[Tt]\s?[Ii]\s?[Oo]\s?[Nn].*?([A-Za-z’]+[\.\-][A-Za-z\s\d\.\-’]+@\s?u\s?s\s?a\s?c\s?e\s?\.\s?a\s?r\s?m\s?y\s?\.\s?m\s?i\s?l)', pdf_text).group(1)
            if any(word in manager_email for word in ["to", "at"]):
                manager_email = re.sub(r'.*\s(at|to)\s', "", manager_email)
            manager_email = manager_email.replace(" ", "")
        except:
            manager_email = "ERROR" 
    
    if district == "swg":
        # Typical formatting: swg_xxx_xxx@usace.army.mil OR SWGxxxxxx@usace.army.mil
        try: 
            manager_email = re.search(r'[Ss]\s?[Ww][A-Za-z\s\d\_]+@\s?u\s?s\s?a\s?c\s?e\s?\.\s?a\s?r\s?m\s?y\s?\.\s?m\s?i\s?l',
                                      pdf_text).group().replace(" ", "")
        except:
            manager_email = "ERROR"
        


    # MANAGER NAME ----------------------------------------------------------------------------------------
    
    if district == "mvn":
        
        # Typical formatting: Project Manager(:) xxx (also applied to joint notices which have two project managers)
        try:
            manager_name = re.search(r'(P\s?r\s?o\s?j\s?e\s?c\s?t\s{0,2}M\s?a\s?n\s?a\s?g\s?e\s?r\s?:?)\s*?(\1|C\s?e\s?r\s?t\s?i\s?f\s?i\s?c\s?a\s?t\s?i\s?o\s?n\s{0,2}A\s?n\s?a\s?l\s?y\s?s\s?t\s?:?)?\s*?([A-Z][a-zA-Z\s\.,]*)(\(|\d|P\s?e\s?r\s?m\s?i\s?t|P\s?r\s?o\s?j\s?e\s?c\s?t|' + manager_email + ')', pdf_text).group(3)
            # Clean up the names: replace "Project Manager" and unneccessary spaces
            manager_name = re.sub(r'P\s?r\s?o\s?j\s?e\s?c\s?t\s{0,2}M\s?a\s?n\s?a\s?g\s?e\s?r\s?:?', "", manager_name).strip()
            manager_name = re.sub(r'\s{2,}', ", ", manager_name)
        
        # When the key phase "Project Manager" is missing, try another format: Branch xxx
        except:
            try:
                manager_name = re.search(r'B\s?r\s?a\s?n\s?c\s?h([a-zA-Z\s\.]*)(\(|\d|P\s?e\s?r\s?m\s?i\s?t|' + manager_email + ')', pdf_text).group(1).strip()
                manager_name = re.sub(r'\s{2,}', "", manager_name)
            except:
                manager_name = "ERROR"
                
        # If mistakenly pull "Regulatory" branch name, pull the words after that
        if len(re.findall(r'R\s?e\s?g\s?u\s?l\s?a\s?t\s?o\s?r\s?y', manager_name)) != 0:
            try:
                manager_name = re.search(r'P\s?r\s?o\s?j\s?e\s?c\s?t\s{0,2}M\s?a\s?n\s?a\s?g\s?e\s?r\s?.*?(B\s?r\s?a\s?n\s?c\s?h|\))\s*?([A-Z][a-zA-Z\s\.]*)', pdf_text).group(2).strip()
                manager_name = re.sub(r'\s{2,}', "", manager_name)
            except:
                manager_name = "ERROR"
        
        # When the pulled text is too long, other text is mistakenlly pulled; try to pull the words directly before phone number
        if len(manager_name) > 50:
            if manager_phone != "ERROR":
                try:
                    manager_phone = re.sub(r'(\(|\))', '', manager_phone)
                    manager_name = re.search(r'[A-Za-z\s\.]*(?=\(' + manager_phone[0:3] + '\))', pdf_text).group().strip()
                    manager_name = re.sub(r'\s{2,}', "", manager_name)
                except:
                    manager_name = "ERROR"
            else:
                manager_name = "ERROR"
            
            
            
    if district == "saj":
        
        # Typical formatting: the P(p)roject M(m)anager(:) xxx; contact xxx; directed to xxx
        try:
            manager_name = re.search(r'((t\s?h\s?e|o\s?r)\s{0,2}[Pp]\s?r\s?o\s?j\s?e\s?c\s?t\s{0,2}[Mm]\s?a\s?n\s?a\s?g\s?e\s?r\s?\,?\:?|c\s?o\s?n\s?t\s?a\s?c\s?t|d\s?i\s?r\s?e\s?c\s?t\s?e\s?d\s{0,2}t\s?o)(\s{0,2}[A-Z-].*?)(?=(\,|\,?\so\s?r|\,?\sb\s?y|\,?\sa\s?t|\,?\si\s?n))', pdf_text).group(3).strip()
            manager_name = re.sub(r'\s{2,}', "", manager_name)
        except:
            manager_name = "ERROR"
    
    

    if district == "sam":
        
        # Typical paragraph formmating: direct(ed) (any written comments) to(via) xxx ... "Copies" OR "copy" OR "For additional ..."
        try:
            para_manager = re.search(r'd\s?i\s?r\s?e\s?c\s?t\s?e?\s?d?\s{0,2}(any\swritten\scomments)?(\s?t\s?o|v\s?i\s?a).*?(?=C\s?o\s?p\s?i\s?e\s?s|c\s?o\s?p\s?y|F\s?o\s?r\s{0,2}a\s?d\s?d\s?i\s?t\s?i\s?o\s?n\s?a\s?l)', pdf_text).group().strip()
            para_manager = re.sub(r'\s{2,}', "" ,para_manager)
        except:
            para_manager = "ERROR"
            
        if para_manager != "ERROR":
            
            # Typical key phase formmating in pdf_location: "Attention(Attn)(. or :)" OR "P(p)roject M(m)anager(, or :)" OR "contact" xxx "," OR "or" OR "by" OR "at" OR "in" OR "via" OR numbers
            try:
                manager_name = re.search(r'(A\s?t\s?t\s?e?\s?n\s?t?\s?i?\s?o?\s?n?\s?\.?\:?|[Pp]\s?r\s?o\s?j\s?e\s?c\s?t\s{0,2}[Mm]\s?a\s?n\s?a\s?g\s?e\s?r\s?\,?\:?|c\s?o\s?n\s?t\s?a\s?c\s?t)(.*?)(?=(\,|\so\s?r|\sb\s?y|\sa\s?t|\si\s?n|\d{3,4}))', para_manager).group(2).strip()
            except:
                manager_name = "ERROR"
                
            # When mistakenlly pulled organization names (branch, division, engineers) or having error:
            if len(re.findall(r'ERROR|[Bb]\s?r\s?a\s?n\s?c\s?h|[Dd]\s?i\s?v\s?i\s?s\s?i\s?o\s?n|[Ee]\s?n\s?g\s?i\s?n\s?e\s?e\s?r\s?s|U\s?S\s?A\s?C\s?E', manager_name)) != 0:
                
                #try another formatting in pdf_text: "M(m)anager for this application," OR "the P(p)roject M(m)anager, xxx" OR  "M(m)anager ... Attention(Attn)(, or . or :)" xxx "," OR "or" OR "by" OR "at" OR "in" OR "via" OR numbers OR "("
                try:
                    manager_name = re.search(r'([Mm]\s?a\s?n\s?a\s?g\s?e\s?r\s{0,2}f\s?o\s?r\s{0,2}t\s?h\s?i\s?s\s{0,2}a\s?p\s?p\s?l\s?i\s?c\s?a\s?t\s?i\s?o\s?n\,|t\s?h\s?e\s{0,2}[Pp]\s?r\s?o\s?j\s?e\s?c\s?t\s{0,2}[Mm]\s?a\s?n\s?a\s?g\s?e\s?r\s?\,|[Mn]\s?a\s?n\s?a\s?g\s?e\s?r.*?\s?A\s?t\s?t\s?e?\s?n\s?t?\s?i?\s?o?\s?n?\s?\,?\.?\:?)(\s{0,2}[A-Z].*?)(?=(\,|\,?\so\s?r|\,?\sb\s?y|\,?\sa\s?t|\,?\si\s?n|\,?\sv\s?i\s?a|\d{3,4}|\s{0,2}\())', pdf_text).group(2).strip()
                except:
                    manager_name = "ERROR"
        else:
            manager_name = "ERROR"
           
        
        
    if district  == "swg":
        # Typical paragraph formatting: COMMENT PERIOD ... submitted to(:) ... District ...
        try:
            para_manager = re.search(r'C\s?O\s?M\s?M\s?E\s?N\s?T\s{0,2}P\s?E\s?R\s?I\s?O\s?D.*s\s?u\s?b\s?m\s?i\s?t\s?t\s?e\s?d.*?t\s?o\s?:?(.*?)(?=D\s?I\s?S\s?T\s?R\s?I\s?C\s?T)', pdf_text).group(1).strip()
            para_manager = re.sub(r'\s{2,}', "" ,para_manager)
        except:
            para_manager = "ERROR"
            
        if para_manager.find("ERROR") == -1:
            
            # Typical key phase formatting: xxx "U.S." OR "Galveston" OR "Post" OR "PO" OR "P.O." OR numbers OR "S(s)wg_"
            try:
                manager_name = re.search(r'.*?(?=(U\s?\.\s?S\s?\.|G\s?a\s?l\s?v\s?e\s?s\s?t\s?o\s?n|P\s?o\s?s\s?t|P\s?O|P\s?\.\s?O\s?\.|\d{4}|[Ss]\s?w\s?g\s?_))', para_manager).group().strip().replace("  ", "")
                # If none is pulled, no specific sub organization is mentioned
                if manager_name == "":
                    manager_name = "U.S. Army Corps of Engineers"
            except:
                manager_name = "ERROR"
        else:
            manager_name = "ERROR" 
        
    return {"manager_name":manager_name, 
            "manager_phone":manager_phone, 
            "manager_email":manager_email}




def get_pdf_applicant(pdf_text, district):
    """ 
    Get all info in "NAME OF APPLICANT"
    """
    
    if district == "mvn":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', pdf_text)) != 0:
            
            # Applicant full info
            try:
                pdf_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]\s?:?(.+)(?=L\s?[Oo]\s?[Cc]\s?[Aa]\s?[Tt]\s?[Ii]\s?[Oo]\s?[Nn])', pdf_text).group(1).strip()
                pdf_applicant_contents = re.sub(r'\s{2,}', "", pdf_applicant_contents)

                # Extract applicant and contractor when the contractor exists
                if len(re.findall(r'c\s?\/\s?o', pdf_applicant_contents)) != 0:
                    try:
                        applicant = re.search(r'.+?(?=\,?\s?c\s?\/\s?o)', pdf_applicant_contents).group().strip()
                    except:
                        applicant = "ERROR"
                    try:    
                        contractor = re.search(r'c\s?\/\s?o\s?:?\s?(.+?)(?=(,?\s?P\s?o\s?s\s?t|,?\s?P\s?O|,?\s?P\s?\.\s?O\s?\.|,?\s*\d|,?\s?[Aa][tT]{2}))', pdf_applicant_contents).group(1).strip()
                    except:
                        contractor = "ERROR"
                        
                 # Extract applicant and contractor when no contractor
                else:
                    contractor = "unknown"
                    try:
                        applicant = re.search(r'.+?(?=(,?\s?P\s?o\s?s\s?t|,?\s?P\s?O|,?\s?P\s?\.\s?O\s?\.|,?\s*\d|,?\s?[Aa][tT]{2}))', pdf_applicant_contents).group().strip()
                    except:
                        applicant = "ERROR"

            except:
                pdf_applicant_contents = applicant = contractor = "ERROR"
        else:
            pdf_applicant_contents = applicant = contractor = "unknown"
    
    
    
    if district == "sam":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', pdf_text)) != 0:
            
            # Applicant full info
            try:
                pdf_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt].+(?=(W\s?A\s?T\s?E\s?R\s?W\s?A\s?Y|L\s?O\s?C\s?A\s?T\s?I\s?O\s?N))', pdf_text).group().strip()
                pdf_applicant_contents = re.sub(r'\s{2,}', "", pdf_applicant_contents)
            except:
                pdf_applicant_contents = "ERROR"
                
            # Applicant
            try:
                applicant = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]\s?\:?(.+?)(?=(P\s?o\s?s\s?t|P\s?O|P\s?\.\s?O\s?\.|\d|c\/o|A\s?t\s?t\s?n|A\s?t\s?t\s?e\s?n\s?t\s?i\s?o\s?n))', pdf_text).group(1).strip()
            except:
                applicant = "ERROR"
        else:
            pdf_applicant_contents = applicant = "unknown"
            
        # Agent
        if len(re.findall(r'A\s?[Gg]\s?[Ee]\s?[Nn]\s?[Tt]', pdf_text)) != 0:
            try:
                contractor = re.search(r'A\s?[Gg]\s?[Ee]\s?[Nn]\s?[Tt]\s?:?(.+?)(?=(P\s?o\s?s\s?t|P\s?O|P\s?\.\s?O\s?\.|\d|c\/o|A\s?t\s?t\s?n|A\s?t\s?t\s?e\s?n\s?t\s?i\s?o\s?n|L\s?O\s?C\s?A\s?T\s?I\s?O\s?N))', pdf_text).group(1).strip()
            except:
                contractor = "ERROR"
        else:
            contractor = "unknown"
            
            
            
    if district == "saj":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', pdf_text)) != 0:
                
            # Applicant full info
            try:
                pdf_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt].+(?=(W\s?A\s?T\s?E\s?R\s?W\s?A\s?Y|L\s?O\s?C\s?A\s?T\s?I\s?O\s?N))', pdf_text).group().strip()
                pdf_applicant_contents = re.sub(r'\s{2,}', "", pdf_applicant_contents)

                # Extract applicant; no contractor for Jacksonville                  
                try:
                    applicant = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]\s?\:?(.+?)(?=(P\s?o\s?s\s?t|P\s?O|P\s?\.\s?O\s?\.|\d|c\/o|A\s?t\s?t\s?n|A\s?t\s?t\s?e\s?n\s?t\s?i\s?o\s?n|$))', pdf_applicant_contents).group(1).strip()
                except:
                    applicant = "ERROR"
                contractor = "unknown"

            except:
                pdf_applicant_contents = applicant = "ERROR"
                contractor = "unknown"
        else:
            pdf_applicant_contents = applicant = contractor = "unknown"
            
            
        
    if district == "swg":
        
        if len(re.findall(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]', pdf_text)) != 0:
            
            # Applicant full info
            try:
                pdf_applicant_contents = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt].+(?=(L\s?O\s?C\s?A\s?T\s?I\s?O\s?N|P\s?R\s?O\s?J\s?E\s?C\s?T))', pdf_text).group().strip()
                pdf_applicant_contents = re.sub(r'\s{2,}', "", pdf_applicant_contents)
            except:
                pdf_applicant_contents = "ERROR"
                
            # Applicant
            try:
                applicant = re.search(r'A\s?[Pp]\s?[Pp]\s?[Ll]\s?[Ii]\s?[Cc]\s?[Aa]\s?[Nn]\s?[Tt]\s?\:?(.+?)(?=(P\s?o\s?s\s?t|P\s?O|P\s?\.\s?O\s?\.|\d|c\/o|A\s?t\s?t\s?n|A\s?t\s?t\s?e\s?n\s?t\s?i\s?o\s?n))', pdf_text).group(1).strip()
            except:
                applicant = "ERROR"
        else:
            pdf_applicant_contents = applicant = "unknown"
        
        # Agent
        if len(re.findall(r'A\s?[Gg]\s?[Ee]\s?[Nn]\s?[Tt]', pdf_text)) != 0:
            try:
                contractor = re.search(r'A\s?[Gg]\s?[Ee]\s?[Nn]\s?[Tt]\s?:?(.+?)(?=(P\s?o\s?s\s?t|P\s?O|P\s?\.\s?O\s?\.|\d|c\/o|A\s?t\s?t\s?n|A\s?t\s?t\s?e\s?n\s?t\s?i\s?o\s?n|L\s?O\s?C\s?A\s?T\s?I\s?O\s?N))', pdf_text).group(1).strip()
            except:
                contractor = "ERROR"
        else:
            contractor = "unknown"
            
    return {"pdf_applicant_contents":pdf_applicant_contents, 
            "applicant":applicant, 
            "contractor":contractor}



    
def get_pdf_location(pdf_text, district):
    """
    Get location of work
    """
    
    if re.findall(r'L\s?[Oo]\s?[Cc]\s?[Aa]\s?[Tt]\s?[Ii]\s?[Oo]\s?[Nn]', pdf_text) != 0:
        
        if district == "mvn":
            try:
                pdf_location = re.search(r'L\s?[Oo]\s?[Cc]\s?[Aa]\s?[Tt]\s?[Ii]\s?[Oo]\s?[Nn]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk]\s?:?(.*)(?=C\s?[Hh]\s?[Aa]\s?[Rr]\s?[Aa]\s?[Cc]\s?[Tt]\s?[Ee]\s?[Rr]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk])', pdf_text).group(1).replace("  ", " ").strip()
            except:
                pdf_location = "ERROR"
                
        if district  == "sam":
            try:
                pdf_location = re.search(r'(L\s?O\s?C\s?A\s?T\s?I\s?O\s?N|W\s?A\s?T\s?E\s?R\s?W\s?A\s?Y)\s?:?(.*)(?=(P\s?R\s?O\s?J\s?E\s?C\s?T|P\s?R\s?O\s?P\s?O\s?S\s?E\s?D|A\s?P\s?P\s?L\s?I\s?C\s?A\s?N\s?T|W\s?O\s?R\s?K))', pdf_text).group(2).replace("  ", " ").strip()
            except:
                pdf_location = "ERROR"
                
        if district == "saj":
            try:
                pdf_location = re.search(r'L\s?O\s?C\s?A\s?T\s?I\s?O\s?N\s?:?(.*)(?=(D\s?i\s?r\s?e\s?c\s?t\s?i\s?o\s?n\s?s|A\s?P\s?P\s?R\s?O\s?X\s?I\s?M\s?A\s?T\s?E|P\s?R\s?O\s?J\s?E\s?C\s?T))', pdf_text).group(1).replace("  ", " ").strip()
            except:
                pdf_location = "ERROR"
                
        if district == "swg":
            try:
                pdf_location = re.search(r'L\s?O\s?C\s?A\s?T\s?I\s?O\s?N\s?:?(.*)(?=(L\s?A\s?T\s?I\s?T\s?U\s?D\s?E|A\s?G\s?E\s?N\s?D\s?A|P\s?R\s?O\s?J\s?E\s?C\s?T|A\s?V\s?O\s?I\s?D\s?A\s?N\s?C\s?E))', pdf_text).group(1).replace("  ", "").strip()
            except:
                pdf_location = "ERROR"
                
    else:
        pdf_location = "unknown"
        
    return pdf_location

 
    
    
def get_pdf_character(pdf_text, district):
    """
    Get character of work
    """
    
    if district == "mvn":
        if len(re.findall(r'C\s?[Hh]\s?[Aa]\s?[Rr]\s?[Aa]\s?[Cc]\s?[Tt]\s?[Ee]\s?[Rr]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk]', pdf_text)) != 0:
            try:
                pdf_character = re.search(r'C\s?[Hh]\s?[Aa]\s?[Rr]\s?[Aa]\s?[Cc]\s?[Tt]\s?[Ee]\s?[Rr]\s{0,2}[Oo]\s?[Ff]\s{0,2}W\s?[Oo]\s?[Rr]\s?[Kk](.*?)(?=(M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N|T\s?h\s?e\s{0,2}c\s?o\s?m\s?m\s?e\s?n\s?t\s{0,2}p\s?e\s?r\s?i\s?o\s?d))', pdf_text).group(1).strip()
                pdf_character = re.sub(r'\s{2,}', "", pdf_character)
            except:
                pdf_character = "ERROR"
        else:
            pdf_character = "unknown"
            
    if district in ("sam", "saj"):
        if len(re.findall(r'W\s?O\s?R\s?K', pdf_text)) != 0:
            try:
                pdf_character = re.search(
                r'(P\s?R\s?O\s?P\s?O\s?S\s?E\s?D\s{0,2}W\s?O\s?R\s?K|W\s?O\s?R\s?K\s{0,2}D\s?E\s?S\s?C\s?R\s?I\s?P\s?T\s?I\s?O\s?N|W\s?O\s?R\s?K)\s?:?(.*?)(?=(A\s?V\s?O\s?I\s?D\s?A\s?N\s?C\s?E|C\s?O\s?A\s?S\s?T\s?A\s?L|T\s?h\s?e\s{0,2}a\s?p\s?p\s?l\s?i\s?c\s?a\s?n\s?t\s{0,2}h\s?a\s?s\s{0,2}a\s?p\s?p\s?l\s?i\s?e\s?d))',
                pdf_text).group(2).strip()
                pdf_character = re.sub(r'\s{2,}', "", pdf_character)
            except:
                pdf_character = "ERROR"
        else:
            pdf_character = "unknown"
            
    if district == "swg":
        if len(re.findall(r'P\s?R\s?O\s?J\s?E\s?C\s?T\s{0,2}D\s?E\s?S\s?C\s?R\s?I\s?P\s?T\s?I\s?O\s?N', pdf_text)) != 0:
            try:
                pdf_character = re.search(r'P\s?R\s?O\s?J\s?E\s?C\s?T\s{0,2}D\s?E\s?S\s?C\s?R\s?I\s?P\s?T\s?I\s?O\s?N(.*?)(?=[A-Z\s]+:)', pdf_text).group(1).strip()
                pdf_character = re.sub(r'\s{2,}', "", pdf_character)
            except:
                pdf_character = "ERROR"
        else:
            pdf_character = "unknown"
            
    return pdf_character




def get_pdf_mitigation(pdf_text, district):
    """
    Get mitigation
    """
    
    if district == "mvn":
        if len(re.findall(r'M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N', pdf_text)) != 0:
            try:
                pdf_mitigation = re.search(r'M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N(.*?)(?=T\s?h\s?e\s{0,2}c\s?o\s?m\s?m\s?e\s?n\s?t\s{0,2}p\s?e\s?r\s?i\s?o\s?d)', pdf_text).group(1).strip()
                pdf_mitigation = re.sub(r'\s{2,}', "", pdf_mitigation)
            except:
                pdf_mitigation = "ERROR"
        else:
            pdf_mitigation = "unknown"
    
    if district in ["sam", "saj", "swg"]:
        if len(re.findall(r'(A\s?V\s?O\s?I\s?D\s?A\s?N\s?C\s?E\s?(&|A\s?N\s?D)\s?M\s?I\s?N\s?I\s?M\s?I\s?Z\s?A\s?T\s?I\s?O\s?N|C?\s?O?\s?M?\s?P?\s?E?\s?N?\s?S?\s?A?\s?T?\s?O?\s?R?\s?Y?\s{0,2}M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N)', pdf_text)) != 0:
                # pdf_mitigation = re.search(r'(AVOIDANCE|COMPENSATORY|MITIGATION).*?(?=WATER|The applicant will apply|The applicant has applied|CULTURAL)', pdf_text).group().strip()
            try:
                pdf_avio_mini = re.search(r'M\s?I\s?N\s?I\s?M\s?I\s?Z\s?A\s?T\s?I\s?O\s?N\s{0,2}I?\s?N?\s?F?\s?O?\s?R?\s?M?\s?A?\s?T?\s?I?\s?O?\s?N?.+?(?=[A-Z\s]+:)', pdf_text).group().strip()
            except:
                pdf_avio_mini = "ERROR: AVOIDANCE AND MINIMIZATION"
            try:
                pdf_comp_miti = re.search(r'M\s?I\s?T\s?I\s?G\s?A\s?T\s?I\s?O\s?N.+?(?=[A-Z\s]+:)', 
                                     pdf_text).group().strip()
            except:
                pdf_comp_miti = "ERROR: COMPENSATORY MITIGATION"
            if "ERROR" not in pdf_avio_mini and "ERROR" not in pdf_comp_miti:
                pdf_mitigation = pdf_avio_mini + " " + pdf_comp_miti
                pdf_mitigation = re.sub(r'\s{2,}', "", pdf_mitigation)
            else:
                pdf_mitigation = "ERROR"
        else:
            pdf_mitigation = "unknown"
        
    return pdf_mitigation
                



# Extract fields from paragraphs

## From location of work

# def get_pdf_city_county_parish_MVN_SAM(pdf_text):
#     """
#     Get county, city or parish name for New Orleans and Mobile
#     """
    
#     if pdf_text.find("COUNTY") != -1:
#         try:
#             county = re.search(r'[\w\s]+C\s?ounty', pdf_text).group().strip()
#         except Exception as e:
#             county = "ERROR: " + str(e)
#         try:
#             city = re.search(r'[\w\s]+(?=,\s*' + county + ')', pdf_text).group().strip()
#         except Exception as e:
#             city = "ERROR: " + str(e)
#     else:
#         county = None
#         city = None
#     if pdf_text.find("PARISH") != -1:
#         try:
#             parish = re.search(r'((?<=(IN|in)).{1,50}PARISH)', pdf_text).group().strip()
#             #parish = re.search(r'((?<=in).{1,100}(?= Parish))', pdf_text).group().strip()
#         except Exception as e:
#             parish = "ERROR: " + str(e)
#     else:
#         parish = None
            
#     return county, parish, city




def get_pdf_city_county_parish(pdf_location):
    """
    Get county, city, and parish name
    """
    
    loc_sent_list = re.findall(r'.*?\D\.', pdf_location)
    if len(loc_sent_list) == 0:
        loc_sent_list = [pdf_location]
    
    county_list = []
    city_list = []
    
    for sent in loc_sent_list:
        # if any(x in sent for x in ["Louisiana", "LA", "Alabama", "AL", "Florida", "Fl orida", "FL", "Texas", "TX"]):
        have_county = re.findall(r'[Cc]\s?o\s?u\s?n\s?t\s?y', sent)
        if len(have_county)!= 0:
            try:
                county = re.search(r'(,|\sin)([\w\s]+C\s?ounty)', sent).group(2).strip()
            except:
                county = "ERROR"
            if "ERROR" not in county:
                try:
                    city = re.search(r'(in|near)([\w\s]+)(?=,\s*' + county + ')', 
                                     sent).group(2).strip()
                except:
                    city = "ERROR"
                county = county.replace("in", "").strip()
                if "ERROR" not in city and len(city) > 25:
                    city = "Might be ERROR: " + city
            else:
                city = "CHECK: fail to pull county"
        else:
            county = "unknown"
            try:
                city = re.search(
                    r'(entitled|in|near|of):?([\w\s]+)(?=,?\s?(Louisiana|LA|Alabama|AL|Fl\s?orida|FL|Texas|TX))', 
                    sent).group(2).strip()
            except:
                city = "ERROR"
            if len(city) > 25:
                city = "CHECK: " + city

        county_list.append(county)
        city_list.append(city)
        
        if all(county == "unknown" for county in county_list):
            county = "unknown"
        elif sum([county == "unknown" for county in county_list]) == 1:
            county = [county for county in county_list if county == "unknown"][0]
        else:
            county = [county for county in county_list if county != "unknown"]
            
        if all("ERROR" in city for city in city_list):
            city = "unknown"
        elif sum(["ERROR" not in city for city in city_list]) == 1:
            city = [city for city in city_list if "ERROR" not in city][0]
        else:
            city = [city for city in city_list if "ERROR" not in city]
            
        if "Parish" in sent:
            try:
                parish = re.search(r'(?<=in|of).{1,50}Parish', sent).group().strip()
            except:
                parish = "ERROR"
        else:
            parish = "unknown"
                    
    return [county, parish, city]




def get_pdf_hydrologic(pdf_text):
    """
    Get hydrologic unit code
    """
    if len(re.findall(r'H\s?y\s?d\s?r\s?o\s?l\s?o\s?g\s?i\s?c\s{0,2}U\s?n\s?i\s?t\s{0,2}C\s?o\s?d\s?e', pdf_text)) != 0:
        try:
            hydrologic_unit_code = re.search(r'H\s?y\s?d\s?r\s?o\s?l\s?o\s?g\s?i\s?c\s{0,2}U\s?n\s?i\s?t\s{0,2}C\s?o\s?d\s?e\s?:?\s?([\s\d]*)', pdf_text).group(1).strip().replace(" ", "")
        except:
            hydrologic_unit_code = "ERROR"
    else:
        hydrologic_unit_code = "unknown"
    return hydrologic_unit_code




def get_lon_lat(pdf_text):
    """
    Get longitude and latitude for New Orleans and Mobile districts
    """
    
    def isfloat(x):
        try:
            float(x)
            return True
        except ValueError:
            return False
    
    
    # Longitude
    lon_exist = re.findall(r'([Ll]\s?[Oo]\s?[Nn]\s?[Gg]\s?[Ii]\s?[Tt]\s?[Uu]\s?[Dd]\s?[Ee]|[Ll]\s?[Oo]\s?[Nn]\s?[Gg]\s?\.)', pdf_text)
    
    # when longitude is provided
    if len(lon_exist) != 0:  
        
        # Try to pull lon in decimal degree format
        lon = re.findall(r'([Ll]\s?o\s?n\s?g?\s?i?\s?t?\s?u?\s?d?\s?e?\s?\.?:?|-|–|W\s?e?\s?s?\s?t?\s?\.?:?)(\s*[\d\s]{2,3}\.[\d\s]{3,8})', pdf_text)
        lon = [i[1] for i in lon]
        
        # Try another decimal degree format
        if len(lon) == 0 or any(i in ["", "1"] for i in lon):
            lon = re.findall(r'([\d\s]{2,3}\.[\d\s]{3,8})\s*[°ºo]?\s*[Ww]\s?e?\s?s?\s?t?', pdf_text)
        
        # Cleaning
            
        ## 1. Trim unecessary words and spaces
        # lon = [re.sub("([Ll]\s?o\s?n\s?g?\s?i?\s?t?\s?u?\s?d?\s?e?\s?\.?:?|-|W\s?e?\s?s?\s?t?\s?\.?:?|\s*°?\s*[Ww]\s?e?\s?s?\s?t?|\s)", "", i) for i in lon]
        lon = [i.replace(" ", "") for i in lon]
        ## 2. Trim the heading zero
        lon = [i[1:] if len(i) > 0 and i[0] == "0" else i for i in lon]
        
        if len(lon) != 0:
            ## 3. Delete anything that it not a longitude:
            lon_decimal_max = max([len(re.sub(r'.*\.', "", i)) for i in lon])
            lon = [i for i in lon if len(re.sub(r'.*\.', "", i)) == lon_decimal_max]
            
        ## 4. Add negative sign if not included
        lon = ["-" + i if float(i) > 0 else i for i in lon if isfloat(i) == True] 
        
        
    else:
        lon = "unknown"
    
    
    # Latitude
    lat_exist = re.findall(r'([Ll]\s?[Aa]\s?[Tt]\s?[Ii]\s?[Tt]\s?[Uu]\s?[Dd]\s?[Ee]|[Ll]\s?[Aa]\s?[Tt]\s?\.)', pdf_text) 
    
    # When latitude is provided
    if len(lat_exist) != 0:
        
        # Try to pull lon in decimal degree format
        lat = re.findall(r"(?<=[^-W°ºo][^-\d°ºo])\d\s?\d\s?\.[\d\s]{4,8}", pdf_text)
        
        # Cleaning
            
        ## 1. Trim spaces
        lat = [i.replace(" ", "") for i in lat]
        ## 2. Trim the heading zero
        lat = [i[1:] if len(i) > 0 and i[0] == "0" else i for i in lat]
        ## 3. Delete longitudes and other numbers that are mistakenlly pulled into latitude list
        lat = [i for i in lat if float(i) < 50 and float(i) > 15 if isfloat(i) == True]
        
        if len(lat) != 0:
            ## 4. Delete anything that it not a latitute:
            lat_decimal_max = max([len(re.sub(r'.*\.', "", i)) for i in lat])
            lat = [i for i in lat if len(re.sub(r'.*\.', "", i)) == lat_decimal_max]
        
    else:
        lat = "unknown"
        
    # Try to pull lon/lat in Degrees/Decimal Minutes format
    if lon != "unknown" and lat != "unknown":
        
        ## (1) the first type of degree: xx°xx'xx''
        if len(lon) == 0 or len(lat) == 0:
    
            degree_lonlat = re.findall(r'([Ll]\s?a\s?t|[Ll]\s?o\s?n\s?g)[A-Za-z\s\.:-]*?(\d\s?\d\s?[°ºo][\s\d\.]*\\?[′\'’]?[\d\s\.]*[″"”]?)', pdf_text)

            def degree_to_decimal(degree_lonlat):
                try:
                    degree = re.search(r'[\d\s]*(?=[°ºo])', degree_lonlat).group().replace(" ", "")
                except:
                    degree = "ERROR"
                if len(re.findall(r'[′\'’]', degree_lonlat)) != 0:
                    try:
                        minute = re.search(r'[\d\.\s]*(?=[′\\\'’])', degree_lonlat).group().replace(" ", "")
                    except:
                        minute = "ERROR"
                else:
                    minute = 0
                if len(re.findall(r'[″"”]', degree_lonlat)) != 0:
                    try:
                        second = re.search(r'[\d\.\s]*(?=[″"”])', degree_lonlat).group().replace(" ", "")
                    except:
                        second = "ERROR"
                else:
                    second = 0
                if isfloat(degree) == True and isfloat(minute) == True and isfloat(second) == True:
                    decimal_lonlat = float(degree) + float(minute)/60 + float(second)/3600
                else:
                    decimal_lonlat = 0
                return decimal_lonlat

            decimal_lonlat = [degree_to_decimal(i[1]) for i in degree_lonlat]
            decimal_lonlat = [i for i in decimal_lonlat if i != 0]

            # Group into lon and lat
            lon = ["-" + str(i)[:9] for i in decimal_lonlat if i > 50]
            lat = [str(i)[:9] for i in decimal_lonlat if i < 50]
        
        ## (2) The second type of degree: xx xx xx
        if len(lon) == 0 or len(lat) == 0:
            
            degree_lonlat = re.findall(r'([Ll]\s?a\s?t\s?\.?|[Ll]\s?o\s?n\s?g\s?\.?\s*?-?)([\d\s\.]*)(?=[,\)])', pdf_text)
            
            def degree_to_decimal(degree_lonlat):
                try:
                    degree = re.search(r'[\d]{2}(?=\s)', degree_lonlat).group()
                except:
                    degree = "ERROR"
                try:
                    minute = re.search(r'' + degree + '\s([\d\.]*)(?=\s)', degree_lonlat).group(1)
                except:
                    minute = "ERROR"
                try:
                    second = re.search(r'' + minute + '\s([\d\.]*)', degree_lonlat).group(1)
                except:
                    second = "ERROR"
                if isfloat(degree) == True and isfloat(minute) == True and isfloat(second) == True:
                    decimal_lonlat = float(degree) + float(minute)/60 + float(second)/3600
                else:
                    decimal_lonlat = 0
                return decimal_lonlat

            decimal_lonlat = [degree_to_decimal(i[1]) for i in degree_lonlat]
            decimal_lonlat = [i for i in decimal_lonlat if i != 0]

            # # Group into lon and lat
            lon = ["-" + str(i)[:9] for i in decimal_lonlat if i > 50]
            lat = [str(i)[:9] for i in decimal_lonlat if i < 50]
        
    return {"lon":lon, 
            "lat":lat}




# def get_lon_lat_SAJ_SWG(pdf_text):
#     """
#     Get longitude and latitude for Jacksonville and Galveston
#     """
    
#     # Longitude
#     long_exist = re.findall(r'[Ll]\s?[Oo]\s?[Nn]\s?[Gg]\s?[Ii]\s?[Tt]\s?[Uu]\s?[Dd]\s?[Ee]', pdf_text)
#     if len(long_exist) != 0:
#         try:
#             lon = re.findall(r"[Ll]\s?[Oo]\s?[Nn]\s?[Gg]\s?[Ii]\s?[Tt]\s?[Uu]\s?[Dd]\s?[Ee]\s?:?([\s\-\d\.]{3,})", pdf_text)
#         except Exception as e:
#             lon = "ERROR: " + str(e)
#         if isinstance(lon, str) == False:
#             if any(i in ["", "1"] for i in lon):
#                 try:
#                     lon = re.findall(r'(?<=[-W])(\s*\d{2}\.[\d\s]{3,8})', pdf_text)
#                 except Exception as e:
#                     lon = "ERROR: " + str(e)
#             if isinstance(lon, str) == False:    
#                 lon = [i.replace(":", "").replace(" ", "") for i in lon]
#                 lon = [i[1:] if len(i) > 0 and i[0] == "0" else i for i in lon]
#                 lon = ["-" + i if float(i) > 0 else i for i in lon]
#     else:
#         lon = None
    
#     # Latitude
#     lat_exist = re.findall(r'[Ll]\s?a\s?t\s?i?\s?t?\s?u?\s?d?\s?e', pdf_text)    
#     if len(lat_exist) != 0:
#         try:
#             lat = re.findall(r"(?<=Latitude)\s?:?([\s\d\.]+)", pdf_text)
#         except Exception as e:
#             lat = "ERROR: " + str(e)
#         if isinstance(lat, str) == False:
#             if any(i in [""] for i in lat):
#                 try:
#                     lat = re.findall(r'(?<=[^-W°][^-\d°])\d{2}\.[\d\s]{3,8}', pdf_text)
#                 except Exception as e:
#                     lat = "ERROR: " + str(e)
#             if isinstance(lat, str) == False:
#                 lat = [i.replace(":", "").replace(" ", "") for i in lat]
#                 lat = [i[1:] if len(i) > 0 and i[0] == "0" else i for i in lat]
#     else:
#         lat = None
    
#     # Form coordinate
#     # for i in range(0,len(lon))
        
#     return lon, lat




## From character of work

def acre_type_term(acre_item):
    """
    Extract acreage impacted, impacted type, and impacted time length in one part of a sentence, which only has one subject, one verb, and one object.
    NOTE: Impact_length_missing is a flag to identify if "permanent/temporary" impact can be found in other parts of the same sentence.
    # 0: Exactly identify the impact will be permanent/temporary; 
    # 1: How long the impact is exactly unknow; 
    # 2: Might find how long the impact will be in other parts of the same sentence
    """
    
    # Pull the impacted number regardless of the impact is negative/positive
    try:
        impact_number = re.search(r'[^A-Za-z]+(?=acres?\)?)', acre_item).group()
    except:
        impact_number = "ERROR"
    impact_unit = "acre"

    # type of impacted areas: wetland;habitat;pond;waterbottom;marsh/water
    have_type = re.findall(r'(h\s?a\s?b\s?i\s?t\s?a\s?t|w\s?e\s?t\s?l\s?a\s?n\s?d|p\s?o\s?n\s?d|w\s?a\s?t\s?e\s?r\s?b\s?o\s?t\s?t\s?o\s?m|m\s?a\s?r\s?s\s?h|w\s?a\s?t\s?e\s?r)', acre_item)
    
    # Pull the impact type info
    if len(have_type) != 0:
        try:
            impact_type = re.search(
                r'' + impact_number + 'acres?\)?.*?of(\simpacts\sto|.*?in)?(.*?(h\s?a\s?b\s?i\s?t\s?a\s?t|w\s?e\s?t\s?l\s?a\s?n\s?d|p\s?o\s?n\s?d|w\s?a\s?t\s?e\s?r\s?b\s?o\s?t\s?t\s?o\s?m|m\s?a\s?r\s?s\s?h|w\s?a\s?t\s?e\s?r\s?s?))',
                acre_item).group(2).strip()
        except:
            impact_type = "ERROR"
    else:
        impact_type = "project size"
        
    # Negative: impact/affect/loss/fill/excavate/dredge
    is_negative = re.findall(r'i\s?m\s?p\s?a\s?c\s?t|a\s?f\s?f\s?e\s?c\s?t|l\s?o\s?s\s?s|f\s?i\s?l\s?l|e\s?x\s?c\s?a\s?v\s?a|d\s?r\s?e\s?d\s?g', acre_item)
    # Postive: benefit/benefical/preserve/preservation/create
    is_positive = re.findall(r'(b\s?e\s?n\s?e\s?f|p\s?r\s?e\s?s\s?e\s?r\s?v|c\s?r\s?e\s?a\s?t)', acre_item)
    # Avioded: aviod
    is_avoid = re.findall(r'\sa\s?v\s?o\s?i\s?d', acre_item)
    
    ## negative key words only: 
    if len(is_negative) != 0 and len(is_positive) == 0:
        impact_condition = "negative"
        if "credit" in acre_item:
            impact_condition = "negative, compensate by purchasing credits from the mitigation bank"

    ## positive key words only:
    elif len(is_negative) == 0 and len(is_positive) != 0:
        impact_condition = "positive"

    ## A sentence might have both positive/negative words, in different parts separatly:
    elif len(is_negative) != 0 and len(is_positive) != 0:
        impact_condition = "manually review required"

    ## This part of sentence doesn't have any verbs indicating negative/positive impacts
    else: # len(is_negative) == 0 and len(is_positive) == 0
        impact_condition = "same as previous/later one"
    
    # Project size usually comes along with "fill", but the impacy should be neutral
    if impact_type == "project size":
        impact_condition = "neutral"
        
    if len(is_avoid) != 0:
        impact_condition = "avoided"

    # If the impact is permanent or temperary
    have_length = re.findall(r'(p\s?e\s?r\s?m\s?a\s?n\s?e\s?n\s?t|t\s?e\s?m\s?p\s?o\s?r\s?a\s?r)', acre_item)
    
    if  (len(is_negative) != 0 or len(is_positive) != 0) and len(have_length) != 0:
        try:
            impact_length = re.search(r'(p\s?e\s?r\s?m\s?a\s?n\s?e\s?n\s?t\s?[a-z]*|t\s?e\s?m\s?p\s?o\s?r\s?a\s?r\s?[a-z]*)\)?\s', acre_item).group(0).strip()
        except:
            impact_length = "ERROR"
        impact_length_missing = 0
    elif (len(is_negative) != 0 or len(is_positive) != 0) and len(have_length) == 0:
        impact_length = "unknown"
        impact_length_missing = 1
    else:
        impact_length = "unknown"
        impact_length_missing = 2

    # clear up the number of acreage being impacted
    impact_number = impact_number.replace(" ", "").replace("-", "").replace(",", "").replace("(", "").strip()
    
    return {"impact_number": impact_number, 
            "impact_unit": impact_unit, 
            "impact_number_type": impact_type, 
            "impact_condition": impact_condition,
            "impact_duration": impact_length,
            "impact_duration_missing": impact_length_missing}




def ft2_type_term(ft2_item):
    """
    Draw square feet impacted, impacted type, and impacted time length 
    """

    # Pull the impacted number regardless of the impact is negative/positive
    try:
        impact_number = re.search(r'[^A-Za-z]+(?=(square|ft2))', ft2_item).group()
    except:
        impact_number = "ERROR"
    impact_unit = "square feet"
    
    # type of impacted areas: wetland;habitat;pond;waterbottom;marsh/water
    have_type = re.findall(r'(h\s?a\s?b\s?i\s?t\s?a\s?t|w\s?e\s?t\s?l\s?a\s?n\s?d|p\s?o\s?n\s?d|w\s?a\s?t\s?e\s?r\s?b\s?o\s?t\s?t\s?o\s?m|m\s?a\s?r\s?s\s?h|w\s?a\s?t\s?e\s?r)', ft2_item)

    # type of impacted areas
    if len(have_type) != 0:
        try:
            impact_type = re.search(
                r'' + impact_number + '(square)?-?\s?f[eo]*t2?.*?of(\simpacts\sto|.*?in)?(.*?(h\s?a\s?b\s?i\s?t\s?a\s?t|w\s?e\s?t\s?l\s?a\s?n\s?d|p\s?o\s?n\s?d|w\s?a\s?t\s?e\s?r\s?b\s?o\s?t\s?t\s?o\s?m|m\s?a\s?r\s?s\s?h|w\s?a\s?t\s?e\s?r\s?s?))', ft2_item).group(3).strip()
        except:
            impact_type = "ERROR"
    else:
        impact_type = "project size"
        
    # Negative: impact/affect/loss/fill/excavate/drege
    is_negative = re.findall(r'i\s?m\s?p\s?a\s?c\s?t|a\s?f\s?f\s?e\s?c\s?t|l\s?o\s?s\s?s|f\s?i\s?l\s?l|e\s?x\s?c\s?a\s?v\s?a|d\s?r\s?e\s?d\s?g', ft2_item)
    # Postive: benefit/benefical/preserve/preservation/create
    is_positive = re.findall(r'(b\s?e\s?n\s?e\s?f|p\s?r\s?e\s?s\s?e\s?r\s?v|c\s?r\s?e\s?a\s?t)', ft2_item)
    # Avioded: aviod
    is_avoid = re.findall(r'\sa\s?v\s?o\s?i\s?d', ft2_item)
    
    ## negative key words only: 
    if len(is_negative) != 0 and len(is_positive) == 0:
        impact_condition = "negative"
        if "credit" in ft2_item:
            impact_condition = "negative, compensate by purchasing credits from the mitigation bank"

    ## positive key words only:
    elif len(is_negative) == 0 and len(is_positive) != 0:
        impact_condition = "positive"

    ## A sentence might have both positive/negative words, in different parts separatly:
    elif len(is_negative) != 0 and len(is_positive) != 0:
        impact_condition = "manually review required"

    ## This part of sentence doesn't have any verbs indicating negative/positive impacts
    else: # len(is_negative) == 0 and len(is_positive) == 0
        impact_condition = "same as previous/later one"
    
    # Project size usually comes along with "fill", but the impacy should be neutral
    if impact_type == "project size":
        impact_condition = "neutral"
        
    if len(is_avoid) != 0:
        impact_condition = "avoided"

    # If the impact is permanent or temperary
    have_length = re.findall(r'(p\s?e\s?r\s?m\s?a\s?n\s?e\s?n\s?t|t\s?e\s?m\s?p\s?o\s?r\s?a\s?r)', ft2_item)
    
    if  (len(is_negative) != 0 or len(is_positive) != 0) and len(have_length) != 0:
        try:
            impact_length = re.search(r'(p\s?e\s?r\s?m\s?a\s?n\s?e\s?n\s?t\s?[a-z]*|t\s?e\s?m\s?p\s?o\s?r\s?a\s?r\s?[a-z]*)\)?\s', ft2_item).group(0).strip()
        except:
            impact_length = "ERROR"
        impact_length_missing = 0
    elif (len(is_negative) != 0 or len(is_positive) != 0) and len(have_length) == 0:
        impact_length = "unknown"
        impact_length_missing = 1
    else:
        impact_length = "unknown"
        impact_length_missing = 2
        
    # clear up the number of acreage being impacted
    impact_number = impact_number.replace(" ", "").replace("-", "").replace(",", "")
    
    return {"impact_number": impact_number, 
            "impact_unit": impact_unit, 
            "impact_number_type": impact_type, 
            "impact_condition": impact_condition,
            "impact_duration": impact_length,
            "impact_duration_missing": impact_length_missing}




def lf_type_term(lf_item):
    """
    Draw linear feet impacted, impacted type, and impacted time length 
    """

    # Pull the impacted number regardless of the impact is negative/positive
    try:
        impact_number = re.search(r'[^A-Za-z]+(?=linear)', lf_item).group()
    except:
        impact_number = "ERROR"
    impact_unit = "linear feet"
    
    # type of impacted areas: stream;shortline;water
    have_type = re.findall(r'(s\s?t\s?r\s?e\s?a\s?m|s\s?h\s?o\s?r\s?t\s?l\s?i\s?n\s?e|w\s?a\s?t\s?e\s?r)', lf_item)

    # type of impacted areas
    if len(have_type) != 0:
        try:
            impact_type = re.search(
                r'' + impact_number + '.*?of(impacts\sto)?(.*?(s\s?t\s?r\s?e\s?a\s?m|s\s?h\s?o\s?r\s?t\s?l\s?i\s?n\s?e|w\s?a\s?t\s?e\s?r))',
                lf_item).group(2).strip()
        except:
            impact_type = "ERROR"
    else:
        impact_type = "project size"
    
    # Negative: impact/affect/loss/fill/excavate/drege
    is_negative = re.findall(r'i\s?m\s?p\s?a\s?c\s?t|a\s?f\s?f\s?e\s?c\s?t|l\s?o\s?s\s?s|f\s?i\s?l\s?l|e\s?x\s?c\s?a\s?v\s?a|d\s?r\s?e\s?d\s?g', lf_item)
    # Postive: benefit/benefical/preserve/preservation/create
    is_positive = re.findall(r'(b\s?e\s?n\s?e\s?f|p\s?r\s?e\s?s\s?e\s?r\s?v|c\s?r\s?e\s?a\s?t)', lf_item)
    # Avioded: aviod
    is_avoid = re.findall(r'\sa\s?v\s?o\s?i\s?d', lf_item)
    
    ## negative key words only: 
    if len(is_negative) != 0 and len(is_positive) == 0:
        impact_condition = "negative"
        if "credit" in lf_item:
            impact_condition = "negative, compensate by purchasing credits from the mitigation bank"

    ## positive key words only:
    elif len(is_negative) == 0 and len(is_positive) != 0:
        impact_condition = "positive"

    ## A sentence might have both positive/negative words, in different parts separatly:
    elif len(is_negative) != 0 and len(is_positive) != 0:
        impact_condition = "manually review required"

    ## This part of sentence doesn't have any verbs indicating negative/positive impacts
    else: # len(is_negative) == 0 and len(is_positive) == 0
        impact_condition = "same as previous/later one"
    
    # Project size usually comes along with "fill", but the impacy should be neutral
    if impact_type == "project size":
        impact_condition = "neutral"
        
    if len(is_avoid) != 0:
        impact_condition = "avoided"

    # If the impact is permanent or temperary
    have_length = re.findall(r'(p\s?e\s?r\s?m\s?a\s?n\s?e\s?n\s?t|t\s?e\s?m\s?p\s?o\s?r\s?a\s?r)', lf_item)
    
    if  (len(is_negative) != 0 or len(is_positive) != 0) and len(have_length) != 0:
        try:
            impact_length = re.search(r'(p\s?e\s?r\s?m\s?a\s?n\s?e\s?n\s?t\s?[a-z]*|t\s?e\s?m\s?p\s?o\s?r\s?a\s?r\s?[a-z]*)\)?\s', lf_item).group(0).strip()
        except:
            impact_length = "ERROR"
        impact_length_missing = 0
    elif (len(is_negative) != 0 or len(is_positive) != 0) and len(have_length) == 0:
        impact_length = "unknown"
        impact_length_missing = 1
    else:
        impact_length = "unknown"
        impact_length_missing = 2

    # clear up the number of acreage being impacted
    impact_number = impact_number.replace(" ", "").replace("-", "").replace(",", "")
    
    return {"impact_number": impact_number, 
            "impact_unit": impact_unit, 
            "impact_number_type": impact_type, 
            "impact_condition": impact_condition,
            "impact_duration": impact_length,
            "impact_duration_missing": impact_length_missing}




def get_pdf_impact(pdf_character):
    """
    Get impacted acreage
    """
    # Split character of work into sentences
    char_sent_list = re.findall(r'.*?\D\.', pdf_character)
    
    # Create a empty impact output list
    impact_output = []

    # Select sentences containing key words indicating impacts
    for char_sent in char_sent_list:
        
        # is_impact = re.findall(r'im\s?pact|affect|loss|excava|b\s?enef|preserv|creat', char_sent)
        # if len(is_impact) != 0:

        # Create empty impact output list of different units in each sentence
        acre_output = ft2_output = lf_output = []

        if "acre" in char_sent:

            # Break one sentence into pieces with each piece having one subject, one verb, and one object
            acre_list = re.findall(r'(.*?\d*,?\d*\s?\.?\s?\d*-?\s?acres?.+?\D(,|\.|\sand)[A-Za-z\s]*)', char_sent)
            # For each piece, pull the number, impacted type, and impacted time length
            acre_output = acre_output + [acre_type_term(x[0]) for x in acre_list]

        if any(w in char_sent for w in ["square", "ft2"]):

            # Break one sentence into pieces with each piece having one subject, one verb, and one object
            ft2_list = re.findall(r'(.*?\d*,?\d*\s?\.?\s?\d*-?\s?(square)?-?\s?f[eo]*t2?.+?\D(,|\.|\sand)[A-Za-z\s]*)', char_sent)
            # For each piece, pull the number, impacted type, and impacted time length
            ft2_output = ft2_output + [ft2_type_term(x[0]) for x in ft2_list]

        if "linear" in char_sent:

             # Break one sentence into pieces with each piece having one subject, one verb, and one object
            lf_list = re.findall(r'(.*?\d*,?\d*\s?\.?\s?\d*-?\s?linear\sfe?e?t.+?\D(,|\.|\sand)[A-Za-z\s]*)', char_sent)
            # For each piece, pull the number, impacted type, and impacted time length
            lf_output = lf_output + [lf_type_term(x[0]) for x in lf_list]

        # The impact time length and for this text piece might be found in other text piece: eg. permanently impact xxx, xxx, and xxx
        if len(acre_output + ft2_output + lf_output) != 0:
            impact_df = pd.DataFrame(acre_output + ft2_output + lf_output)

            # "temporarily impact a and b", impact time length of a and b should be "temporary"
            if any(n == 0 for n in impact_df["impact_duration_missing"]):
                for r in range(len(impact_df)):
                    if impact_df.loc[r, "impact_duration_missing"] == 2:
                        impact_df.loc[r, "impact_duration"] = impact_df[impact_df["impact_duration_missing"] == 0].reset_index().loc[0, "impact_duration"]

            # "impact/preserve a and b", a and b should be both negatively/positively impacted
            if any(n != "same as previous/later one" for n in impact_df["impact_condition"]):
                for r in range(len(impact_df)):
                    if impact_df.loc[r, "impact_condition"] == "same as previous/later one":
                        impact_df.loc[r, "impact_condition"] = impact_df[impact_df["impact_condition"] != "same as previous/later one"].reset_index().loc[0, "impact_condition"]
            else:
                for r in range(len(impact_df)):
                    impact_df.loc[r, "impact_condition"] = "unknown"

            impact_output = impact_output + impact_df.drop("impact_duration_missing", axis = 1).to_dict("records")
            
    return impact_output




# Others

def get_wqc(pdf_text):
    """
    Get the Water Quality Certificant
    """
    
    if pdf_text.find("WQC") != -1:
        try:
            wqc = re.search(r'(?<=WQC)[\d\s\:]*-[\s\d]*', pdf_text).group().strip().replace(" ", "")
        except:
            wqc = "ERROR"
    else:
        wqc = "unknown"
    return wqc




def get_coastal_use_permit(pdf_text):
    """
    Get the coastal use permit numbers
    """
    
    if pdf_text.find("Natural Resource’s Coastal Resources Program") != -1:
        try:
            coastal_use_permit_list = re.findall(r'P\d{8}', pdf_text)
            coastal_use_permit = ", ".join(coastal_use_permit_list)
        except:
            coastal_use_permit = "ERROR"
    else:
        coastal_use_permit = "unknown"
        
    return coastal_use_permit

    
    
    
# FINAL FUNCTION (COMBINED)

def pdf_extraction(pdf_url, tesseract_path = "C:/Program Files/Tesseract-OCR/tesseract.exe"):
    """
    This function consists of all the components above to extract fields from the public notice pdf.
    """
    # print(pdf_url)
    
    # PDF url exists
    if pd.isnull(pdf_url) == False:
        
        # Identify the district
        try:
            district = re.search(r'www\.(.*?)\.usace', pdf_url).group(1)
        except:
             # The pdf url for Jacksonville is unique: do not contain district abbreviation
            district = "saj"

        district_dic = {"MVN": "New Orleans District",
                   "SWG": "Galveston District",
                   "SAM": "Mobile District",
                   "SAJ": "Jacksonville District"}

        pdf_dist_code = district.upper()
        pdf_dist_name = district_dic[pdf_dist_code]
        
        pdf_text = pdf_read(pdf_url, district)
        if isinstance(pdf_text, str) == False:
            pdf_text = "ERROR"
            
        if len(pdf_text) == 0:
            try:
                pdf_text = OCR(pdf_url, tesseract_path)
            except:
                pdf_text = "ERROR"

        # No PDF reader problem
        if pdf_text != "ERROR": 

            pdf_trimmed = trim_pdf(pdf_text, district)

            comment_window = get_comment_window(pdf_text, district)

            pdf_app_num = get_pdf_app_num(pdf_text, district)

            pdf_manager = get_pdf_manager(pdf_text, district)

            pdf_applicant = get_pdf_applicant(pdf_text, district)

            pdf_location = get_pdf_location(pdf_text, district)

            pdf_character = get_pdf_character(pdf_text, district)

            pdf_mitigation = get_pdf_mitigation(pdf_text, district)

            wqc = get_wqc(pdf_text)

            cup = get_coastal_use_permit(pdf_text)

            if pdf_location == "unknown":
                hydrologic_unit_code = county = city = parish = "unknown"
            elif "ERROR" in pdf_location:
                hydrologic_unit_code = county = city = parish = "ERROR: cannot extract location of work"
            else:
                hydrologic_unit_code = get_pdf_hydrologic(pdf_location)
                county = get_pdf_city_county_parish(pdf_location)[0]
                parish = get_pdf_city_county_parish(pdf_location)[1]
                city = get_pdf_city_county_parish(pdf_location)[2]

            lon = get_lon_lat(pdf_text)["lon"]
            lat = get_lon_lat(pdf_text)["lat"]

            if pdf_character == "unknown":
                impact_output = "unknown"
            elif "ERROR" in pdf_character:
                impact_output = "ERROR: cannot extract character of work " + pdf_character
            else:
                impact_output = get_pdf_impact(pdf_character)

            # Special public notice
            if any(w in pdf_text for w in ["Special Public Notice", "SPECIAL"]):
                special = 1
                if "ERROR" in pdf_app_num:
                    pdf_app_num = "unknown"
            else:
                if all(item == "unknown" for item in [pdf_applicant["pdf_applicant_contents"], pdf_location, pdf_character, pdf_mitigation]):
                    special = 1
                    if "ERROR" in pdf_app_num:
                        pdf_app_num = "unknown"
                else:
                    special = 0
     
        # PDF reader problem
        else:
            special = "ERROR: fail to read pdf"
            pdf_app_num = pdf_dist_code = pdf_dist_name = "ERROR: fail to read pdf"
            pdf_manager = {"manager_name":"ERROR: fail to read pdf",
                           "manager_phone":"ERROR: fail to read pdf",
                           "manager_email": "ERROR: fail to read pdf"}
            pdf_applicant = {"pdf_applicant_contents":"ERROR: fail to read pdf",
                             "applicant":"ERROR: fail to read pdf",
                             "contractor": "ERROR: fail to read pdf"}
            comment_window = pdf_location = pdf_character = pdf_mitigation = county = parish = city = hydrologic_unit_code = lon = lat = wqc = cup = "ERROR: fail to read pdf"
            impact_output = "ERROR: fail to read pdf"
            pdf_text = "ERROR: fail to read pdf"
            pdf_trimmed = "ERROR: fail to read pdf"
    
    # Do not have pdf url
    else:
        special = 1
        pdf_app_num = pdf_dist_code = pdf_dist_name = "unknown"
        pdf_manager = {"manager_name":"unknown",
                       "manager_phone":"unknown",
                       "manager_email": "unknown"}
        pdf_applicant = {"pdf_applicant_contents":"unknown",
                         "applicant":"unknown",
                         "contractor": "unknown"}
        comment_window = pdf_location = pdf_character = pdf_mitigation = county = parish = city = hydrologic_unit_code = lon = lat = wqc = cup = "unknown"
        impact_output = "unknown"
        pdf_text = "unknown"
        pdf_trimmed = "unknown"
        
    # print(pdf_app_num)
        
    return {'specialFlag': special,
            'pdf_comment_window': comment_window,                           
            'usacePermitNumber': pdf_app_num,
            'pdf_districtCode':  pdf_dist_code,
            'pdf_districtName': pdf_dist_name,
            'name': pdf_manager["manager_name"],
            'phone': pdf_manager["manager_phone"],
            'email': pdf_manager["manager_email"],
            'applicantDetails': pdf_applicant["pdf_applicant_contents"],
            'applicantCompanyName': pdf_applicant["applicant"],
            'applicantContractorName': pdf_applicant["contractor"],
            'pdf_location': pdf_location, 
            'pdf_longitude': lon,
            'pdf_latitude': lat,
            'pdf_county': county,
            'pdf_parish': parish,
            'pdf_city': city,
            'pdf_character': pdf_character, 
            'pdf_mitigation': pdf_mitigation,
            'hydrologicUnitCode': hydrologic_unit_code, 
            'pdf_wqc': wqc,
            'pdf_cup': cup,
            'pdf_impact': impact_output,
            'pdf_full_text': pdf_text,
            'pdf_trimmed': pdf_trimmed}  


    
def pdf_to_aws(aws_access_key_id, aws_secret_access_key, web_url, pdf_url, notice_id):
    
    # Download PDFs
    try:
        pdf_bytes = requests.get(pdf_url).content
    except:
        pdf_bytes = "ERROR"
        print(pdf_url)
        
    # Identify the district
    district = pdf_url[12:15]
    
    # For Galveston where attachment PDF has a separate link
    if district == "swg":
        
        ## 1. Extract the attachment link
        try:
            req = requests.get(web_url)
            content = req.text
            soup = BeautifulSoup(content, 'html.parser')
            attachment_end = soup.find("div", {"itemprop":"articleBody"}).p.find_all("a")[1].get("href")
        except:
            attachment_end = "ERROR"
            print(web_url)

        if "ERROR" not in attachment_end:
            attachment_url = web_url[:30] + attachment_end
        else:
            attachment_url = "ERROR"

        ## 2. Merge main text PDF with attachment PDF
        if "ERROR" not in attachment_url:
            try:
                attachment_bytes = requests.get(attachment_url).content
            except:
                attachment_bytes = "ERROR"
                print(web_url)
        else:
            attachment_bytes = "ERROR"

        if pdf_bytes != "ERROR" and attachment_bytes != "ERROR":
            try:
                merged_pdf = pdf.PdfMerger()
                merged_pdf.append(io.BytesIO(pdf_bytes))
                merged_pdf.append(io.BytesIO(attachment_bytes))
                merged_bytes = io.BytesIO()
                merged_pdf.write(merged_bytes)
                merged_bytes.seek(0)
                pdf_bytes = merged_bytes.read()
            except:
                pdf_bytes = "ERROR"
                print(web_url)
        else:
            pdf_bytes = "ERROR"

    # Set up the id and key
    client = boto3.client(
        's3',
        aws_access_key_id = aws_access_key_id,
        aws_secret_access_key = aws_secret_access_key)
    
    if pdf_bytes != "ERROR":
        client.put_object(
            Body = pdf_bytes, 
            Bucket = "usace-notices", 
            Key = "full-pdf/" + notice_id + '.pdf', 
            ACL = "public-read")
        
    aws_link = "https://usace-notices.s3.amazonaws.com/full-pdf/" + notice_id + ".pdf"
    
    time.sleep(1)
    
    return {"noticeID": notice_id,
            "awsLink": aws_link}

    # Extract images in the attachment
        # pdf_reader = pdf.PdfReader(io.BytesIO(pdf_bytes))
        # for p in range(len(pdf_reader.pages)):
        #     pdf_page = pdf_reader.pages[p]
        #     if p != 0 and len(pdf_page.images) != 0:
        #         open("test/" + str(p) + ".png", "wb").write(pdf_page.images[0].data)

        
        
        
        
        
        
        
        
        
def pdf_extraction_test(pdf_url, pdf_text):
    """
    This function consists of all the components above to extract fields from the public notice pdf.
    """
    # print(pdf_url)
    
    # PDF url exists
    if len(str(pdf_url)) > 0 and len(re.findall(r'[Pp]\s?[Uu]\s?[Bb]\s?[Ll]\s?[Ii]\s?[Cc]\s{0,2}[N]\s?[Oo]\s?[Tt]\s?[Ii]\s?[Cc]\s?[Ee]', str(pdf_text))) != 0: 
        
        # Identify the district
        try:
            district = re.search(r'www\.(.*?)\.usace', pdf_url).group(1)
        except:
             # The pdf url for Jacksonville is unique: do not contain district abbreviation
            district = "saj"

        district_dic = {"MVN": "New Orleans District",
                   "SWG": "Galveston District",
                   "SAM": "Mobile District",
                   "SAJ": "Jacksonville District"}

        pdf_dist_code = district.upper()
        pdf_dist_name = district_dic[pdf_dist_code]
        
        # pdf_text = pdf_read(pdf_url, district)
        if isinstance(pdf_text, str) == False:
            pdf_text = "ERROR"
            
        if len(pdf_text) == 0:
            try:
                pdf_text = OCR(pdf_url, tesseract_path)
            except:
                pdf_text = "ERROR"

        # No PDF reader problem
        if pdf_text != "ERROR": 

            pdf_trimmed = trim_pdf(pdf_text, district)

            comment_window = get_comment_window(pdf_text, district)

            pdf_app_num = get_pdf_app_num(pdf_text, district)

            pdf_manager = get_pdf_manager(pdf_text, district)

            pdf_applicant = get_pdf_applicant(pdf_text, district)

            pdf_location = get_pdf_location(pdf_text, district)

            pdf_character = get_pdf_character(pdf_text, district)

            pdf_mitigation = get_pdf_mitigation(pdf_text, district)

            wqc = get_wqc(pdf_text)

            cup = get_coastal_use_permit(pdf_text)

            if pdf_location == "unknown":
                hydrologic_unit_code = county = city = parish = "unknown"
            elif "ERROR" in pdf_location:
                hydrologic_unit_code = county = city = parish = "ERROR: cannot extract location of work"
            else:
                hydrologic_unit_code = get_pdf_hydrologic(pdf_location)
                county = get_pdf_city_county_parish(pdf_location)[0]
                parish = get_pdf_city_county_parish(pdf_location)[1]
                city = get_pdf_city_county_parish(pdf_location)[2]

            lon = get_lon_lat(pdf_text)["lon"]
            lat = get_lon_lat(pdf_text)["lat"]

            if pdf_character == "unknown":
                impact_output = "unknown"
            elif "ERROR" in pdf_character:
                impact_output = "ERROR: cannot extract character of work " + pdf_character
            else:
                impact_output = get_pdf_impact(pdf_character)

            # Special public notice
            if any(w in pdf_text for w in ["Special Public Notice", "SPECIAL"]):
                special = 1
                if "ERROR" in pdf_app_num:
                    pdf_app_num = "unknown"
            else:
                if all(item == "unknown" for item in [pdf_applicant["pdf_applicant_contents"], pdf_location, pdf_character, pdf_mitigation]):
                    special = 1
                    if "ERROR" in pdf_app_num:
                        pdf_app_num = "unknown"
                else:
                    special = 0
     
        # PDF reader problem
        else:
            special = "ERROR: fail to read pdf"
            pdf_app_num = pdf_dist_code = pdf_dist_name = "ERROR: fail to read pdf"
            pdf_manager = {"manager_name":"ERROR: fail to read pdf",
                           "manager_phone":"ERROR: fail to read pdf",
                           "manager_email": "ERROR: fail to read pdf"}
            pdf_applicant = {"pdf_applicant_contents":"ERROR: fail to read pdf",
                             "applicant":"ERROR: fail to read pdf",
                             "contractor": "ERROR: fail to read pdf"}
            comment_window = pdf_location = pdf_character = pdf_mitigation = county = parish = city = hydrologic_unit_code = lon = lat = wqc = cup = "ERROR: fail to read pdf"
            impact_output = "ERROR: fail to read pdf"
            # pdf_text = "ERROR: fail to read pdf"
            pdf_trimmed = "ERROR: fail to read pdf"
    
    # Do not have pdf url
    else:
        special = 1
        pdf_app_num = pdf_dist_code = pdf_dist_name = "unknown"
        pdf_manager = {"manager_name":"unknown",
                       "manager_phone":"unknown",
                       "manager_email": "unknown"}
        pdf_applicant = {"pdf_applicant_contents":"unknown",
                         "applicant":"unknown",
                         "contractor": "unknown"}
        comment_window = pdf_location = pdf_character = pdf_mitigation = county = parish = city = hydrologic_unit_code = lon = lat = wqc = cup = "unknown"
        impact_output = "unknown"
        # pdf_text = "unknown"
        pdf_trimmed = "unknown"
        
    # print(pdf_app_num)
        
    return {'specialFlag': special,
            'pdf_comment_window': comment_window,                           
            'usacePermitNumber': pdf_app_num,
            'pdf_districtCode':  pdf_dist_code,
            'pdf_districtName': pdf_dist_name,
            'name': pdf_manager["manager_name"],
            'phone': pdf_manager["manager_phone"],
            'email': pdf_manager["manager_email"],
            'applicantDetails': pdf_applicant["pdf_applicant_contents"],
            'applicantCompanyName': pdf_applicant["applicant"],
            'applicantContractorName': pdf_applicant["contractor"],
            'pdf_location': pdf_location, 
            'pdf_longitude': lon,
            'pdf_latitude': lat,
            'pdf_county': county,
            'pdf_parish': parish,
            'pdf_city': city,
            'pdf_character': pdf_character, 
            'pdf_mitigation': pdf_mitigation,
            'hydrologicUnitCode': hydrologic_unit_code, 
            'pdf_wqc': wqc,
            'pdf_cup': cup,
            'pdf_impact': impact_output,
            # 'pdf_full_text': pdf_text,
            'pdf_trimmed': pdf_trimmed}       