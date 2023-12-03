#!/usr/bin/env python
# coding: utf-8

# # Extract fields from PDF text - USACE Wetland project
# 
# 
# Last Updates: 16 September 2023
# 
# 
# The following notebook seeks to extract the following fields, defined in the glossary.
# 
# - longitude
# - latitude
# - Acreage
# - acre_type
# - acre_term
# - linear_feet
# - oilgas: look in applicant name
# - expiry period
# 
# It does this through three Functions:
# 
# ### 1. get abstractive summaries (on entire PDF)
# 
# -    a) Run the function once for just a 3 sentence summary for dashboard use
# -    b) Run the function once for a 10 sentence summary for use in next step
#     
#     
# ### 2. Run regex on text+summaries for a given column
# 
# Use pre-built regex patterns and modify as needed, to get best attempt of extracting fields from the summaries and/or the original text.
# 
# ### 3. Pass text/summary to OpenAI API, and extract structured data on wetlands 
# 
# 
### Required libraries
# install azure

#pip install azure-core, azure-ai-ml, azure-identity, azure-ai-textanalytics

from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
import configparser
import re
import os
import PyPDF2
import pandas as pd
import numpy as np
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
import csv
from typing import List

import nltk
#nltk.download('punkt')
from nltk.tokenize import sent_tokenize

import openai
from openai import OpenAI

import tiktoken
import json
import requests

# from langchain import OpenAI
# from langchain.chat_models import ChatOpenAI
# from langchain.chains import create_extraction_chain


# ## CHange PATH

# # Function 1: Use Azure API to get abstractive summary 
# 
# 

# In[2]:


### Setup Azure Text Analytics

#get API key from config file
# azureConfig = configparser.ConfigParser()
# azureConfig.read('example pdfs/azureFreeKeyphrase.ini', encoding='utf-8')
# key = azureConfig['Azure']['APIkey']
# endpoint =  azureConfig['Azure']['endpoint']

# In[20]:

### Function 1
@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def getDocumentAbstractiveSummary(text, endpoint, key, sentenceCount=5):
    """
    Extract an abstrative summary using Microsoft Cognitive Services' Language Resource.
    Input is a string of text.
    Output is a string of text.
    """
    
    #setup Azure client
    text_analytics_client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key), default_language='en')

    if sentenceCount > 20:
        sentenceCount = 20
        
    #fixed typo
    poller = text_analytics_client.begin_abstract_summary([text],sentence_count=sentenceCount)
    
    abstractive_summary_results = poller.result()
    for result in abstractive_summary_results:
        if result.kind == "AbstractiveSummarization":
            summary = [summary.text for summary in result.summaries]
        elif result.is_error is True:
            summary = f"Uh oh. Error with code '{result.error.code}' and message '{result.error.message}'"
    
    #if multiple summaries
    if len(summary) > 1:
        summary = '\n\n'.join(summary)
    else:
        summary = summary[0]
    return summary


# ### Issues:
# 
# ### Issue 1: Long texts with many mentions of wetland impacts are not captured in detail.
# 
# ### Issue 2: Related to 1, the summarization sometimes gets rid of the keywords needed for Regex or extraction.


#######################################################################################################

# REGEX on sentences
#nltk.download('punkt')

def sent_regex_extraction(text: str):
    acre_pattern = r'(\b\d+(\.\d+)?-?\d*\b\s?acres?)'
    wetland_pattern = r'\b(\w+\s(?:wetland|wetlands|marsh))\b'

    # Tokenize the text into sentences
    sentences = sent_tokenize(text)

    # Initialize list to store sentences with matches
    matching_sentences = []

    # Loop through each sentence to find matches
    for sentence in sentences:
        has_acre = re.search(acre_pattern, sentence)
        has_wetland = re.search(wetland_pattern, sentence, re.IGNORECASE)

        # If both patterns are found in the sentence, add it to the list
        if has_acre and has_wetland:
            matching_sentences.append(sentence)

    return matching_sentences



#############################################################################################################################
# # 
# # Function 3: Use OpenAI LLM call to extract structured info
# 
# 
# **Only run through OpenAI (Function 3) if the row has some mention of wetlands, i.e. step 2 gives a non missing value in reg_wetland.**
# 
# 
# ## Insert OpenAI API Key

# ## Function 3 Step 1: Define OpenAI function, response schema and API call

# In[490]:

### step 1 - set up Chat Completion

@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(GPT_MODEL, messages, API_KEY, functions=None, function_call=None):
    """
    This function makes a POST request to the OpenAI Chat Completion API, sending a JSON payload 
    that includes the GPT model, a series of messages. It is designed to retry up to three times with 
    exponential backoff in case of failures. 

    Parameters:
    GPT_MODEL (str): The identifier of the GPT model to be used for generating responses.
    messages (list): A list of message dictionaries, where each dictionary represents a single exchange 
                     within the chat. Each message has a 'role' (either 'user' or 'assistant') and 
                     'content' (the message text).
    API_KEY (str): The API key for authentication with the OpenAI API.
    functions (list, optional): A list of additional functions to be used along with the GPT model. 
                                Default is None.
    function_call (dict, optional): A dictionary representing a function call, including function name 
                                    and parameters. Default is None.

    Returns:
    requests.models.Response: The response object from the API call if successful.
    Exception: The exception object if the API call fails.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + API_KEY,
    }
    json_data = {"model": GPT_MODEL, "messages": messages, "temperature": 0}
    if functions is not None:
        json_data.update({"functions": functions})
    if function_call is not None:
        json_data.update({"function_call": function_call})
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=json_data,
        )
        return response
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        return e


#############################################################################################

### Function 1 - Wetland impact

main_func = [

            { # function to capture wetland impacts
              "name": "wetland_analysis",
              "description": """Get attributes for project, wetlands, area and duration.""",
              "parameters": {
                "type": "object",
                "properties": {
                   "wetlands": {
                    "type": "array",
                    "description": "Array containing information about project and impact on wetlands etc..",
                    "items": {
                      "type": "object",
                      "properties": {
                        "wetland_type": {
                          "type": "string",
                          "description": "The type or descriptor of the wetland, waters, waterbottoms, swamp, marsh etc."
                        },

                          "impact_quantity": {
                          "type": "string",
                          "description": "The quantity of the wetland, stream or land impacted. Only numeric."
                        },
                          
                        "impact_unit": {
                          "type": "string",
                          "enum": ["acres", "sq. feet", "linear feet"],
                          "description": "The units of the measurement for the impacted area of the wetland. Only text."
                        },

                        "impact_duration": {
                          "type": "string",
                          "enum": ["permanent", "temporary", "unknown"],
                          "description": "Duration of impact or loss of the wetland, e.g., 'permanent' or 'temporary'. Write 'Unknown' if no descriptor in same sentence."
                        },
                        "impact_type": {
                          "type": "string",
                          "description": "Whether project impact is harmful, beneficial or unknown. "
                        }
                          
                      }
                    }
                  }
                }
              }
            }

        ]


def openAIfunc_wetland(input_text,  API_KEY, GPT_MODEL):
    
    messages = []
   # messages.append({"role": "system", "content": "Work step by step."})   # POTENTIAL ERROR
    messages.append({"role": "user", "content": """
            
            You will get a passage about a project. Use the function schema to get a dictionary. 
            For each wetland, provide its type or descriptor, the area it occupies in acres,
            and the duration of its impact (e.g., 'permanent' or 'temporary'). 
            You should focus on sentences which contain information on area or (linear feet) and wetland type impacted.
            The priority is the breakdown by wetland type. 
            Only record 'impact_duration' as 'permanent' or 'temporary' if it appears in the same sentence as 'wetland_type' 
            and 'area', otherwise write 'unknown'. 
            DON'T exclude valid sentences.
            Some passages describe multiple projects, and sequentially describe the wetland impacts for each project.            
            Keywords like 'including' or 'of which', or parentheses '()' may indicate nested projects - Do not double count impacts.
            The impact_type for a wetland is usually loss or damage. 
            Sometimes words like positive, beneficial, restoration etc. will indicate a positive or neutral impact, record it.
            Take a deep breath, and work on this problem step-by-step. 

            Here is the text: """  + input_text                
                    })

# https://arxiv.org/pdf/2309.03409.pdf
    chat_response = chat_completion_request(GPT_MODEL,
        messages, API_KEY, functions=main_func, function_call={"name": "wetland_analysis"}
    )

    func_response = chat_response.json()["choices"][0]["message"]["function_call"]["arguments"]

    # Convert the stringified JSON to a Python dictionary
    func_response_dict = json.loads(func_response)

    # except (KeyError, json.JSONDecodeError) as e:
    # print(f"An error occurred: {e}")
    # func_response_dict = {}

    return func_response_dict

####################################################################################################################

####################################################################################################################

### Function 2 - Project details

project_func = [
    {
        "name": "project_analysis",
        "description": "Get attributes for project type, total project area, and categorize the project based on the given description into one of the predefined categories.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_detail": {
                    "type": "string",
                    "description": "Summarize the project into less than 5 words."
                },
                "total_project_area": {
                    "type": "string",
                    "description": "Total project area (in square feet or acres), distinct from the wetland impact. Write unknown if not available."
                },
                "project_category": {
                    "type": "string",
                    "enum": [
                        "Commercial developments",
                        "Drainage features",
                        "Industrial developments",
                        "Oil and Gas facilities",
                        "Pipelines and flowlines",
                        "Recreation facilities",
                        "Residential subdivisions",
                        "Transportation",
                        "Utility",
                        "Ports",
                        "Levee",
                        "Marina"
                    ],
                    "description": "Categorize the project based on the given description into one of the predefined categories. Select 2 where appropriate."
                }
            }
        }
    }
]

        
def openAIfunc_project(input_text,  API_KEY, GPT_MODEL):
    
    messages = []
   # messages.append({"role": "system", "content": "Work step by step."})   # POTENTIAL ERROR
    messages.append({"role": "user", "content": """

Projects can be categorized into the following:

1. Commercial developments - Include non-manufacturing business establishments 
such as department stores, hardware stores, retail outlets, grocery stores, car washes, corner stores, 
office buildings, strip malls, shopping centers, movie theaters, hotels/motels/inns, hospitals, etc

2. Drainage features - Drainage features  include gravity drainage channels and canals; water control structures; and pump stations and associated structures.

3. Industrial developments - Industrial developments are defined as facilities used to produce goods in connection with, 
or as part of, a process or system.  Such developments incl ude refineries, steel mills, 
shipyards, fabrication facilities, food processing facilities, bulk loading facilities,
landfills, water treatment systems, etc.

3. Oil and Gas facilities - Oil and Gas facilities located within the coastal zone include 
(for the purposes of this guide) well sites, production facilities and storage facilities.  

4. Pipelines and flowlines - Pipelines and flowlines (hereafter referred to as “lines”) are linear features installed for 
the purpose of transporting materials from one location to another.  Lines can be of any diameter 
and length and any type of liquid or gaseous material can be transported within them. 

5. Recreation facilities  - Recreation facilities include, but are not limited to, parks; visitor centers; picnic areas; ball 
fields; playgrounds; public golf courses; community swimming pools, tennis courts and basketball courts; 
and nature, hiking and bike trails.

6. Residential subdivisions - residential subdivisions  as multi -house/unit residential developments. 

7. Transportation - Transportation features include roads, bridges and ferries, construction and maintenance of 
which typically are undertaken by state or local governmental bodies, or in the case of ferries, 
private companies.  This guide is focused more transportation features constructe d by municipal entities. 
For the purposes of application processing, air and rail developments should refer to our  
commercial or industrial developments guides depending on the nature of the activity; boat
traffic should refer to our M arinas, Ports or Recreational Facilities guides depending on 
the nature of the activity; and bike and foot trails should refer to  the R ecreational Facilities  guide.

8. Utility - Utility activities include potable water facilities and lines, sewerage facilities and lines, gas and electricity facilities 
and lines, phone lines, cable lines and fiber optic lines.

9. Ports  - a port as an industrial type, water -based cargo transfer facility 

10. Levee - A levee is defined as an embankment or wall to control or prevent water movement, to retain water 
or other material, or to raise a road or other lineal use above normal or flood water levels.  
Examples include levees, dikes, flood walls and embankments of any kind.

11. Marina - marinas  as any type of development focused on providing water access and docking services to the boating 
community.   Marina amenities  include fueling stations, pump -out stations, wash stations, ice houses, seafood processing 
facilities (including fish cleaning stations), stores, bait shops, restaurants, lodging, etc.  Shipyards and other exclusive
retail/service type facilities such as boat retail and/or repair are not considered marinas for the purposes of this guide.

    Here is the text: """  + input_text                
                    })

# https://arxiv.org/pdf/2309.03409.pdf
    chat_response = chat_completion_request(GPT_MODEL,
        messages, API_KEY,  functions=project_func, function_call={"name": "project_analysis"}
    )

    func_response = chat_response.json()["choices"][0]["message"]["function_call"]["arguments"]

    # Convert the stringified JSON to a Python dictionary
    func_response_dict = json.loads(func_response)
    
    # except (KeyError, json.JSONDecodeError) as e:
    # print(f"An error occurred: {e}")
    # func_response_dict = {}

    return func_response_dict

###################################################################################################

# ## Function 3 Step 2: JSON to dict to columns

# In[311]:


def dict_to_columns(df_source: pd.DataFrame, dict_col: str, index_cols: list) -> pd.DataFrame:
    """
    Processes a DataFrame to extract information into a new DataFrame.

    Parameters:
    - df_source (pd.DataFrame): The source DataFrame containing the data.
    - dict_col (str): The column name in df_source that contains dictionaries.
    - index_cols (list): The column names in df_source containing the indices or IDs you wish to record.

    Returns:
    - pd.DataFrame: A new DataFrame with extracted information.
    """
    # Initialize an empty DataFrame to store the final data
    df_main = pd.DataFrame()
    
    # Loop through each row in the source DataFrame
    for _, row in df_source.iterrows():
        # Extract the dictionary and index for each row
        wetland_dict = row[dict_col].get('wetlands', [])
        ids = {col: row[col] for col in index_cols}
        
        # Create a DataFrame for the wetlands data
        wetlands_df = pd.DataFrame(wetland_dict)

        # Handle the case where no wetlands data is present
        if wetlands_df.empty:
            wetlands_df = pd.DataFrame(columns=['wetland_type', 'area', 'impact_duration', 'impact_type'])
        
        # Add ID columns
        for col, id_val in ids.items():
            wetlands_df[col] = id_val

        # Append to the main DataFrame
        df_main = pd.concat([df_main, wetlands_df], ignore_index=True)
        
    return df_main

###########################################################################

# part 4- create embeddings


# part 4- create embeddings
@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def openai_embed(input_text, API_KEY):
    """
    This function initializes an OpenAI client with the provided API key and then generates embeddings 
    for the specified input text using the 'text-embedding-ada-002' model. It counts the number of tokens 
    in the input text, generates embeddings, and extracts the embedding vector from the response.

    Parameters:
    input_text (str): The text for which embeddings are to be generated.
    API_KEY (str): The API key for authentication with the OpenAI API.

    Returns:
    A tuple containing two elements:
           1. token_count (int): The number of tokens in the input text.
           2. vector (list or str): The embedding vector if successful, or an error message if an exception occurs.

    Raises:
    Exception: Captures and returns any exceptions that occur during the API call or processing of the response.
    """

    # initialize client
    client = OpenAI(
    api_key=API_KEY,  
    )
    try:
        openai.api_key= API_KEY
        encoding = tiktoken.encoding_for_model('text-embedding-ada-002')
        #count number of tokens
        token_count =  len(encoding.encode(input_text))

        #generate embeddings  
        response = client.embeddings.create(input=input_text, model='text-embedding-ada-002')
        
        embeddings = response.model_dump_json(indent=0)
        
    #     embeddings = embeddings.values[0]
        
        # Load the JSON data
        data = json.loads(embeddings)

        # Access and extract the vector
        vector = data["data"][0]["embedding"]
        return token_count, vector
    
    except Exception as e:
            # Return the error message in place of embeddings
        return token_count, f"Error: {str(e)}"


###############################################################################