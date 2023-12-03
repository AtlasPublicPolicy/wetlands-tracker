import pandas as pd
import numpy as np
import os
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import io
import json
import re
import ast 
import glob
from collections import Counter
import itertools
import Levenshtein
import seaborn as sns
import unicodedata

from IPython.core.interactiveshell import InteractiveShell
InteractiveShell.ast_node_interactivity = "all"
from IPython.display import Markdown




def error_report(directory):

    # Read in tables 
    raw_df = pd.read_csv(f"{directory}raw_df.csv")
    # raw_df = raw_df.drop(columns = ["pdf_full_text", "pdf_trimmed"])
    val_df = pd.read_csv(glob.glob(f"{directory}validation_*")[0])
    wetland_df = pd.read_csv(glob.glob(f"{directory}wetland_*")[0])
    
    ####################
    markdown_content = f"# 1: Check the results pulled by regex\n\n"
    
    # pdf_text_flag is used to track the PDF reading process during scraping
    pdf_reading = raw_df.pdf_text_flag.value_counts()
    pdf_reading_table = pd.DataFrame({"PDF Reading Status": pdf_reading.index, "Count": pdf_reading.values})
    pdf_reading_table["Percentage (%)"] = round((pdf_reading_table.Count / pdf_reading_table.Count.sum()) * 100, 2)
    pdf_reading_table_md = pdf_reading_table.to_markdown(index=False)
    markdown_content += f"## 1.1 Track PDF reading problems\n\n{pdf_reading_table_md}\n\n"

    ## Count the number of valid texts, either from PDF or webpage
    num_valid = raw_df[raw_df.pdf_text_flag != "Replaced with webpage text but no texts in the webpage body"].usaceWebUrl.count()
    pct_valid = round(num_valid / raw_df.usaceWebUrl.count() * 100, 2)
    markdown_content += f"{num_valid} ({pct_valid}%) of notices have valid texts\n\n"

    
    # if any text is pulled from PDF or webpage, how many of them are special notices?
    special_flag = raw_df[raw_df.specialFlag != "ERROR: no pdf or webpage text found"].specialFlag.value_counts()
    special_flag_table = pd.DataFrame({"Special Notice": special_flag.index, "Count": special_flag.values})
    special_flag_table["Percentage (%)"] = round((special_flag_table.Count / special_flag_table.Count.sum()) * 100)
    special_flag_table_md = special_flag_table.to_markdown(index=False)
    markdown_content += f"## 1.2 For those notices that have a valid texts, how many are special public notices?\n\n{special_flag_table_md}\n\n"

    ## Count the number of valid non-special notices
    non_special_count = special_flag_table.loc[0, "Count"]
    non_special_pct = special_flag_table.loc[0, "Percentage (%)"]
    markdown_content += f"{non_special_count} ({non_special_pct}%) notices having texts from PDF or webpage are not special public notices.\n\n"
    
    
    # Non-special notices that have unknown or NA values
    non_special = raw_df[(raw_df.specialFlag == 0) | (raw_df.specialFlag == "0")]
    unknown_counts = non_special.apply(lambda col: col[(col == "unknown") | col.isna()].count())

    ## Calculate the percentage of 'unknown' an NANs in each column
    total_counts = non_special.apply(lambda col: col.count())
    unknown_pct = round((unknown_counts / total_counts) * 100, 2)

    ## Create a table
    unknown_table = pd.DataFrame({'Column': unknown_counts.index, 'Unknown Count': unknown_counts.values, 'Unknown Percentage (%)': unknown_pct.values})
    unknown_table = unknown_table[unknown_table['Unknown Count'] != 0]
    unknown_table = unknown_table.sort_values(by="Unknown Percentage (%)", ascending=False)
    unknown_table_md = unknown_table.to_markdown(index=False)
    markdown_content += f"## 1.3 Non-special notices that have unknown or NA values\n\n{unknown_table_md}\n\n"
    
    
    # Non-special notices that have errors
    error_counts_df = non_special.map(lambda cell: "ERROR" in str(cell))
    error_counts = error_counts_df.sum()
    error_pct = round((error_counts / total_counts) * 100, 2)

    ## Create a table
    error_table = pd.DataFrame({'Column': error_counts.index, 'Error Count': error_counts.values, 'Error Percentage (%)': error_pct.values})
    error_table = error_table[error_table['Error Count'] != 0]

    ## The main reason of error
    column_error = error_table.Column.to_list()
    error_table["Main Error"] = [non_special[non_special[col].str.contains("ERROR", na=False)][col].mode().iloc[0] for col in column_error]
    error_table = error_table.sort_values(by="Error Percentage (%)", ascending=False)
    error_table_md = error_table.to_markdown(index=False)
    markdown_content += f"## 1.4 Non-special notices that have errors\n\n{error_table_md}\n\n"
    
    
    # Does the number of latitude pulled matches with longitude pulled for one notice
#     lonlat_check = non_special.copy()

#     # Convert string representations of lists to actual lists
#     lonlat_check["lat_check"] = ["[]" if x == "unknown" else x for x in non_special["pdf_latitude"]]
#     lonlat_check["lon_check"] = ["[]" if x == "unknown" else x for x in non_special["pdf_longitude"]]
#     lonlat_check['lat_check'] = lonlat_check['lat_check'].apply(ast.literal_eval)
#     lonlat_check['lon_check'] = lonlat_check['lon_check'].apply(ast.literal_eval)

#     # Compare the lengths of the lists
#     lonlat_check['length_comparison'] = lonlat_check.apply(lambda row: len(row['lat_check']) == len(row['lon_check']), axis=1)
#     lonlat_check = lonlat_check.loc[~lonlat_check.length_comparison, ["usaceWebUrl", "usacePermitNumber", "PdfUrl", "pdf_location", "pdf_latitude", "pdf_longitude"]]
#     lonlat_check_md = lonlat_check.to_markdown(index=False)
#     markdown_content += f"## Does the number of latitude pulled matches with longitude pulled for one notice\n\n{lonlat_check_md}\n\n"
    
    
    ####################
    markdown_content += f"# 2: Check the errors of wetland impacts pulled by LLM and Regex\n\n"
    
    # Check impact_unit==0
    markdown_content += f"## 2.1 Counts of extracted unit, type, duration\n\n"
    
    ## Function to check if any dict in the list has 'impact_unit' equal to '0'
    def check_impact_zero(json_str):
        try:
            data = json.loads(json_str)  # Load the string as JSON
            return any(d.get('impact_quantity') == '0' for d in data)  # Check if 'impact_unit' is '0' in any dict
        except json.JSONDecodeError:
            return False  # Return False if JSON is not valid

    ## Apply the function to each row in the 'wetland_llm_dict' column
    val_df['impact_zero'] = val_df['wetland_llm_dict'].apply(check_impact_zero)
    impact_unit_0 = val_df['impact_zero'].sum()
    
    markdown_content += f"No. of wetland entries with impact_unit 0.0 = {impact_unit_0}\n\n"
    
    
    # Number of notices by unit, type and duration
    markdown_content += f"## 2.2 Counts of extracted unit, type, duration\n\n"
    
    def extract_impact_units(json_str, key:str):
        # Convert single quotes to double quotes for valid JSON format
        json_str = json_str.replace("'", '"')

        try:
            # Parse the JSON string into a dictionary
            data = json.loads(json_str)

            # Initialize an empty list to store impact_unit values
            impact_unit_list = []

            # Check if 'wetlands' has entries and iterate through each object if it does
            if len(data.get('wetlands', [])) > 0:
                for i in range(len(data['wetlands'])):
                    # Safely get 'impact_unit' with a default value if the key doesn't exist
                    impact_unit_i = data['wetlands'][i].get(key, None)
                    impact_unit_list.append(impact_unit_i)

            return impact_unit_list

        except json.JSONDecodeError:
            # Return a default value or handle the error as needed
            return []

    # Assuming val_df is your DataFrame
    val_df['impact_unit_list'] = val_df['wetland_llm_dict'].apply(lambda x: extract_impact_units(x, key='impact_unit'))
    val_df['impact_type_list'] = val_df['wetland_llm_dict'].apply(lambda x: extract_impact_units(x, key='impact_type'))
    val_df['impact_dur_list'] = val_df['wetland_llm_dict'].apply(lambda x: extract_impact_units(x, key='impact_duration'))

    def count_unique_values(list_of_lists):
        # Flatten the list of lists into a single list
        flattened_list = list(itertools.chain(*list_of_lists))

        # Count the occurrences of each unique value
        counts = Counter(flattened_list)

        # Convert the counts to a DataFrame and sort it
        counts_df = pd.DataFrame.from_dict(counts, orient='index', columns=['Count']).sort_values(by='Count', ascending=False).reset_index()

        # Replace empty strings with "[blank]"
        counts_df = counts_df.replace({"index": {"" : "[blank]"}})

        counts_df['percent'] = 100*np.round(counts_df['Count']/counts_df['Count'].sum(), 2)
        return counts_df

    # Apply the function to each column
    impact_unit_counts_df = count_unique_values(val_df['impact_unit_list'])
    impact_type_counts_df = count_unique_values(val_df['impact_type_list'])
    impact_duration_counts_df = count_unique_values(val_df['impact_dur_list'])

    impact_type_counts_df_md = impact_type_counts_df.to_markdown(index=False)
    markdown_content += f"{impact_type_counts_df_md}\n\n"
    
    
    ## Visualization 
    
#     def visualize_and_summarize_by_threshold(df, threshold_perc):
#         """
#         Function to create a horizontal bar plot for categories with a percentage above the threshold,
#         and to print out the unique values and total frequency for categories below that threshold.

#         :param df: DataFrame with 'index', 'Count', and 'percent' columns.
#         :param threshold_perc: Percentage threshold to filter categories.
#         """

#         # Select categories above the threshold percentage
#         df_above_threshold = df[df['percent'] >= threshold_perc]

#         # Plotting the horizontal bar graph for categories above the threshold
#         plt.figure(figsize=(8, 6))
#         barplot = sns.barplot(x='percent', y='index', data=df_above_threshold, palette='Greens_d', hue='index')

#         # Annotating each bar with the count
#         for index, row in df_above_threshold.iterrows():
#             barplot.text(row['percent'], index, f'{row["Count"]}', color='black', ha="left")

#         plt.xlabel('Percentage')
#         plt.ylabel('Categories', fontsize=14)
#         plt.title('Categories Above Threshold (Counts Labeled Near Bar)', fontsize=18 )
#         plt.tight_layout()
    
#         # Filtering for unique values below the threshold percentage
#         df_below_threshold = df[df['percent'] < threshold_perc]
#         unique_values = df_below_threshold['index'].unique()
#         total_frequency = df_below_threshold['Count'].sum()

#         # Print the unique values and total frequency
#         print("-"*60)
#         print("\n")
#         print("Other terms captured:", ", ".join(unique_values))
#         print("\n")
#         print("-"*60)
#         print("Total frequency:", total_frequency)

    # Example usage of the function (assuming a DataFrame is already prepared)
#     if visualization == 1:
#         visualize_and_summarize_by_threshold(impact_type_counts_df, 1) # Replace 'your_dataframe' with your actual DataFrame variable
#         plt.savefig("data_schema/impact_type_viz.png")
#         markdown_content += f"![Impact Type Counts]({directory}impact_type_viz.png)\n\n"

#         visualize_and_summarize_by_threshold(impact_duration_counts_df, 1) # Replace 'your_dataframe' with your actual DataFrame variable
#         plt.savefig("data_schema/impact_duration_viz.png")
#         markdown_content += f"![Impact Duration Counts]({directory}impact_duration_viz.png)\n\n"
    
    
    # Compare the results pulled by OpenAI and regex
    markdown_content += f"## 3.3 OpenAI errors/difference w. regex\n\n"
    
    def extract_values_regex(text):
        # Pattern to match key-value pairs
        pattern = r"'(\w+)': '([^']*)'"
        matches = re.findall(pattern, text)

        # Create a dictionary from the matches
        result = []
        for key, value in matches:
            # Append the value to the corresponding key in the result dictionary
            result.append(value)
        return result

    # Apply the function to each row
    val_df['lev_distance'] = val_df.apply(lambda row: Levenshtein.distance(extract_values_regex(row['pdf_impact']),
                                                                           extract_values_regex(row['wetland_llm_dict'])), axis=1)

    val_df['len1'] = val_df.pdf_impact.apply(lambda x: len(x))
    val_df['len2'] = val_df.wetland_llm_dict.apply(lambda x: len(x))

    def determine_message(row):
        if row['len1'] == 2 and row['len2'] == 16:
            return 'Both returned NAs'
        elif row['len1'] == 2 and row['len2'] > 16:
            return 'Regex returned NAs'
        elif row['len2'] == 16  and row['len1'] != 2:
            return 'OpenAI returned NAs'
        elif row['len2'] != 16  and row['len1'] != 2 and row['lev_distance']>10:
            return 'Both returned different objects'
        else:
            return 'Both returned similar'

    # Apply the function to each row
    val_df['wetland_extraction'] = val_df.apply(determine_message, axis=1)
    llm_regex = val_df.wetland_extraction.value_counts()
    llm_regex_table = pd.DataFrame({"Wetland impact extraction": llm_regex.index, "Count": llm_regex.values})
    llm_regex_table_md = llm_regex_table.to_markdown(index=False)
    markdown_content += f"### Overview\n\n{llm_regex_table_md}\n\n"
    
    # Detailed info for notices that have unmatched regex and LLM results
    
#     if visualization == 1:
#         df = val_df[['web_title', 'pdf_impact', 'wetland_llm_dict', 'lev_distance', 'len1', 'len2']].copy()
#         # llm_regex_detail = df.sort_values(by='len1')
#         # llm_regex_detail_md = llm_regex_detail.to_markdown(index=False)
#         # markdown_content += f"### Detailed Table\n\n{llm_regex_detail_md}\n\n"
        
#         fig, ax = plt.subplots(1, figsize=(8, 8))
#         df[(df.len1<2000)].len1.hist(color='red', alpha=.6, bins=30, legend=True)
#         df[(df.len2<2000)].len2.hist(color='blue', alpha=.5, bins=30, legend=True)
#         fig.savefig("data_schema/llm_regex_viz.png")
#         markdown_content += f"![LLM vs Regex histograms]({directory}llm_regex_viz.png)\n\n"
    
    # Remove non-ASCII characters
    non_ascii_pattern = re.compile('[^\x00-\x7F]+')
    markdown_content = non_ascii_pattern.sub('', markdown_content)

    # Keep only specific characters (ASCII letters, digits, and some Markdown-related characters)
    markdown_content = ''.join(
        char if char != '\xad' else '' for char in markdown_content
        # if unicodedata.category(char)[0] == 'L' or char in {'\n', '\r', ' ', '\t', '#', '*', '-', '_', '[', ']', '(', ')', '`'}
    )
    
    return markdown_content
    
    
    
    
    
    