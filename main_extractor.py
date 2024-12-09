import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import io
import re
import scrape_rss_webpage
import scrape_pdf
import ast
import os
import tiktoken
# import redivis
import sys
import time
from tqdm import tqdm
from datetime import datetime
import glob
import tempfile
from IPython.core.interactiveshell import InteractiveShell
InteractiveShell.ast_node_interactivity = "all"

from llmFunctions import getDocumentAbstractiveSummary
#from llmFunctions import sent_regex_extraction
from llmFunctions import openAIfunc_wetland, openAIfunc_project, openai_embed, dict_to_columns

import pathlib
import os
import logging
import boto3

#set temp directory
# temp_path = r'tempdir/'
# tempfile.tempdir=temp_path
# assert tempfile.gettempdir() == temp_path

# Run the process that exports to the temp dir

def restart_or_update(aws_client, update, n_days, max_notices, logging, district = "all", tesseract_path = None): # redivis_dataset
    """
    Generate the main scraping results
    
    update: 1, update; 0, first-time-scraping; default as 1
    n_days: numeric; notices published in the past n days; default as 100
    district: "New Orleans", "Galveston", "Jacksonville", or "Mobile"; default as "all"
    """
    
    # (1) A list of notice webpage links and titles
    
    # First-time scraping: scrape the USACE website to get a list of notice webpage links
    if update == 0:
        weblist = scrape_rss_webpage.get_weblist(district)
        print(f"{len(weblist)} public notices captured")
    
    # Update scraping: scrape the RSS feed to get new notice webpage links
    if update == 1:

        # A. Get current version of data from Redivis
        
        # ## Set up the reference to Redivis and get as df
        # scraped_notices = redivis_dataset.table("main_notices").to_pandas_dataframe(variables = ["noticeID", "usaceWebUrl", "datePublished"],
                                                                                    # progress=False)
        
        # ## Set up the reference to AWS S3
        response = aws_client.get_object(Bucket = "usace-notices",
                                         Key = "dashboard-data/main_df.csv")

        content = response['Body'].read()
        scraped_notices = pd.read_csv(io.BytesIO(content))
        
        print(f"The number of notices found on the existing main table is {len(scraped_notices)}")
        scraped_notices_list = scraped_notices["usaceWebUrl"].to_list()
            
        ## option 2-download csv from redivis to dir

        # Perform a query on the Demo CMS Medicare data. Table at https://redivis.com/demo/datasets/1754/tables
        # query = redivis.query("""
        #     SELECT *
        #       FROM `portugalmo.usaceData.main_notices`
        # """)
        # scraped_notices = query.to_dataframe()
        # redivis_dataset.table("main_notices").download_files(path=r'tempdir/', progress=True)
        # scraped_notices=pd.read_csv(r'tempdir/main_notices.csv')

        # B. Scrape the RSS feed to get the most recent notices
        weblist_ndays = scrape_rss_webpage.update_weblist_from_rss(district, n_days)
        print(f"The number of notices retreived in date range: {len(weblist_ndays)}.")

        # C. Subset the most recent notices to only those that are not in database already
        weblist = weblist_ndays[~weblist_ndays["usaceWebUrl"].isin(scraped_notices_list)]
        #PRINT NEW NOTICES
        print(f'Notices published in date range not found in S3 bucket = {len(weblist)}')
        
        # D. Check if the there are more notices updated in the past n days than the maxmium notices set in the configuration
        if len(weblist) > max_notices:
            warning_message = f"Notices updated ({len(weblist)}) are more than the maximum notices set in the configuration ({max_notices})"
            print(f"WARNING: {warning_message}")
            # Log the warning message to the file
            logging.warning(warning_message)

    # no new notices
    if len(weblist) == 0:
        print("Exiting program, no new notices")
        sys.exit()

    # (2) Scrape the webpage for each public notice to get more detailed information
    
    webpage = pd.DataFrame([scrape_rss_webpage.web_extraction(x, update) for x in weblist["usaceWebUrl"]])
    
    # Merge with weblist table
    webpage = weblist.reset_index(drop = True).join(webpage)
    
    # sort by date
    webpage = webpage.sort_values(by='datePublished', ascending=False)

    # subset to max_notices - number of newest notices
    # webpage = webpage.head(max_notices)
    webpage = webpage[:max_notices]
    print('Notices to process =', webpage.shape[0])

    # (3) Scrape the PDF of each notice
    
    # Scrape the pdf for each public notice
    pdf = pd.DataFrame([scrape_pdf.pdf_extraction(webpage.loc[x, "PdfUrl"], webpage.loc[x, "web_text"], webpage.loc[x, "web_title"], tesseract_path) for x in webpage.index])

    # # Merge with weblist and webpage table
    df_base = webpage.reset_index(drop = True).join(pdf)
    
    return df_base




def data_schema_preprocess(df_base, aws_client, GPT_MODEL): # redivis_dataset
    """
    Proprocess the raw scraping data: remove all unknowns and generate noticeID
    """
    
    ## A.  Replace all ERRORs
    df = df_base.map(lambda x: "unknown" if "ERROR" in str(x) else x)

    ## B. Replace all NAs
    df.fillna('unknown', inplace=True)

    ## C. Create the primary key column noticeID
    
    ### get all the noticeID in Redivis
    # scraped_notices = redivis_dataset.table("main_notices").to_pandas_dataframe(variables = ["noticeID", "usaceWebUrl", "datePublished"],
                                                                                # progress=False)    
        
    ### get all the noticeID in AWS S3 main_df
    response = aws_client.get_object(Bucket = "usace-notices",
                                     Key = "dashboard-data/main_df.csv")

    content = response['Body'].read()
    scraped_notices = pd.read_csv(io.BytesIO(content))

    ### find the most latest noticeID
    noticeID_start_on = max([int(re.sub(r'Notice_NO_', "", id_num)) for id_num in scraped_notices["noticeID"]]) + 1
    df['noticeID'] = 'Notice_NO_' + (df.index + noticeID_start_on).astype(str)

    #E D. Generate column of token counts
    #encoding = tiktoken.encoding_for_model(GPT_MODEL)
    encoding= tiktoken.get_encoding("cl100k_base")
    
    # Count the number of tokens
    df['tokens'] = df['pdf_character'].apply(lambda x: len(encoding.encode(x)))
    
    ## E. Drop if all errors or unknowns
    
    # List of columns to exclude from the check
    exclude_columns = ['error', 'noticeID', 'tokens']

    # List of columns to include in the check
    check_columns = [col for col in df.columns if col not in exclude_columns]

    # Create a boolean mask for rows where all columns in check_columns are 'unknown'
    mask = df[check_columns].apply(lambda row: all(row == 'unknown'), axis=1)

    # Filter out rows where the mask is True
    df = df[~mask]

    return df

#Global variable for the 3 Azure/OpenAI functions
batch_size = 10

def data_schema_summarization(df, price_cap, AZURE_ENDPOINT, AZURE_API_KEY, aws_client, n_sentences, logging): #redivis_dataset
    """
    # Pricing - https://azure.microsoft.com/en-us/pricing/details/cognitive-services/language-service/
    # $2 for 1000 text records - 1000 character units
    # ==> $2 for 1,000,000 characters
    # ==> Price per character = $ 0.000002
    """
    print('Starting Azure summarization...')
    # Subset df to a full text table
    fulltext_df = df[['noticeID' ,'pdf_full_text', 'pdf_trimmed']].copy()
    fulltext_df = fulltext_df[~(fulltext_df.pdf_full_text=="unknown")].copy()


    # Create rowID (Redivis ver)
    # fulltext_df_redivis = redivis_dataset.table("fulltext").to_pandas_dataframe(variables = ["rowID"], progress=False)
    # fulltext_df['rowID'] = fulltext_df.reset_index().index + fulltext_df_redivis.shape[0] + 1
    
    # Create rowID (AWS ver)
    response = aws_client.get_object(Bucket = "usace-notices", Key = "dashboard-data/fulltext_df.csv")
    content = response['Body'].read()
    fulltext_existing_row = len(pd.read_csv(io.BytesIO(content)))
    fulltext_df['rowID'] = fulltext_df.reset_index().index + fulltext_existing_row + 1
    
    # Initialize an empty DataFrame to hold the summaries
    summary_df = pd.DataFrame()

    # Create the batches
    #batch_size = 10
    grouped = [fulltext_df[i:i + batch_size] for i in range(0, fulltext_df.shape[0], batch_size)]

    # Calculate characters
    character_count_all = 0

    # Price per character and maximum cost
    price_per_character = 0.0000027
    
    # Process each batch
    for i, batch in enumerate(grouped):
        try:
            print(f'Processing batch {i}')

            # Assuming getDocumentAbstractiveSummary() is a predefined function
            # batch['short_summary'] = [getDocumentAbstractiveSummary(x, 
            #                                                         endpoint=AZURE_ENDPOINT, 
            #                                                         key=AZURE_API_KEY, 
            #                                                         sentenceCount=n_sentences) for x in batch['pdf_trimmed']]
            batch['short_summary'] = batch['pdf_trimmed'].apply(lambda x: getDocumentAbstractiveSummary(x, 
                                                                                                        endpoint=AZURE_ENDPOINT, 
                                                                                                        key=AZURE_API_KEY, 
                                                                                                        sentenceCount=n_sentences))

            # Concatenate the processed batch to the final DataFrame
            summary_df = pd.concat([summary_df, batch], ignore_index=True)

            character_count_batch = sum([len(x) for x in batch['pdf_trimmed']])
            character_count_all += character_count_batch

            # Calculate total cost and check against the maximum cost
            total_cost = character_count_all * price_per_character
            
            # Print the character count and total cost after every 2 batches
            if (i + 1) % 2 == 0:
                print(f"After batch {i}, total characters: {character_count_all}, Total cost: ${total_cost:.6f}")
            
            if total_cost >= 0.95 * price_cap:
                print("95% of pre-set price cap exceeded")

        except Exception as e:
            error_message = f'Batch {i} failed to process due to: {e}'
            print(error_message)
            logging.error(error_message)

    # Optional: Drop the "pdf_full_text" column if you no longer need it in the final DataFrame
    summary_df = summary_df.drop(columns=["pdf_full_text", "pdf_trimmed"])
    
    # Clean special characters in the fulltext_df (do no remove special character before summarization to avoid generating misleading info)
    fulltext_df = clean_special_characters(fulltext_df, ['pdf_full_text', 'pdf_trimmed'])
    summary_df['short_summary'] = summary_df['short_summary'].str.replace('\\n', '', regex=True)

    return {"fulltext_df": fulltext_df,
            "summary_df": summary_df}

    
    
        
def data_schema_impact(df, GPT_MODEL_SET, OPENAI_API_KEY, aws_client, logging): #redivis_dataset
    """
    Apply LLM to extract the information about the impacts on wetlands
    """
    print('Starting OpenAI extraction...')
    
    # subset to character of work or proposed work column
    wetland_df = df[['noticeID' ,'pdf_character']].copy()
    wetland_df = wetland_df[~(wetland_df.pdf_character=="unknown")].copy()
    
    ## A. Generate a column with a dictionary of results 
    
    t1 = time.time()

    ### Initialize an empty list to hold the DataFrames
    processed_batches = []

    ### Create the batches
    #batch_size = 10
    grouped = [wetland_df[i:i + batch_size] for i in range(0, wetland_df.shape[0], batch_size)]

    ### Process each batch
    for i, batch in enumerate(tqdm(grouped, desc="Processing batches")):
        try:
            print(f'Processing batch {i}')

            # LLM - wetland impact
            batch['wetland_llm_dict'] = batch['pdf_character'].apply(lambda x: openAIfunc_wetland(x, 
                                                                                                  API_KEY=OPENAI_API_KEY, 
                                                                                                  GPT_MODEL=GPT_MODEL_SET))

            # Append the processed batch to the list
            processed_batches.append(batch)

        except Exception as e:
            error_message = f'Batch {i} failed to process due to: {e}'
            print(error_message)
            logging.error(error_message)

    ### Concatenate all processed batches to form the final DataFrame
    wetland_impact_df = pd.concat(processed_batches, ignore_index=True)

    # wetland_impact_df['rowID'] = wetland_impact_df.reset_index().index + 1

    t2 = time.time()
    print('Time taken:', np.round(t2-t1, 3), 'seconds')
    
    
    ## B. Break out dictionary to columns
    
    #wetland_impact_df2 = dict_to_columns(df_source=wetland_impact_df, dict_col='wetland_llm_dict', index_cols=['noticeID', 'rowID'])
    wetland_impact_df2 = dict_to_columns(df_source=wetland_impact_df, dict_col='wetland_llm_dict', index_cols=['noticeID'])

    # round 1 - a number (may contain .) and a string , if the string is same as the word in impact_unit, remove string
    # Extracting 'acres', 'sq. feet' etc
    wetland_impact_df2['impact_unit_2'] = wetland_impact_df2['impact_quantity'].str.extract(r'([a-zA-Z]+)')

    wetland_impact_df2['impact_unit_2'] = wetland_impact_df2.apply(
        lambda row: row['impact_unit_2']
        if pd.notnull(row['impact_unit_2']) and row['impact_unit'].lower() != 'unknown' and not any(word in row['impact_unit_2'] for word in str(row['impact_unit']).split())
        else None,
        axis=1
    )

    # Define a dictionary for replacements
    replacements = {
        r'\bacres\b': 'acres',
        r'\bacre\b': 'acres',
        r'square feet\.': 'square feet', #pending - fix this
        r'\bsq. feet\b': 'square feet',
        r'\bsq. ft\b': 'square feet', 
        r'\bsquare foot\b': 'square feet',
        r'\bft\b': 'feet',
        r'\bCubic Yards\b': 'cubic yards',
        r'\bcy\b': 'cubic yards',
        r'': 'unknown'
    }

    # Replace the values in the 'impact_unit' column
    wetland_impact_df2['impact_unit_clean'] = wetland_impact_df2['impact_unit'].replace(replacements, regex=True)

    # pd.DataFrame(wetland_impact_df2.impact_unit_clean.value_counts()).head(30)

    # List of specified units
    clean_units = ['acres', 'linear feet', 'square feet', 'unknown', 'cubic yards', 'feet', 'miles']

    # Replace values not in specified categories with 'other'
    wetland_impact_df2['impact_unit_clean'] = wetland_impact_df2['impact_unit_clean'].apply(lambda x: x if x in 
                                                                                            clean_units else 'other')
    
    # C. Cleaning
    
    # Extracting the number, handling commas, decimals, NaNs, and blanks
    wetland_impact_df2['impact_qty_num'] = wetland_impact_df2['impact_quantity'].str.extract(r'([\d,.]+)').replace(',', '', regex=True)
    wetland_impact_df2['impact_qty_num'] = pd.to_numeric(wetland_impact_df2['impact_qty_num'], errors='coerce')

    #replace 0.00 values
    wetland_impact_df2['impact_qty_num'] = wetland_impact_df2['impact_qty_num'].replace(0.00, np.nan)

    wetland_impact_df2 = wetland_impact_df2.drop(columns = ['impact_quantity', 'impact_unit', 'impact_unit_2'])

    # Check if the column 'area' exists in the DataFrame
    if 'area' in wetland_impact_df2.columns:
        # Drop the 'area' column
        wetland_impact_df2 = wetland_impact_df2.drop(columns=['area'])

    wetland_final_df = wetland_impact_df2.rename(columns={'impact_qty_num': 'impact_quantity', 'impact_unit_clean': 'impact_unit'})

    # Replace NAs to 'unknown' except impact_quantity, and remove rows that are unknown for all
    wetland_final_df = wetland_final_df.replace("", "unknown")
    wetland_final_df[["wetland_type", "impact_duration", "impact_type", "impact_unit"]] = wetland_final_df[["wetland_type", "impact_duration", "impact_type", "impact_unit"]].fillna('unknown', inplace=False)

    wetland_final_df = wetland_final_df[~((wetland_final_df.wetland_type == "unknown") &
                (wetland_final_df.impact_duration == "unknown") &
                (wetland_final_df.impact_type == "unknown") &
                (wetland_final_df.impact_unit == "unknown") &
                wetland_final_df.impact_quantity.isna())]

    # Generate rowID (Redivis ver)
    # wetland_impact_df_redivis = redivis_dataset.table("wetland_impact").to_pandas_dataframe(variables = ["rowID"], progress=False)
    # wetland_final_df['rowID'] = wetland_final_df.reset_index().index + wetland_impact_df_redivis.shape[0] + 1
    
    # Create rowID (AWS ver)
    response = aws_client.get_object(Bucket = "usace-notices", Key = "dashboard-data/wetland_final_df.csv")
    content = response['Body'].read()
    wetland_existing_row = len(pd.read_csv(io.BytesIO(content)))
    wetland_final_df['rowID'] = wetland_final_df.reset_index().index + wetland_existing_row + 1

    del wetland_df
    
    return {"wetland_impact_df": wetland_impact_df, 
            "wetland_final_df": wetland_final_df}




def data_schema_embeding(df, GPT_MODEL_SET, OPENAI_API_KEY, aws_client, logging): #redivis_dataset
    """
    Generate the project type and embedding table 
    """
    print('Starting OpenAI embedding...')
    
    # subset to the work of character and proposed work + count of tokens
    embed_df = df[['noticeID', 'pdf_character', 'tokens']].copy()
    embed_df = embed_df[embed_df.pdf_character != "unknown"]
    embed_df = embed_df[embed_df.tokens < 4000]
    
    t1 = time.time()

    # Create the batches
    #batch_size = 30
    grouped = [embed_df[i:i + batch_size] for i in range(0, embed_df.shape[0], batch_size)]

    # List to collect processed DataFrames
    processed_batches = []

    # Process each batch
    for i, batch in enumerate(tqdm(grouped, desc="Embedding batch")):
        try:
            print(f'Processing batch {i}')

            # Apply the openai_embed function and convert its output to DataFrame columns
            embed_columns = batch['pdf_character'].apply(lambda x: openai_embed(x, API_KEY=OPENAI_API_KEY)).apply(pd.Series)
            embed_columns.columns = ['embed_tokens', 'embeddings']  # Assuming the output is two columns

            # Apply the openAIfunc_project function
            project_llm_dict_series = batch['pdf_character'].apply(lambda x: openAIfunc_project(x, 
                                                                                                API_KEY=OPENAI_API_KEY, 
                                                                                                GPT_MODEL=GPT_MODEL_SET))

            # Concatenate the new columns to the batch
            batch = pd.concat([batch, project_llm_dict_series.apply(pd.Series), embed_columns], axis=1)

            # Add the processed batch to the list
            processed_batches.append(batch)

        except Exception as e:
            error_message = f'Batch {i} failed to process due to: {e}'
            print(error_message)
            logging.error(error_message)

    # Concatenate all processed batches into the final DataFrame
    embed_final_df = pd.concat(processed_batches, ignore_index=True)
    
    # print(embed_final_df.columns)

    # Replace NAs to 'unknown'
    embed_final_df = embed_final_df.replace("", "unknown")
    embed_final_df[["pdf_character", "project_detail", "total_project_area", "project_category"]] = embed_final_df[["pdf_character", "project_detail", "total_project_area", "project_category"]].fillna('unknown', inplace=False)

    # Generate ID (Redivis Ver)
    # embed_df_redivis = redivis_dataset.table("embed_project_type").to_pandas_dataframe(variables = ["rowID"], progress=False)
    # embed_final_df['rowID'] = embed_final_df.index + embed_df_redivis.shape[0] + 1
    
    # Create rowID (AWS ver)
    response = aws_client.get_object(Bucket = "usace-notices", Key = "dashboard-data/embed_final_df.csv")
    content = response['Body'].read()
    embed_existing_row = len(pd.read_csv(io.BytesIO(content)))
    embed_final_df['rowID'] = embed_final_df.reset_index().index + embed_existing_row + 1

    del embed_df

    t2 = time.time()
    print('Time taken:', np.round(t2-t1, 3), 'seconds')
    
    return {"embed_final_df": embed_final_df}




def clean_special_characters(df, columns, ascii_threshold=127):
    """
    Replace special characters and non-printable characters
    """
    
    # Initialize set for special characters
    special_chars = set()

    # Regular expression to find at least one letter
    pattern = re.compile('[a-zA-Z]')

    # Filter columns to only those that contain at least one letter
    filtered_columns = [col for col in columns if col in df.columns and df[col].astype(str).apply(lambda x: bool(pattern.search(x))).any()]

    # Collect all special characters from the specified filtered columns
    for col in filtered_columns:
        for value in df[col].astype(str):
            special_chars.update(char for char in value if ord(char) > ascii_threshold)

    # Check if special_chars is not empty
    if special_chars:
        # Create a regular expression pattern for all special characters
        special_chars_pattern = "[" + re.escape("".join(special_chars)) + "]"

        # Replace special characters in the filtered columns
        for col in filtered_columns:
            df[col] = df[col].astype(str).apply(lambda x: re.sub(special_chars_pattern, "?", x))
    # else:
        # If no special characters found, no replacement needed
        # print("No special characters found above the ASCII threshold.")
    
    # special_chars = list(special_chars)
    # print(len(special_chars), "special characters removed")
    
    # Define a regular expression to match non-printable characters
    non_printable_pattern = r'(\\t|\\n|\\r|\\b|\\f|\\v|\\xa0|\\xad)'

    # Iterate through the specified columns and replace non-printable characters
    for col in columns:
        df[col] = df[col].replace({non_printable_pattern: ''}, regex=True)
    
    return df




def data_schema(df, aws_client): # redivis_dataset
    """
    Process the base dataframe to several tables stored in Redivis database
    """
    print('Splitting tables by schema...')    
    # PREPROCESS
    # df = data_schema_preprocess(df_base)

    # (1) Store PDFs to AWS
    
    # Place pdf to AWS S3 bucket and generate a table with notice id and aws link
    aws_df = pd.DataFrame([scrape_pdf.pdf_to_aws(aws_client,
                                                 df.loc[index, "usaceWebUrl"],
                                                 df.loc[index, "PdfUrl"], 
                                                 df.loc[index, "noticeID"]) for index in df.index])
    
    # (2) Main table
    
    # Rename columns to match powerpoint dataset 
    main_df = df.copy()

    # List of columns to include
    columns_to_include = ['noticeID', 
                          'usacePermitNumber',
                          'usaceWebUrl',
                          'PdfUrl',
                          'datePublished',
                          'specialFlag',
                          'dateExpiry',
                          'applicantCompanyName',
                          'applicantContractorName',
                          'applicantDetails',
                          'hydrologicUnitCode']

    # Filter main_df to include only the specified columns
    main_df = main_df[columns_to_include]

    # Remove the "ERROR" and "NA" in hydrologicUnitCode
    main_df["hydrologicUnitCode"] = pd.to_numeric(main_df["hydrologicUnitCode"], downcast='integer', errors='coerce')

    
    
    # (3) Manager table
    
    manager_df = df[['noticeID' , 'name' ,'phone','email' ]].copy()

    # Check if phone number is valid
    def check_phone(phone):
        # Count the number of digits in the phone number
        digits = re.sub(r'\D', '', phone)  # Remove non-digit characters
        return "unknown" if len(digits) < 10 else phone

    manager_df['phone'] = manager_df['phone'].apply(check_phone)


    # Check if email is valid
    def check_email(email):

        # Check if email ends with 'WORD@usace.army.mil'
        if not re.search(r'\b\w+@usace\.army\.mil$', email):
            return "unknown"

        return email

    # Apply the function and update the email column
    manager_df['email'] = manager_df['email'].apply(check_email)

    # Remove rows where all columns are unknown
    manager_df = manager_df[~((manager_df['name'] == 'unknown') & 
                              (manager_df['phone'] == 'unknown') & 
                              (manager_df['email'] == 'unknown'))].copy()
    
    # Create rowID (Redivis ver)
    # manager_df_redivis = redivis_dataset.table("manager").to_pandas_dataframe(variables = ["rowID"], progress=False)
    # manager_df['rowID'] = manager_df.reset_index().index + manager_df_redivis.shape[0] + 1
    
    # Create rowID (AWS ver)
    response = aws_client.get_object(Bucket = "usace-notices", Key = "dashboard-data/manager_df.csv")
    content = response['Body'].read()
    manager_existing_row = len(pd.read_csv(io.BytesIO(content)))
    manager_df['rowID'] = manager_df.reset_index().index + manager_existing_row + 1
    
    
    
    # (4) Character of work / proposed work
    
    character_df = df[['noticeID' , 'web_character', 'pdf_character']].copy() 

    character_df = pd.melt(character_df, 
                           id_vars=['noticeID'], 
                           value_vars =  ['web_character', 'pdf_character'], 
                           var_name = 'source', 
                           value_name='text')

    character_df = character_df[~(character_df.text=="unknown")].copy()

    # Create rowID (Redivis ver)
    # character_df_redivis = redivis_dataset.table("character").to_pandas_dataframe(variables = ["rowID"], progress=False)
    # character_df['rowID'] = character_df.reset_index().index + character_df_redivis.shape[0] + 1
    
    # Create rowID (AWS ver)
    response = aws_client.get_object(Bucket = "usace-notices", Key = "dashboard-data/character_df.csv")
    content = response['Body'].read()
    character_existing_row = len(pd.read_csv(io.BytesIO(content)))
    character_df['rowID'] = character_df.reset_index().index + character_existing_row + 1
    
    
    
    # (5) Mitigation
    
    mitigation_df = df[['noticeID' , 'web_mitigation', 'pdf_mitigation']].copy()

    mitigation_df = pd.melt(mitigation_df, 
                            id_vars=['noticeID'], 
                            value_vars =  ['web_mitigation', 'pdf_mitigation'],
                            var_name = 'source', 
                            value_name='text')

    mitigation_df = mitigation_df[~(mitigation_df.text=="unknown")].copy()

    # Create rowID (Redivis ver)
    # mitigation_df_redivis = redivis_dataset.table("mitigation").to_pandas_dataframe(variables = ["rowID"], progress=False)
    # mitigation_df['rowID'] = mitigation_df.reset_index().index + mitigation_df_redivis.shape[0] + 1
    
    # Create rowID (AWS ver)
    response = aws_client.get_object(Bucket = "usace-notices", Key = "dashboard-data/mitigation_df.csv")
    content = response['Body'].read()
    mitigation_existing_row = len(pd.read_csv(io.BytesIO(content)))
    mitigation_df['rowID'] = mitigation_df.reset_index().index + mitigation_existing_row + 1


    
    # (6) Location
    
    location_df = df[['noticeID', 'pdf_districtCode', 'pdf_longitude', 'pdf_latitude', 'pdf_parish', 
                  'pdf_county' , 'pdf_city', 'pdf_districtName']].copy()

    location_df = pd.melt(location_df , 
                          id_vars = ['noticeID'],
                          value_vars = ['pdf_longitude', 'pdf_latitude', 'pdf_parish', 'pdf_county', 'pdf_city', 
                                        'pdf_districtCode', 'pdf_districtName'] , 
                          var_name = 'type', 
                          value_name='detail')

    location_df = location_df[~(location_df.detail=="unknown")].copy()

    # Create rowID (Redivis ver)
    # location_df_redivis = redivis_dataset.table("location").to_pandas_dataframe(variables = ["rowID"], progress=False)
    # location_df['rowID'] = location_df.reset_index().index + location_df_redivis.shape[0] + 1
    
    # Create rowID (AWS ver)
    response = aws_client.get_object(Bucket = "usace-notices", Key = "dashboard-data/location_df.csv")
    content = response['Body'].read()
    location_existing_row = len(pd.read_csv(io.BytesIO(content)))
    location_df['rowID'] = location_df.reset_index().index + location_existing_row + 1

    location_df['type'] = location_df['type'].str.split('_').str[-1]
      
    # Final Clean:
    
    main_df = clean_special_characters(main_df, ['usacePermitNumber', 'applicantCompanyName', 'applicantContractorName', 'applicantDetails'])
    manager_df = clean_special_characters(manager_df, ['name', 'phone', 'email'])
    character_df = clean_special_characters(character_df, ['text'])
    mitigation_df = clean_special_characters(mitigation_df, ['text'])
    location_df = clean_special_characters(location_df, ['detail'])
    
    return {
            "aws_df": aws_df, 
            "main_df": main_df, 
            "manager_df": manager_df, 
            "character_df": character_df, 
            "mitigation_df":mitigation_df, 
            "location_df":location_df, 
            # "fulltext_df":fulltext_df, 
            # "summary_df":summary_df, 
            # "wetland_final_df":wetland_final_df, 
            # "embed_final_df":embed_final_df,
            # "validation_df":validation_df
    }

def geocode(aws_client, new_locations): #dataset
    """
    This function looks for lat/longs that have yet to be geocoded (not just for new new notices but all notices). 
    It then geocodes them and returns it as a dataframe.
    """
    #Load needed tables (Redivis)
    ## Geocoded Locations
    # table = dataset.table("geocoded_locations:9jz4")
    # geocodedDf = table.to_pandas_dataframe(progress=False)

    ## All Locations
    # table = dataset.table("location:xvtg")
    # allDf = table.to_pandas_dataframe(progress=False)
    # allDf = pd.concat([allDf, new_locations], axis=0)
    
    #Load needed tables (AWS)
    ## Geocoded Locations
    response = aws_client.get_object(Bucket = "usace-notices",
                                     Key = "dashboard-data/geocoded_df.csv")

    content = response['Body'].read()
    geocodedDf = pd.read_csv(io.BytesIO(content))
    
    ## All Locations
    response = aws_client.get_object(Bucket = "usace-notices",
                                     Key = "dashboard-data/location_df.csv")

    content = response['Body'].read()
    allDf = pd.read_csv(io.BytesIO(content))
    allDf = pd.concat([allDf, new_locations], ignore_index=True)
    

    # Find all locations that should be geocoded
    types = ['latitude', 'longitude']
    locationMaster = allDf[allDf.type.isin(types)]

    def filterDetail(cell):
        """
        This function filters our errors and empty cells. 
        """

        if 'error' in cell or cell == '[]' or cell == 'unknown':
            return False
        else:
            return cell

    cleanLocations = [(filterDetail(d), n, t) for (d,n,t) in zip(locationMaster['detail'], locationMaster['noticeID'], locationMaster['type']) if filterDetail(d) != False]
    cleanLocationsDf = pd.DataFrame(cleanLocations, columns=['detail', 'noticeID', 'type'])

    # Create lat/long pairs for each unique noticeID
    latLongPairs = []
    for noticeID in cleanLocationsDf.noticeID.unique():
        try:
            tempDF = cleanLocationsDf[cleanLocationsDf.noticeID == noticeID]
            lat = tempDF[tempDF.type == 'latitude']['detail'].values[0]
            long = tempDF[tempDF.type == 'longitude']['detail'].values[0]
            
            #check if the noticeID has multiple locations
            latList = lat.split(',')
            longList = long.split(',')

            for i in range(0, len(latList)):
                l1 = latList[i].replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()
                l2 = longList[i].replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()
                try:
                    l1 = float(l1)
                    l2 = float(l2)
                    latLongPairs.append((l1, l2, noticeID))
                except:
                    print(f"Error converting lat/long to float: {l1}, {l2}")
        except:
            pass

    latLongPairsDf = pd.DataFrame(latLongPairs, columns=['latitude', 'longitude', 'noticeID'])

    # Find all locations that have NOT been geocoded yet
    notGeocoded = [n for n in latLongPairsDf['noticeID'].unique() if n not in geocodedDf['noticeID'].unique()]

    #Geocode function
    def geocodeCensus(lat, long, censusYear=2020):
        """
        This function takes a location and returns a list with geocoded location data and data appends from Geocod.io.
        """

        if long > 0:
            raise Exception(f"Longitude should be negative to be in the continental US. Received {long}.")

        ## Geocod.io (Not great because it tries to map to a street and it's not very accurate for wetlands)
        #API_KEY = os.environ['GEOCODIO_API_TOKEN']
        #url = "https://api.geocod.io/v1.7/reverse?api_key="+API_KEY+"&fields=census2010,cd"
        #params = "&q="+str(lat)+","+str(long)

        #FCC API
        url = "https://geo.fcc.gov/api/census/area?"
        latLon = "lat="+str(lat)+"&lon="+str(long)
        censusYear = f"&censusYear={censusYear}"+"&format=json"
        response = requests.get(url=url+latLon+censusYear)
        
        if response.status_code == 200:
            try:
                responseJson = response.json()
                return (response.status_code, responseJson)
            except:
                return (response.status_code, {'results':[]})
        else:
            return (response.status_code, {'results':[]})

    geocodedDf = pd.DataFrame([])
    for n in notGeocoded:
        resultsDf = pd.DataFrame()
        lat = latLongPairsDf[latLongPairsDf['noticeID'] == n]['latitude'].values[0]
        long = latLongPairsDf[latLongPairsDf['noticeID'] == n]['longitude'].values[0]
        if long > 0:
            long = -long
        #Get 2020 Census Data
        code, response = geocodeCensus(lat, long, censusYear=2020)
        if code == 200 and len(response['results']) > 0:
            results = response['results'][0]
            if 'bbox' in results:
                del results['bbox']
            results['censusYear'] = 2020
            results['lat'] = lat
            results['long'] = long
            resultsDf = pd.DataFrame(results, index=[0])
            

        #Get 2010 Census Data
        code, response = geocodeCensus(lat, long, censusYear=2010)
        if code == 200 and len(response['results']) > 0:
            results = response['results'][0]
            if 'bbox' in results:
                del results['bbox']
            results['censusYear'] = 2010
            results['lat'] = lat
            results['long'] = long
            resultsDf = pd.concat([resultsDf, pd.DataFrame(results, index=[0])], axis=0)
        
        if len(resultsDf) > 0:
            resultsDf['noticeID'] = n
            geocodedDf = pd.concat([geocodedDf, resultsDf], axis=0)
        geocodedDf.reset_index(inplace=True, drop=True)
    
    if len(geocodedDf) > 0:
        print(f"Geocoded {len(geocodedDf)} locations.")
        return geocodedDf
    else:
        return []


def dataframe_to_csv(df, df_name, directory):
    """
    Export dataframes to csv
    """
    print("Exporting data to local CSVs...")    
    # Get the current date
    today = datetime.today()
    
    # Extract date components
    date_str = today.strftime('%Y_%m_%d_%H_%M')
    
    # Create the filename with the specified prefix, year, and date
    filename = f'{directory}{str(df_name)}_{date_str}.csv'
    
    # Save the DataFrame to the CSV file
    df.to_csv(filename, index = False)
    
    return df_name




def upload_redivis(tbl_to_upload, redivis_dataset, directory, overwrite_redivis = 0):
    """
    Append the new data to Redivis data tables
    
    Parameter:
    # confirm_upload: 1, confirm upload; 0, cancel upload
    """

    print('Starting upload to Redivis...')

    # Extract date components
    today = datetime.today()
    date_str = today.strftime('%Y_%m_%d_%H_%M')
    
    # Get a list of uploading file pathes
    if tbl_to_upload == "all": 
        filelist = glob.glob(f"{directory}*{date_str}.csv")
    elif tbl_to_upload == "none":
        filelist = []
    else:
        filelist = []
        for filename in tbl_to_upload:
            filelist.extend(glob.glob(f"{directory}{filename}*{date_str}.csv"))

    for filepath in filelist:

        try:

            if "main" in filepath:
                table = redivis_dataset.table("main_notices")
            if "manager" in filepath:
                table = redivis_dataset.table("manager")
            if "location" in filepath:
                table = redivis_dataset.table("location")
            if "character" in filepath:
                table = redivis_dataset.table("character")
            if "mitigation" in filepath:
                table = redivis_dataset.table("mitigation")
            if "summary" in filepath:
                table = redivis_dataset.table("summary")
            if "wetland" in filepath:
                table = redivis_dataset.table("wetland_impact")
            if "fulltext" in filepath:
                table = redivis_dataset.table("fulltext")
            if "embed" in filepath:
                table = redivis_dataset.table("embed_project_type")
            if "validation" in filepath:
                table = redivis_dataset.table("validation")
            if "aws" in filepath:
                table = redivis_dataset.table("aws_link")
            if "geocoded" in filepath:
                table = redivis_dataset.table("geocoded_locations")

            with open(filepath) as file:
                upload = table.upload(filepath).create(
                    file, 
                    type="delimited",
                    remove_on_fail=True,    # Remove the upload if a failure occurs
                    wait_for_finish=True,   # Wait for the upload to finish processing
                    raise_on_fail=True,      # Raise an error on failure
                    replace_on_conflict=bool(overwrite_redivis) # replace existing tables
                )
                
            print(f"{filepath} was successfully uploaded")
        except Exception as e:
            print(f"Error with uploading {filepath} to {table.name}: {e}")

            
            
            
def upload_aws(main_tbls, tbl_to_upload, aws_client):
    """
    Upload tables to AWS S3 bucket;
    main_tbls: a dictionary of dataframes
    tbl_to_upload: "all", "none", or a list such as ["main_df", "manager_df", "location_df", "character_df", "mitigation_df", "fulltext_df", "summary_df", "wetland_final_df", "embed_final_df", "validation_df", "aws_df", "geocoded_df"]
    """
    
    # Get a list of uploading files
    if tbl_to_upload.lower() == "all": 
        # tbl_list = list(main_tbls.items())
        tbl_dict = main_tbls
        print('Starting upload all tabls to the bucket...')
    elif tbl_to_upload.lower() == "none":
        print("Do not upload any tables to the bucket")
        return
    else:
        # tbl_list = [main_tbls[tbl_name] for tbl_name in list(main_tbls.keys()) if tbl_name in tbl_to_upload] 
        tbl_dict = {tbl_name: main_tbls[tbl_name] for tbl_name in list(main_tbls.keys()) if tbl_name in tbl_to_upload}
        print('Starting upload selected tables to the bucket...')
    
    for tbl_name, tbl in tbl_dict.items():
        
        # Pull existing data in AWS
        try:
            response = aws_client.get_object(Bucket = "usace-notices",
                                             Key = f"dashboard-data/{tbl_name}.csv")
        
            content = response['Body'].read()
            existing_df = pd.read_csv(io.BytesIO(content))
        except:
            existing_df = pd.DataFrame()
            
        # Append data
        upload_df = pd.concat([existing_df, tbl], ignore_index=True)
        
        # Convert DataFrame to bytes
        csv_buffer = io.BytesIO()
        upload_df.to_csv(csv_buffer, index=False)
        upload_bytes = csv_buffer.getvalue()
        
        aws_client.put_object(
            Body = upload_bytes, 
            Bucket = "usace-notices", 
            Key = f'dashboard-data/{tbl_name}.csv', 
            ACL = "public-read")
        
        print(f"{tbl_name} was successfully uploaded")