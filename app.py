import os
import re
import random
import time
from datetime import date, timedelta, datetime
from dash import dcc, html, dash_table, ALL, State, ctx
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import Output, DashProxy, Input, MultiplexerTransform
import dash_daq as daq
import plotly.express as px
import dash_bootstrap_components as dbc
import json
import gunicorn
from bs4 import BeautifulSoup
import requests
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from derive_scouting_features import damage_done_before_death, damage_taken
from plot_csgo import *

# multiplexer transfrom lets us have multiple callbacks target the same output.
app = DashProxy(__name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    prevent_initial_callbacks=True,
    transforms=[MultiplexerTransform()],
)

server = app.server


# Quick breakdown of dash: The app.layout is the static part,
# and the functions after are what makes the page dynamic.
# The functions after app.callbacks will take input from some
# part of the page, and output to another part of the page,
# responding to user input.

# Some variables to be used later
display_cols = [
    "id",
    "series",
    "date",
    "winners",
    "losers",
    "score",
    "winners T rounds",
    "winners CT rounds",
    "losers T rounds",
    "losers CT rounds",
    "winning players",
    "losing players",
]

# This defines the layout of the app, using html and dash's premade elements
app.layout = html.Div(
    [
        html.Div(
            className="box",
            children=[
                html.Div(
                    id="head-img-div",
                    children=html.Img(id="head-img", src="assets/eg_logo.png"),
                ),
                html.Div(
                    id="head-title",
                    children=html.H1(
                        "CSGO Visualization v1.0",
                        style={"margin": "0", "margin-bottom": "10px"},
                    ),
                ),
                html.Div(
                    style={"text-align": "center"},
                    children=[
                        dcc.Markdown(
                            """
        This tool is designed for the CSGO coaching staff and team to analyze EG's CSGO data.  
        (Instructions at bottom of page.) 
        """,
                            id="head-description",
                        )
                    ],
                ),
                html.Div(
                    style={"text-align": "center", "margin-bottom": "20px"},
                    children=[
                        dbc.Button(
                            "Save/Load Visualization",
                            color="primary",
                            style={"height": "40px"},
                            id="open",
                            n_clicks=0,
                        )
                    ],
                ),
                dcc.Markdown("*Portfolio edition (only test data and limited features)"),
                # load visualization modal
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Save/Load Visualization")),
                        dbc.ModalBody(
                            [
                                html.Div(
                                    [
                                        dash_table.DataTable(
                                            id="load-vis-table",
                                            columns=[
                                                {"id": i, "name": i}
                                                if i != "Notes"
                                                else {
                                                    "id": i,
                                                    "name": i,
                                                    "presentation": "markdown",
                                                }
                                                for i in [
                                                    "Date Created",
                                                    "Name",
                                                    "Created by",
                                                    "Notes",
                                                ]
                                            ],
                                            data=None,
                                            style_table={"overflowX": "auto"},
                                            row_selectable="single",
                                            selected_rows=[],
                                            page_size=10,
                                        )
                                    ]
                                ),
                                html.Div(
                                    [
                                        html.H5("Enter info to save visualization (disabled):"),
                                        dcc.Input(
                                            id="vis-name",
                                            className="vis-input",
                                            placeholder="Vis. name...",
                                        ),
                                        dcc.Input(
                                            id="vis-created-by",
                                            className="vis-input",
                                            placeholder="Created by...",
                                        ),
                                        dcc.Input(
                                            id="vis-note-url",
                                            className="vis-input",
                                            placeholder="Notes url...",
                                        ),
                                    ],
                                    style={"margin-top": "15px"},
                                ),
                            ]
                        ),
                        dbc.ModalFooter(
                            [
                                html.Button(
                                    "Delete",
                                    id="delete-vis-button",
                                    n_clicks=0,
                                    style={"margin-right": "auto"},
                                ),
                                html.Button("Save", id="save-vis-button", n_clicks=0),
                                html.Button("Load", id="load-vis-button", n_clicks=0),
                                html.Button("Close", id="close", n_clicks=0),
                            ]
                        ),
                    ],
                    id="modal",
                    is_open=False,
                    size="xl",
                ),
            ],
        ),
        html.Div(
            className="box",
            children=[
                html.H2("Select Map and Matches", className="title"),
                html.Div(
                    id="map-select",
                    children=[
                        html.Div("Select Map", id="map-text"),
                        dcc.Dropdown(
                            className="dropdown",
                            id="map-dropdown",
                            options=[
                                "ancient",
                                "inferno (not in demo)",
                                "mirage (not in demo)",
                                "nuke (not in demo)",
                                "overpass (not in demo)",
                                "anubis (not in demo)",
                                "vertigo (not in demo)",
                            ],
                            value=None,
                            clearable=False,
                        ),
                    ],
                ),
                html.Div(
                    id="match-filter-box",
                    children=[
                        html.Div(
                            className="match-filter",
                            children=[
                                html.Div(
                                    className="team-box",
                                    children=[
                                        html.Div(
                                            "Filter by Teams",
                                            style={
                                                "margin-bottom": "10px",
                                                "text-align": "center",
                                            },
                                        ),
                                        dcc.Dropdown(
                                            className="team-dropdown",
                                            id="team-dropdown",
                                            options=[],
                                            value=[],
                                            multi=True,
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="player-box",
                                    children=[
                                        html.Div(
                                            "Filter by Players",
                                            style={
                                                "margin-bottom": "10px",
                                                "text-align": "center",
                                            },
                                        ),
                                        dcc.Dropdown(
                                            className="player-dropdown",
                                            id="player-dropdown",
                                            options=[],
                                            value=[],
                                            multi=True,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            id="date-filter-div",
                            children=[
                                html.Div(
                                    "Filter by Date",
                                    style={"margin-top": "0", "margin-bottom": "10px"},
                                ),
                                dcc.DatePickerRange(
                                    id="date-filter",
                                    display_format="YYYY-MM-DD",
                                    initial_visible_month=date.today()
                                    - timedelta(days=180),
                                    end_date=date.today(),
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    id="match-select-buttons-div",
                    children=[
                        html.Div(
                            id="select-n-div",
                            children=[
                                html.Div(
                                    id="container-button-basic",
                                    children="Select last N matches",
                                ),
                                dcc.Input(
                                    id="select-value",
                                    placeholder="N = ?",
                                    type="number",
                                    style={"width": "80px", "margin-bottom": "5px"},
                                ),
                                html.Button("Select", id="submit-val", n_clicks=0),
                                html.Div(
                                    id="select-all-matches-div",
                                    children=[
                                        html.Button(
                                            "Select All",
                                            id="select-all-matches",
                                            n_clicks=0,
                                        )
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            id="add-data-div",
                            children=[
                                html.Button(
                                    "Add Selected to Match Pool",
                                    style={"float": "right"},
                                    id="add-data",
                                    n_clicks=0,
                                )
                            ],
                        ),
                    ],
                ),
                html.Div(
                    dash_table.DataTable(
                        id="match-table",
                        columns=[{"id": i, "name": i} for i in display_cols],
                        data=None,
                        style_table={"overflowX": "auto"},
                        row_selectable="multi",
                        selected_rows=[],
                        page_size=10,
                    )
                ),
                html.H4(
                    "Match Pool", style={"text-align": "center", "margin-top": "0"}
                ),
                html.Div(
                    [
                        html.Div(
                            id="remove-pool-div",
                            children=[
                                html.Button("Remove All", id="remove-pool", n_clicks=0)
                            ],
                        ),
                        html.Div(
                            id="import-export-id-div",
                            children=[
                                html.Div(
                                    id="id-float-div",
                                    children=[
                                        dcc.Input(
                                            id="import-id",
                                            placeholder="enter ids...",
                                            type="text",
                                            style={
                                                "width": "100px",
                                                "margin-bottom": "5px",
                                            },
                                        ),
                                        html.Button(
                                            "Load IDs",
                                            id="import-id-button",
                                            n_clicks=0,
                                        ),
                                        html.Button(
                                            "Export IDs",
                                            id="export-id-button",
                                            n_clicks=0,
                                        ),
                                        dcc.Download(id="download-ids"),
                                    ],
                                )
                            ],
                        ),
                    ]
                ),
                html.Div(
                    dash_table.DataTable(
                        id="selected-match-table",
                        columns=[{"id": i, "name": i} for i in display_cols],
                        data=None,
                        style_table={"overflowX": "auto"},
                        row_deletable=True,
                        page_size=10,
                    ),
                    style={"margin-bottom": "30px"},
                ),
            ],
        ),
        html.Div(
            className="box",
            children=[
                html.H2("Add Filters", className="title"),
                html.Div(
                    id="all-player-set-div",
                    children=[
                        html.Button("Set all T", id="all-T", n_clicks=0),
                        html.Button("Set all CT", id="all-CT", n_clicks=0),
                        html.Button("Toggle both sides", id="both-sides", n_clicks=0),
                    ],
                ),
                dcc.Dropdown(
                    id="all-filter-weapon",
                    options=[],
                    multi=True,
                    placeholder="Weapon Filter...",
                ),
                dcc.Loading(id="loading-1", type="default", children=[]),
                html.Div(
                    id="player-selector",
                    children=[],
                    style={"align": "center", "margin-bottom": "20px"},
                ),
                html.Div(
                    id="round-select-div",
                    children=[
                        html.Div(
                            id="round-number-div",
                            children=[
                                html.Div("Select round numbers"),
                                dcc.Input(
                                    id="round-selector",
                                    placeholder="ex: 1-5, 6 23",
                                    type="text",
                                    value="",
                                    style={
                                        "width": "30%",
                                        "textAlign": "center",
                                        "margin-bottom": "20px",
                                    },
                                ),
                            ],
                        ),
                        html.Div(
                            id="round-buy-type-div",
                            children=[
                                html.Div("Select buy type"),
                                dcc.Dropdown(
                                    className="dropdown",
                                    id="round-buy-dropdown",
                                    options=[
                                        "T full",
                                        "T half",
                                        "T full eco",
                                        "T eco",
                                        "CT full",
                                        "CT half",
                                        "CT full eco",
                                        "CT eco",
                                    ],
                                    clearable=True,
                                    multi=True,
                                ),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    id="round-time-div",
                    children=[
                        html.Div("Select time range in round (seconds):"),
                        dcc.RangeSlider(0, 155, value=[0, 155], id="time-slider"),
                    ],
                ),
                html.Div(
                    id="net-dmg-div",
                    children=[
                        html.Div("Select net damage:"),
                        dcc.RangeSlider(
                            -200, 200, value=[-200, 200], id="net-dmg-slider"
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="box",
            children=[
                html.H2("Visualize Kills and Deaths", className="title"),
                html.Div(
                    id="visualization-option-div",
                    children=[
                        dcc.Dropdown(
                            [
                                {
                                    "label": html.Div(
                                        ["Deaths Scatter"],
                                        style={
                                            "color": "DarkRed",
                                            "font-size": 16,
                                            "margin-right": "10px",
                                        },
                                    ),
                                    "value": "Deaths Scatter",
                                },
                                {
                                    "label": html.Div(
                                        ["Deaths Heatmap"],
                                        style={
                                            "color": "DarkRed",
                                            "font-size": 16,
                                            "margin-right": "10px",
                                        },
                                    ),
                                    "value": "Deaths Heatmap",
                                },
                                {
                                    "label": html.Div(
                                        ["Kills Scatter"],
                                        style={
                                            "color": "DarkGreen",
                                            "font-size": 16,
                                            "margin-right": "10px",
                                        },
                                    ),
                                    "value": "Kills Scatter",
                                },
                                {
                                    "label": html.Div(
                                        ["Kills Heatmap"],
                                        style={
                                            "color": "DarkGreen",
                                            "font-size": 16,
                                            "margin-right": "10px",
                                        },
                                    ),
                                    "value": "Kills Heatmap",
                                },
                            ],
                            id="plot-types",
                            multi=True,
                            placeholder="Select Data Visualizations",
                            style={
                                "width": "90%",
                                "margin": "auto",
                                "margin-bottom": "20px",
                            },
                            value=[],
                        )
                    ],
                ),
                html.Div(
                    id="graph-tool-div",
                    children=[
                        html.Div("Select Tool"),
                        dcc.Dropdown(
                            id="graph-tool",
                            options=[
                                "Victim/Killer connection",
                                "HLTV link",
                                "Highlight player",
                            ],
                            clearable=False,
                            value="Victim/Killer connection",
                        ),
                    ],
                    style={"width": "50%", "margin": "auto", "text-align": "center"},
                ),
                html.Div(id="graph-div", style={"margin-bottom": "20px"}),
                html.Div(
                    id="palette-div",
                    style={"margin-bottom": "20px", "text-align": "center"},
                    children=[
                        html.Div(
                            id="ds-palette",
                            className="palette-box",
                            children=[
                                html.Div(
                                    "Deaths Scatter Palette",
                                    style={"border-bottom": "solid 1px black"},
                                ),
                                html.Div("size of point"),
                                dcc.Slider(
                                    1,
                                    20,
                                    step=None,
                                    marks=None,
                                    value=8,
                                    id="ds-size-slider",
                                ),
                            ],
                        ),
                        html.Div(
                            id="ks-palette",
                            className="palette-box",
                            children=[
                                html.Div(
                                    "Kills Scatter Palette",
                                    style={"border-bottom": "solid 1px black"},
                                ),
                                html.Div("size of point"),
                                dcc.Slider(
                                    1,
                                    20,
                                    step=None,
                                    marks=None,
                                    value=8,
                                    id="ks-size-slider",
                                ),
                            ],
                        ),
                        html.Div(
                            id="dh-palette",
                            className="palette-box",
                            children=[
                                html.Div(
                                    "Deaths Heatmap Palette",
                                    style={"border-bottom": "solid 1px black"},
                                ),
                                html.Div("size of bin"),
                                dcc.Slider(
                                    1,
                                    50,
                                    step=None,
                                    marks=None,
                                    value=15,
                                    id="dh-size-slider",
                                ),
                                daq.ColorPicker(
                                    id="dh-color",
                                    label="Color Picker",
                                    value={"rgb": {"r": 250, "g": 42, "b": 5, "a": 1}},
                                ),
                                html.Div(" ", style={"height": "20px"}),
                            ],
                        ),
                        html.Div(
                            id="kh-palette",
                            className="palette-box",
                            children=[
                                html.Div(
                                    "Kills Heatmap Palette",
                                    style={"border-bottom": "solid 1px black"},
                                ),
                                html.Div("size of bin"),
                                dcc.Slider(
                                    1,
                                    50,
                                    step=None,
                                    marks=None,
                                    value=15,
                                    id="kh-size-slider",
                                ),
                                daq.ColorPicker(
                                    id="kh-color",
                                    label="Color Picker",
                                    value={"rgb": {"r": 2, "g": 191, "b": 27, "a": 1}},
                                ),
                                html.Div(" ", style={"height": "20px"}),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    id="scatter-div",
                    children=[
                        html.H4(
                            "Plot Data",
                            style={"text-align": "center", "margin-top": "0"},
                        ),
                        dcc.Graph(
                            id="scatter-plot",
                            style={"height": "80vh", "width": "85vw"},
                            config={"frameMargins": 0},
                        ),
                        html.Div(
                            className="scatter-dropdown",
                            children=[
                                html.Div("Plot Type"),
                                dcc.Dropdown(
                                    id="scatter-plot-type",
                                    options=[
                                        "Scatter",
                                        "Box",
                                    ],
                                    value="Scatter",
                                    clearable=False,
                                ),
                            ],
                        ),
                        html.Div(
                            className="scatter-dropdown",
                            children=[
                                html.Div("Feature 1"),
                                dcc.Dropdown(id="scatter-x"),
                            ],
                        ),
                        html.Div(
                            className="scatter-dropdown",
                            children=[
                                html.Div("Feature 2"),
                                dcc.Dropdown(id="scatter-y"),
                            ],
                        ),
                        html.Div(
                            className="scatter-dropdown",
                            children=[
                                html.Div("Category"),
                                dcc.Dropdown(id="scatter-color"),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="box",
            children=[
                html.H2("Instructions", className="title"),
                html.Div(
                    style={"margin": "50px"},
                    children=[
                        dcc.Markdown(
                            """   
        Steps:  
                
        1. Select map and matches, then add matches to data pool. (You can export your match pool to csv and reload it later.)  
          
        2. Apply filters to data set.
            - Side  
            - Weapon   
            - Round number  
            - Buy type  
            - Seconds elapsed in round  
          
        3. Select visualization tool.   
            - Kills and Deaths  
            - Scatterplots  
                - hoverover info  
                - data selection tool  
                    - killer/victim connection  
                    - HLTV link  
                    - Highlight selected player in match  
            - Heatmaps
            - Drawing tools
        """
                        )
                    ],
                ),
            ],
        ),
        dcc.Store(id="dumped_kills_table"),
        dcc.Store(id="dumped_rounds_table"),
        dcc.Store(id="dumped_filtered_kills_table"),
        dcc.Store(id="dumped-load-table"),
        dcc.Store(id="player-selector-load"),
        dcc.Store(id="selected-match-table-load"),
        html.Div(id="placeholder"),
    ]
)

# Now we have a bunch of functions that make the static layout dynamic.


# fill load table
@app.callback(
    Output("load-vis-table", "data"),
    Output("dumped-load-table", "data"),
    Input("save-vis-button", "n_clicks"),
    Input("delete-vis-button", "n_clicks"),
    Input("open", "n_clicks"),
)
def fill_load_table(n1, n2, n3):
    time.sleep(0.5)
    # url_object = URL.create(
    #     "postgresql+psycopg2",
    #     host=os.environ["DB_HOST"],
    #     database="eg_gaming_dev",
    #     port=os.environ["DB_PORT"],
    #     username=os.environ["DB_USER"],
    #     password=os.environ["DB_PASSWORD"],
    # )

    # engine = create_engine(url_object)

    # fill_load_table_query = """ SELECT * FROM CSGO_DATA_VIS.SAVED_VIS """

    # try:
    #     output = engine.execute(fill_load_table_query)
    #     df = pd.DataFrame(output.fetchall())
    # except:
    #     print("load table pull failed")

    # rename_cols = {
    #     "date_created": "Date Created",
    #     "name": "Name",
    #     "created_by": "Created by",
    #     "url": "Notes",
    # }
    # df.rename(columns=rename_cols, inplace=True)
    df = pd.DataFrame({"Date Created" : ["07/04/1776"],
                        "Name" : ["Some visualization"],
                        "Created by" : ["Alex"],
                        "Notes" : ["someurl.com"]})

    return (
        df[["Date Created", "Name", "Created by", "Notes"]].to_dict("records"),
        df.to_json(),
    )


# open/close modal and set fullscreen loading
@app.callback(
    Output("modal", "is_open"),
    Output("loading-1", "fullscreen"),
    [
        Input("open", "n_clicks"),
        Input("close", "n_clicks"),
        Input("load-vis-button", "n_clicks"),
    ],
    [State("modal", "is_open")],
)
def toggle_modal(n1, n2, n3, is_open):
    fullscreen = False
    if n1:
        fullscreen = True
    if n2:
        fullscreen = False
    if n1 or n2 or n3:
        return not is_open, fullscreen
    return is_open, fullscreen


# load visualization settings
@app.callback(
    Output("map-dropdown", "value"),
    Output("selected-match-table-load", "data"),
    Output("player-selector-load", "data"),
    Output("all-filter-weapon", "value"),
    Output("round-selector", "value"),
    Output("round-buy-dropdown", "value"),
    Output("time-slider", "value"),
    Output("net-dmg-slider", "value"),
    Output("loading-1", "fullscreen"),
    Output("ds-size-slider", "value"),
    Output("ks-size-slider", "value"),
    Output("dh-color", "value"),
    Output("kh-color", "value"),
    Output("dh-size-slider", "value"),
    Output("kh-size-slider", "value"),
    State("load-vis-table", "selected_rows"),
    State("dumped-load-table", "data"),
    Input("load-vis-button", "n_clicks"),
)
def load_vis(selected, data, n):
    if selected != [] and ctx.triggered_id == "load-vis-button" and ctx.triggered_id != "load-vis-button": #add for disable
        df = pd.read_json(data)
        settings = df.loc[selected[0]]["settings"]
        return (
            settings["map"],
            settings["selected_match"],
            settings["player_filters"],
            settings["all_weapon"],
            settings["round"],
            settings["round_buy"],
            settings["time"],
            settings["net_dmg"],
            False,
            settings["ds_size"],
            settings["ks_size"],
            settings["dh_color"],
            settings["kh_color"],
            settings["dh_size"],
            settings["kh_size"],
        )
    else:
        raise PreventUpdate


# Save visualization
@app.callback(
    Output("placeholder", "children"),
    State("map-dropdown", "value"),
    State("selected-match-table", "data"),
    State("player-selector", "children"),
    State("all-filter-weapon", "value"),
    State("round-selector", "value"),
    State("round-buy-dropdown", "value"),
    State("time-slider", "value"),
    State("net-dmg-slider", "value"),
    State("vis-name", "value"),
    State("vis-created-by", "value"),
    State("vis-note-url", "value"),
    State("ds-size-slider", "value"),
    State("ks-size-slider", "value"),
    State("dh-color", "value"),
    State("kh-color", "value"),
    State("dh-size-slider", "value"),
    State("kh-size-slider", "value"),
    Input("save-vis-button", "n_clicks"),
)
def save_vis(
    map,
    selected_match,
    player_filters,
    all_weapon,
    round,
    round_buy,
    time,
    net_dmg,
    name,
    created_by,
    url,
    ds_size,
    ks_size,
    dh_color,
    kh_color,
    dh_size,
    kh_size,
    n_clicks,
):
    if n_clicks > 0 and n_clicks < 0: # added this line to disable
        date_created = date.today()

        settings = {
            "map": map,
            "selected_match": selected_match,
            "player_filters": player_filters,
            "all_weapon": all_weapon,
            "round": round,
            "round_buy": round_buy,
            "time": time,
            "net_dmg": net_dmg,
            "ds_size": ds_size,
            "ks_size": ks_size,
            "dh_color": dh_color,
            "kh_color": kh_color,
            "dh_size": dh_size,
            "kh_size": kh_size,
        }

        url_object = URL.create(
            "postgresql+psycopg2",
            host=os.environ["DB_HOST"],
            database="eg_gaming_dev",
            port=os.environ["DB_PORT"],
            username=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )

        engine = create_engine(url_object)

        save_query = """ INSERT INTO csgo_data_vis.saved_vis(id,
                                                name,
                                                created_by,
                                                date_created,
                                                url,
                                                settings
                                                )
                        values(
                        '{id}',
                        '{name}',
                        '{created_by}',
                        '{date_created}',
                        '{url}',
                        '{settings}'::json
                        );
        """.format(
            id=str(random.randint(0, 1000000)),
            name=name,
            created_by=created_by,
            date_created=date_created,
            url=url,
            settings=str(json.dumps(settings)),
        )

        try:
            print(save_query)
            engine.execute(text(save_query))
        except SQLAlchemyError as e:
            error = str(e.__dict__["orig"])
            print(error)

    return None


# delete saved visualization
@app.callback(
    Output("placeholder", "children"),
    State("load-vis-table", "selected_rows"),
    State("dumped-load-table", "data"),
    Input("delete-vis-button", "n_clicks"),
)
def delete_vis(selected, data, n1):
    if selected != [] and ctx.triggered_id == "delete-vis-button" and ctx.triggered_id != "delete-vis-button": #add for disable
        df = pd.read_json(data)
        to_delete = df.loc[selected[0]]

        url_object = URL.create(
            "postgresql+psycopg2",
            host=os.environ["DB_HOST"],
            database="eg_gaming_dev",
            port=os.environ["DB_PORT"],
            username=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )

        engine = create_engine(url_object)

        delete_query = """ delete from csgo_data_vis.saved_vis
                        where 
                        id = '{id}'
        """.format(
            id=to_delete["id"]
        )

        try:
            engine.execute(text(delete_query))
        except SQLAlchemyError as e:
            error = str(e.__dict__["orig"])
            print(error)
    return []

# populate match table
@app.callback(
    Output("match-table", "data"),
    Output("team-dropdown", "options"),
    Output("player-dropdown", "options"),
    Input("map-dropdown", "value"),
    Input("team-dropdown", "value"),
    Input("player-dropdown", "value"),
    Input("date-filter", "start_date"),
    Input("date-filter", "end_date"),
)
def display_map_matches(
    map_string, selected_teams, selected_players, start_date, end_date
):
    time.sleep(0.5)
    # sqlalchemy engine to make SQL fetches
    # url_object = URL.create(
    #     "postgresql+psycopg2",
    #     host=os.environ["DB_HOST"],
    #     database=os.environ["DB_NAME"],
    #     port=os.environ["DB_PORT"],
    #     username=os.environ["DB_USER"],
    #     password=os.environ["DB_PASSWORD"],
    # )

    # engine = create_engine(url_object)

    # match_table_query = """ SELECT MATCH_ID,
    #                             MATCH_DATE,
    #                             WINNING_TEAM,
    #                             LOSING_TEAM,
    #                             SCORE,
    #                             WINNING_T_WINS,
    #                             WINNING_CT_WINS,
    #                             LOSING_T_WINS,
    #                             LOSING_CT_WINS,
    #                             WINNING_PLAYERS,
    #                             LOSING_PLAYERS
    #                         FROM CSGO_DSA.MATCH_INFO
    #                         WHERE MAP_NAME ILIKE '%%{map_name}%%'
    #                         ORDER BY MATCH_DATE DESC
    # """.format(
    #     map_name=map_string
    # )
    read_cols = [
        "match_id",
        'series',
        "match_date",
        "winning_team",
        "losing_team",
        "score",
        "winning_t_wins",
        "winning_ct_wins",
        "losing_t_wins",
        "losing_ct_wins",
        "winning_players",
        "losing_players",
    ]
    rename_cols = {x: y for x, y in zip(read_cols, display_cols)}

    df = pd.DataFrame(columns=read_cols)

    if map_string == 'ancient':
        data = pd.read_csv("data/game_round.csv")
        data = data[data['map_name'] == 'de_ancient']
        frame_players = pd.read_csv("data/frame_player.csv")
        for match_id in data['match_id'].unique():
            series = data[data['match_id'] == match_id]['series'].iloc[0]
            match_date = data[data['match_id'] == match_id]['created_at'].apply(lambda x: x[:10]).iloc[0]
            winning_team = data[data['match_id'] == match_id].winning_team.value_counts().sort_values(ascending=False).index[0]
            losing_team = data[data['match_id'] == match_id].winning_team.value_counts().sort_values(ascending=False).index[1]
            score = str(data[data['match_id'] == match_id].winning_team.value_counts().sort_values(ascending=False)[0]) + "-" + str(data[data['match_id'] == match_id].winning_team.value_counts().sort_values(ascending=False)[1])
            round_wins = data[data['match_id'] == match_id][['winning_team', 'winning_side']].value_counts()
            winning_t_wins = round_wins[winning_team]['T']
            winning_ct_wins = round_wins[winning_team]['CT']
            losing_t_wins = round_wins[losing_team]['T']
            losing_ct_wins = (round_wins[losing_team]['CT'] if len(round_wins[losing_team]) == 2 else 0)
            winning_players = frame_players[(frame_players['team']==winning_team) & (frame_players.match_id == match_id)]['name'].unique()
            string = ''
            for player in winning_players:
                player = player.replace('nouns.', '')
                player = player.replace('WC', '')
                string += str(player) + ", "
            string = string[:-2]
            winning_players = string
            losing_players = frame_players[(frame_players['team']==losing_team) & (frame_players.match_id == match_id)]['name'].unique()
            string = ''
            for player in losing_players:
                player = player.replace('nouns.', '')
                player = player.replace('WC', '')
                string += str(player) + ", "
            string = string[:-2]
            losing_players = string
            df.loc[len(df)] = [match_id, series, match_date, winning_team, losing_team, score, winning_t_wins, winning_ct_wins, losing_t_wins, losing_ct_wins, winning_players, losing_players]

    # # Building match dataframe
    # df = pd.DataFrame(columns=read_cols)

    # try:
    #     output = engine.execute(match_table_query)
    #     df = pd.DataFrame(output.fetchall())
    # except SQLAlchemyError as e:
    #     print(e)

    df.rename(columns=rename_cols, inplace=True)

    # # drop dups because ties mess up the SQL code
    # df.drop_duplicates(subset=["id"], inplace=True)

    teams = list(set(df.winners.unique()) | set(df.losers.unique()))
    winning_players = [
        player.replace(",", "")
        for players in [x.split() for x in df["winning players"]]
        for player in players
    ]
    losing_players = [
        player.replace(",", "")
        for players in [x.split() for x in df["losing players"]]
        for player in players
    ]
    players = list(set(winning_players) | set(losing_players))

    # filter df based on selected date range
    if start_date == None:
        start_date = "1917-03-08"

    df = df.loc[
        [
            (
                datetime.strptime(str(x)[:10], "%Y-%m-%d")
                <= datetime.strptime(end_date, "%Y-%m-%d")
            )
            and (
                datetime.strptime(str(x)[:10], "%Y-%m-%d")
                >= datetime.strptime(start_date, "%Y-%m-%d")
            )
            for x in df.date
        ]
    ]

    # filter df based on selected players and teams
    if selected_teams != []:
        ids = list(
            df.loc[
                (df.winners == selected_teams[0]) | (df.losers == selected_teams[0])
            ].id
        )
        if len(selected_teams) == 2:
            ids = [
                x
                for x in ids
                if x
                in list(
                    df.loc[
                        (df.winners == selected_teams[1])
                        | (df.losers == selected_teams[1])
                    ].id
                )
            ]
        elif len(selected_teams) > 2:
            print("You can only select two teams.")
        df = df.loc[df.id.isin(ids)]

    if selected_players != []:
        ids = []
        for plyr in selected_players:
            id = list(
                df.loc[
                    [
                        x or y
                        for x, y in zip(
                            [plyr in z for z in df["winning players"]],
                            [plyr in z for z in df["losing players"]],
                        )
                    ]
                ].id
            )
            ids.append(id)

        ids = set.intersection(*map(set, ids))

        df = df.loc[df.id.isin(ids)]

    # Dash uses dictionaries to store data
    return df.to_dict("records"), teams, players


# automate row selection
@app.callback(
    Output("match-table", "selected_rows"),
    Input("select-all-matches", "n_clicks"),
    Input("match-table", "data"),
    Input("submit-val", "n_clicks"),
    State("select-value", "value"),
)
def select_n_rows(all_n_clicks, data, n_n_clicks, value):
    if "select-all-matches" == ctx.triggered_id:
        length = len(data)
        selected_rows = np.arange(length)
    elif value is not None:
        selected_rows = np.arange(value)
    else:
        selected_rows = []
    return selected_rows


# Move data from matches to match pool
@app.callback(
    Output("selected-match-table", "data"),
    State("selected-match-table", "data"),
    Input("match-table", "data"),
    Input("remove-pool", "n_clicks"),
    Input("add-data", "n_clicks"),
    State("match-table", "selected_rows"),
    Input("import-id-button", "n_clicks"),
    State("import-id", "value"),
    State("selected-match-table-load", "data"),
    Input("load-vis-button", "n_clicks"),
)
def add_data(
    current_data,
    data,
    remove_n_clicks,
    n_clicks,
    selected_rows,
    import_clicks,
    import_ids,
    load_data,
    n_load,
):
    selected_data = [data[i] for i in selected_rows]

    if current_data is None:
        current_data = selected_data
    else:
        for x in selected_data:
            if x not in current_data:
                current_data.append(x)

    if ctx.triggered_id == "remove-pool":
        current_data = None

    if ctx.triggered_id == "import-id-button" and type(import_ids) == str:
        df = pd.DataFrame.from_dict(data)
        df = df.loc[df.id.isin(import_ids.split())]
        current_data = df.to_dict("records")

    if ctx.triggered_id == "load-vis-button" and load_data is not None:
        current_data = load_data

    return current_data

# download ids in match pool
@app.callback(
    Output("download-ids", "data"),
    State("selected-match-table", "data"),
    State("map-dropdown", "value"),
    Input("export-id-button", "n_clicks"),
    prevent_initial_call=True,
)
def func(data, map, n_clicks):
    id_list = list(pd.DataFrame.from_dict(data).id)
    id_string = ""
    for i in id_list:
        id_string += i + " "
    id_string = id_string[:-1]

    return dict(content=id_string, filename=map + ".txt")

# make unfiltered data sets, populate player selector
@app.callback(
    Output("player-selector", "children"),
    Output("all-filter-weapon", "options"),
    Output("dumped_kills_table", "data"),
    Output("dumped_rounds_table", "data"),
    Output("loading-1", "children"),
    Output("loading-1", "fullscreen"),
    Input("selected-match-table", "data"),
    State("player-selector-load", "data"),
    Input("load-vis-button", "n_clicks"),
)
def show_teams(data, load_data, n1):
    # sqlalchemy engine to make SQL fetches
    # url_object = URL.create(
    #     "postgresql+psycopg2",
    #     host=os.environ["DB_HOST"],
    #     database=os.environ["DB_NAME"],
    #     port=os.environ["DB_PORT"],
    #     username=os.environ["DB_USER"],
    #     password=os.environ["DB_PASSWORD"],
    # )

    # engine = create_engine(url_object)

    # building the dataframes
    kill_df = pd.DataFrame()
    round_df = pd.DataFrame()
    damage_df = pd.DataFrame()
    match_df = pd.DataFrame()

    # function to fill match df with hltv link
    def find_link(x):
        search = "hltv " + str(x)
        url = "https://www.google.com/search"

        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82",
        }
        parameters = {"q": search}

        content = requests.get(url, headers=headers, params=parameters, timeout=10).text
        soup = BeautifulSoup(content, "html.parser")

        search = soup.find(id="search")
        first_link = search.find("a")

        return first_link["href"]

    if data is not None:
        match_ids = [data[i]["id"] for i in range(len(data))]
        serieses = [data[i]["series"] for i in range(len(data))]

        kill_df_big = pd.read_csv('data/kills.csv')
        for id, series in zip(match_ids, serieses):
            kill_df = pd.concat([kill_df, kill_df_big[(kill_df_big.match_id == id) & (kill_df_big.series == series)]], axis=0)
        round_df_big = pd.read_csv('data/game_round.csv')
        for id, series in zip(match_ids, serieses):
            round_df = pd.concat([round_df, round_df_big[(round_df_big.match_id == id) & (round_df_big.series == series)]], axis=0)
        damage_df_big = pd.read_csv('data/damage.csv')
        for id, series in zip(match_ids, serieses):
            damage_df = pd.concat([damage_df, damage_df_big[(damage_df_big.match_id == id) & (damage_df_big.series == series)]], axis=0)
        

        # match_query_string = "("
        # for i in match_ids:
        #     match_query_string += "'" + i + "',"
        # match_query_string = match_query_string[:-1]
        # match_query_string += ")"
        # kill_table_query = """ SELECT *
        #                     FROM CSGO_DSA.HLTV_KILL
        #                     WHERE MATCH_ID IN {string}
        #                     ORDER BY MATCH_ID, TICK ASC
        # """.format(
        #     string=match_query_string
        # )
        # round_table_query = """ SELECT *
        #                     FROM CSGO_DSA.HLTV_GAME_ROUND
        #                     WHERE MATCH_ID IN {string}
        #                     ORDER BY MATCH_ID
        # """.format(
        #     string=match_query_string
        # )
        # damage_table_query = """ SELECT *
        #                     FROM CSGO_DSA.HLTV_DAMAGE
        #                     WHERE MATCH_ID IN {string}
        #                     ORDER BY MATCH_ID
        # """.format(
        #     string=match_query_string
        # )
        # match_table_query = """ SELECT MATCH_URN as ID,
        #                     extra_metadata as metadata
        #                     FROM CSGO_DSA.MATCH_GAME
        #                     WHERE MATCH_URN IN {string}
        #                     ORDER BY ID
        # """.format(
        #     string=match_query_string
        # )

        # if match_ids != []:
        #     try:
        #         output = engine.execute(kill_table_query)
        #         kill_df = pd.DataFrame(output.fetchall())
        #         output = engine.execute(round_table_query)
        #         round_df = pd.DataFrame(output.fetchall())
        #         output = engine.execute(damage_table_query)
        #         damage_df = pd.DataFrame(output.fetchall())
        #         output = engine.execute(match_table_query)
        #         match_df = pd.DataFrame(output.fetchall())
        #     except SQLAlchemyError as e:
        #         print(e)
        #         print("kill/round/damage table pull failed")

        if not kill_df.empty and not round_df.empty:
            # add some features from scripts in derive_scouting_features
            kill_df["damage_done_before_death"] = kill_df.apply(
                lambda x: damage_done_before_death(x, damage_df), axis=1
            )
            kill_df["damage_taken"] = kill_df.apply(
                lambda x: damage_taken(x, damage_df), axis=1
            )
            kill_df["net_dmg"] = (
                kill_df["damage_done_before_death"] - kill_df["damage_taken"]
            )

            # add hltv link for each kill
            # id_to_hltv = {
            #     x: find_link(y)
            #     for x, y in zip(list(match_df.id), [x['source_match_filename'] for x in match_df.metadata])
            # }
            #use this since seems there's a bug in the code
            kill_df = kill_df.dropna()
            #  kill_df["hltv_link"] = [id_to_hltv[x] for x in kill_df["match_id"]]
            teams = list(kill_df.attacker_team.unique())
            
            def true_round_time(x):
                # need this function to get true time from start of round in seconds
                round_start_tick = max(
                    round_df.loc[
                        (round_df.match_id == x.match_id)
                        & (round_df.start_tick < x.tick)
                    ].start_tick
                )
                return round((x.tick - round_start_tick) / 128, 1)

            # Add true round time to dataframe
            kill_df["true_round_time"] = kill_df.apply(
                true_round_time, axis=1
            )

            # populate the player selection table
            children = html.Div(
                style={"width": "100%"},
                children=[
                    html.Center(
                        html.Div(
                            style={
                                "display": "table-row",
                                "float": "center",
                                "overflow": "scroll",
                            },
                            children=[
                                html.Div(
                                    style={
                                        "display": "table-cell",
                                        "border": "1px solid black",
                                        "text-align": "center",
                                    },
                                    children=[
                                        html.Div(
                                            children=[
                                                html.Div(team),
                                                html.Button(
                                                    "T",
                                                    id={
                                                        "type": "T-button",
                                                        "index": team,
                                                    },
                                                    n_clicks=0,
                                                ),
                                                html.Button(
                                                    "CT",
                                                    id={
                                                        "type": "CT-button",
                                                        "index": team,
                                                    },
                                                    n_clicks=0,
                                                ),
                                                html.Button(
                                                    "Both",
                                                    id={
                                                        "type": "both-button",
                                                        "index": team,
                                                    },
                                                    n_clicks=0,
                                                ),
                                                dcc.Dropdown(
                                                    id={
                                                        "type": "team-filter-weapon",
                                                        "index": team,
                                                    },
                                                    style={"padding-top": "10px"},
                                                    options=sorted(
                                                        kill_df.loc[
                                                            kill_df.attacker_team
                                                            == team
                                                        ].weapon.unique()
                                                    ),
                                                    multi=True,
                                                    placeholder="all",
                                                ),
                                            ],
                                            style={
                                                "padding": "10px",
                                                "border-bottom": "2px solid black",
                                            },
                                        )
                                    ]
                                    + [
                                        html.Div(
                                            [
                                                html.Div(
                                                    style={
                                                        "padding": "10px 10px 0 10px"
                                                    },
                                                    id={
                                                        "type": "player-name",
                                                        "index": "index",
                                                    },
                                                    children=player,
                                                ),
                                                dcc.Checklist(
                                                    id={
                                                        "type": "player-filter-checklist",
                                                        "index": team + "&" + player,
                                                    },
                                                    options=["T", "CT"],
                                                    value=["T", "CT"],
                                                ),
                                                dcc.Dropdown(
                                                    id={
                                                        "type": "player-filter-weapon",
                                                        "index": player,
                                                    },
                                                    style={
                                                        "padding-bottom": "10px",
                                                        "padding-right": "10px",
                                                        "padding-left": "10px",
                                                    },
                                                    options=sorted(
                                                        kill_df.loc[
                                                            kill_df.attacker_name
                                                            == player
                                                        ].weapon.unique()
                                                    ),
                                                    multi=True,
                                                    placeholder="all",
                                                ),
                                            ]
                                        )
                                        for player in kill_df.loc[
                                            kill_df.attacker_team == team
                                        ].attacker_name.unique()
                                    ],
                                )
                                for team in teams
                            ],
                        )
                    )
                ],
            )
            kill_df.reset_index(inplace=True)
        else:
            teams = []

            children = html.Div(
                "no matches selected",
                style={"margin-top": "15px", "margin-bottom": "15px"},
            )

        if not kill_df.empty:
            weapons = sorted(kill_df["weapon"].unique())
        else:
            weapons = []
    else:
        children = html.Div("no matches in match pool", style={"margin-top": "15px"})
        weapons = []

    # loading option
    if ctx.triggered_id == "load-vis-button" and load_data is not None:
        children = load_data

    return children, weapons, kill_df.to_json(), round_df.to_json(), [], False

# update player selector with button presses
@app.callback(
    Output({"type": "player-filter-checklist", "index": ALL}, "value"),
    State({"type": "player-filter-checklist", "index": ALL}, "id"),
    State({"type": "player-filter-checklist", "index": ALL}, "value"),
    Input({"type": "T-button", "index": ALL}, "n_clicks"),
    Input({"type": "CT-button", "index": ALL}, "n_clicks"),
    Input({"type": "both-button", "index": ALL}, "n_clicks"),
    Input({"type": "both-button", "index": ALL}, "id"),
    Input("all-T", "n_clicks"),
    Input("all-CT", "n_clicks"),
    Input("both-sides", "n_clicks"),
)
def select_T_CT(ids, values, x1, x2, x3, x3_ids, n1, n2, both_sides):
    if "all-T" == ctx.triggered_id:
        for i in range(len(values)):
            values[i] = ["T"]
    elif "all-CT" == ctx.triggered_id:
        for i in range(len(values)):
            values[i] = ["CT"]
    elif "both-sides" == ctx.triggered_id:
        if (both_sides % 2) == 0:
            for i in range(len(values)):
                values[i] = ["T", "CT"]
        else:
            for i in range(len(values)):
                values[i] = []

    if type(ctx.triggered_id) is not str and ctx.triggered_id is not None:
        team = ctx.triggered_id["index"]
        team_index_bool = [team == x["index"].split("&")[0] for x in ids]
        index = [i for i, x in enumerate(team_index_bool) if x]

        if "T-button" == ctx.triggered_id["type"]:
            for i in index:
                values[i] = ["T"]
        elif "CT-button" == ctx.triggered_id["type"]:
            for i in index:
                values[i] = ["CT"]
        elif "both-button" == ctx.triggered_id["type"]:
            x3_index = [x["index"] for x in x3_ids]
            which_x3 = x3_index.index(team)
            if (x3[which_x3] % 2) == 0:
                for i in index:
                    values[i] = ["T", "CT"]
            else:
                for i in index:
                    values[i] = []

    return values


# cut dataset with filters
@app.callback(
    Output("dumped_filtered_kills_table", "data"),
    Input("dumped_kills_table", "data"),
    Input("dumped_rounds_table", "data"),
    Input("time-slider", "value"),
    Input("round-buy-dropdown", "value"),
    Input("round-selector", "value"),
    Input({"type": "player-name", "index": ALL}, "children"),
    Input({"type": "player-filter-checklist", "index": ALL}, "value"),
    Input({"type": "player-filter-weapon", "index": ALL}, "value"),
    Input({"type": "team-filter-weapon", "index": ALL}, "id"),
    Input({"type": "team-filter-weapon", "index": ALL}, "value"),
    Input("all-filter-weapon", "value"),
    Input("net-dmg-slider", "value"),
)
def filter_table(
    data,
    round_data,
    time,
    buy_type,
    rounds,
    players,
    sides,
    player_weapons,
    team_weapons_id,
    team_weapons,
    all_weapons,
    net_dmg,
):
    if rounds == "":
        rounds = np.arange(1, 32)
    else:
        # interpret round selector input, find numbers and dashes
        a = re.findall(r"(\d+|-)", rounds)
        dash_indices = [i for i, x in enumerate(a) if x == "-"]
        list_rounds = [x for x in a if x != "-"]
        for ind in dash_indices:
            if ind != len(list_rounds):
                list_rounds += [str(x) for x in range(int(a[ind - 1]), int(a[ind + 1]))]
        list_rounds = sorted(list_rounds)
        # remove duplicates
        list_rounds = [*set(list_rounds)]
        rounds = [int(x) - 1 for x in list_rounds]

    df = pd.read_json(data)
    round_df = pd.read_json(round_data)

    def round_type(x):
        """
        finds type of round for a given kill
        """
        round = (
            round_df.loc[
                (round_df.match_id == x.match_id) & (round_df.start_tick <= x.tick)
            ]
            .sort_values(by=["start_tick"], ascending=False)
            .iloc[0]
        )

        t_type = round.t_buy_type
        ct_type = round.ct_buy_type

        return [t_type, ct_type]

    df_victim, df_attacker = pd.DataFrame(), pd.DataFrame()
    
    if not df.empty:
        # time filter
        df = df.loc[(df.true_round_time > time[0]) & (df.true_round_time < time[1])]

        # net dmg filter
        df = df.loc[(df.net_dmg > net_dmg[0]) & (df.true_round_time < net_dmg[1])]

        # round filter
        df = df.loc[df.round_num.isin(rounds)]

        # add victim info
        def victim_side(x):
            if x["is_teamkill"]:
                return x["attacker_side"]
            elif x["attacker_side"] == "T":
                return "CT"
            else:
                return "T"

        if not df.empty:  # apply throws error if df is empty
            df["victim_side"] = df.apply(victim_side, axis=1)
            # round type filter
            df["t_round_type"] = df.apply(lambda x: round_type(x)[0], axis=1)
            df["ct_round_type"] = df.apply(lambda x: round_type(x)[1], axis=1)
        else:
            df["victim_side"] = pd.NA
            df["t_round_type"] = pd.NA
            df["ct_round_type"] = pd.NA

        if buy_type is not None:

            def translate_buy(x):
                if x == "T full" or x == "CT full":
                    return "Full Buy"
                elif x == "T half" or x == "CT half":
                    return "Half Buy"
                elif x == "T full eco" or x == "CT full eco":
                    return "Full Eco"
                else:
                    return "Eco"

            CT_types = [type for type in buy_type if "CT" in type]
            T_types = [type for type in buy_type if not type in CT_types]
            CT_types = [translate_buy(type) for type in CT_types]
            T_types = [translate_buy(type) for type in T_types]

            if T_types != []:
                df = df.loc[df.t_round_type.isin(T_types)]
            if CT_types != []:
                df = df.loc[df.ct_round_type.isin(CT_types)]

        # add player weapon filter
        player_wep_dict = {x: y for x, y in zip(players, player_weapons)}
        for player in players:
            if player_wep_dict[player] is not None:
                df.drop(
                    df.loc[
                        (df.attacker_name == player)
                        & ~df.weapon.isin(player_wep_dict[player])
                    ].index,
                    inplace=True,
                )

        # add team weapon filter
        teams = [x["index"] for x in team_weapons_id]
        team_wep_dict = {x: y for x, y in zip(teams, team_weapons)}
        for team in teams:
            if team_wep_dict[team] is not None:
                df.drop(
                    df.loc[
                        (df.attacker_team == team)
                        & ~df.weapon.isin(team_wep_dict[team])
                    ].index,
                    inplace=True,
                )

        # add all weapon filter
        if all_weapons is not None:
            df.drop(df.loc[~df.weapon.isin(all_weapons)].index, inplace=True)

        df_victim = df.copy()
        df_attacker = df.copy()

        for player, side in zip(players, sides):
            df_victim.drop(
                df_victim.loc[
                    (df_victim.victim_name == player)
                    & (~df_victim.victim_side.isin(side))
                ].index,
                inplace=True,
            )
        for player, side in zip(players, sides):
            df_attacker.drop(
                df_attacker.loc[
                    (df_attacker.attacker_name == player)
                    & (~df_attacker.attacker_side.isin(side))
                ].index,
                inplace=True,
            )
    return [df_victim.to_json(), df_attacker.to_json()]


# make map plot with kills and deaths data
@app.callback(
    Output("graph-div", "children"),
    Input("dumped_filtered_kills_table", "data"),
    Input("map-dropdown", "value"),
    Input("plot-types", "value"),
    State("graph-tool", "value"),
    Input({"type": "graph", "index": ALL}, "clickData"),
    Input({"type": "graph", "index": ALL}, "selectedData"),
    Input("ds-size-slider", "value"),
    Input("ks-size-slider", "value"),
    Input("dh-color", "value"),
    Input("kh-color", "value"),
    Input("dh-size-slider", "value"),
    Input("kh-size-slider", "value"),
)
def make_graph(
    filtered_data,
    map_string,
    plot_types,
    graph_tool,
    click_data,
    selected_data,
    ds_size,
    ks_size,
    dh_color,
    kh_color,
    dh_size,
    kh_size,
):
    """
    This function outputs the graphs. Note it has to make multiple
    if a map has two pngs associated with it (i.e. vertigo/nuke).
    """
    if filtered_data != None:
        dfs = [pd.read_json(df) for df in filtered_data]
    else:
        dfs = [pd.DataFrame(), pd.DataFrame()]

    figs = []
    highlight_indices = [[], []]

    if not dfs[0].empty:
        # scale and filter the data based on options
        x_shift, y_shift, s = find_scale(
            map_dict[map_string + "_game_x"],
            map_dict[map_string + "_game_y"],
            map_dict[map_string + "_map_x"],
            map_dict[map_string + "_map_y"],
        )

        for dff in dfs:
            dff["victim_x"] = (dff["victim_x"] - x_shift) * s
            dff["victim_y"] = (dff["victim_y"] - y_shift) * s
            dff["attacker_x"] = (dff["attacker_x"] - x_shift) * s
            dff["attacker_y"] = (dff["attacker_y"] - y_shift) * s

        # figure out df indices shared with click data for highlights

        if graph_tool == "Highlight player":
            if len(click_data) == 2:
                click_data = [data for data in click_data if data is not None]
                if click_data != []:
                    click_data = click_data[0]
                else:
                    click_data = None
            else:
                click_data = click_data[0]
            if click_data is not None:
                selected_index = int(click_data["points"][0]["customdata"])
                selected_match = [
                    dff.loc[dff['index'] == selected_index].match_id.values[0] for dff in dfs
                ]
                selected_match = [x for x in selected_match if x is not None]
                selected_match = selected_match[0]
                selected_player = [
                    dfs[0].loc[dfs[0]['index'] == selected_index].victim_name.values[0],
                    dfs[1].loc[dfs[1]['index'] == selected_index].attacker_name.values[0],
                ]

                highlight_indices = [
                    list(
                        dfs[0]
                        .loc[
                            (dfs[0].victim_name == selected_player[0])
                            & (dfs[0].match_id == selected_match)
                        ]
                        .index
                    ),
                    list(
                        dfs[1]
                        .loc[
                            (dfs[0].attacker_name == selected_player[1])
                            & (dfs[1].match_id == selected_match)
                        ]
                        .index
                    ),
                ]

        if selected_data == [[]]:
            selected_data = [[], []]

        if map_string not in ["vertigo", "nuke"]:
            figs.append(
                plot(
                    dfs,
                    map_string,
                    plot_types,
                    selected_data[0],
                    click_data,
                    graph_tool,
                    highlight_indices,
                )
            )
        else:
            dff_upper = [
                dfs[0].loc[dfs[0].victim_z > map_dict[map_string + "_z_division"]],
                dfs[1].loc[dfs[1].attacker_z > map_dict[map_string + "_z_division"]],
            ]
            dff_lower = [
                dfs[0].loc[dfs[0].victim_z <= map_dict[map_string + "_z_division"]],
                dfs[1].loc[dfs[1].victim_z <= map_dict[map_string + "_z_division"]],
            ]
            figs.append(
                plot(
                    dff_upper,
                    map_string,
                    plot_types,
                    selected_data[0],
                    click_data,
                    graph_tool,
                    highlight_indices,
                )
            )
            figs.append(
                plot(
                    dff_lower,
                    map_string + "_lower",
                    plot_types,
                    selected_data[1],
                    click_data,
                    graph_tool,
                    highlight_indices,
                )
            )

    else:
        if map_string not in ["vertigo", "nuke"]:
            figs.append(
                plot(
                    [pd.DataFrame(), pd.DataFrame()],
                    map_string,
                    plot_types,
                    selected_data,
                    click_data,
                    graph_tool,
                    highlight_indices,
                )
            )
        else:
            figs.append(
                plot(
                    [pd.DataFrame(), pd.DataFrame()],
                    map_string,
                    plot_types,
                    selected_data,
                    click_data,
                    graph_tool,
                    highlight_indices,
                )
            )
            figs.append(
                plot(
                    [pd.DataFrame(), pd.DataFrame()],
                    map_string + "_lower",
                    plot_types,
                    selected_data,
                    click_data,
                    graph_tool,
                    highlight_indices,
                )
            )

    I_dim = Image.open("map_images/de_" + map_string + "_radar.jpg")
    w, h = I_dim.size

    # update with palette options
    for fig in figs:
        fig.update_traces(marker_size=ds_size, selector={"marker_symbol": "x"})
        fig.update_traces(marker_size=ks_size, selector={"marker_symbol": "circle"})
        fig.update_traces(
            marker_size=ks_size, selector={"marker_symbol": "circle-open"}
        )
        kh_rgba = (
            "rgba("
            + str(kh_color["rgb"]["r"])
            + ","
            + str(kh_color["rgb"]["g"])
            + ","
            + str(kh_color["rgb"]["b"])
            + ","
            + str(kh_color["rgb"]["a"])
            + ")"
        )
        fig.update_traces(
            colorscale=[[0, "rgba(0,0,0,0)"], [1, kh_rgba]],
            xbins=dict(start=0, end=w, size=kh_size),
            ybins=dict(start=0, end=h, size=kh_size),
            selector={"name": "kh"},
        )
        dh_rgba = (
            "rgba("
            + str(dh_color["rgb"]["r"])
            + ","
            + str(dh_color["rgb"]["g"])
            + ","
            + str(dh_color["rgb"]["b"])
            + ","
            + str(dh_color["rgb"]["a"])
            + ")"
        )
        fig.update_traces(
            colorscale=[[0, "rgba(0,0,0,0)"], [1, dh_rgba]],
            xbins=dict(start=0, end=w, size=dh_size),
            ybins=dict(start=0, end=h, size=dh_size),
            selector={"name": "dh"},
        )

    graphs = [
        dcc.Graph(
            id={"type": "graph", "index": "index"},
            figure=fig,
            style={"height": "85vw", "width": "85vw"},
            config={
                "frameMargins": 0,
                "doubleClick": False,
                "modeBarButtonsToAdd": [
                    "drawline",
                    "drawopenpath",
                    "drawclosedpath",
                    "drawcircle",
                    "drawrect",
                    "eraseshape",
                ],
            },
        )
        for fig in figs
    ]
    # Prevents the selected_data input from double triggering the update.
    if str(
        ctx.triggered_prop_ids
    ) == """{'{"index":"index","type":"graph"}.selectedData': {'index': 'index', 'type': 'graph'}}""" and (
        str(selected_data) == "[{'points': []}]"
        or str(selected_data) == "[None, {'points': []}]"
        or str(selected_data) == "[{'points': []}, None]"
    ):
        raise PreventUpdate

    return graphs


# make feature plot
@app.callback(
    Output("scatter-plot", "figure"),
    Output("scatter-x", "options"),
    Output("scatter-y", "options"),
    Output("scatter-color", "options"),
    Input("dumped_filtered_kills_table", "data"),
    Input("scatter-x", "value"),
    Input("scatter-y", "value"),
    Input("scatter-color", "value"),
    Input("scatter-plot-type", "value"),
)
def scatter_plot(data, x, y, color, plot_type):
    placeholder = color
    fig = go.Figure()
    columns = []
    dfs = [pd.read_json(d) for d in data]
    df = pd.concat([dfs[0], dfs[1]])
    df.drop_duplicates(inplace=True)
    plot_cols = []
    color_cols = [
        "match_id",
        "attacker_name",
        "attacker_side",
        "attacker_team",
        "victim_name",
        "is_trade",
        "is_first_kill",
        "is_teamkill",
        "weapon",
        "attacker_area_name",
        "victim_area_name",
        "hltv_link",
        "victim_side",
        "t_round_type",
        "ct_round_type",
    ]
    drop_cols = [
        "created_at",
        "clock_time",
        "attacker_steam_id",
        "victim_steam_id",
        "player_traded_steam_id",
        "player_traded_team",
        "attacker_area_id",
        "victim_area_id",
        "upsert_at",
    ]
    if not df.empty:
        color_cols = list(set(df.columns).intersection(set(color_cols)))
        drop_cols = list(set(df.columns).intersection(set(drop_cols)))
        df.drop(columns=drop_cols, inplace=True)
        columns = list(df.columns)

        plot_cols = columns
        for col in color_cols:
            plot_cols.remove(col)

        colors_value = px.colors.qualitative.Light24

        if x is not None and y is not None and "Scatter" == plot_type:
            if color is not None:
                for i, val in enumerate(df[color].unique()):
                    fig.add_trace(
                        trace=go.Scatter(
                            name=val,
                            x=df.loc[df[color] == val][x],
                            y=df.loc[df[color] == val][y],
                            customdata=df["index"],
                            mode="markers",
                            marker_symbol="circle",
                            marker_color=colors_value[i % len(colors_value)],
                        )
                    )
                fig.update_layout(xaxis_title=x, yaxis_title=y, legend_title=color)
            else:
                fig.add_trace(
                    trace=go.Scatter(
                        x=df[x],
                        y=df[y],
                        customdata=df["index"],
                        mode="markers",
                        marker_symbol="circle",
                    )
                )
                fig.update_layout(xaxis_title=x, yaxis_title=y)

        elif (
            (x is None or y is None)
            and (x is not None or y is not None)
            and ("Scatter" == plot_type)
        ):
            if x is None:
                dat = y
            else:
                dat = x
            if color is None:
                fig.add_trace(trace=go.Histogram(x=df[dat]))
                fig.update_layout(xaxis_title=dat, yaxis_title="count")
            else:
                for i, val in enumerate(df[color].unique()):
                    fig.add_trace(
                        trace=go.Histogram(
                            name=val,
                            x=df.loc[df[color] == val][dat],
                            marker_color=colors_value[i % len(colors_value)],
                        )
                    )
                fig.update_layout(
                    xaxis_title=dat,
                    yaxis_title="count",
                    barmode="overlay",
                    legend_title=color,
                )
                fig.update_traces(opacity=0.6)

        elif (
            (x is not None or y is not None)
            and ("Box" == plot_type)
            and (color is not None)
        ):
            if x is None:
                dat = y
            else:
                dat = x

            val_mean = []
            for val in df[color].unique():
                val_mean.append([val, df.loc[df[color] == val][dat].median()])

            val_mean = sorted(val_mean, reverse=True, key=lambda x: x[1])
            sorted_vals = [x[0] for x in val_mean]

            for i, val in enumerate(sorted_vals):
                fig.add_trace(
                    trace=go.Box(
                        name=val,
                        x=df.loc[df[color] == val][dat],
                        marker_color=colors_value[i % len(colors_value)],
                        boxpoints="all",
                        jitter=0.3,
                        pointpos=-1.8,
                    )
                )
            fig.update_layout(xaxis_title=dat, yaxis_title="count", legend_title=color)

    fig.update_layout(
        margin=dict(l=30, r=30, t=20, b=0),
    )
    return fig, sorted(plot_cols), sorted(plot_cols), sorted(color_cols)


# Runs the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
