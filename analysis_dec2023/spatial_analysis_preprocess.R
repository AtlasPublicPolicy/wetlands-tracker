
#devtools::install_github("redivis/redivis-r", ref="main")
#install.packages("devtools")
library(aws.s3)
library(tidyverse)
library(arrow)
library(lubridate)
library(ggplot2)
library(strucchange)
library(ggthemes)
library(tidycensus)
library(sf)
library(redivis)
library(purrr)


setwd('analysis_dec2023') 


# Set your tidycensus API key
census_api_key("")

# enter AWS credentials
Sys.setenv("AWS_ACCESS_KEY_ID" = "",
           "AWS_SECRET_ACCESS_KEY" = "",
           "AWS_DEFAULT_REGION" = "us-east-1")


#get_bucket(bucket = "usace-notices")
files <- get_bucket_df(
  bucket = "usace-notices", 
  region = "us-east-1", 
  max = 20000
) %>% 
  as_tibble()


# GET TABLES

# 1- geocoded locations

loc_df <- get_object(bucket = "usace-notices",
                  object = "dashboard-data/location_df.csv")

loc_df <- read.csv(text = rawToChar(loc_df))

write_csv(loc_df, 'data_download/location_df.csv')



##################################################


# 2. Spatial analysis
# First, reshape the dataframe to spread latitude and longitude into separate columns
reshaped_df <- loc_df %>%
  filter(type %in% c('latitude', 'longitude')) %>%
  pivot_wider(names_from = "type", values_from = "detail") %>%
  group_by(noticeID) %>%
  summarize(latitude = na.omit(latitude)[1],
            longitude = na.omit(longitude)[1])

# Function to parse the latitude and longitude strings into numeric vectors
parse_coordinates <- function(coord_str) {
  coord_str %>%
    str_replace_all("\\[|\\]|'", "") %>%  # Remove brackets and single quotes
    str_split(", ") %>%                  # Split string into a list
    unlist() %>%                         # Flatten the list
    as.numeric()                         # Convert to numeric
}


# Function to pair latitudes and longitudes
create_coord_pairs <- function(lat, lon) {
  if (length(lat) == length(lon)) {
    map2(lat, lon, ~ paste(.x, .y, sep = ", "))
  } else {
    list(NA_character_)  # Handle error or mismatch in length
  }
}

# Applying the function to the dataframe
reshaped_df <- reshaped_df %>% 
  group_by(noticeID) %>%
  mutate(lat = map(latitude, parse_coordinates),
         lon = map(longitude, parse_coordinates)) %>% 
  select(noticeID, lat, lon) %>% 
  mutate(coord = map2(lat, lon, create_coord_pairs)) %>%
  filter_at(vars(lat,lon),any_vars(!is.na(.))) %>%
unnest(coord) 



##############

#plot points - Converting reshaped_df to an sf object


reshaped_sf <- reshaped_df %>%
  filter(!is.na(coord) & lat != "NA" & lon != "NA") %>%
  separate(coord, into = c("latitude", "longitude"), sep = ",", convert = TRUE) %>%
  st_as_sf(coords = c("longitude", "latitude"), crs = 4326)

ggplot(data = reshaped_sf) +
  geom_sf() +
  theme_minimal()


###########
# Convert to WIDE - 1 row = 1 noticeID
data_wide <- reshaped_df %>%
  group_by(noticeID) %>%
  mutate(coord_id = paste0("coord", row_number())) %>%
  ungroup() %>%
  pivot_wider(names_from = coord_id, values_from = coord)

####################################################


# Fetch data for Alabama
options(tigris_use_cache = TRUE)



al_acs <- get_acs(variables = c(total_pop = "B02001_001E", 
                                 white_pop = "B02001_002E", 
                                 black_pop = "B02001_003E", 
                                median_inc = "B19013_001E"),
                  geography = "block group",   geometry = TRUE,
                   state = "AL", year = 2019) %>%    
  filter(!is.na(variable))  %>% 
  pivot_wider(
    names_from = "variable", 
    values_from = "estimate") %>%
  group_by(GEOID, geometry) %>%
  summarize(total_pop = mean(B02001_001, na.rm = TRUE),
            white_pop = mean(B02001_002, na.rm = TRUE),
            black_pop = mean(B02001_003, na.rm = TRUE),
            median_inc = mean(B19013_001, na.rm = TRUE)
            
            ) %>%
  ungroup()


# Define function to get ACS data and geometry
get_acs_func <- function(select_st, select_yr) {
  # Fetch ACS data
  st_acs <- get_acs(variables = c(total_pop = "B02001_001E", 
                                  white_pop = "B02001_002E", 
                                  black_pop = "B02001_003E", 
                                  median_inc = "B19013_001E"),
                    geography = "block group",
                    geometry = TRUE,
                    state = select_st, 
                    year = select_yr) %>%
    # Clean and reshape the data
    filter(!is.na(variable)) %>%
    pivot_wider(names_from = "variable", values_from = "estimate") %>%
    group_by(GEOID, geometry) %>%
    summarize(total_pop = mean(B02001_001, na.rm = TRUE),
              white_pop = mean(B02001_002, na.rm = TRUE),
              black_pop = mean(B02001_003, na.rm = TRUE),
              median_inc = mean(B19013_001, na.rm = TRUE)) %>%
    ungroup()
  
  # Return the result
  return(st_acs)
}


# get data for each state

al_acs <- get_acs_func("AL", 2019)

la_acs <- get_acs_func("LA", 2019)

tx_acs <- get_acs_func("TX", 2019)


# plot
basic_plot <- ggplot(data = tx_acs) +
  geom_sf() +
  theme_minimal()
basic_plot


##################################################


## Spatial Join location with Census/CEJST

# Spatial join - Blocgroup
al_acs <- st_transform(al_acs, 4326)
joined_df <- st_join( reshaped_sf,al_acs,
                      join = st_within)%>% 
  filter(!is.na(GEOID))

# Plotting
# Plot without spatial join
ggplot() +
  geom_sf(data = al_acs, fill = "lightblue") +
  geom_sf(data = joined_df, color = "red") +
  theme_minimal() +
  ggtitle("Points over Polygons (Without Spatial Join)")



# CEJST

# Authenticate  (replace with your credentials or token)
# link to dataset: https://redivis.com/datasets/jf53-3sapx6pmv/tables/4d46-2t7fab7tf?v=next

cj <- read_csv('CEJST_communities_list_shapefile.csv')

# Filter rows where SF is 'Texas'
cj <- cj %>%  filter( SF %in% c('Texas', 'Alabama', 'Louisiana'))

## plot for Alabama, replace with needed state
cj_al <- cj %>%  filter( SF %in% c('Alabama')) %>%
  st_as_sf(wkt = "geometry", crs = 4326)


joined_df <- st_join( reshaped_sf, cj_al,
                      join = st_within)%>% 
  filter(!is.na(GEOID10))

# Plotting
# Plot without spatial join
ggplot() +
  geom_sf(data = cj_al, fill = "lightblue") +
  geom_sf(data = joined_df, color = "red") +
  theme_minimal() +
  ggtitle("Points over Polygons (Without Spatial Join)")

#################################################################


# 2- VALIDATION/MAIN DF
val_df <- get_object(bucket = "usace-notices",
                     object = "dashboard-data/validation_df.csv")

val_df <- read.csv(text = rawToChar(val_df))

write_csv(val_df, 'data_download/validation_df.csv')

# 3 - embedding/project type
emb_df <- get_object(bucket = "usace-notices",
                     object = "dashboard-data/embed_final_df.csv")

emb_df <- read.csv(text = rawToChar(emb_df))

# 4 - WETLAND DF
# 3 - embedding/project type
wet_df <- get_object(bucket = "usace-notices",
                     object = "dashboard-data/wetland_final_df.csv")

wet_df <- read.csv(text = rawToChar(wet_df))


# subset to projects where impacts are loss/adverse
# impact type - loss

loss_impacts <- c('adverse impact', 'adversely impacted', 'damage',
                  'displacement', 'fill', 'fill material', 'filling', 'loss')

wet_loss <- wet_df %>% filter(impact_type %in% loss_impacts) %>% 
 #filter()
  group_by(noticeID) %>% summarize(n_losses=n_distinct(rowID))

#join filtered wetlands to above spatial data
joined_df2<- left_join(joined_df, wet_loss, by="noticeID") %>%
  mutate(n_losses = ifelse(is.na(n_losses), 0, n_losses))


# 2nd variable - project type, from emb_df table
joined_df2<- left_join(joined_df2, emb_df, by="noticeID") 

# Plotting

# Plotting point map
plot <- ggplot() +
  geom_sf(data = cj_al, fill = "lightblue") +
  geom_sf(data = joined_df2, aes(color = n_losses)) +
  scale_color_gradient(low = "blue", high = "red", na.value = "blue",
                       limits = c(0, max(joined_df2$n_losses, na.rm = TRUE))) +
  theme_minimal() +
  ggtitle("Projects with impacts: loss, Alabama") +
  labs(color = "No. of separate impacts",
       caption = "Note: Color represents the number of separate wetland impacts classified as loss") +
  theme(axis.text.x = element_blank(), axis.text.y = element_blank(),  # Remove axis text
        axis.ticks = element_blank(),  # Remove axis ticks
        plot.margin = margin(5.5, 5.5, 30, 5.5, "pt"))     #Adjust margins to make space for note

plot

# similarly plot project type


# Reminder: USACE districts are separate from Census or state boundaries.
# Mobile district contains almost all of Alabama
# shapes here: https://www.usace.army.mil/Missions/Locations/


#######

# if already downloaded, read in


###########

# gen var for district names
val_df <- val_df %>%
  mutate(distName = case_when(
    pdf_districtCode == "SAJ" ~ "Jacksonville",
    pdf_districtCode == "SAM" ~ "Mobile",
    pdf_districtCode == "SWG" ~ "Galveston",
    pdf_districtCode == "MVN" ~ "New Orleans",
    TRUE ~ as.character(pdf_districtCode)  # Keep the original 'detail' if it doesn't match any of the above
  ))

# Function to try multiple date formats
tryFormats <- function(date, formats) {
  for (format in formats) {
    result <- tryCatch(as.Date(date, format=format), error=function(e) NA)
    if (!is.na(result)) {
      return(result)
    }
  }
  return(NA)
}

# Define a vector of possible date formats
dateFormats <- c("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y")  # Add all formats you expect

# Apply the function to your date column
converted_dates <- sapply(val_df$datePublished, function(x) tryFormats(x, dateFormats))

# Ensure the conversion to Date type and then format
val_df$YearMonth <- ifelse(!is.na(converted_dates), format(as.Date(converted_dates), "%Y-%m"), NA)


#############################

## 1. Temporal analysis


## 1.1 Total and single

groupby_data <- function(df, district = "total") {
  
  # Convert YearMonth to Date
  df$YearMonth <- as.Date(paste0(df$YearMonth, "-01"))
  
  # Filter and summarise data based on district
  if (district != "all" && district != "total") {
    monthly_data <- df %>% 
      filter(distName == district) %>%
      group_by(YearMonth, distName) %>%
      summarise(n_notices = n_distinct(noticeID)) %>%
      filter(!is.na(YearMonth))
    
  } else if (district == "total") {
    monthly_data <- df %>% 
      group_by(YearMonth) %>%
      summarise(n_notices = n_distinct(noticeID)) %>%
      filter(!is.na(YearMonth))
    
  } else if (district == "all") {
    monthly_data <- df %>% 
      group_by(YearMonth, distName) %>%
      summarise(n_notices = n_distinct(noticeID)) %>%
      filter(!is.na(YearMonth)) %>% 
      filter(!grepl("error", distName, ignore.case = TRUE))
  }
  
  return(monthly_data)
}


## Single plot

tsplot_single <- function(df, struc_break = FALSE) {
  # Perform structural break analysis if needed
  if (struc_break) {
    breakpoints_analysis <- breakpoints(df$n_notices ~ 1, h = 8)
    bp_indices <- breakpoints_analysis$breakpoints
    
    # Map indices to MonthYear
    bp_dates <- df$YearMonth[bp_indices]
    
    
    # Extract the date of the last breakpoint
    last_bp_date <- tail(bp_dates, n = 1)
  }
  
  # Plotting
  p <- ggplot(df, aes(x = YearMonth, y = n_notices)) +
    geom_line() +
    scale_color_brewer(palette = "Set1") +
    theme_minimal(base_size = 12) +
    labs(title = "Notices Published by District and Month",
         x = "Month",
         y = "Number of Notices",
         color = "District") +
    scale_x_date(date_labels = "%Y-%m", date_breaks = "2 year") +
    theme_economist() +
    theme(plot.title = element_text(size = 16, face = "bold"),
          axis.title = element_text(size = 14),
          legend.position = "bottom",
          legend.title.align = 0.5,
          legend.text = element_text(size = 10),
          axis.text.x = element_text(angle = 45, hjust = 0),
          axis.text.y = element_text(angle = 0, hjust = 1)) +
    geom_smooth(method = "loess", se = TRUE)
  
  # Add structural break lines and annotations if applicable
  if (struc_break && !is.null(bp_dates)) {
    p <- p + geom_vline(xintercept = last_bp_date, color = "black", linetype = "dashed") +
      annotate("text", x = last_bp_date, y = max(df$n_notices), label = last_bp_date, hjust = -0.1, vjust = 1.5)
  }
  
  # Handle view type for faceted plot
  
  return(p)
}



## Multi-plot
tsplot_multi <- function(df, struc_break = FALSE, view = "facet") {
  # Perform structural break analysis if needed
  if (struc_break) {
    breakpoints_analysis <- breakpoints(df$n_notices ~ 1, h = 8)
    bp_indices <- breakpoints_analysis$breakpoints
    
    # Map indices to MonthYear
    bp_dates <- df$YearMonth[bp_indices]
    
    # Extract the date of the last breakpoint
    last_bp_date <- tail(bp_dates, n = 1)
  }
  
  # Plotting
  p <- ggplot(df, aes(x = YearMonth, y = n_notices, color = distName)) +
    geom_line() +
    scale_color_brewer(palette = "Set1") +
    theme_minimal(base_size = 12) +
    labs(title = "Notices Published by District and Month",
         x = "Month",
         y = "Number of Notices",
         color = "District") +
    scale_x_date(date_labels = "%Y-%m", date_breaks = "2 year") +
    theme_economist() +
    theme(plot.title = element_text(size = 16, face = "bold"),
          axis.title = element_text(size = 14),
          legend.position = "bottom",
          legend.title.align = 0.5,
          legend.text = element_text(size = 10),
          axis.text.x = element_text(angle = 45, hjust = 0),
          axis.text.y = element_text(angle = 0, hjust = 1)) +
    geom_smooth(method = "loess", se = TRUE)
  
  # Add structural break lines and annotations if applicable
  if (struc_break && !is.null(bp_dates)) {
    p <- p + geom_vline(xintercept = last_bp_date, color = "black", linetype = "dashed") +
      annotate("text", x = last_bp_date, y = max(df$n_notices), label = format(last_bp_date, "%Y-%m"), hjust = -0.1, vjust = 1.5)
  }
  
  # Handle view type for faceted plot
  if (view == "facet") {
    p <- p + facet_wrap(~distName)
  }
  
  return(p)
}


dft <- groupby_data(val_df, district="all")
cc <- tsplot_multi(dft, struc_break = TRUE, view="facet")
cc


cc <- tsplot_single(dft, struc_break = TRUE)

#ggsave("pics/p6_brk.png", width = 11, height = 8.5, dpi = 300)

##################################################################
