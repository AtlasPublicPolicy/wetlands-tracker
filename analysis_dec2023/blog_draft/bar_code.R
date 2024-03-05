library(tidyverse)
# install.packages("ggchicklet", repos = "https://cinc.rud.is")
library(ggchicklet)
library(grid)

setwd('blog_draft')

df <- read_csv('blog_barplot_tbl.csv')

# We'll use tidyr to pivot the data to long format for ggplot
df_long <- df %>% 
  select(disad, total_oil_gas, total_projects, `acre_per_cap_1k...9`) %>%
  pivot_longer(cols = -disad, names_to = "category", values_to = "count") %>%
  mutate(disadv = ifelse(disad == 1, 'Disadvantaged', 'Not Disadvantaged'))



###### plot 1 - project counts ####
df <- df_long
# Plot with corrected code for the 3-patch legend
p1 <- ggplot(data = df, aes(x = disadv, y = count, fill = disadv)) +
  # Add bar for total projects with specified color, ensuring `disadv` is used as factor
  geom_bar(data = df %>% filter(category == "total_projects"),
  aes(fill = disadv), stat = "identity", position = position_dodge(width = 3), color = "black" , size = 0.2) +

  # geom_chicklet( radius = grid::unit(4, 'mm'), position = "stack",data = df %>% filter(category == "total_projects"), 
  #                aes(fill = disadv), stat = "identity", color = "black") +
  
  # Overlay bar for total_oil_gas in black, creating a separate entry for "Industrial"
  geom_bar(data = df %>% filter(category == "total_oil_gas"), 
           aes(fill = "Industrial"), stat = "identity",position = position_dodge(width = 3), color = "black", size = 0.2) +
  # Text labels
  # Custom annotations for oil and gas projects
  geom_text(data = df %>% filter(category == "total_oil_gas" & disadv == "Disadvantaged"), 
            aes(x = disadv, y = count, label = "120 (9%)"), size=3,
            vjust = -0.5, position = position_dodge(width = 0), width = 0) +
  
  geom_text(data = df %>% filter(category == "total_oil_gas" & disadv == "Not Disadvantaged"), 
            aes(x = disadv, y = count, label = "172 (5%)"),size=3,
            vjust = -0.5, color='white', position = position_dodge(width = 0), width = 0) +
  
  # geom_text(aes(label = count), vjust = -0.5, position = position_dodge(width = 0.9)) +
  # Manually define the legend with updated labels and colors
  scale_fill_manual(
    name = "Tract + Project type",
    values = c("Disadvantaged" = "#F45D01", "Not Disadvantaged" = "#333C6B", "Industrial" = "#C5C5C5"),
    labels = c("Not DA tract, non-industrial",  "Both, Industrial", "DA tract, non-industrial" )
  ) +
  labs(x = "Tract Status", y = "Total Projects") +
  theme_minimal() +
  theme(
    axis.text.x =element_text(size = 7),
    panel.grid.major.x = element_blank(),
    panel.grid.minor.x = element_blank(),
    panel.grid.major.y = element_line(color = "grey", linewidth = 0.1), # Keep horizontal gridlines; customize as needed
    
    plot.title = element_text(face = "bold", size = 11, hjust = 0),
    plot.margin = margin(5.5, 40, 5.5, 5.5),
    # plot.background = element_rect(fill = "transparent",  colour = NA_character_),
    plot.background = element_rect(color = "black", fill = "transparent"), # Border around the entire plot
    panel.background = element_rect(fill = "transparent", colour = NA), # Ensure bar area has no additional border
    # panel.border = element_rect(color = "black", fill = NA, size = .1),
    legend.title = element_text(face = "bold",size = 8),
    legend.text = element_text(size = 8),
    
    legend.position = "right",
    # legend.box.background = element_rect(color = "black", fill = NA),
    legend.background = element_blank(),
    axis.title.x = element_text(margin = margin(t = 9)),
    axis.title.y = element_text(size=8)
    # panel.border = element_rect(color = "black", fill = NA, size = .1)
  ) +
  
  ggtitle("Project category by Tract Disadvantage Status")

p1

ggsave("images/barplot_counts.png", plot = p1, dpi = 300)  # Adjust dpi as needed

##################### plot 2 - barplot of avg. acreage #########3

p2 <- ggplot(data = df, aes(x = disadv, y = count, fill = disadv)) +
  # Add bar for total projects with specified color, ensuring `disadv` is used as factor
  geom_bar(data = df %>% filter(category == "acre_per_cap_1k...9"),
           aes(fill = disadv), stat = "identity", position = position_dodge(width = 2.2), color = "black") +

           # color = "grey", fill = "orange") + # Assuming you want both fill and border in orange for simplicity
           # 
     # Text labels
  # Custom annotations for oil and gas projects
  geom_text(data = df %>% filter(category == "acre_per_cap_1k...9" & disadv == "Disadvantaged"), 
            aes(x = disadv, y = count, label = "3.94"), vjust = -0.5, position = position_dodge(width = 0.1)) +
  geom_text(data = df %>% filter(category == "acre_per_cap_1k...9" & disadv == "Not Disadvantaged"), 
            aes(x = disadv, y = count, label = "1.68"), vjust = -0.5, position = position_dodge(width = 0.1)) +
  
  # geom_text(aes(label = count), vjust = -0.5, position = position_dodge(width = 0.9)) +
  # Manually define the legend with updated labels and colors
  scale_fill_manual(
    name = "Tract type",
    values = c("Disadvantaged" = "#F45D01", "Not Disadvantaged" = "#333C6B"),
  ) +
  # guides(fill = guide_legend(override.aes = list(shape = 22, size = 6, color = "black")))+ # Here we override the aesthetics for the legend

  labs(x = "Tract Status", y = "Mean Acres per 1000 people") +
  theme(
    axis.text.x =element_text(size = 9),
    panel.grid.major.x = element_blank(),
    panel.grid.minor.x = element_blank(),
    panel.grid.major.y = element_line(color = "grey", linewidth = 0.1), # Keep horizontal gridlines; customize as needed
    
    plot.title = element_text(face = "bold", size = 11, hjust = 0),
    plot.margin = margin(5.5, 40, 5.5, 5.5),
    # plot.background = element_rect(fill = "transparent",  colour = NA_character_),
    plot.background = element_rect(color = "black", fill = "transparent"), # Border around the entire plot
    panel.background = element_rect(fill = "transparent", colour = NA), # Ensure bar area has no additional border
    # panel.border = element_rect(color = "black", fill = NA, size = .1),
    legend.title = element_text(face = "bold",size = 8),
    legend.text = element_text(size = 8),
    
    legend.position = "right",
    # legend.box.background = element_rect(color = "black", fill = NA),
    legend.background = element_blank(),
    axis.title.x = element_text(margin = margin(t = 9)),
    axis.title.y = element_text(size=8)
    # panel.border = element_rect(color = "black", fill = NA, size = .1)
  ) +
  ggtitle("Acres impacted per 1000 population, by Tract type") +  ylim(c(0, 5))

p2

ggsave("images/barplot_acres.png", plot = p2, dpi = 300)  # Adjust dpi as needed

##################################################


## plot 3 - time series plot of notices

dft <- read_csv('notices_smooth_ts.csv')

# Define colors for each district
district_colors <- c("Galveston" = "#FF0000",  # Red
                     "Jacksonville" = "#800080",  # Purple
                     "Mobile" = "#008000",  # Green
                     "New Orleans" = "#0000FF")  # Blue


# Assuming your dataframe is named df_dist
p3 <- ggplot(data = dft, aes(x = as.Date(date), y = smoothed_n_notices, color = District)) +
  geom_line(size = .3, key_glyph = "timeseries") +  # Draw the lines
  # scale_color_viridis_d(end = 0.9, option = "D", direction = 1, name = "District Name") +  
  # Use a viridis color scale for distinction
  scale_color_manual(values = district_colors) +
  guides(color = guide_legend(override.aes = list(shape = 16, stroke = 8))) + # Using dots in legend
  labs(    title = "Avg. notices issued per day by district (rolling average)",
    x = "Year",
    y = "Smoothed Number of Notices"
  ) +
  theme(
    axis.text = element_text(size = 12),
    plot.title = element_text(face = "bold", size = 13, hjust = 0), # Center align main title
    legend.title = element_text(face = "bold", size=13),
    legend.text = element_text(size = 13), 
    axis.title = element_text(size = 13),
    panel.grid.major.x = element_blank(),
    panel.grid.minor.x = element_blank(),
    panel.grid.major.y = element_line(color = "grey", linewidth = 0.01), # Keep horizontal gridlines; customize as needed
    panel.background = element_rect(fill = "ivory", colour = NA_character_),
    plot.background = element_rect(fill = "transparent", colour = NA_character_),
    legend.position = "bottom", # This line is repeated; you might want to remove the duplication
    # Add borders to the bottom and left axes only
    axis.line.x = element_line(color = "black", linewidth = 0.5),
    # Adds a border to the bottom x-axis
    legend.background = element_rect(color = "black", fill = NA, size = 0.5), # Add a black border around the legend
    
    axis.line.y = element_line(color = "black", linewidth = 0.5))+
    # Adjust tick length for both x and y axes
    # Adds a border to the left y-axis +
  scale_x_date(
    date_labels = "%Y",  # Display only the year on the x-axis
    date_breaks = "2 year"  # Set breaks such that ticks are placed every year
  ) 

p3

#export
ggsave("images/time_plot.png",width = 9, height = 6, plot = p3, dpi = 300)  # Adjust dpi as needed

#