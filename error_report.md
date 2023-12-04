# 1: Check the results pulled by regex

## 1.1 Track PDF reading problems

| PDF Reading Status   |   Count |   Percentage (%) |
|:---------------------|--------:|-----------------:|
| normal               |       2 |              100 |

2 (100.0%) of notices have valid texts

## 1.2 For those notices that have a valid texts, how many are special public notices?

|   Special Notice |   Count |   Percentage (%) |
|-----------------:|--------:|-----------------:|
|                0 |       2 |              100 |

2 (100.0%) notices having texts from PDF or webpage are not special public notices.

## 1.3 Non-special notices that have unknown or NA values

| Column         |   Unknown Count |   Unknown Percentage (%) |
|:---------------|----------------:|-------------------------:|
| pdf_county     |               2 |                      100 |
| pdf_wqc        |               2 |                      100 |
| pdf_cup        |               2 |                      100 |
| web_mitigation |               1 |                       50 |
| pdf_longitude  |               1 |                       50 |
| pdf_latitude   |               1 |                       50 |
| pdf_mitigation |               1 |                       50 |

## 1.4 Non-special notices that have errors

| Column     |   Error Count |   Error Percentage (%) | Main Error                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|:-----------|--------------:|-----------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| pdf_impact |             1 |                     50 | [{'impact_number': '805', 'impact_unit': 'acre', 'impact_number_type': 'ERROR: regex fails', 'impact_condition': 'unknown', 'impact_duration': 'unknown'}, {'impact_number': '670', 'impact_unit': 'acre', 'impact_number_type': 'project size', 'impact_condition': 'neutral', 'impact_duration': 'unknown'}, {'impact_number': '42.41', 'impact_unit': 'acre', 'impact_number_type': 'w etland', 'impact_condition': 'negative', 'impact_duration': 'unknown'}] |

# 2: Check the errors of wetland impacts pulled by LLM and Regex

## 2.1 Counts of extracted unit, type, duration

No. of wetland entries with impact_unit 0.0 = 0

## 2.2 Counts of extracted unit, type, duration

| index                                    |   Count |   percent |
|:-----------------------------------------|--------:|----------:|
| unknown                                  |      56 |        42 |
| loss                                     |      45 |        34 |
| restoration                              |       8 |         6 |
| construction                             |       7 |         5 |
| damage                                   |       3 |         2 |
| secondary impact                         |       3 |         2 |
| preservation                             |       2 |         2 |
| dredging                                 |       1 |         1 |
| placement                                |       1 |         1 |
| gain                                     |       1 |         1 |
| modification                             |       1 |         1 |
| development                              |       1 |         1 |
| erosion control and shoreline protection |       1 |         1 |
| fill material                            |       1 |         1 |
| enhance and restore                      |       1 |         1 |
| assist with restoration construction     |       1 |         1 |

## 3.3 OpenAI errors/difference w. regex

### Overview

| Wetland impact extraction       |   Count |
|:--------------------------------|--------:|
| Both returned similar           |      24 |
| Both returned different objects |      14 |
| Regex returned NAs              |       8 |
| Both returned NAs               |       1 |

