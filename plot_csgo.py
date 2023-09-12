"""
This is a library to use in making plotly plots of
csgo data. Currently there's
map_dict - dictionary of map coordinates for calibration
find_scale - function to align game data to png map scale
plot - function to plot coordinate data on top of csgo maps
"""
import numpy as np
from PIL import Image
import plotly.graph_objects as go
import webbrowser

# these are all the coordinates used to calibrate the data scaling function that follows
map_dict = {
    "ancient_game_x": [-2144, 1384, -140],
    "ancient_game_y": [1228, -860, -294],
    "inferno_game_x": [-1752.75, 2634, 4.03],
    "inferno_game_y": [811.5, -474, 3244],
    "mirage_game_x": [1359.3, -2032, -2636],
    "mirage_game_y": [520, -1765.5, 104],
    "nuke_game_x": [3498, -2992, 2100.3],
    "nuke_game_y": [-280, -584, -2331.6],
    "overpass_game_x": [-1416, -2700, -588],
    "overpass_game_y": [-3496, 1672, -336],
    "anubis_game_x": [471.5, 1488, -1223.4],
    "anubis_game_y": [3069.7, 572, -984.6],
    "vertigo_game_x": [-33, -1568, -2634],
    "vertigo_game_y": [-1359, 1007.9, 176.0],
    "ancient_map_x": [158, 865.8, 564],
    "ancient_map_y": [840, 417.4, 533.46],
    "inferno_map_x": [70.3, 963, 426.1],
    "inferno_map_y": [398.1, 139.3, 895.6],
    "mirage_map_x": [919.5, 236.5, 115],
    "mirage_map_y": [787.5, 330.5, 703.5],
    "overpass_map_x": [656, 408.7, 814.5],
    "overpass_map_y": [4, 1004.4, 610.5],
    "anubis_map_x": [626.7, 881, 298.4],
    "anubis_map_y": [974.6, 766, 197.1],
    "nuke_map_x": [998, 64.09, 799.2],
    "nuke_map_y": [573, 531, 273.8],
    "vertigo_map_x": [792, 397, 128.6],
    "vertigo_map_y": [242.5, 840, 621],
    "nuke_z_division": -480.9,
    "vertigo_z_division": 11600,
}


def find_scale(game_x, game_y, map_x, map_y):
    """This is how you calibrate the data to the map:
    Pick two points on the map.
    Their in game x(y) coordinates are game_x(y),
    and their image x(y) coordinates are map_x(y).
    If you got the coordinates accurately, the data should
    be automatically aligned by the transformation coefficients
    outputted by this function. The formulas can be derived w
    a bit of algebra.

    scaled coord = (coord - shift) * s

    output is x_shift, y_shift, s"""

    s = []
    x = []
    y = []

    idx = np.arange(len(game_x))
    pairs = [(a, b) for a in idx for b in idx[a + 1 :]]

    for i, j in pairs:
        s.append((map_x[i] - map_x[j]) / (game_x[i] - game_x[j]))

    s = np.mean(s)

    for i in idx:
        x.append((game_x[i] * s - map_x[i]) / s)
        y.append((game_y[i] * s - map_y[i]) / s)

    x = np.mean(x)
    y = np.mean(y)

    return x, y, s


def plot(dfs, map_string, plot_types, selected_data, click_data, graph_tool, highlight_index):
    """
    This function produces a plotly plot with heatmaps and scatters
    of deaths and kills. Additionally, it allows for selection of data
    to plot the connections of kills and deaths.
    Input:
    [df_victim, df_attacker],
    map_string (i.e. 'anubis'),
    plot_types (i.e. 'Death Scatter'),
    selected_data (index of data selected on plot).
    tool_type (selected data tool)

    Output:
    python dict describing plot
    """
    df_victim = dfs[0].copy()
    df_attacker = dfs[1].copy()
    # Add image
    I = Image.open("map_images/de_" + map_string + "_radar.jpg")
    w, h = I.size
    fig = go.Figure()

    fig.add_layout_image(
        dict(
            source=I,
            xref="x",
            yref="y",
            x=0,
            y=h,
            sizex=w,
            sizey=h,
            sizing="fill",
            layer="below",
        )
    )
    fig.update_xaxes(
        range=[0, w],
        scaleanchor="y",
        scaleratio=1,
        constrain="domain",
        showticklabels=False,
        showgrid=False,
        zeroline=False,
    )
    fig.update_shapes(dict(xref="x", yref="y"))
    fig.update_yaxes(range=[0, h], showticklabels=False, showgrid=False, zeroline=False)
    fig.update_layout(
        margin=dict(l=0, r=0, t=25, b=0),
        clickmode="event+select",
        autosize=True,
        yaxis_range=[0, h],
        xaxis_range=[0, w],
        template="plotly_white",
        showlegend=False,
        newshape_line_color='rgb(255, 234, 0)',
    )

    if not df_victim.empty:
        if "Deaths Heatmap" in plot_types:
            # Add heatmap trace
            fig.add_trace(
                trace=go.Histogram2dContour(name="dh",
                    x=df_victim["victim_x"],
                    y=df_victim["victim_y"],
                    autobinx=False,
                    autobiny=False,
                    xbins=dict(start=0, end=w, size=15),
                    ybins=dict(start=0, end=h, size=15),
                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(250, 42, 5, 1)"]],
                    hoverinfo="none",
                    showscale=False,
                )
            )

        if "Kills Heatmap" in plot_types:
            # Add heatmap trace
            fig.add_trace(
                trace=go.Histogram2dContour(name="kh",
                    x=df_attacker["attacker_x"],
                    y=df_attacker["attacker_y"],
                    autobinx=False,
                    autobiny=False,
                    xbins=dict(start=0, end=w, size=15),
                    ybins=dict(start=0, end=h, size=15),
                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(2, 191, 27, 1)"]],
                    hoverinfo="none",
                    showscale=False,
                )
            )

        # this is the data selected
        selected_index = (
            [x["customdata"] for x in selected_data["points"]]
            if selected_data is not None
            else []
        )

        selected_victim_index = list(set(selected_index) & set(df_victim.index))
        selected_attacker_index = list(set(selected_index) & set(df_attacker.index))

        if "Deaths Scatter" in plot_types:
            # Add victim scatter trace
            fig.add_trace(
                trace=go.Scatter(
                    x=df_victim["victim_x"],
                    y=df_victim["victim_y"],
                    customdata=df_victim["index"],
                    hoverinfo="text",
                    text="name: "
                    + df_victim.victim_name
                    + "<br>"
                    + "attacker: "
                    + df_victim.attacker_name
                    + "<br>"
                    + "killed with: "
                    + df_victim.weapon
                    + "<br>"
                    + "seconds: "
                    + df_victim.true_round_time.apply(lambda x: str(x))
                    + "<br>"
                    + "side:"
                    + df_victim.victim_side
                    + "<br>"
                    + "net dmg:"
                    + df_victim.net_dmg.apply(lambda x: str(x)),
                    mode="markers",
                    marker_symbol="x",
                    marker_color="rgb(255,0,0)",
                )
            )
            # add highlight trace
            if "Victim/Killer connection" == graph_tool:
                for i in selected_victim_index:
                    fig.add_shape(
                        type="line",
                        x0=float(df_victim.loc[[i]].attacker_x),
                        y0=float(df_victim.loc[[i]].attacker_y),
                        x1=float(df_victim.loc[[i]].victim_x),
                        y1=float(df_victim.loc[[i]].victim_y),
                        line=dict(
                            color="rgb(46, 154, 255)",
                            width=2,
                            dash="dot",
                        ),
                    )
                fig.add_trace(
                    trace=go.Scatter(
                        x=df_victim.loc[selected_victim_index].attacker_x,
                        y=df_victim.loc[selected_victim_index].attacker_y,
                        hoverinfo="text",
                        text="name: "
                        + df_victim.loc[selected_victim_index].attacker_name
                        + "<br>"
                        + "victim: "
                        + df_victim.loc[selected_victim_index].victim_name
                        + "<br>"
                        + "weapon: "
                        + df_victim.loc[selected_victim_index].weapon
                        + "<br>"
                        + "seconds: "
                        + df_victim.loc[selected_victim_index].true_round_time.apply(
                            lambda x: str(x)
                        )
                        + "<br>"
                        + "side:"
                        + df_victim.loc[selected_victim_index].attacker_side
                        + "<br>"
                        + "dmg dealt:"
                        + df_victim.damage_taken.apply(lambda x: str(x)),
                        mode="markers",
                        marker_symbol="circle",
                        marker_color="rgb(35, 201, 2)",
                    )
                )
            elif graph_tool == "HLTV link":
                if len(click_data) == 2:
                    click_data = [data for data in click_data if data is not None]
                    if click_data != []:
                        click_data = click_data[0]
                    else:
                        click_data = None
                else:
                    click_data = click_data[0]

                if click_data is not None:
                    try:
                        webbrowser.open_new(df_victim.loc[click_data["points"][0]["customdata"]].hltv_link)
                    except:
                        pass
            elif graph_tool == "Highlight player":
                fig.add_trace(
                        trace=go.Scatter(
                        x=df_victim.loc[df_victim.index.isin(highlight_index[0])]["victim_x"],
                        y=df_victim.loc[df_victim.index.isin(highlight_index[0])]["victim_y"],
                        mode="markers",
                        hoverinfo='skip',
                        marker_symbol="x",
                        marker_color="rgb(248, 252, 3)",
                        )
                    )

        if "Kills Scatter" in plot_types:
            # Add victim scatter trace
            fig.add_trace(
                trace=go.Scatter(
                    x=df_attacker["attacker_x"],
                    y=df_attacker["attacker_y"],
                    customdata=df_attacker["index"],
                    hoverinfo="text",
                    text="name: "
                    + df_attacker.attacker_name
                    + "<br>"
                    + "victim: "
                    + df_attacker.victim_name
                    + "<br>"
                    + "weapon: "
                    + df_attacker.weapon
                    + "<br>"
                    + "seconds: "
                    + df_attacker.true_round_time.apply(lambda x: str(x))
                    + "<br>"
                    + "side:"
                    + df_attacker.attacker_side
                    + "<br>"
                    + "dmg dealt:"
                    + df_attacker.damage_taken.apply(lambda x: str(x)),
                    mode="markers",
                    marker_symbol="circle-open",
                    marker_color="rgb(35, 201, 2)",
                )
            )
            
            if "Victim/Killer connection" == graph_tool:
                for i in selected_attacker_index:
                    fig.add_shape(
                        type="line",
                        x0=float(df_attacker.loc[[i]].attacker_x),
                        y0=float(df_attacker.loc[[i]].attacker_y),
                        x1=float(df_attacker.loc[[i]].victim_x),
                        y1=float(df_attacker.loc[[i]].victim_y),
                        line=dict(
                            color="rgb(46, 154, 255)",
                            width=2,
                            dash="dot",
                        ),
                    )
                fig.add_trace(
                    trace=go.Scatter(
                        x=df_attacker.loc[selected_attacker_index].victim_x,
                        y=df_attacker.loc[selected_attacker_index].victim_y,
                        hoverinfo="text",
                        text="name: "
                        + df_attacker.loc[selected_attacker_index].victim_name
                        + "<br>"
                        + "attacker: "
                        + df_attacker.loc[selected_attacker_index].attacker_name
                        + "<br>"
                        + "killed with: "
                        + df_attacker.loc[selected_attacker_index].weapon
                        + "<br>"
                        + "seconds: "
                        + df_attacker.loc[selected_attacker_index].true_round_time.apply(
                            lambda x: str(x)
                        )
                        + "<br>"
                        + "side:"
                        + df_attacker.loc[selected_attacker_index].victim_side
                        + "<br>"
                        + "net dmg:"
                        + df_attacker.net_dmg.apply(lambda x: str(x)),
                        mode="markers",
                        marker_symbol="x",
                        marker_color="rgb(255,0,0)",
                    )
                )
            elif graph_tool == "HLTV link":
                if len(click_data) == 2:
                    click_data = [data for data in click_data if data is not None]
                    if click_data != []:
                        click_data = click_data[0]
                    else:
                        click_data = None
                else:
                    click_data = click_data[0]

                if click_data is not None:
                    try:
                        webbrowser.open_new(df_attacker.loc[click_data["points"][0]["customdata"]].hltv_link)
                    except:
                        pass

            elif graph_tool == "Highlight player":
                # add highlight trace
                fig.add_trace(
                        trace=go.Scatter(
                        x=df_attacker.loc[df_attacker.index.isin(highlight_index[1])]["attacker_x"],
                        y=df_attacker.loc[df_attacker.index.isin(highlight_index[1])]["attacker_y"],
                        mode="markers",
                        hoverinfo='skip',
                        marker_symbol="circle",
                        marker_color="rgb(248, 252, 3)",
                        )
                    )


    return fig
