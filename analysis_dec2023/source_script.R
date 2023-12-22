# 0 - Source data

# setup -------------------------------------------------------------------

# Check if the packages needed are installed
packages_required <- 
  c("tidyverse", 
    "tidycensus", 
    "aws.s3",
    "dotenv",
    "sf",
    "lubridate",
    "patchwork",
    "tigris",
    "ggspatial",
    "gganimate")

for (package in packages_required) {
  if (!requireNamespace(package, quietly = TRUE)) {
    install.packages(package)
  } else {
    print(
      paste0(package, " is installed"))
  }
}

rm(packages_required)
rm(package)

# Load packages
library(tidycensus)
library(aws.s3)
library(tidyverse)
library(dotenv)
library(sf)

# Set up the connection to AWS
dotenv::load_dot_env()

Sys.setenv(
  "AWS_ACCESS_KEY_ID" = Sys.getenv("AWS_ACCESS_KEY_ID"),
  "AWS_SECRET_ACCESS_KEY" = Sys.getenv("AWS_SECRET_ACCESS_KEY"),
  "AWS_DEFAULT_REGION" = "us-east-1")

# Get tidycensus API
census_api_key <- Sys.getenv("CENSUS_API_KEY")


# Get relevant objects from the bucket ------------------------------------

# Specify which tables to be loaded in R

tbl_to_load = 
  c("wetland_final_df.csv", # wetland impact
    "location_df.csv", # extract lon/lat
    # "geocoded_df.csv", # based on 2010 census
    "embed_final_df.csv", # embedding and project types
    "main_df.csv") # publish time

# Load all notice tables into a list

notice <- 
  tbl_to_load %>% 
  map(
    ~ {
      print(
        paste0("Getting ",
               .x))
      
      # Get object in bytes from S3 bucket
      tbl_bytes <- 
        get_object(
          bucket = "usace-notices",
          object = 
            paste0("dashboard-data/",
                   .x))
      
      # Convert the byte object into df
      read.csv(text = rawToChar(tbl_bytes)) %>% 
        as_tibble()
      }
    ) %>%
  
  # Name the df in the notice list
  set_names(
    c("wetland_impact_df",
      "location_df",
      "embed_proj_type_df",
      "main_df"))

rm(tbl_to_load)

# Pull census data --------------------------------------------------------

# EXAMPLE: Census block-group data - NOT YET FINAL

# Get dataframe of variable codes
# lookup_var <- load_variables(2019, "acs5", cache = TRUE)

# get census data for relevant states

# acs_2019 <- 
  # get_acs(
  #   year = 2019,
  #   survey = "acs5",
  #   key = census_api_key,
  #   geography = "block group",
  #   state = c("AL", "FL", "LA", "TX", "MS", "PR"),
  #   variables = "B02001_001", # set required variables
  #   geometry = FALSE)


# Create the point geometry column ----------------------------------------

notice[["notice_geometry"]] <- 
  notice$location %>% 
  select(!rowID) %>% 
  
  # Remove non-lon/lat info and empty lon/lat 
  filter(
    type %in% c("longitude", "latitude"), 
    detail != "[]") %>% 
  
  # Extract the first lon/lat of each project and create columns
  mutate(
    detail = 
      detail %>% 
      str_replace_all("\\[|\\]|\'", "") %>% 
      str_extract(".*?(?=(,|$))") %>% 
      as.numeric()) %>% 
  pivot_wider(
    names_from = "type",
    values_from = "detail") %>% 
  
  # Create sf object by converting lon/lat to geometry
  filter(
    !is.na(latitude),
    !is.na(longitude)) %>% 
  st_as_sf(
    coords = c("longitude", "latitude"),
    crs = 4269) # mofigy crs as needed

print("Created project coordinate geometry")








