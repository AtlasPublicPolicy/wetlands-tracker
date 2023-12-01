# MAIN file

import os
import pkg_resources
import subprocess
import logging
import sys


# PREREQUISITE
############################

# Import requirements.txt

with open('requirements.txt', encoding='utf-8') as f:
    required_modules = [line.strip() for line in f]

installed_modules = {pkg.key for pkg in pkg_resources.working_set}
missing_modules = set(required_modules) - installed_modules

if missing_modules:
    print(f"Installing missing modules: {', '.join(missing_modules)}")
    subprocess.check_call(['pip', 'install'] + list(missing_modules))
    print("Installation complete.")
else:
    print("All required modules are already installed.")

    
# Load external modules
import glob
import pandas as pd
from dotenv import load_dotenv
import main_extractor
import redivis
from error_report import error_report

# Configuration: set up parameters and API keys

class configuration:
    def __init__(self):
        
        # Load environment variables from a .env file
        load_dotenv(r'api_keys.env')

        # Azure
        self.AZURE_ENDPOINT = os.environ.get('AZURE_ENDPOINT')
        self.AZURE_API_KEY = os.environ.get('AZURE_API_KEY')

        # Redivis
        self.REDIVIS_API_KEY = os.environ.get('REDIVIS_API_KEY')
        self.redivis_dataset = redivis.user("portugalmo").dataset("usaceData", version = "next")

        # openAI
        self.OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

        # AWS S3 bucket
        self.aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

        # Other configuration parameters
        
        ## 1) Do you want to scrape all historical notices or only recently updated ones: 1, update; 0, first-time-scraping; default as 1
## IMPORTANT  ## be careful with scraping ALL historical notices; might run for hours and incur high costs of Azure and LLM serives 
        self.update = 1
        
        ## 2）How many days in the past you would like search for updated notices: numeric # from 0 to 500; default as 100
        self.n_days = 14

        ## 3) How many maximum notices (sorted by date) to download?
        self.max_notices = 20
        
        ## 4）which district you would like to scrape: "New Orleans", "Galveston", "Jacksonville", "Mobile", or "all"; default as "all"
        self.district = "all"

        ## 5) which table you would like to upload to Redivis?
        ## Any of tables in the list = ["main", "manager", "character", "mitigation", "location", "fulltext", "summary", "wetland", "embed", "validation", "aws", "geocoded"], "none" or "all"; defaul as "none"
        self.tbl_to_upload = "none"
        
        ## 6) For Azure summarization, please set a price cap
        self.price_cap = 5
        
        ## 7) How many sentences you would like to have for summarization
        self.n_sentences = 4
        
        ## 8) file directory
        self.directory = "data_schema/"

        ## 9) Overwrite file with same name on Redivis
        self.overwrite_redivis = 0

        ## 10) Skip paid services including OpenAI and Azure Summaries. 1, skip; 0, do not skip; default = 0
        self.skipPaid = 1

        ## 11) If you have problem running OCR(Optical Character Recognition), please specify the path for tesseract.exe such as "C:/Program Files/Tesseract-OCR/tesseract.exe".
        self.tesseract_path = None
        
        ## 12) Generate visualization in error report or not? 1, yes; 0, no
        self.viz = 1


###############################
# district URLS included:
# Galveston: "https://www.swg.usace.army.mil/Media/Public-Notices/"
# New Orleans: "https://www.mvn.usace.army.mil/Missions/Regulatory/Public-Notices/"
# Jacksonville: "https://www.saj.usace.army.mil/Missions/Regulatory/Public-Notices/"
# Mobile: "https://www.sam.usace.army.mil/Missions/Regulatory/Public-Notices/"

# IMPLEMENTATION
###########################

def main(config):
    
    # Start info/error logging
    logging.basicConfig(
        filename='log.txt', 
        filemode='w', 
        format='%(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO)
    
    try:
        ## Connect to Redivis DB:
        os.environ['REDIVIS_API_TOKEN'] = config.REDIVIS_API_KEY

        ## If update == 0: scrape all historical notices
        ## If update == 1: Check latest notices for selected days; For those have not been in Redivis DB, scrape webpage and pdf
        df_base = main_extractor.restart_or_update(config.redivis_dataset,
                                                   config.update, 
                                                   config.n_days, 
                                                   config.max_notices,
                                                   config.district,
                                                   config.tesseract_path
                                                   )
        # Print the number of notices retrieved
        print(f"Number of notices retrieved: {len(df_base)}")


        # EXPORT RAW_DF AT THIS STAGE - EXCLUDE FULL_TEXT COLUMN
        raw_df = df_base.drop(columns=['pdf_full_text', 'pdf_trimmed'])
        raw_df.to_csv(f'{config.directory}raw_df.csv', index=False)


        ## Pre-clean
        df = main_extractor.data_schema_preprocess(df_base, 
                                                   config.redivis_dataset)

        ## Clean/Validation

        ### A. main, manager, character of work, mitigation, location, and aws links
        main_tbls = main_extractor.data_schema(df, 
                                               config.aws_access_key_id, 
                                               config.aws_secret_access_key,
                                               config.redivis_dataset)

        ### B. Azure summarization
        if config.skipPaid == 0:
            fulltext_and_summary_tbl = main_extractor.data_schema_summarization(df, 
                                                                                config.price_cap, 
                                                                                config.AZURE_ENDPOINT, 
                                                                                config.AZURE_API_KEY, 
                                                                                config.redivis_dataset,
                                                                                config.n_sentences)
            main_tbls.update(fulltext_and_summary_tbl)
        else:
            print("Skipping Azure summaries")

        ### C. LLM: wetland impacts 
        if config.skipPaid == 0:
            impact_tbl = main_extractor.data_schema_impact(df, 
                                                           config.OPENAI_API_KEY,
                                                           config.redivis_dataset)
            main_tbls.update({"wetland_final_df":impact_tbl["wetland_final_df"]})
        else:
            print("Skipping wetland impacts")

        ### D.generate a table for troubleshooting and validation
        if config.skipPaid == 0:
            validation_tbl_regex = df.drop(["pdf_trimmed", "tokens"], axis = 1)
            validation_tbl_llm = impact_tbl["wetland_impact_df"][["noticeID", "wetland_llm_dict"]]
            validation_df = pd.merge(validation_tbl_regex, validation_tbl_llm, on="noticeID") 
            main_tbls.update({"validation_df":validation_df})
        else:
            print("Skipping validations")

        ### E. LLM: embeding and project types
        if config.skipPaid == 0:
            embeding_tbl = main_extractor.data_schema_embeding(df, 
                                                            config.OPENAI_API_KEY,
                                                            config.redivis_dataset)
            main_tbls.update(embeding_tbl)
        else:
            print("Skipping embedings")

        ### F. Geocoding
        geocode_tbl = main_extractor.geocode(config.redivis_dataset)
        main_tbls.update({"geocoded_df": geocode_tbl})

        ## Export tables to directory
        [main_extractor.dataframe_to_csv(main_tbls[df_name], df_name, config.directory) for df_name in main_tbls]

        ## Upload to Redivis DB
        main_extractor.upload_redivis(config.tbl_to_upload, config.redivis_dataset, config.directory, config.overwrite_redivis)
        
        ## Error report
        markdown_content = error_report(config.directory, config.viz)

        with open("error_report.md", "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        # Construct the path to the Pandoc executable within the virtual environment
        # pandoc_path = os.path.join(os.path.dirname(__file__), 'venv', 'Lib', 'site-packages', 'pandoc-3.1.9', 'pandoc.exe')
            
        # subprocess.run(
            # [pandoc_path, "error_report.md", "-o", "error_report.pdf"])
            
    except Exception as e:
        logging.error(str(e), exc_info=True)
        print(str(e))

if __name__ == "__main__":
    config = configuration()
    main(config)

