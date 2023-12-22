# q 3, 4

# setup -------------------------------------------------------------------

source('source_script.R')
library(lubridate)
library(patchwork)
library(tigris)
library(ggspatial)
library(gganimate)

# Set up default theme for all plotting

theme_temp <- 
  theme_minimal() +
  theme(
    # panel.background = element_rect(fill = "white"),
    panel.grid.minor = element_blank(),
    title = element_text(size = 9,
                         face = "bold"),
    axis.title = element_text(face = "bold",
                              size = 9),
    axis.text = element_text(size = 8),
    legend.title = element_text(size = 9),
    legend.text = element_text(size = 8))


# Prepare analysis base ---------------------------------------------------

impact_temporal <- 
  notice$wetland_impact_df %>%
  select(!rowID) %>% 
  
  # Join impact data with main_df to get published date
  left_join(
    select(notice$main_df, noticeID, datePublished),
    by = "noticeID") %>% 
  
  # Join impact data with location_df to get district name
  left_join(
    notice$location_df %>% 
      filter(type == "districtName") %>% 
      select(!rowID) %>% 
      pivot_wider(
        names_from = "type",
        values_from = "detail"), 
    by = "noticeID") %>% 
  
  # Join impact data with geometry df to get project coordinates
  left_join(
    notice$notice_geometry,
    by = "noticeID") %>%
  
  # Clean up the date and impact units
  mutate(
    date = if_else(
      str_detect(datePublished, "-"),
      as.Date(datePublished, format = "%Y-%m-%d"),
      as.Date(datePublished, format = "%m/%d/%Y")),
    impact_quantity = 
      case_when(
        impact_unit == "miles" ~ impact_quantity * 5280,
        impact_unit == "square feet" ~ impact_quantity / 43560,
        .default = impact_quantity),
    impact_quantity = impact_quantity / 1000,
    impact_unit = 
      case_when(
        impact_unit == "linear feet" ~ "feet",
        impact_unit == "miles" ~ "feet",
        impact_unit == "square feet" ~ "acres",
        .default = impact_unit),
    impact_unit = 
      case_when(
        impact_unit == "feet" ~ "Thousand feet",
        impact_unit == "acres" ~ "Thousand acres",
        impact_unit == "cubic yards" ~ "Thousand cubic yards",
        .default = impact_unit)
  )


# How does the issuance of notices vary with time?  -----------------------

## overall trend -----------------------------------------------------------

proj_n_month <-
  impact_temporal %>% 
  transmute(
    noticeID,
    year = year(date),
    month = month(date)) %>%
  distinct() %>% 
  group_by(year, month) %>% 
  summarise(
    proj_n = n()) %>% 
  
  # plotting
  ggplot(
    aes(
      x = paste0(year, "-", month, "-01") %>% 
        as.Date(format = "%Y-%m-%d"),
      y = proj_n)) +
  geom_line(
    linewidth = 0.7) +
  
  # set labels, scales, and theme
  labs(
    title = "The number of notices published monthly") +
  scale_x_date(date_breaks = "year") + 
  theme_temp +
  theme(
    axis.text.x = element_text(angle = 20),
    axis.title = element_blank())


proj_n_year <-
  impact_temporal %>% 
  transmute(
    noticeID,
    year = year(date)) %>% 
  distinct() %>% 
  group_by(year) %>% 
  summarise(
    proj_n = n()) %>% 
  
  # plotting
  ggplot(
    aes(
      x = year,
      y = proj_n)) +
  geom_line(
    linewidth = 0.7) +
  geom_point(
    size = 1.7) +
  
  # set labels, scales, and theme
  labs(
    title = "The number of notices published annually") +
  scale_x_continuous(n.breaks = 11) + 
  theme_temp +
  theme(
    axis.title = element_blank())

proj_n_month / proj_n_year

# From 2017-2020, there was an increase in the number of notices published. The following section decomposes all notices into four districts to detect which accounts for the rise.


## by district -------------------------------------------------------------

impact_temporal %>% 
  filter(
    !is.na(districtName)) %>% 
  transmute(
    noticeID,
    year = year(date),
    districtName) %>% 
  distinct() %>% 
  group_by(year, districtName) %>% 
  summarise(
    proj_n = n()) %>% 
  
  # plotting
  ggplot(
    aes(
      x = year,
      y = proj_n,
      color = districtName)) +
  geom_line(
    size = 0.7) +
  geom_point(
    size = 1.7) +
  
  # Set labels and scales
  labs(
    y = "The number of notices published",
    title = "Jacksonville district accounts for the rise in the number of notices published in 2017-2020") + 
  scale_x_continuous(n.breaks = 12) +
  
  # Set theme
  theme_temp + 
  theme(
    legend.position = "bottom",
    legend.title = element_blank(),
    axis.title.x = element_blank())

# Jacksonville district accounts for the rise in the number of notices published in 2017-2020. In Jacksonville, there were barely any notices published before 2017, so the next section maps the distribution of notices published during the peak, 2017-2020, in Jacksonville to have a closer look at which areas contributed to the rise.


## Where in Jacksonville are most notices in 2017-2020 located? -------------------------

# Get Jacksonville district county map

county_fl_pr <-  
  tigris::counties(
    state = c("FL", "PR"), 
    cb = TRUE, 
    year = 2020) %>% 
  select(NAME, STATE_NAME)

# Count the # of projects by Jacksonville county

proj_n_saj_county <- 
  impact_temporal %>% 
  filter(
    districtName == "Jacksonville District") %>%
  
  # only look at the number of project
  transmute(
    noticeID,
    geometry,
    year = year(date)) %>% 
  distinct() %>% 
  
  # spatial join with country maps
  st_as_sf() %>% 
  st_join(
    county_fl_pr,
    .,
    join = st_intersects) %>% 
  
  # remove counties that do not have any projects
  filter(!is.na(noticeID)) %>% 
  
  # only 1 notice was published annually from 2012-2014 and no notice was pulished during 2015-2016
  # The changes in # of notices published in each country of Jacksonville during 2012-2020 is almost equal to # of notices published during 2017-2020
  group_by(STATE_NAME, NAME, geometry, year) %>% 
  summarise(proj_n = n())

# choropleth map to show the change in the # of notices published by Jacksonville country
proj_n_saj_county %>% 
  filter(
    year %in% 2017:2020) %>% 
  st_transform(crs = 3857) %>% 
  ggplot() +
  annotation_map_tile(zoom = 6) +
  geom_sf(
    aes(
      fill = proj_n),
    color = "grey50",
    alpha = 0.6) +
  
  # Set labels and scales
  labs(
    fill = "# of notices published 2017-2020") +
  scale_fill_gradient(
    low = "#deebf7",
    high = "#2171b5",
    na.value = "#ffffff") +
  
  # Set theme
  theme_temp +
  theme(
    panel.grid = element_blank(),
    axis.text = element_blank(),
    legend.position = c(0.8, 0.85),
    legend.direction = "horizontal",
    legend.background = element_rect(fill = "white",
                                     color = "white")) +
  guides(
    fill = guide_colourbar(title.position = "top",
                           barwidth = 10))

# The map shows that the increase in the number of notices in 2017-2020 mainly came from southern and northeastern Florida, specifically Monroe County.


# How does the impact size vary with time? --------------------------------

## overall trend -----------------------------------------------------------

# impact_size_year <- 
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    wetland_type != "unknown",
    !(impact_unit %in% c("other", "unknown"))) %>% 
  group_by(year, impact_unit) %>% 
  summarise(impact = sum(impact_quantity, na.rm = TRUE)) %>% 

  # plotting
  ggplot(
    aes(
      x = year,
      y = impact)) +
  geom_line(
    size = 0.7) +
  geom_point(
    size = 1.7) +
  
  # panels by unit
  facet_wrap(
    vars(impact_unit),
    scales = "free_y",
    nrow = 3) +
  
  # set labels, scales, and themes
  labs(y = "Impact size") +
  scale_x_continuous(n.breaks = 13) +
  theme_temp +
  theme(
    axis.title.x = element_blank(),
    strip.text = element_text(size = 9,
                              face = "bold"))

# There seem to be multiple peaks. Further dive into each district in the next section.


## by district -------------------------------------------------------------

impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    wetland_type != "unknown",
    !(impact_unit %in% c("other", "unknown")),
    !is.na(districtName)) %>% 
  group_by(year, districtName, impact_unit) %>% 
  summarise(
    impact = sum(impact_quantity, na.rm = TRUE)) %>% 
  
  # plotting
  ggplot(
    aes(
      x = year,
      y = impact,
      color = districtName)) +
  geom_line(
    size = 0.7) +
  geom_point(
    size = 1.7) +
  
  # panels by unit
  facet_wrap(
    vars(impact_unit),
    scales = "free_y",
    nrow = 3) +
  
  # set labels
  labs(
    x = "",
    y = "Impact size",
    color = "") +
  
  # set scales
  scale_x_continuous(n.breaks = 13) +
  
  theme_temp +
  theme(
    legend.position = "bottom",
    strip.text = element_text(size = 9,
                              face = "bold"))

# Peaks to look at:

# New Orleans:
# - acres: 2014
# - cy: 2018, 2019, 2023
# - ft: 2016, 2017, 2022

# Mobile:
# - acres: 2018, 2019, 2022, 2023
# - ft: 2015
# 
# Jacksonville:
# - acres: 2019, 2021
# - cy: 2019, 2020, 2022
# - ft: 2017, 2021
# 
# Galveston:
# - ft: 2018, 2019, 2020, 2021

# SUMMARISE for the following sub-sections:
# 1. Wrong values drive the impact abnormally high. Mistakenly took values for sq ft as acres. See the error_counting.txt for specific error notices.
# 2. Some big-impact projects (outliers) constitute the peaks. Details about those projects are listed below.

### New Orleans -------------------------------------------------------------

# acres
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    wetland_type != "unknown",
    impact_unit == "Thousand acres",
    year == 2014,
    districtName == "New Orleans District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, impact_quantity)

# Notice_NO_4668 and Notice_NO_3363 contain wrong values, driving the impact abnormally high.

# cubic years
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    wetland_type != "unknown",
    impact_unit == "Thousand cubic yards",
    year %in% c(2018, 2019, 2023),
    districtName == "New Orleans District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, datePublished, impact_quantity, wetland_type)

notice$location_df %>% 
  filter(
    noticeID %in% c("Notice_NO_2313", 
                    "Notice_NO_2033",
                    "Notice_NO_1977",
                    "Notice_NO_4522"),
    type == "parish")

# Notice_NO_2313 (2018), Notice_NO_1582 (2023), Notice_NO_1977 (2019), and Notice_NO_4522 (2019) are the main contributors to the big impact on wetlands measured in cubic yards in New Orleans in 2018, 2019, and 2023. They involved large cubic yards of fill materials for different purposes, such as increasing the evaluations, tidal control, land development, and dredging in Ascension Parish,, Terrebonne Parish, and Cameron Parish.

# feet
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    impact_type != "unknown",
    impact_unit == "Thousand feet",
    year %in% c(2016, 2017, 2022),
    districtName == "New Orleans District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, datePublished, impact_quantity, wetland_type)

notice$location_df %>% 
  filter(
    noticeID %in% c("Notice_NO_2794", 
                    "Notice_NO_2628",
                    "Notice_NO_2056"),
    type == "parish")

# Notice_NO_2794 (2016), Notice_NO_2628 (2017), and Notice_NO_2056 (2023) aare the main contributors to the big impact on wetlands measured in linear feet in New Orleans in 2016, 2017, and 2023. They were to clean vegetation and debris of canals and create marsh terraces). Canal projects are in Tangipahoa Parish and the Terrance project is in Lafourche Parish.


### Mobile ------------------------------------------------------------------

# acres
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    impact_type != "unknown",
    impact_unit == "Thousand acres",
    year %in% c(2018, 2019, 2022, 2023),
    districtName == "Mobile District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, date, impact_quantity)

# For Notice_NO_1251 (2019), Notice_NO_1094 (2022), Notice_NO_3647 (2018), Notice_NO_1102 (2022), Notice_NO_1023 (2023), LLM mistakenly assigned impact quantity in square ft to impact unit acres, which drive the impact in Mobile district abnormally high

impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    !(noticeID %in% c("Notice_NO_1251", "Notice_NO_1094", "Notice_NO_3647", "Notice_NO_1102", "Notice_NO_1023")),
    impact_type != "unknown",
    impact_unit == "Thousand acres",
    districtName == "Mobile District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, date, impact_quantity)

# "Notice_NO_1243", "Notice_NO_1431", "Notice_NO_1241", "Notice_NO_3550", "Notice_NO_1049" are the main contributors to the big impact on wetlands measured in acres in Mobile district in 2015, 2016, 2019, 2023. They were to construct an artificial reef zone in the Gulf of Mexico.

# Feet
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    impact_type != "unknown",
    impact_unit == "Thousand feet",
    districtName == "Mobile District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, date, impact_quantity, wetland_type)

notice$location_df %>% 
  filter(
    noticeID %in% c("Notice_NO_3722", 
                    "Notice_NO_3748"),
    type == "county")

# "Notice_NO_3722" and "Notice_NO_3748" are the main contributors to the big impact on wetlands measured in linear feet in the Mobile district in 2015. They were about construct barge access channels and breakwater structures in Hancock County.


### Jacksonville ------------------------------------------------------------

# acres
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    impact_type != "unknown",
    impact_unit == "Thousand acres",
    year %in% c(2019, 2021),
    districtName == "Jacksonville District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, date, impact_quantity)

# For Notice_NO_889 (2021) and Notice_NO_5543 (2019), LLM mistakenly assigned impact quantity in square ft and cubic yards to impact unit acres, which drive the impact in Mobile district abnormally high

# cubic yards
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    wetland_type != "unknown",
    impact_unit == "Thousand cubic yards",
    year %in% c(2019, 2020, 2022),
    districtName == "Jacksonville District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, date, impact_quantity, wetland_type)

notice$location_df %>% 
  filter(
    noticeID %in% c("Notice_NO_691", 
                    "Notice_NO_4061",
                    "Notice_NO_5539",
                    "Notice_NO_5462"),
    type == "county")

# "Notice_NO_691", "Notice_NO_4061", "Notice_NO_5539", and "Notice_NO_5462" are the main contributors to the big impact on wetlands measured in cubic yards in Jacksonville district in 2019, 2020 and 2022. They were about beach renourishment in the Gulf of Mexico, specially in Lee County and Palm Beach County, Indian River County, and Duval County, respectively.

# Feet
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    wetland_type != "unknown",
    impact_unit == "Thousand feet",
    year %in% c(2017, 2021),
    districtName == "Jacksonville District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, date, impact_quantity, wetland_type)


notice$location_df %>% 
  filter(
    noticeID %in% c("Notice_NO_4013", 
                    "Notice_NO_6132",
                    "Notice_NO_6139"),
    type == "county")

# "Notice_NO_4013", "Notice_NO_6132", and "Notice_NO_6139" are the main contributors to the big impact on wetlands measured in linear feet in Jacksonville district in 2017 and 2021. They were about shoreline stabilization in Charlotte County, Martin County, respectively.


### Galveston ---------------------------------------------------------------

# Feet
impact_temporal %>% 
  mutate(
    year = lubridate::year(date)) %>% 
  filter(
    wetland_type != "unknown",
    impact_unit == "Thousand feet",
    year %in% 2018:2021,
    districtName == "Galveston District") %>% 
  arrange(desc(impact_quantity)) %>% 
  select(noticeID, date, impact_quantity, wetland_type)

notice$location_df %>% 
  filter(
    noticeID %in% c("Notice_NO_292", 
                    "Notice_NO_450",
                    "Notice_NO_4403"),
    type == "county")

# "Notice_NO_292", "Notice_NO_450", and "Notice_NO_4403" are the main contributors to the big impact on wetlands measured in linear feet in Galveston district from 2018 to 2021. They were about beach maintenance and nourishment in Galveston County and Cameron County.


## Where are those big-impact projects located? ---------------------------------------

# Get four districts' states map
states <-  
  tigris::states(cb = TRUE, year = 2020) %>% 
  select(NAME)

# Draw the US boundaries to exclude those that are outside of the US because of incorrect lon/lat pulled (Maybe)
us <- 
  st_union(states)

# Create a sf object for the big-impact projects
impact_big <- 
  impact_temporal %>% 
  filter(
    noticeID %in% c("Notice_NO_2313", 
                    "Notice_NO_1582", 
                    "Notice_NO_1977", 
                    "Notice_NO_4522", 
                    "Notice_NO_2794", 
                    "Notice_NO_2628", 
                    "Notice_NO_2056",
                    "Notice_NO_1243", 
                    "Notice_NO_1431", 
                    "Notice_NO_1241", 
                    "Notice_NO_3550", 
                    "Notice_NO_1049",
                    "Notice_NO_3722", 
                    "Notice_NO_3748",
                    "Notice_NO_691", 
                    "Notice_NO_4061",
                    "Notice_NO_5539",
                    "Notice_NO_5462",
                    "Notice_NO_4013",
                    "Notice_NO_6132", 
                    "Notice_NO_6139",
                    "Notice_NO_292",
                    "Notice_NO_450",
                    "Notice_NO_4403"),
    !(impact_unit %in% c("unknown", "other"))) %>%
  mutate(
    impact_type = 
      case_when(
        impact_type %in% c("enhancement",
                           "positive",
                           "nourishment",
                           "restoration",
                           "maintenance",
                           "stabilization") ~ "mainenance/enhancement/nourishment/restoration/stablization",
        impact_type %in% c("loss",
                           "damage") ~ "loss/damage",
        impact_type %in% c("addition", 
                           "modification",
                           "placement") ~ "modification/placement",
        .default = impact_type)) %>% 
  st_as_sf() %>% 
  st_filter(us)

# prepare base map
base_osm <- 
  OpenStreetMap::openmap(
    c(33, -100),
    c(20, -77),
    minNumTiles = 7,
    type = "osm")

# map the big-impact projects on top of the base map
OpenStreetMap::autoplot.OpenStreetMap(
  OpenStreetMap::openproj(base_osm)) +
  geom_point(
    data = 
      as_tibble(
        sf::st_coordinates(impact_big)) %>% 
      bind_cols(
        impact_type = impact_big$impact_type), 
    aes(x = X, 
        y = Y,
        shape = impact_type,
        color = impact_type),
    alpha = 0.7,
    size = 5,
    position = position_jitter(width = 0.3, height = 0.3)) +
  
  # Set labels and scales
  labs(
    shape = "Impact Type",
    color = "Impact Type") +
  scale_shape_manual(
    values = c(17, 16, 18, 15)) +
  
  # Set theme
  theme_temp +
  theme(
    axis.text = element_blank(),
    axis.title = element_blank(),
    axis.ticks = element_blank(),
    legend.position = c(0.4, 0.15),
    legend.direction = "horizontal",
    legend.title = element_text(size = 9),
    legend.text = element_text(size = 8),
    # legend.margin = margin(0, 0, 0, 0, unit = "pt"),
    legend.background = element_rect(fill = "white",
                                     color  = "white")) +
  guides(
    shape = guide_legend(title.position = "top",
                         ncol = 2),
    color = guide_legend(title.position = "top",
                         ncol = 2))

# Many projects of big impact identified as loss/damage clustered in the Baton Rouge and New Orleans area, along the Mississippi River, and in the bayous of South Louisiana. Some identified as maintenance/enhancement/nourishment/restoration/stabilization were located at the eastern shoreline of Florida.


# impact type -------------------------------------------------------------

proj_type_sf <- 
  notice$embed_proj_type_df %>% 
  select(noticeID, project_category) %>% 
  
  # Reduce the project categories
  mutate(
    project_category = 
      case_when(
        str_detect(project_category, "Oil") ~ "Oil and Gas",
        str_detect(project_category, "Residential") ~ "Residential Buildout",
        str_detect(project_category, "Drainage") ~ "Drainage",
        str_detect(project_category, "[R|r]estoration") ~ "Restoration",
        .default = "Other")) %>% 
  
  # Get date and geometry columns and create sf object
  left_join(
    impact_temporal %>% 
      select(c(noticeID, date, geometry)) %>% 
      distinct(),
    by = "noticeID") %>% 
  mutate(
    year = year(date)) %>% 
  st_as_sf() %>% 
  st_filter(us)


# prepare base map
base_osm <- 
  OpenStreetMap::openmap(
    c(36, -100),
    c(22, -77),
    minNumTiles = 7,
    type = "osm")

# Oil and Gas
oil_gas <- 
  OpenStreetMap::autoplot.OpenStreetMap(
    OpenStreetMap::openproj(base_osm)) +
  geom_point(
    data = 
      proj_type_sf %>% 
      filter(project_category == "Oil and Gas") %>% 
      sf::st_coordinates() %>% 
      as_tibble() %>% 
      bind_cols(
        year = 
          filter(proj_type_sf, 
                 project_category == "Oil and Gas") %>% 
          pull(year)),
    aes(x = X, 
        y = Y),
    alpha = 0.6,
    color = "orange",
    size = 2,
    position = position_jitter(width = 0.1, height = 0.1)) +
  
  labs(
    title = "Oil and Gas Facilities") +
  
  # Set theme
  theme_temp +
  theme(
    axis.text = element_blank(),
    axis.title = element_blank(),
    axis.ticks = element_blank()) 

# Residential
residential <- 
  OpenStreetMap::autoplot.OpenStreetMap(
    OpenStreetMap::openproj(base_osm)) +
  geom_point(
    data = 
      proj_type_sf %>% 
      filter(project_category == "Residential Buildout") %>% 
      sf::st_coordinates() %>% 
      as_tibble() %>% 
      bind_cols(
        year = 
          filter(
            proj_type_sf, 
            project_category == "Residential Buildout") %>% 
          pull(year)),
    aes(x = X, 
        y = Y),
    alpha = 0.6,
    color = "#6a51a3",
    size = 2,
    position = position_jitter(width = 0.1, height = 0.1)) +
  
  labs(
    title = "Residential Subsivisions") +
  
  # Set theme
  theme_temp +
  theme(
    axis.text = element_blank(),
    axis.title = element_blank(),
    axis.ticks = element_blank()) 


# Dredging
drainage <- 
  OpenStreetMap::autoplot.OpenStreetMap(
    OpenStreetMap::openproj(base_osm)) +
  geom_point(
    data = 
      proj_type_sf %>% 
      filter(project_category == "Drainage") %>% 
      sf::st_coordinates() %>% 
      as_tibble() %>% 
      bind_cols(
        year = 
          filter(
            proj_type_sf, 
            project_category == "Drainage") %>% 
          pull(year)),
    aes(x = X, 
        y = Y),
    alpha = 0.6,
    color = "#4292c6",
    size = 2,
    position = position_jitter(width = 0.1, height = 0.1)) +
  
  labs(
    title = "Drainage Features") +
  
  # Set theme
  theme_temp +
  theme(
    axis.text = element_blank(),
    axis.title = element_blank(),
    axis.ticks = element_blank()) 

# Restoration
restoration <- 
  OpenStreetMap::autoplot.OpenStreetMap(
    OpenStreetMap::openproj(base_osm)) +
  geom_point(
    data = 
      proj_type_sf %>% 
      filter(project_category == "Restoration") %>% 
      sf::st_coordinates() %>% 
      as_tibble() %>% 
      bind_cols(
        year = 
          filter(
            proj_type_sf, 
            project_category == "Restoration") %>% 
          pull(year)),
    aes(x = X, 
        y = Y),
    alpha = 0.6,
    color = "#41ae76",
    size = 2,
    position = position_jitter(width = 0.1, height = 0.1)) +
  
  labs(
    title = "Restoration") +
  
  # Set theme
  theme_temp +
  theme(
    axis.text = element_blank(),
    axis.title = element_blank(),
    axis.ticks = element_blank()) 

# Other
Other <- 
  OpenStreetMap::autoplot.OpenStreetMap(
    OpenStreetMap::openproj(base_osm)) +
  geom_point(
    data = 
      proj_type_sf %>% 
      filter(project_category == "Other") %>% 
      sf::st_coordinates() %>% 
      as_tibble(),
    aes(x = X, 
        y = Y),
    alpha = 0.6,
    color = "#252525",
    size = 2,
    position = position_jitter(width = 0.1, height = 0.1)) +
  
  # Set theme
  theme_temp +
  theme(
    axis.text = element_blank(),
    axis.title = element_blank(),
    axis.ticks = element_blank()) 

(oil_gas | residential) / (drainage | restoration)

# The hotpots for oil and gas projects are Trinity Bay, Galveston Bay, Sabine Lake (close to Houston) in Texas and the bayous areas in the south of New Orleans in Louisiana.

# Besides the Houston and New Orleans areas, Florida, especially its shoreline, is a hot spot for residential and drainage projects. Only a few projects are categorized as restoration in New Orleans area.


## How do different project category types change over time? -----------------------

# Animation of changes in the project locations for different project categories

oil_gas +
  transition_states(
    year, 
    transition_length = 5, 
    state_length = 5) +
  enter_fade() +
  exit_fade() +
  labs(
    title = "Oil and Gas",
    subtitle = "Year: {closest_state}")


residential +
  transition_states(
    year, 
    transition_length = 5, 
    state_length = 5) +
  enter_fade() +
  exit_fade() +
  labs(
    title = "Residential Buildout",
    subtitle = "Year: {closest_state}")

drainage +
  transition_states(
    year, 
    transition_length = 5, 
    state_length = 5) +
  enter_fade() +
  exit_fade() +
  labs(
    title = "Drainage features",
    subtitle = "Year: {closest_state}")

restoration +
  transition_states(
    year, 
    transition_length = 5, 
    state_length = 5) +
  enter_fade() +
  exit_fade() +
  labs(
    title = "Restoration",
    subtitle = "Year: {closest_state}")


# How does the number of notices in different project categories change over time?

# Create a df including impact data
proj_type_df <- 
  notice$embed_proj_type_df %>% 
  select(noticeID, project_category) %>% 
  mutate(
    project_category = 
      case_when(
        str_detect(project_category, "Oil") ~ "Oil and Gas",
        str_detect(project_category, "Residential") ~ "Residential Buildout",
        str_detect(project_category, "Drainage") ~ "Drainage",
        str_detect(project_category, "[R|r]estoration") ~ "Restoration",
        .default = "Other")) %>% 
  left_join(
    impact_temporal %>% 
      select(noticeID, impact_unit, impact_quantity, date),
    .,
    by = "noticeID")

proj_type_df %>% 
  filter(
    project_category != "Other",
    !is.na(project_category)) %>% 
  transmute(
    noticeID,
    # month = paste0(year(date), "-", month(date), "-01") %>% 
    #   as_date(),
    year = year(date),
    project_category) %>% 
  distinct() %>% 
  group_by(project_category, year) %>%
  summarise(proj_n = n()) %>% 
  ggplot(
    aes(
      x = year,
      y = proj_n,
      color = project_category)) +
  geom_line(
    # color = "#4eb3d3",
    size = 0.7) +
  geom_point(
    size = 1.7) +
  labs(
    y  = "The number of notices bulished",
    title = "Residential projects accounted for the peak in notices published during 2018-2019",
    color = "Project Category") +
  scale_x_continuous(n.breaks = 13) +
  theme_temp +
  theme(
    axis.title.x = element_blank(),
    legend.position = "bottom") +
  guides(
    color = guide_legend(title.position = "top",
                         title.hjust = 0.5))

# The number of notices relevant to oil and gas is relatively small compared to other project categories. Supplement to the previous temporal analysis projects relevant to residential buildout contributed to the rise of notices published in 2017-2020.


## oil and gas -------------------------------------------------------------

# Compare impact size with other categories

proj_type_df %>% 
  group_by(project_category, impact_unit) %>% 
  summarise(
    impact_size = sum(impact_quantity, na.rm = T)) %>% 
  filter(
    project_category != "Other",
    !(impact_unit %in% c("other", "unknown")),
    !is.na(project_category)) %>% 
  
  # plotting
  ggplot() +
  geom_col(
    aes(
      x = project_category,
      y = impact_size),
    fill = "#4eb3d3") +
  facet_wrap(
    vars(impact_unit),
    scales = "free_y") +
  labs(
    y = "Impact Size") +
  theme_temp +
  theme(
    axis.text.x = element_text(angle = 90,
                               hjust = 1),
    axis.title.x = element_blank(),
    strip.text = element_text(face = "bold"))

# The impact measured by different units of projects relevant to oil and gas is relatively small compared to other project categories.

# How did the number of oil and gas notices published change over time?

proj_type_df %>% 
  filter(
    project_category == "Oil and Gas") %>% 
  transmute(
    noticeID,
    month = paste0(year(date), "-", month(date), "-01") %>% 
      as_date()) %>% 
  distinct() %>% 
  group_by(month) %>%
  summarise(proj_n = n()) %>% 
  
  # plotting
  ggplot() +
  geom_line(
    aes(
      x = month,
      y = proj_n),
    color = "#4eb3d3",
    size = 0.7) +
  labs(
    y  = "The number of notices bulished",
    title = "Proposed oil and gas-relevant projects increased in October of 2018") +
  scale_x_date(date_breaks = "year") +
  theme_temp +
  theme(
    axis.title.x = element_blank(),
    axis.text.x = element_text(angle = 30))

# 2018
oil_gas_2018 <- 
proj_type_df %>% 
  filter(
    project_category == "Oil and Gas",
    year(date) == 2018) %>%
  transmute(
    noticeID,
    month = month(date)) %>% 
  distinct() 

oil_gas_2018 %>% 
  group_by(month) %>% 
  summarise(proj_n = n())

# Oct, 2018 had 6 projects:
oil_gas_2018 %>% 
  filter(month == 10)

# Notice_NO_404: A new natural gas fired compressor station
# Notice_NO_406: LNG and 3 pipelines across Texas and Louisanan
# Notice_NO_408 and Notice_NO_409: Natural gas processing and distilling plant
# Notice_NO_2324: Drill brine wells (not a oil and gas project)
# Notice_NO_2328: Drill the South Houma Prospect
