# 0 - create dataset


#install.packages("aws.s3")
#install.packages("tidycensus")
library(tidycensus)
library(aws.s3)
library(tidyverse)

setwd('analysis_dec2023')

# enter auth details and delete
Sys.setenv("AWS_ACCESS_KEY_ID" = "",
           "AWS_SECRET_ACCESS_KEY" = "",
           "AWS_DEFAULT_REGION" = "us-east-1")

# enter tidycensus API
census_api <- ""


table(lookup_var$geography)
# manually get the files

# 1 - wetland table
df1 <- get_object(bucket = "usace-notices",
           object = "dashboard-data/wetland_final_df.csv")

df1 <- read.csv(text = rawToChar(df1))

write_csv(df1, 'data_download/wetland_final_df.csv.csv')

# 2 - geocoded locations

df2 <- get_object(bucket = "usace-notices",
                  object = "dashboard-data/location_df.csv")

df2 <- read.csv(text = rawToChar(df2))

write_csv(df2, 'data_download/location_df.csv')


# 3 - embedding/project type
df3 <- get_object(bucket = "usace-notices",
                  object = "dashboard-data/embed_final_df.csv")

df3 <- read.csv(text = rawToChar(df3))

#write_csv(df3, 'data_download/embed_final_df.csv')

#############################################################

# 4 - Census block-group data - NOT YET FINAL

# use tidycensus

# set API key
census_api_key(census_api, install = TRUE)

#get dataframe of variable codes
lookup_var <- load_variables(2019, "acs5", cache = TRUE)

# get data for required states and append them
al_data <- get_acs(geography = "block group",
                                        state = "AL",
                                        year = 2019,
                                        variables = "B02001_002") # set required variables


# we need to join the above block-grop level census data with the notice data


#method 1: spatial join with location coordinates -
df2 <- df2 %>% filter(type%in% c("longitude", "latitude"), detail!="[]")
# Remove brackets and split the string into a list
data <- df2
data$detail <- str_replace_all(data$detail, "\\[|\\]", "")
data <- transform(data, detail = strsplit(as.character(detail), ", "))

# Expand the list into multiple rows
data_long <- unnest(data, detail)

# Split the data into latitudes and longitudes
latitudes <- data_long %>% filter(type == "latitude") %>% rename(latitude = detail)
longitudes <- data_long %>% filter(type == "longitude") %>% rename(longitude = detail)

# Remove the type column as it is no longer needed
latitudes$type <- NULL
longitudes$type <- NULL

# Merge the two data frames by noticeID and rowID
combined_data <- merge(latitudes, longitudes, by = c("noticeID"))

# Create a coordinates column by pasting latitude and longitude together
combined_data$coordinates <- paste(combined_data$latitude, combined_data$longitude, sep = ", ")



# Spread the data to wide format
data_wide <- data_long %>% 
  spread(Type, detail) %>% 
  rename(Latitude = latitude, Longitude = longitude)

##################################################################################

# method 2: use pre-made 'geocoded_location_df'
## ISSUES - at BLOCK level, also not matching IDs
options(scipen = 999, digits = 13)


geo_block <- get_object(bucket = "usace-notices",
                        object = "dashboard-data/geocoded_df.csv")

geo_block <- read.csv(text = rawToChar(geo_block))


geo_block$modified_block_fips <- substr(as.character(geo_block$block_fips), 3, nchar(as.character(geo_block$block_fips)))

al_data <- inner_join(al_data, geo_block, by = join_by(GEOID == block_fips_char))








