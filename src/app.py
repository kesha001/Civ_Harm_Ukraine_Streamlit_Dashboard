import pandas as pd
import numpy as np
import streamlit as st
import pydeck as pdk
import plotly.express as px
import json
import geopandas as gpd
import contextily as cx
import matplotlib.pyplot as plt
import folium
from folium.plugins import HeatMap
from datetime import datetime
from streamlit_folium import folium_static

civharm_data_path = "./data/ukr-civharm-2023-06-01.json"
regions_data_path = "./data/ukr_admbnda_sspe_20230201_SHP/ukr_admbnda_adm1_sspe_20230201.shp"

@st.cache_data(persist=True)
def load_json_file(data_path):
    with open(data_path, 'r') as file:
        data = json.loads(file.read())
        
    incidents_data = pd.json_normalize(data, record_path='filters', \
                                       meta=['id', 'date', 'latitude', 'longitude', 'location', 'description'])

    incidents_data = incidents_data[incidents_data['key'] == 'Type of area affected'].rename(columns={'value': 'area_type'}).reset_index()

    columns = [
        'id', 
        'date', 
        'latitude', 
        'longitude', 
        'location', 
        'area_type', 
        'description'
    ]

    incidents_data = incidents_data[columns]
    incidents_data[["latitude", "longitude"]] = incidents_data[["latitude", "longitude"]].apply(pd.to_numeric)

    incidents_data['date'] = pd.to_datetime(incidents_data['date'])

    return incidents_data


@st.cache_data(persist=True)
def load_regions_data(path):
    regions = gpd.read_file(path)
    regions.to_crs(epsg=3857, inplace=True)

    return regions


@st.cache_data(persist=True)
def incidents_by_area_type(data):

    incidents_by_type = data.groupby('area_type').size()
    incidents_by_type = incidents_by_type.to_frame(name='n_events').reset_index()
    incidents_by_type = incidents_by_type.sort_values(by='n_events', ascending=False)

    civ_harm_by_area = px.bar(incidents_by_type, y='n_events', x='area_type', title='Civilian harm by type of affected area', 
                hover_data=['n_events'], labels={'n_events':'Number of incidents'}, color='area_type')

    return civ_harm_by_area


@st.cache_data(persist=True)
def incidents_by_day_line(data):
    incidents_by_day = data.groupby('date').size().to_frame(name='n_events').reset_index()
    incidents_by_day_fig = px.line(incidents_by_day, x='date', y='n_events', \
                               title='Number of incidents per day', labels={'n_events':'Number of incidents'})
    
    return incidents_by_day_fig


def folium_heat_map(incidents_data, regions):
    geo_incidents_df = gpd.GeoDataFrame(incidents_data, geometry=gpd.points_from_xy(incidents_data['longitude'], \
                                                                                    incidents_data['latitude']), crs="EPSG:4326")
    geo_incidents_df.to_crs(epsg=3857, inplace=True)

    combined_geo_incidents_df = gpd.sjoin(geo_incidents_df, regions[['ADM1_EN', 'geometry']], predicate='within').drop(columns=['index_right'])
    m = folium.Map(location=[49.107892273527504, 31.444630060047018], tiles = 'stamentoner', zoom_start=6, control_scale=True)

    heat_data = list(zip(combined_geo_incidents_df["latitude"], combined_geo_incidents_df["longitude"]))

    HeatMap(heat_data).add_to(m)

    return m


incidents_data = load_json_file(civharm_data_path)
# regions = load_regions_data(regions_data_path)


st.title("Civilian Harm Incidents by rusia in Ukraine")


with st.sidebar:
    st.title("Panel for map visualisation")
    option = st.selectbox(
        'Data of map',
        ('Until date', 'Between dates', 'On date'))
    st.write('You selected:', option)


    map_type = st.selectbox(
        'Type of map visualisation',
        ('Scatterplot', 'Heatmap', 'Hexagonmap'))
    st.write('You selected:', map_type)


start = min(incidents_data['date'])
end = max(incidents_data['date'])

if option=='Until date':
    end_date = st.slider(
        "Events until",
        min_value = start,
        max_value = end,
        value = end.to_pydatetime(),
        format="MM/DD/YYYY")
    incidents_data_period = incidents_data.query("date <= @end_date")
elif option=='Between dates':
    start_date, end_date = st.slider(
        "Events between",
        min_value = start,
        max_value = end,
        value = (start.to_pydatetime(), end.to_pydatetime()),
        format="MM/DD/YYYY")
    incidents_data_period = incidents_data.query("(date <= @end_date) & (date >= @start_date)")
else:
    spec_date = st.slider(
        "Events on",
        min_value = start,
        max_value = end,
        value = start.to_pydatetime(),
        format="MM/DD/YYYY")
    incidents_data_period = incidents_data.query("date == @spec_date ")


# Midpoint for initial view
midpoint = (np.average(incidents_data['latitude']), np.average(incidents_data['longitude']))

if map_type == "Scatterplot":
    st.map(incidents_data_period[['longitude', 'latitude']], zoom=5)
elif map_type == "Heatmap":
    py_deck_heatlayer =  pdk.Layer(
            "HeatmapLayer",
            data = incidents_data_period,
            get_position=['longitude', 'latitude'],
        )
    py_deck_heatmap= pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v11",
        initial_view_state={
            'latitude': midpoint[0],
            'longitude': midpoint[1],
            'zoom': 5,
            'pitch': 0,
        },
        layers=[py_deck_heatlayer],
    )
    st.pydeck_chart(py_deck_heatmap)
else:
    pitch_size = 0
    if st.sidebar.checkbox("Pitch map", False):
        pitch_size = 50
    extruded = st.sidebar.checkbox("Extrude map", False)

    hexagon_layer = pdk.Layer(
            "HexagonLayer",
            data = incidents_data_period,
            opacity=0.8,
            get_position=['longitude', 'latitude'],
            radius=500,
            pickable=True,
            filled=True, 
            extruded=extruded,
            elevation_scale=10,
            elevation_range=[500, 10000],
        ),

    py_deck_hexagonmap = pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v11",
        initial_view_state={
            'latitude': midpoint[0],
            'longitude': midpoint[1],
            'zoom': 5,
            'pitch': pitch_size,
        },
        layers = [hexagon_layer]
    )
    st.pydeck_chart(py_deck_hexagonmap)
    

if st.checkbox("Show raw data", False):    
    st.write(incidents_data_period)

civ_harm_by_area = incidents_by_area_type(incidents_data_period)
st.write(civ_harm_by_area)

incidents_by_day_line_fig = incidents_by_day_line(incidents_data)
st.write(incidents_by_day_line_fig)