library(purrr)
library(tidyverse)

# Creating a sample data frame
data <- data.frame(
  type = c(rep("Notice", 5)),
  noticeID = c("Notice_NO_1", "Notice_NO_10", "Notice_NO_10", "Notice_NO_100", "Notice_NO_100"),
  districtName = c(rep("Galveston District", 5)),
  latitude = I(list(c(28.430325), c(30.27316, 30.27412), c(30.27316, 30.27412), c(29.984252, 29.984701, 29.984742, 29.983542), c(29.984252, 29.984701, 29.984742, 29.983542))),
  longitude = I(list(c(-96.443543), c(-94.03610, -93.61009), c(-94.03610, -93.61009), c(-95.573280, -95.574886, -95.574952, -95.57225), c(-95.573280, -95.574886, -95.574952, -95.57225))),
  stringsAsFactors = FALSE
)

# combines latitude and longitude into coordinates
data <- data %>%
  mutate(coord = map2(latitude, longitude, ~ if (length(.x) == length(.y)) map2(.x, .y, ~ c(.x, .y)) else list(NULL)))


# explode the list column into multiple rows
data <- data %>%
  unnest(cols = c(coord))

##########################

# convert to wide - one row = one noticeID
data_wide <- data %>%
  mutate(coord = map2(latitude, longitude, ~ map2(.x, .y, ~ c(.x, .y)))) %>%
  select(-latitude, -longitude) %>%
  group_by(noticeID) %>%
  summarize(coord = list(unlist(coord, recursive = FALSE)))


# Unnest the coordinates
data_wide <- data_wide %>%
  unnest_longer(col = coord)

# Create a new column to facilitate the pivot
data_wide <- data_wide %>%
  group_by(noticeID) %>%
  mutate(coord_id = paste0("coord", row_number())) %>%
  ungroup()

# Pivot to wide format
data_wide <- data_wide %>%
  pivot_wider(names_from = coord_id, values_from = coord)