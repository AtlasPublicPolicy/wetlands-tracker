
install.packages('ggthemes')
# For data manipulation (similar to pandas)
library(tidyverse)
library(readr)
# For advanced matrix operations
library(matrixStats)
# For plotting (similar to matplotlib)
library(ggplot2)
# For clustering (similar to sklearn.cluster)
library(cluster)
# For metrics like silhouette score
library(factoextra) 

library(ggthemes)
# time series related
library(lubridate)
library(xts)
library(forecast)
library(strucchange)
library(tseries)


# Set the working directory
setwd()

# Read the CSV file
df <- read.csv('wetland_final_df.csv')


loc <- read.csv('data_download/location_df.csv')
loc <- loc %>% filter(loc$type=='districtCode')



# Function to calculate unknown and NaN counts and percentages
calculate_unknown_nan <- function(df) {
  results <- data.frame(Column = character(),
                        Unknown_Count = numeric(),
                        Unknown_Percent = numeric(),
                        NaN_Count = numeric(),
                        NaN_Percent = numeric(),
                        stringsAsFactors = FALSE)
  
  for (column in names(df)) {
    unknown_count <- sum(df[[column]] == 'unknown', na.rm = TRUE)
    nan_count <- sum(is.na(df[[column]]))
    total_count <- nrow(df)
    
    unknown_percent <- (unknown_count / total_count) * 100
    nan_percent <- (nan_count / total_count) * 100
    
    results <- rbind(results, data.frame(Column = column,
                                         Unknown_Count = unknown_count,
                                         Unknown_Percent = unknown_percent,
                                         NaN_Count = nan_count,
                                         NaN_Percent = nan_percent))
  }
  
  return(results)
}

# Generate the table
unknown_nan_table <- calculate_unknown_nan(df) %>% filter(!Column %in% c('rowID', 'noticeID'))
unknown_nan_table

# Reshape the data to long format for ggplot
long_data <- unknown_nan_table %>%
  select(Column, Unknown_Percent, NaN_Percent) %>%
  pivot_longer(cols = -Column, names_to = "Type", values_to = "Percent") %>%
  mutate(Percent = round(Percent, 1))  # Round to 1 decimal

# Create the stacked bar plot
p1 <- ggplot(long_data, aes(y = Column, x = Percent, fill = Type)) +
  geom_bar(stat = "identity", position = "stack") +
  scale_fill_manual(values = c("Unknown_Percent" = "pink", "NaN_Percent" = "darkred")) +
  labs(title = "Percentage of Unknowns and NaNs in Each Column",
       x = "Column",
       y = "Percentage",
       fill = "Type") +
  theme_minimal() +
  
  theme(axis.text.x = element_text(angle = 45, hjust = 1))  # Adjust X-axis labels for readability
ggsave("pics/p1_unk.png", width = 11, height = 8.5, dpi = 300)

########################
# Read and merge required DataFrame
main <- read_csv('data_download/main_df.csv')

# Select specific columns
main <- main %>% select(noticeID, datePublished, dateExpiry)

main <- merge(main, loc, by = 'noticeID', all.x = FALSE)


dfs <- main

# Convert the date columns to Date objects
dfs$date1 <- as.Date(dfs$datePublished, format="%Y-%m-%d")  # Adjust the format if needed
dfs$date2 <- as.Date(dfs$dateExpiry, format="%m/%d/%Y")  # Adjust the format if needed

# Calculate the difference in days
dfs$day_diff <- as.numeric(dfs$date2 - dfs$date1)

# Calculate the 0.99 quantile
qtl <- quantile(dfs$day_diff, 0.99, na.rm=TRUE)

# Filter the data
filtered_dfs <- filter(dfs, day_diff <= qtl & day_diff>=0)

# Calculate the median of day_diff
median_day_diff <- median(filtered_dfs$day_diff, na.rm = TRUE)

# Plotting the histogram with a vertical line at the median
p2<- ggplot(filtered_dfs, aes(x = day_diff)) + 
  geom_histogram(alpha = 0.6, binwidth = 1, fill = "cyan1", color = "black") +
  geom_vline(aes(xintercept = median_day_diff), 
             color = "red", linetype = "dashed", size = 1) +
  annotate("text", x = median_day_diff, y = max(table(filtered_dfs$day_diff)), 
           label = paste("Median =", median_day_diff, "days"), vjust = 5, hjust=-.2,
           color = "red") +
  labs(title = "Histogram - Open comment period", 
       x = "Days Difference", y = "Frequency") +
  theme_minimal()

ggsave("pics/p2_hist.png", width = 11, height = 8.5, dpi = 300)


# notices with expiry date before published date
sum(dfs$day_diff < 0, na.rm=TRUE)

summary(filtered_dfs$day_diff)

## excluding anomalies and 99 percentile outliers
#Min. 1st Qu.  Median    Mean 3rd Qu.    Max. 
#0.00   20.00   23.00   24.77   30.00   49.00 


# Extract Year-Month from 'datePublished'
dfs$YearMonth <- format(dfs$date1, "%Y-%m")

# Aggregate data by month
monthly_data <- dfs %>% 
  group_by(YearMonth, detail) %>% 
  summarise(
    AvgDayDiff = mean(day_diff, na.rm = TRUE),
    n_notices = n_distinct(noticeID)
  )
# Drop rows where 'YearMonth' is NA
monthly_data <- monthly_data[!is.na(monthly_data$YearMonth), ]
# Replace NaN with 0
monthly_data <- monthly_data %>% mutate_all(~replace(., is.nan(.), 0))

# Convert 'YearMonth' back to a Date object for plotting
monthly_data$YearMonth <- as.Date(paste0(monthly_data$YearMonth, "-01"))

# Create a new 'district' variable based on 'detail'
monthly_data <- monthly_data %>%
  mutate(district = case_when(
    detail == "SAJ" ~ "Jacksonville",
    detail == "SAM" ~ "Mobile",
    detail == "SWG" ~ "Galveston",
    detail == "MVN" ~ "New Orleans",
    TRUE ~ as.character(detail)  # Retain original detail for others
  ))

# multi -district

# Now plot the data using the 'district' variable for coloring and labeling
ggplot(monthly_data, aes(x = YearMonth, y = AvgDayDiff, color = district)) +
 # geom_line(size = 0.8) +
  scale_color_brewer(palette = "Set1") +  # A softer color palette
  theme_minimal(base_size = 12) +  # Clean theme with larger base font size
  labs(title = "Avg. comment period over time (in days)",
       x = "Month",
       y = "Days before expiry",
       color = "District") +  # Change legend label to 'District'
  theme_economist() + 
  theme(plot.title = element_text(size = 16, face = "bold"),
        axis.title = element_text(size = 14),
        legend.position = "bottom",  # Place legend at the bottom
        legend.title.align = 0.5,  # Center-align the legend title
        legend.text = element_text(size = 10),  # Adjust the legend text size
        axis.text.x = element_text(angle = 45, hjust = 0),  # Rotate x labels for better fit
  axis.text.y = element_text(angle = 0, hjust = 2)) +  # Rotate x labels for better fit
  geom_smooth(se = TRUE, method = "loess") + # Use 'district' for smooth lines as well
  theme(legend.title = element_text(colour="black", size=10, 
                                    face="bold"))+
  theme(legend.position='right') + 
  scale_x_date(date_labels = "%Y-%m", date_breaks = "2 year")
# geom_rect()
ggsave("pics/p3_commline.png", width = 11, height = 8.5, dpi = 300)


#### TS analysis



# lineplot of notices
ggplot(monthly_data, aes(x = YearMonth, y = n_notices, color = district)) +
  #geom_line(size = 0.8) +
  scale_color_brewer(palette = "Set1") +  # A softer color palette
  theme_minimal(base_size = 12) +  # Clean theme with larger base font size
  labs(title = "Notices published by district and month",
       x = "Month",
       y = "Number",
       color = "District") +  # Change legend label to 'District'
  scale_x_date(date_labels = "%Y-%m", date_breaks = "2 year")+

  theme_economist() + 
  theme(plot.title = element_text(size = 16, face = "bold"),
        axis.title = element_text(size = 14),
        legend.position = "bottom",  # Place legend at the bottom
        legend.title.align = 0.5,  # Center-align the legend title
        legend.text = element_text(size = 10),  # Adjust the legend text size
        axis.text.x = element_text(angle = 45, hjust = 0),  # Rotate x labels for better fit
        axis.text.y = element_text(angle = 0, hjust = 2)) +  # Rotate x labels for better fit
  geom_smooth(method = "loess", se = TRUE)  # Match se band color to line color
theme(legend.title = element_text(colour="black", size=10, 
                                    face="bold"))+
  theme(legend.position='right')  
# geom_rect()
ggsave("pics/p5_notsm.png", width = 11, height = 8.5, dpi = 300)


#ggsave("pics/p4_noticesline.png", width = 11, height = 8.5, dpi = 300)


# Perform the breakpoints analysis
breakpoints <- breakpoints(monthly_data$n_notices ~ 1,  h = 8)
# Visualize the N breakpoints
#plot(breakpoints)
# Extracting the breakpoints
bp_indices <- breakpoints$breakpoints
# Map indices to MonthYear
bp_dates <- monthly_data$YearMonth[bp_indices]


# Extract the date of the third breakpoint
third_bp_date <- bp_dates[3]

# lineplot of notices with annotation for the third breakpoint
ggplot(monthly_data, aes(x = YearMonth, y = n_notices, color = district)) +
  scale_color_brewer(palette = "Set1") +  # A bolder color palette
  theme_minimal(base_size = 12) +  # Clean theme with larger base font size
  labs(title = "Notices published by district and month",
       x = "Month",
       y = "Number",
       color = "District") +  # Change legend label to 'District'
  scale_x_date(date_labels = "%Y-%m", date_breaks = "2 year") +
  geom_vline(xintercept = as.numeric(third_bp_date), color = "black", linetype = "dashed") +
  theme_economist() + 
  theme(plot.title = element_text(size = 16, face = "bold"),
        axis.title = element_text(size = 14),
        legend.position = "bottom",
        legend.title.align = 0.5,
        legend.text = element_text(size = 10),
        axis.text.x = element_text(angle = 45, hjust = 0),
        axis.text.y = element_text(angle = 0, hjust = 1)) +
  geom_smooth(method = "loess", se = TRUE) +  # Smooth line with SE bands
  theme(legend.title = element_text(colour = "black", size = 10, face = "bold")) +
  theme(legend.position = 'right') +
  annotate("text", x =third_bp_date, 
           y = max(monthly_data$n_notices), label = third_bp_date, hjust = 1, vjust = 1)

# geom_rect()
ggsave("pics/p6_brk.png", width = 11, height = 8.5, dpi = 300)


# Plotting - single
ggplot(monthly_data, aes(x = YearMonth, y = n_notices)) +
  geom_line(color = "blue", size = .8) +
  theme_minimal() +
  labs(title = "Monthly total notices",
       x = "Month",
       y = "Unique notice IDs") +
  
  theme(plot.title = element_text(size = 14, face = "bold"),
        axis.title = element_text(size = 12, face = "bold"),
        axis.text = element_text(size = 10))

######### remove duplicates


# Identify duplicates
df$IsDuplicate <- duplicated(df$noticeID) | duplicated(df$noticeID, fromLast = TRUE)

# Data frame with only unique noticeIDs - single wetland
dfu <- df[!df$IsDuplicate, ]

# Data frame with duplicates
dfd <- df[df$IsDuplicate, ]

# Filter rows by damage ty[e]
#dfs <- dfs %>% filter(impact_type %in% c('loss', 'damage', 'fill'))

# Merge data frames
dfu <- merge(dfu, main, by = 'noticeID', all.x = TRUE)


dfu <- dfu %>% 
  mutate(impact_class = case_when(
    impact_type %in% c('loss', 'damage', 'fill', 'removal') ~ 'loss',
    impact_type %in% c('restoration', 'enhancement', 'preservation', 'beneficial', 'positive', 'improvement') ~ 'benefit',
    impact_type == 'unknown' ~ 'unknown',
    TRUE ~ 'other'  # This will catch all other cases
  ))


table(dfu$impact_class)

dfac <- dfu %>% filter(impact_unit =='acres', impact_quantity<1000)
max(dfac$impact_quantity, na.rm=TRUE)


# Calculate the percentages
dfac_percent <- dfac %>%
  count(dfac$impact_class) %>%
  mutate(perc = n / sum(n) * 100)

# Creating a pie chart with percentage annotations
ggplot(dfac_percent, aes(x = "", y = n, fill = impact_class, label = paste0(round(perc, 1), "%"))) +
  geom_bar(width = 1, stat = "identity") +
  coord_polar("y", start = 0) +
  theme_void() +
  labs(fill = "Impact Class", title = "Breakdown of Impact Class") +
  theme(legend.position = "right") +
  geom_text(position = position_stack(vjust = 0.5))  # Add percentage labels


# Creating a bar plot faceted by 'detail' for the sum of 'impact_quantity'
#ggplot(dfac, aes(x = impact_class, y = impact_quantity, fill = impact_class)) +
 
# Creating a bar plot for the count of each impact_class
ggplot(dfac, aes(x = impact_class, fill = impact_class)) +
  geom_bar() +  # This will count the number of occurrences for each impact_class
  # facet_wrap(~ detail) +  # Uncomment this if you want to facet by 'detail'
  theme_minimal() +
  labs(x = "Impact Class", y = "Count", fill = "Impact Class", title = "Count by Impact Class") +
  theme(legend.position = "bottom")

ggsave("pics/p7_bar_loss.png", width = 11, height = 8.5, dpi = 300)


# Convert 'datePublished' to a Date object and create a YearMonth column
dfac$datePublished <- as.Date(dfac$datePublished, format="%Y-%m-%d")
dfac$YearMonth <- format(dfac$datePublished, "%Y-%m")

#groupby
monthly_impact <- dfac %>%
  group_by(YearMonth, impact_class) %>%
  summarise(TotalArea = sum(impact_quantity, na.rm = TRUE))
monthly_impact$YearMonth <- as.Date(paste0(monthly_impact$YearMonth, "-01"))

# Plotting the stacked area plot
ggplot(monthly_impact, aes(x = YearMonth, y = TotalArea, fill = impact_class)) +
  geom_area(alpha = 0.9) +
  theme_minimal() +
  labs(x = "Month", y = "Total Area", fill = "Impact Class",
       title = "Stacked Area Plot of Total Area by Month and Impact Class") +
  theme(legend.position = "bottom")



# Data preparation
dfac$datePublished <- as.Date(dfac$datePublished, format="%Y-%m-%d")
dfac$YearMonth <- format(dfac$datePublished, "%Y-%m")
monthly_impact <- dfac %>%
  group_by(YearMonth, impact_class, detail) %>%
  summarise(TotalArea = sum(impact_quantity, na.rm = TRUE))
monthly_impact$YearMonth <- as.Date(paste0(monthly_impact$YearMonth, "-01"))


# Create a new 'district' variable based on 'detail'
monthly_impact <- monthly_impact %>%
  mutate(district = case_when(
    detail == "SAJ" ~ "Jacksonville",
    detail == "SAM" ~ "Mobile",
    detail == "SWG" ~ "Galveston",
    detail == "MVN" ~ "New Orleans",
    TRUE ~ as.character(detail)  # Retain original detail for others
  ))

# Plotting the stacked area plot with facets
ggplot(monthly_impact, aes(x = YearMonth, y = TotalArea, fill = impact_class)) +
  geom_area(alpha = 0.9) +
  facet_wrap(~ district) +
  theme_minimal() +
  labs(x = "Month", y = "Total Area", fill = "Impact Class",
       title = "Stacked Area Plot of Total Area by Month, Impact Class, and Detail") +
  theme(legend.position = "bottom")
ggsave("pics/p8_stackarea.png", width = 11, height = 8.5, dpi = 300)
