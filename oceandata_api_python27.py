from bs4 import BeautifulSoup
import urllib2, commands
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import os
from matplotlib import pyplot as plt
import datetime

#Downloads data
def download(url, dl_loc):
    data = urllib2.urlopen(url).read()
    filename = url.split('/')[-1]
    with open(dl_loc + '/' + filename, 'w+') as f:
        f.write(data)

def lon_to_x(lat, im_max_x):
    adj_lat = lat + 180 #map from [-180, 180] to [0, 360]
    adj_lat /= 360. #map to [0, 1]
    return int(round(adj_lat * im_max_x, 0))

def lat_to_y(lon, im_max_y):
    adj_lon = lon + 90 #map from [-90, 90] to [0, 180]
    adj_lon /= 180. #map to [0, 1]
    return int(round(adj_lon * im_max_y, 0))

#Clips an image to lat, lon coords
def clip_to_lat_lon(t_floc, lat, lon, scan_radius=None):
    
    array = np.array(Image.open(t_floc), dtype=float)
    lat *= -1. #flip due to how image array coords are handled
    
    if scan_radius:
        lat_min = lat - scan_radius
        lat_max = lat + scan_radius
        lon_min = lon - scan_radius
        lon_max = lon + scan_radius
    else:
        lat_min, lat_max = lat
        lon_min, lon_max = lon
        
    im_max_y, im_max_x = array.shape
    y_min = lat_to_y(lat_min, im_max_y)
    y_max = lat_to_y(lat_max, im_max_y)
    x_min = lon_to_x(lon_min, im_max_x)
    x_max = lon_to_x(lon_max, im_max_x)
    
    return array[y_min:y_max, x_min:x_max]

#Loads an image, clips it, runs transformations if requested, and saves it
def minclip_tif(lat, lon, scan_radius, bandname, dl_loc, scale_max=None, pow_transform=1, mean_transform=False, emboss=False, invert=False):
    fs = [x for x in os.listdir(dl_loc) if 'out_1' in x]
    
    for f in fs:
        
        #Get image clipped to lat, lon
        m_arr = clip_to_lat_lon(dl_loc + '/' + f, lat, lon, scan_radius)
        t_arr = m_arr

        #Determine how we want to scale
        #We need to scale some images due to some crazy ranges you see by default
        if scale_max:
            t_arr = (t_arr - t_arr.min()) / float(scale_max)
        else:
            t_arr = (t_arr - t_arr.min()) / float(float(t_arr.max()) - float(t_arr.min()))
            
        #Misc. optional image transformations
        if invert : t_arr = 1. - t_arr
        t_arr = t_arr ** pow_transform #pow is set to 1 by default
        if mean_transform:
            t_arr_avg = t_arr[t_arr > 0.].mean()
            t_arr = t_arr - t_arr_avg
            t_arr = np.abs(t_arr)
            
        #Set up our image data
        im = Image.fromarray(t_arr * 256.)
        im = im.convert("L")
        
        #Optional image transformation
        if emboss:
            im = im.filter(ImageFilter.EMBOSS)
            
        #Save our iamge
        rawdate = datetime.datetime.strptime(f.split('.')[0][1:5] + ' ' + f.split('.')[0][5:8], '%Y %j')
        im.save(dl_loc + '/images/' + rawdate.strftime('%Y.%m.%d') + '.' + str(bandname) + '.bmp')

#Downloads all files present in a folder
#Uses beautifulsoup
def download_all_files(url, dl_loc, searchterm=None):
    #Download page, discover files to download
    html_doc = urllib2.urlopen(url)
    soup = BeautifulSoup(html_doc, 'html.parser')
    batch_dl_urls = [x['href'] for x in soup.find_all('a') if x.text.endswith('nc')]
    
    #Searching for files made >= 2010
    if searchterm:
        urls = [x['href'] for x in soup.find_all('a') if x.text.endswith('nc') and x.text.startswith('A201') and searchterm in x.text]
    else:
        urls = [x['href'] for x in soup.find_all('a') if x.text.endswith('nc') and x.text.startswith('A201')]
        
    #Download each file, supports skipping already downloaded files
    complete = []
    idx = 0
    existing_files = os.listdir(dl_loc)
    for u in urls:
        idx += 1
        if u in complete: continue
        if u.split('/')[-1] in existing_files: continue
        print((idx, len(urls), u))
        download(u, dl_loc)
        complete.append(u)

#Translates *.nc to GeoTiFF format
def translate_all_to_tif(dl_loc, verbose=False):
    files = os.listdir(dl_loc)
    for f in files:
        if verbose: print('gdal_translate '+dl_loc+'/'+f+' -sds '+dl_loc+'/{O}_out.tif -sds -ot UInt16 -of GTiFF'.format(F=f, O=f))
        commands.getoutput('gdal_translate '+dl_loc+'/'+f+' -sds '+dl_loc+'/{O}_out.tif -sds -ot UInt16 -of GTiFF'.format(F=f, O=f))

#Download all files to a given directory
#Default lat/lon for Cancun
def download_url_to_directory(url, dl_loc, lat=21.1742900, lon=-86.8465600, scan_radius=7., searchterm=None, scale_max=8000.):
    download_all_files(url, dl_loc, searchterm=searchterm)
    try:
        os.mkdir(dl_loc + '/images')
    except OSError:
        pass
    
    #.nc -> .tif
    translate_all_to_tif(dl_loc)
    
    #get the band size for namign reasons
    bandsize = dl_loc.split('_')[-1]
    
    #Scale to [0, 8000] due to sea temp scale
    #take the .tif file, clip it to lat, lon specs and dump the file under {SUBFOLDER}/images
    minclip_tif(lat, lon, scan_radius, bandsize, dl_loc, scale_max=scale_max)

#Example
if __name__ == "__main__":
    #Note: Running this from a folder where ncs_412, ncs_443 etc are present as sub-folders
    dl_locs = ['ncs_412', 'ncs_443', 'ncs_469', 'ncs_488', 'ncs_531', 'ncs_547', 'ncs_555', 'ncs_645', 'ncs_667', 'ncs_678']
    
    for dl_loc in dl_locs:
        
        url_base = 'https://oceandata.sci.gsfc.nasa.gov/MODIS-Aqua/Mapped/Monthly/4km/Rrs_{BAND}/'
        band = dl_loc.split('_')[-1] #Note the folder names: ncs_412, ncs_442, etc. 412, 443 are bands.
        url = url_base.format(BAND=str(dl_loc.split('_')[-1]))
        
        print(url)
        download_url_to_directory(url, dl_loc)
