import ssl, urllib, subprocess, os
from datetime import timedelta
import pandas as pd
import numpy as np
from urllib.request import urlopen
from bs4 import BeautifulSoup
from dateutil.parser import parse

class API:
    
    #Convert lat, lon to a sinusoidal tile
    def _convert_lat_lon_to_tile(self, lat, lon):
        t_data = urlopen('https://modis-land.gsfc.nasa.gov/pdf/sn_bound_10deg.txt', context=ssl.SSLContext()).read()
        zones = []
        in_data = False
        for l in t_data.decode('utf-8').split('\r'):
            if in_data and not l.strip():
                in_data = False
            elif in_data:
                zones.append(l.split())
            if l.strip().startswith('iv  ih'):
                in_data = True

        df = pd.DataFrame(zones, columns=["iv", "ih", "lon_min", "lon_max", "lat_min", "lat_max"])
        for col in df.columns: df[col] = pd.to_numeric(df[col])
        t_lat = lat
        t_lon = lon

        return df[(df['lon_min'] < t_lon) & (df['lon_max'] > t_lon) & (df['lat_min'] < t_lat) & (df['lat_max'] > t_lat)]
    
    #Get our file URL
    def _locate_file_url(self, event_date, tile, major_endpoint, product):
        core_url = 'https://e4ftl01.cr.usgs.gov/{MAJOR_ENDPOINT}/{PRODUCT}/{YR}.{MO}.{DAY}/'.format(YR=event_date.year,
                                                                                         MO=str(event_date.month).zfill(2),
                                                                                         DAY=str(event_date.day).zfill(2),
                                                                                         MAJOR_ENDPOINT=major_endpoint,
                                                                                         PRODUCT=product)
        
        #Download, extract anchor tags
        print("Core url: " + core_url)
        data = urlopen(core_url)
        soup = BeautifulSoup(data, "html.parser")
        linkz = [x['href'] for x in soup.find_all('a') if x['href'].startswith('MY') or  
                 x['href'].startswith('MC') or 
                 x['href'].startswith('MO')]
        
        #Get the search term, search for the tile, and return the full URL
        tile_loc = self._tile_id_to_url_id(tile)
        true_link = [x for x in linkz if tile_loc in x]
        return core_url + true_link[0]
        
    #Convert a tile ID to what you see in a URL
    def _tile_id_to_url_id(self, tile):
        return 'h' + str(tile['h']).zfill(2) + 'v' + str(tile['v']).zfill(2)
    
    #Translates a file (hdf) to tif files
    def _transform_to_tif(self, file_location):
        command = 'gdal_translate '+file_location+' -sds '+file_location+'_out.tif -sds -ot UInt16 -of GTiFF'
        subprocess.run(command, shell=True, check=True)
        
    #Downloads the file at some URL, follows redirects
    def _download_data_by_url(self, url, target_folder, f_desig, H, V):
        try:
            os.mkdir(target_folder + '/modis_h{H}_v{V}'.format(H=str(H), V=str(V)))
        except OSError: pass
        
        print(target_folder + '/modis_h{H}_v{V}/{F_DESIG}'.format(F_DESIG=f_desig, H=str(H), V=str(V)))
        command = 'wget --user '+username+' --password '+password+' \
                --keep-session-cookies -q -O '+target_folder+'/modis_h{H}_v{V}/{F_DESIG} \
                {URL}'.format(URL=url, F_DESIG=f_desig, H=str(H), V=str(V))
                
        subprocess.run(command, shell=True, check=True)
        
    def __init__(self):
        pass
    
'''
Example program
Create a new user @ https://urs.earthdata.nasa.gov/users/new
'''

if __name__ == "__main__":
    api = API()
    df_tile = api._convert_lat_lon_to_tile(1, 2)
    
    event_date = parse('June 1, 2018')
    
    tile = {'h': df_tile.iloc[0]['ih'], 'v': df_tile.iloc[0]['iv']}
    url = api._locate_file_url(event_date, tile, 'MOLA', 'MYDOCGA.006')
    base_folder = '/home/rani/modis/'
    
    filename_modifier = d.strftime('%Y.%m.%d.' + t_url.split('.')[-6].split('/')[-1] + '.' + t_url.split('.')[-1])
    api._download_data_by_url(url, base_folder, username, password, f_desig=filename_modifier, H=tile['h'], V=tile['v'])
    
    file_location = base_folder + '/modis_h{H}_v{V}/{F_DESIG}'.format(F_DESIG=filename_modifier, H=str(tile['h']), V=str(tile['v']))
    api._transform_to_tif(file_location)
    
