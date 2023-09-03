Work-in-progress app.
Known bugs:
- game X Y Z coordinates are not transformed correctly (compare the analyticsdb datasource vs. the csgo_dsa datasource)
- damage dealt and similar damage table-based metrics have 0 values, which should not exist

Make sure you include a .env file in this project's folder  
specifying the postgres server's:  
DB_HOST  
DB_NAME  
DB_USER  
DB_PASSWORD  
DB_PORT  


This is a POC dash app used to visualize events with coordinate data for CSGO. Currently, it can visualize:  
- Deaths  
- Kills  
Other events are certainly possible to visualize as the framework is quite robust!  
Current Features:  
- Scatter plots  
- Heatmap plots  
- Histograms
- Box/whisker plots
- Various data selection tools
- Various data filters

A dash app is an interactive web data dashboard, built using flask to build the webpage and plotly to make the plots.
Examples can be seen at https://dash.gallery/Portal/  

