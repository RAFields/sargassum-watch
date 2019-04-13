import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import os, re
from PIL import Image #pip3 install pillow if missing
from collections import Counter
import random, copy

class DataLoader:

    '''
    Loads an image, returns a numpy array of pixel values
    '''
    def load_image(self, image_location):
        samp_img = Image.open(image_location)
        imgarr = np.asarray(samp_img)
        return imgarr

    '''
    Loads and image and returns some basic descriptive stats
    '''
    def get_image_descriptive_stats(self, image_location, min_clip=84, max_clip=252):
        if os.path.isdir(image_location): return np.nan, np.nan, np.nan, np.nan
        imgarr = self.load_image(image_location)
        raw_img = imgarr
        imgarr = imgarr[min_clip:max_clip, min_clip:max_clip]
        imgarr = imgarr ** 4
        imgarr_raw = imgarr
        imgarr = imgarr[imgarr > 0.]
        perc_missing = float(len(imgarr_raw[imgarr_raw <= 0.].reshape(-1))) / float(len(raw_img.reshape(-1)))

        return imgarr.mean(), imgarr.std(), imgarr.min(), imgarr.max(), perc_missing, raw_img

    '''
    Amounts = a dict of date -> amount
    e.g.
        {
            '2015.12.03': 3,
            '2015.12.04': 4,
        }
    dir_key, if set, will prepend mean/std/min/max keys with the key.
    This will result in column names being prepended with that key later on.
    For instance, a directory key of "rrs_412" will result in pandas columns
    "rrs_412_mean", "rrs_412_max", etc.
    '''
    def get_all_images_from_directory(self, _dir, dir_key, amounts=[], image_folder='images'):
        image_filename_dict = {}

        print(_dir + '/' + image_folder)
        if not os.path.isdir(_dir):
            print("Fail on " + _dir)
            return {}

        #Adjust for trailing /
        if _dir.endswith('/'): _dir = _dir[:-1]

        for _file in os.listdir(_dir + '/' + image_folder):
            if not re.search('(bmp|jpg|tiff|gif|jpeg|png)$', _file): 
                print("Non-image file found, skipping: " + _dir + '/' + image_folder + '/' + _file)
                continue

            try:
                img_mean, img_std, img_min, img_max, perc_missing, raw_img = self.get_image_descriptive_stats(_dir + '/' + image_folder + '/' + _file)
                img_vals = {
                    dir_key + '_mean': img_mean,
                    dir_key + '_std': img_std,
                    dir_key + '_min': img_min,
                    dir_key + '_max': img_max,
                    dir_key + '_missing': perc_missing,
                    dir_key + '_raw': raw_img
                }
                file_date = '.'.join(_file.split('.')[:3])
                if isinstance(amounts, pd.core.series.Series):
                    try:
                        amount = amounts.loc[file_date]
                        img_vals['amount'] = amount
                    except (IndexError, KeyError) as e: 
                        print("Could not parse date data for " + file_date + ", " + str(e))
                image_filename_dict[file_date] = img_vals
            except ValueError: 
                print("Could not compute values for " + str(_dir + '/' + image_folder + '/' + _file))
        return image_filename_dict

    '''
    Load descriptive stats for an image from a folder, returns a pandas dataframe
    of image data
    '''
    def get_pandas_dataframe_from_folder(self, folder='.', amounts=None):

        image_filename_dict = {}

        for _dir in os.listdir(folder):
            base = ''
            if folder != '.': base = folder[:-1] if folder.endswith('/') else folder
            #print("====")
            #print(base)
            if base: base = base + '/'
            if not os.path.isdir(base + _dir): continue
            print((base + _dir, _dir, 'ncs' in _dir))
            #print(base)
            image_folder = 'images' if not 'ncs' in _dir else 'images_minmax'
            temp_image_filename_dict = self.get_all_images_from_directory(base + _dir, _dir, amounts=amounts, image_folder=image_folder)
            for key in temp_image_filename_dict:
                if key not in image_filename_dict: image_filename_dict[key] = {}
                image_filename_dict[key].update(temp_image_filename_dict[key])

        return pd.DataFrame(image_filename_dict).T

    '''
    get_pandas_dataframe_from_folder but also loads amount data
    '''
    def load_image_data_and_amount_data(self, folder='.', amounts=None, csv_location=None, amount_key='amounts', date_key='parsedate'):
        if not amounts:
            amounts = self.load_amount_data(csv_location, amount_key=amount_key, date_key=date_key)
        return self.get_pandas_dataframe_from_folder(folder=folder, amounts=amounts)

    '''
    Loads amount data, assumes you're using csv with an 'amounts' column
    unless specified otherwise.
    Date data in the format of <year>.<month>.<day>
    '''
    def load_amount_data(self, csv_location, amount_key='amounts', date_key='parsedate'):
        csv_data = pd.read_csv(csv_location)
        if amount_key != 'amounts':
            csv_data['amounts'] = csv_data[amount_key]
        csv_data = csv_data.set_index(date_key)
        return csv_data['amounts']

    def __init__(self): pass

'''
Sample models and useful tools
'''
from sklearn.decomposition import PCA, KernelPCA
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import confusion_matrix

# Various models
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.neighbors import KNeighborsClassifier

'''
Like sklearn's train_test_split but undersamples certain classes
to product equal class sizes.

Remaining instances are spun off as test data. If you want a balanced
amount of test data, re-run balanced_sample on the remaining data
with a train_size of 1.0.
'''
def balanced_sample(X, y, train_size=0.8):
    classes = Counter(y.reshape(-1))
    class_indices = {}
    for c in classes:
        if c not in class_indices: class_indices[c] = []
        class_indices[c] = [idx for idx, x in enumerate(y) if x == c]
    train_amt = int(min([train_size * v for v in classes.values()]))
    test_amt = int(min([(1. - train_size) * v for v in classes.values()]))
    train_X = []
    test_X = []
    train_y = []
    test_y = []
    train_X_lox = []
    test_X_lox = []
    for c, v in class_indices.items():
        choices_train = np.random.choice(v, train_amt, replace=False)
        choices_test = list(set(v).difference(set(choices_train)))
        train_X_lox += list(choices_train)
        test_X_lox += list(choices_test)
        if isinstance(y, np.ndarray):
            train_y += list(np.take(y, choices_train))
            test_y += list(np.take(y, choices_test))
        else:
            train_y += list(y.iloc[choices_train])
            test_y += list(y.iloc[choices_test])
    if isinstance(X, np.ndarray):
        return np.take(X, train_X_lox, axis=0), np.take(X, test_X_lox, axis=0), train_y, test_y
    else:
        return X.iloc[train_X_lox], X.iloc[test_X_lox], train_y, test_y

'''
Assigns the value for the first day of a month to the remaining days in that month
For instance, if the sargassum amount was "-2" for 2015.05.01, this will assign 
all days in 2015.05 a sargassum amount of -2.
'''
def apply_to_month(df, col):
    for yr in range(2014, 2020):
        for mo in range(1, 13):
            if yr == 2019 and mo >= 4: break
            try:
                firstday_amt = df.loc[str(yr) + '.' + str(mo).zfill(2) + '.01'][col]
                for day in range(2, 32):
                    try:
                        df.loc[str(yr) + '.' + str(mo).zfill(2) + '.' + str(day).zfill(2), col] = firstday_amt
                        print("Set " + str(str(yr) + '.' + str(mo).zfill(2) + '.' + str(day).zfill(2)) + " to " + str(df.loc[str(yr) + '.' + str(mo).zfill(2) + '.' + str(day).zfill(2)][col]) + ", " + str(firstday_amt))
                    except (KeyError): 
                        print("Inner KeyError on " + str((yr, mo, day)))
            except KeyError: 
                print("KeyError on " + str((yr, mo)))
    return df

#from https://stackoverflow.com/questions/31202843/rolling-majority-on-non-numeric-data
def my_rolling_apply_char(frame, window, func, modfunc):
    index = frame.index[window-1:]
    values = [func(frame.iloc[i:i+window], modfunc) for i in range(len(frame)-window+1)]
    return pd.Series(data=values, index=index).reindex(frame.index)

def ippa_transform(x, modfunc):
    x = x.dropna()
    li = np.array(x.tolist())
    li2 = li.reshape(-1)
    return modfunc(li2[li2>0])

def mpi_transform(x, modfunc):
    print("Entry")
    #windows
    x = x.dropna()
    #numpy array of window frames
    li = np.array(x.tolist())
    #start with the last frame, move forward replacing each pixel with the most recent 
    #non-nan/0 value encountered
    li2 = np.apply_along_axis(lambda x : mpi_transform_for_depth(x), 0, li)
    if True:
        return li2
    #harvest desired stats from our MPI image
    li2 = frame.reshape(-1)
    try:
        return modfunc(li2[li2>0])
    except ValueError:
        return np.nan

def mpi_transform_for_depth(d_vec):
    flipped = np.flip(d_vec, axis=0)
    for entry in flipped:
        if (not np.isnan(entry)) and (entry != 0):
            return entry
    return np.nan



'''
Load data and create an example classifier
'''
if __name__ == '__main__':
    import warnings
    warnings.simplefilter(action='ignore', category=FutureWarning)

    test_folder = '/Volumes/Sparkoflow/modis_data/'
    sargassum_csv = 'sargass_dates_extended.csv'

    #Loads data
    dl = DataLoader()
    df = dl.load_image_data_and_amount_data(folder=test_folder, csv_location=sargassum_csv, amount_key='Amt')

    #Add IPPA (informed per-pixel averaging) values
    colz = [x for x in df.columns if 'raw' in x]
    for c in colz:
        df[c + '_ippa_mean'] = my_rolling_apply_char(df[c], 30, ippa_transform, np.mean)

    colz = [x for x in df.columns if 'raw' in x]
    for c in colz:
        df[c + '_ippa_std'] = my_rolling_apply_char(df[c], 30, ippa_transform, np.std)

    #Add MPI (missing pixel interpolation)

    #Updates the dataframe
    interpolated_df = df.interpolate()
    interpolated_df['diff_amount'] = interpolated_df['amount'].diff()
    interpolated_df = interpolated_df.dropna()

    #Assign the value from the first day of each month to the remaining days for that month
    #Also, change all amount values to [-1, 0, 1]
    month_updated_df = apply_to_month(interpolated_df, 'diff_amount')
    month_updated_df['change_amount'] = month_updated_df['diff_amount'].apply(lambda x : 0 if x == 0 else (1 if x > 0 else -1))

    #Shuffle our dataframe
    shuffled_df = month_updated_df.sample(frac=1)

    '''
    Multinomial examples
    '''

    #Get our X and y
    x_cols = [x for x in shuffled_df.columns if 'amount' not in x]
    y_col = ['change_amount']
    X = shuffled_df[x_cols]
    y = shuffled_df[y_col]
    X_train, X_test, y_train, y_test = balanced_sample(X, y['change_amount'])

    #Example classifier 1
    print("")
    print("Random forest (multinomial):")
    rfc = RandomForestClassifier(50).fit(X_train, y_train)
    preds = rfc.predict(X_test)
    print(classification_report(preds, y_test))
    #print("ROC AUC: " + str(roc_auc_score(preds, y_test)))

    #Example classifier 1
    print("")
    print("Logistic regression (multinomial):")
    lr = LogisticRegression(penalty='l2', C=1.2, solver='sag', multi_class='multinomial', max_iter=500).fit(X_train, y_train)
    preds = lr.predict(X_test)
    print(classification_report(preds, y_test))
    #print("ROC AUC: " + str(roc_auc_score(preds, y_test)))

    '''
    Binary examples
    '''

    #Drop 0 amounts and try again with 
    min_df = shuffled_df[shuffled_df['change_amount'] != 0]
    x_cols = [x for x in min_df.columns if 'amount' not in x]
    y_col = ['change_amount']
    X = min_df[x_cols]
    y = min_df[y_col]
    pca = PCA(40)
    newX = pca.fit_transform(X)
    X_train, X_test, y_train, y_test = balanced_sample(newX, y['change_amount'])

    #Example classifier 1
    print("")
    print("Random forest (binary):")
    rfc = RandomForestClassifier(100).fit(X_train, y_train)
    preds = rfc.predict(X_test)
    print(classification_report(preds, y_test))
    print("ROC AUC: " + str(roc_auc_score(preds, y_test)))

    #Example classifier 1
    print("")
    print("Logistic regression (binary):")
    lr = LogisticRegression(penalty='l2', C=0.7).fit(X_train, y_train)
    preds = lr.predict(X_test)
    print(classification_report(preds, y_test))
    print("ROC AUC: " + str(roc_auc_score(preds, y_test)))


    #Example classifier 1
    print("")
    print("KNC (binary):")
    knc = KNeighborsClassifier(9).fit(X_train, y_train)
    preds = knc.predict(X_test)
    print(classification_report(preds, y_test))
    print("ROC AUC: " + str(roc_auc_score(preds, y_test)))
