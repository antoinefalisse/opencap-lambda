'''
    ---------------------------------------------------------------------------
    OpenCap processing: utils.py
    ---------------------------------------------------------------------------

    Copyright 2022 Stanford University and the Authors
    
    Author(s): Antoine Falisse, Scott Uhlrich
    
    Licensed under the Apache License, Version 2.0 (the "License"); you may not
    use this file except in compliance with the License. You may obtain a copy
    of the License at http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
'''

import os
import requests
import urllib.request
import shutil
import numpy as np
import pandas as pd
import yaml
import pickle
import glob
import zipfile
import platform

from utilsAPI import get_api_url
from utilsAuthentication import get_token

API_URL = get_api_url()
API_TOKEN = get_token()

def download_file(url, file_name):
    with urllib.request.urlopen(url) as response, open(file_name, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def get_session_json(session_id):
    resp = requests.get(
        API_URL + "sessions/{}/".format(session_id),
        headers = {"Authorization": "Token {}".format(API_TOKEN)})
    
    if resp.status_code == 500:
        raise Exception('No server response. Likely not a valid session id.')
        
    sessionJson = resp.json()
    if 'trials' not in sessionJson.keys():
        raise Exception('This session is not in your username, nor is it public. You do not have access.')
    
    # Sort trials by time recorded.
    def get_created_at(trial):
        return trial['created_at']
    sessionJson['trials'].sort(key=get_created_at)
    
    return sessionJson

def get_trial_json(trial_id):
    trialJson = requests.get(
        API_URL + "trials/{}/".format(trial_id),
        headers = {"Authorization": "Token {}".format(API_TOKEN)}).json()
    
    return trialJson

def get_neutral_trial_id(session_id):
    session = get_session_json(session_id)    
    neutral_ids = [t['id'] for t in session['trials'] if t['name']=='neutral']
    
    if len(neutral_ids)>0:
        neutralID = neutral_ids[-1]
    elif session['meta']['neutral_trial']:
        neutralID = session['meta']['neutral_trial']['id']
    else:
        raise Exception('No neutral trial in session.')
    
    return neutralID 
 

def get_calibration_trial_id(session_id):
    session = get_session_json(session_id)
    
    calib_ids = [t['id'] for t in session['trials'] if t['name'] == 'calibration']
                                                          
    if len(calib_ids)>0:
        calibID = calib_ids[-1]
    elif session['meta']['sessionWithCalibration']:
        calibID = get_calibration_trial_id(session['meta']['sessionWithCalibration']['id'])
    else:
        raise Exception('No calibration trial in session.')
    
    return calibID

def get_camera_mapping(session_id, session_path):
    calibration_id = get_calibration_trial_id(session_id)
    trial = get_trial_json(calibration_id)
    resultTags = [res['tag'] for res in trial['results']]

    mappingPath = os.path.join(session_path,'Videos','mappingCamDevice.pickle')
    os.makedirs(os.path.join(session_path,'Videos'), exist_ok=True)
    if not os.path.exists(mappingPath):
        mappingURL = trial['results'][resultTags.index('camera_mapping')]['media']
        download_file(mappingURL, mappingPath)
    

def get_model_and_metadata(session_id, session_path):
    neutral_id = get_neutral_trial_id(session_id)
    trial = get_trial_json(neutral_id)
    resultTags = [res['tag'] for res in trial['results']]
    
    # Metadata.
    metadataPath = os.path.join(session_path,'sessionMetadata.yaml')
    if not os.path.exists(metadataPath) :
        metadataURL = trial['results'][resultTags.index('session_metadata')]['media']
        download_file(metadataURL, metadataPath)
    
    # Model.
    modelURL = trial['results'][resultTags.index('opensim_model')]['media']
    modelName = modelURL[modelURL.rfind('-')+1:modelURL.rfind('?')]
    modelFolder = os.path.join(session_path, 'OpenSimData', 'Model')
    modelPath = os.path.join(modelFolder, modelName)
    if not os.path.exists(modelPath):
        os.makedirs(modelFolder, exist_ok=True)
        download_file(modelURL, modelPath)
        
    return modelName
        
        
def get_motion_data(trial_id, session_path):
    trial = get_trial_json(trial_id)
    trial_name = trial['name']
    resultTags = [res['tag'] for res in trial['results']]

    # Marker data.
    if 'ik_results' in resultTags:
        markerFolder = os.path.join(session_path, 'MarkerData')
        markerPath = os.path.join(markerFolder, trial_name + '.trc')
        os.makedirs(markerFolder, exist_ok=True)
        markerURL = trial['results'][resultTags.index('marker_data')]['media']
        download_file(markerURL, markerPath)
    
    # IK data.
    if 'ik_results' in resultTags:
        ikFolder = os.path.join(session_path, 'OpenSimData', 'Kinematics')
        ikPath = os.path.join(ikFolder, trial_name + '.mot')
        os.makedirs(ikFolder, exist_ok=True)
        ikURL = trial['results'][resultTags.index('ik_results')]['media']
        download_file(ikURL, ikPath)
        
        
def get_geometries(session_path,
                   modelName='LaiUhlrich2022_scaled'):
        
    geometryFolder = os.path.join(session_path, 'OpenSimData', 'Model', 'Geometry')
    try:
        # Download.
        os.makedirs(geometryFolder, exist_ok=True)
        if 'Lai' in modelName:
            modelType = 'LaiArnold'
            vtpNames = [
                'capitate_lvs','capitate_rvs','hamate_lvs','hamate_rvs',
                'hat_jaw','hat_ribs_scap','hat_skull','hat_spine','humerus_lv',
                'humerus_rv','index_distal_lvs','index_distal_rvs',
                'index_medial_lvs', 'index_medial_rvs','index_proximal_lvs',
                'index_proximal_rvs','little_distal_lvs','little_distal_rvs',
                'little_medial_lvs','little_medial_rvs','little_proximal_lvs',
                'little_proximal_rvs','lunate_lvs','lunate_rvs','l_bofoot',
                'l_femur','l_fibula','l_foot','l_patella','l_pelvis','l_talus',
                'l_tibia','metacarpal1_lvs','metacarpal1_rvs',
                'metacarpal2_lvs','metacarpal2_rvs','metacarpal3_lvs',
                'metacarpal3_rvs','metacarpal4_lvs','metacarpal4_rvs',
                'metacarpal5_lvs','metacarpal5_rvs','middle_distal_lvs',
                'middle_distal_rvs','middle_medial_lvs','middle_medial_rvs',
                'middle_proximal_lvs','middle_proximal_rvs','pisiform_lvs',
                'pisiform_rvs','radius_lv','radius_rv','ring_distal_lvs',
                'ring_distal_rvs','ring_medial_lvs','ring_medial_rvs',
                'ring_proximal_lvs','ring_proximal_rvs','r_bofoot','r_femur',
                'r_fibula','r_foot','r_patella','r_pelvis','r_talus','r_tibia',
                'sacrum','scaphoid_lvs','scaphoid_rvs','thumb_distal_lvs',
                'thumb_distal_rvs','thumb_proximal_lvs','thumb_proximal_rvs',
                'trapezium_lvs','trapezium_rvs','trapezoid_lvs','trapezoid_rvs',
                'triquetrum_lvs','triquetrum_rvs','ulna_lv','ulna_rv']
        else:
            raise ValueError("Geometries not available for this model")                
        for vtpName in vtpNames:
            url = 'https://mc-opencap-public.s3.us-west-2.amazonaws.com/geometries_vtp/{}/{}.vtp'.format(modelType, vtpName)
            filename = os.path.join(geometryFolder, '{}.vtp'.format(vtpName))                
            download_file(url, filename)
    except:
        pass
    
def import_metadata(filePath):
    myYamlFile = open(filePath)
    parsedYamlFile = yaml.load(myYamlFile, Loader=yaml.FullLoader)
    
    return parsedYamlFile
    
def download_kinematics(session_id, folder=None, trialNames=None):
    
    # Login to access opencap data from server. 
    
    # Create folder.
    if folder is None:
        folder = os.getcwd()    
    os.makedirs(folder, exist_ok=True)
    
    # Model and metadata.
    neutral_id = get_neutral_trial_id(session_id)
    get_motion_data(neutral_id, folder)
    modelName = get_model_and_metadata(session_id, folder)
    # Remove extension from modelName
    modelName = modelName.replace('.osim','')
    
    # Session trial names.
    sessionJson = get_session_json(session_id)
    sessionTrialNames = [t['name'] for t in sessionJson['trials']]
    if trialNames != None:
        [print(t + ' not in session trial names.') 
         for t in trialNames if t not in sessionTrialNames]
    
    # Motion data.
    loadedTrialNames = []
    for trialDict in sessionJson['trials']:
        if trialNames is not None and trialDict['name'] not in trialNames:
            continue        
        trial_id = trialDict['id']
        get_motion_data(trial_id,folder)
        loadedTrialNames.append(trialDict['name'])
        
    # Remove 'calibration' and 'neutral' from loadedTrialNames.    
    loadedTrialNames = [i for i in loadedTrialNames if i!='neutral' and i!='calibration']
        
    # Geometries.
    get_geometries(folder, modelName=modelName)
        
    return loadedTrialNames, modelName

# %%  Storage file to numpy array.
def storage_to_numpy(storage_file, excess_header_entries=0):
    """Returns the data from a storage file in a numpy format. Skips all lines
    up to and including the line that says 'endheader'.
    Parameters
    ----------
    storage_file : str
        Path to an OpenSim Storage (.sto) file.
    Returns
    -------
    data : np.ndarray (or numpy structure array or something?)
        Contains all columns from the storage file, indexable by column name.
    excess_header_entries : int, optional
        If the header row has more names in it than there are data columns.
        We'll ignore this many header row entries from the end of the header
        row. This argument allows for a hacky fix to an issue that arises from
        Static Optimization '.sto' outputs.
    Examples
    --------
    Columns from the storage file can be obtained as follows:
        >>> data = storage2numpy('<filename>')
        >>> data['ground_force_vy']
    """
    # What's the line number of the line containing 'endheader'?
    f = open(storage_file, 'r')

    header_line = False
    for i, line in enumerate(f):
        if header_line:
            column_names = line.split()
            break
        if line.count('endheader') != 0:
            line_number_of_line_containing_endheader = i + 1
            header_line = True
    f.close()

    # With this information, go get the data.
    if excess_header_entries == 0:
        names = True
        skip_header = line_number_of_line_containing_endheader
    else:
        names = column_names[:-excess_header_entries]
        skip_header = line_number_of_line_containing_endheader + 1
    data = np.genfromtxt(storage_file, names=names,
            skip_header=skip_header)

    return data

# %%  Storage file to dataframe.
def storage_to_dataframe(storage_file, headers):
    # Extract data
    data = storage_to_numpy(storage_file)
    out = pd.DataFrame(data=data['time'], columns=['time'])    
    for count, header in enumerate(headers):
        out.insert(count + 1, header, data[header])    
    
    return out

# %%  Numpy array to storage file.
def numpy_to_storage(labels, data, storage_file, datatype=None):
    
    assert data.shape[1] == len(labels), "# labels doesn't match columns"
    assert labels[0] == "time"
    
    f = open(storage_file, 'w')
    # Old style
    if datatype is None:
        f = open(storage_file, 'w')
        f.write('name %s\n' %storage_file)
        f.write('datacolumns %d\n' %data.shape[1])
        f.write('datarows %d\n' %data.shape[0])
        f.write('range %f %f\n' %(np.min(data[:, 0]), np.max(data[:, 0])))
        f.write('endheader \n')
    # New style
    else:
        if datatype == 'IK':
            f.write('Coordinates\n')
        elif datatype == 'ID':
            f.write('Inverse Dynamics Generalized Forces\n')
        elif datatype == 'GRF':
            f.write('%s\n' %storage_file)
        elif datatype == 'muscle_forces':
            f.write('ModelForces\n')
        f.write('version=1\n')
        f.write('nRows=%d\n' %data.shape[0])
        f.write('nColumns=%d\n' %data.shape[1])    
        if datatype == 'IK':
            f.write('inDegrees=yes\n\n')
            f.write('Units are S.I. units (second, meters, Newtons, ...)\n')
            f.write("If the header above contains a line with 'inDegrees', this indicates whether rotational values are in degrees (yes) or radians (no).\n\n")
        elif datatype == 'ID':
            f.write('inDegrees=no\n')
        elif datatype == 'GRF':
            f.write('inDegrees=yes\n')
        elif datatype == 'muscle_forces':
            f.write('inDegrees=yes\n\n')
            f.write('This file contains the forces exerted on a model during a simulation.\n\n')
            f.write("A force is a generalized force, meaning that it can be either a force (N) or a torque (Nm).\n\n")
            f.write('Units are S.I. units (second, meters, Newtons, ...)\n')
            f.write('Angles are in degrees.\n\n')
            
        f.write('endheader \n')
    
    for i in range(len(labels)):
        f.write('%s\t' %labels[i])
    f.write('\n')
    
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            f.write('%20.8f\t' %data[i, j])
        f.write('\n')
        
    f.close()


def download_videos_from_server(session_id,trial_id,
                             isCalibration=False, isStaticPose=False,
                             trial_name= None, session_path = None):
    
    if session_path is None:
        data_dir = os.getcwd() 
        session_path = os.path.join(data_dir,'Data', session_id)  
    if not os.path.exists(session_path): 
        os.makedirs(session_path, exist_ok=True)
    
    resp = requests.get("{}trials/{}/".format(API_URL,trial_id),
                         headers = {"Authorization": "Token {}".format(API_TOKEN)})
    trial = resp.json()
    if trial_name is None:
        trial_name = trial['name']
    trial_name = trial_name.replace(' ', '')

    print("\nDownloading {}".format(trial_name))

    # The videos are not always organized in the same order. Here, we save
    # the order during the first trial processed in the session such that we
    # can use the same order for the other trials.
    if not os.path.exists(os.path.join(session_path, "Videos", 'mappingCamDevice.pickle')):
        mappingCamDevice = {}
        for k, video in enumerate(trial["videos"]):
            os.makedirs(os.path.join(session_path, "Videos", "Cam{}".format(k), "InputMedia", trial_name), exist_ok=True)
            video_path = os.path.join(session_path, "Videos", "Cam{}".format(k), "InputMedia", trial_name, trial_name + ".mov")
            download_file(video["video"], video_path)                
            mappingCamDevice[video["device_id"].replace('-', '').upper()] = k
        with open(os.path.join(session_path, "Videos", 'mappingCamDevice.pickle'), 'wb') as handle:
            pickle.dump(mappingCamDevice, handle)
    else:
        with open(os.path.join(session_path, "Videos", 'mappingCamDevice.pickle'), 'rb') as handle:
            mappingCamDevice = pickle.load(handle) 
            # ensure upper on deviceID
            for dID in mappingCamDevice.keys():
                mappingCamDevice[dID.upper()] = mappingCamDevice.pop(dID)
        for video in trial["videos"]:            
            k = mappingCamDevice[video["device_id"].replace('-', '').upper()] 
            videoDir = os.path.join(session_path, "Videos", "Cam{}".format(k), "InputMedia", trial_name)
            os.makedirs(videoDir, exist_ok=True)
            video_path = os.path.join(videoDir, trial_name + ".mov")
            if not os.path.exists(video_path):
                if video['video'] :
                    download_file(video["video"], video_path)
              
    return trial_name
   
    
def get_calibration(session_id,session_path):
    calibration_id = get_calibration_trial_id(session_id)

    resp = requests.get("{}trials/{}/".format(API_URL,calibration_id),
                         headers = {"Authorization": "Token {}".format(API_TOKEN)})
    trial = resp.json()
    calibResultTags = [res['tag'] for res in trial['results']]
   
    videoFolder = os.path.join(session_path,'Videos')
    os.makedirs(videoFolder, exist_ok=True)
    
    if trial['status'] != 'done':
        return
    
    mapURL = trial['results'][calibResultTags.index('camera_mapping')]['media']
    mapLocalPath = os.path.join(videoFolder,'mappingCamDevice.pickle')

    download_and_switch_calibration(session_id,session_path,calibTrialID=calibration_id)
    
    # Download mapping
    if len(glob.glob(mapLocalPath)) == 0:
        download_file(mapURL,mapLocalPath)
                        

def download_and_switch_calibration(session_id,session_path,calibTrialID = None):
    if calibTrialID == None:
        calibTrialID = get_calibration_trial_id(session_id)
    resp = requests.get("https://api.opencap.ai/trials/{}/".format(calibTrialID),
                         headers = {"Authorization": "Token {}".format(API_TOKEN)})
    trial = resp.json()
       
    calibURLs = {t['device_id']:t['media'] for t in trial['results'] if t['tag'] == 'calibration_parameters_options'}
    calibImgURLs = {t['device_id']:t['media'] for t in trial['results'] if t['tag'] == 'calibration-img'}
    _,imgExtension = os.path.splitext(calibImgURLs[list(calibImgURLs.keys())[0]])
    lastIdx = imgExtension.find('?') 
    if lastIdx >0:
        imgExtension = imgExtension[:lastIdx]
    
    if 'meta' in trial.keys() and trial['meta'] is not None and 'calibration' in trial['meta'].keys():
        calibDict = trial['meta']['calibration']
        calibImgFolder = os.path.join(session_path,'CalibrationImages')
        os.makedirs(calibImgFolder,exist_ok=True)
        for cam,calibNum in calibDict.items():
            camDir = os.path.join(session_path,'Videos',cam)
            os.makedirs(camDir,exist_ok=True)
            file_name = os.path.join(camDir,'cameraIntrinsicsExtrinsics.pickle')
            img_fileName = os.path.join(calibImgFolder,'calib_img' + cam + imgExtension)
            if calibNum == 0:
                download_file(calibURLs[cam+'_soln0'], file_name)
                download_file(calibImgURLs[cam],img_fileName)
            elif calibNum == 1:
                download_file(calibURLs[cam+'_soln1'], file_name) 
                download_file(calibImgURLs[cam + '_altSoln'],img_fileName)
                
            
def post_file_to_trial(filePath,trial_id,tag,device_id):
    files = {'media': open(filePath, 'rb')}
    data = {
        "trial": trial_id,
        "tag": tag,
        "device_id" : device_id
    }

    requests.post("{}results/".format(API_URL), files=files, data=data,
                         headers = {"Authorization": "Token {}".format(API_TOKEN)})
    files["media"].close()
    

def get_syncd_videos(trial_id,session_path):
    trial = requests.get("{}trials/{}/".format(API_URL,trial_id),
                         headers = {"Authorization": "Token {}".format(API_TOKEN)}).json()
    trial_name = trial['name']
    
    if trial['results']:
        for result in trial['results']:
            if result['tag'] == 'video-sync':
                url = result['media']
                cam,suff = os.path.splitext(url[url.rfind('_')+1:])
                lastIdx = suff.find('?') 
                if lastIdx >0:
                    suff = suff[:lastIdx]
                
                syncVideoPath = os.path.join(session_path,'Videos',cam,'InputMedia',trial_name,trial_name + '_sync' + suff)
                download_file(url,syncVideoPath)
        
        
def download_session(session_id, sessionBasePath= None,
                     zipFolder=False,writeToDB=False, downloadVideos=True):
    print('\nDownloading {}'.format(session_id))
    
    if sessionBasePath is None:
        sessionBasePath = os.path.join(os.getcwd(),'Data')
    
    session = get_session_json(session_id)
    session_path = os.path.join(sessionBasePath,'OpenCapData_' + session_id) 
    
    calib_id = get_calibration_trial_id(session_id)
    neutral_id = get_neutral_trial_id(session_id)
    dynamic_ids = [t['id'] for t in session['trials'] if (t['name'] != 'calibration' and t['name'] !='neutral')]  
    
    # Calibration
    try:
        get_camera_mapping(session_id, session_path)
        if downloadVideos:
            download_videos_from_server(session_id,calib_id,
                                 isCalibration=True,isStaticPose=False,
                                 session_path = session_path) 

        get_calibration(session_id,session_path)
    except:
        pass
    
    # Neutral
    try:
        modelName = get_model_and_metadata(session_id,session_path)
        get_motion_data(neutral_id,session_path)
        if downloadVideos:
            download_videos_from_server(session_id,neutral_id,
                             isCalibration=False,isStaticPose=True,
                             session_path = session_path)

        get_syncd_videos(neutral_id,session_path)
    except:
        pass

    # Dynamic
    for dynamic_id in dynamic_ids:
        try:
            get_motion_data(dynamic_id,session_path)
            if downloadVideos:
                download_videos_from_server(session_id,dynamic_id,
                         isCalibration=False,isStaticPose=False,
                         session_path = session_path)

            get_syncd_videos(dynamic_id,session_path)
        except:
            pass
        
    repoDir = os.path.dirname(os.path.abspath(__file__))
    
    # Readme  
    try:        
        pathReadme = os.path.join(repoDir, 'Resources', 'README.txt')
        pathReadmeEnd = os.path.join(session_path, 'README.txt')
        shutil.copy2(pathReadme, pathReadmeEnd)
    except:
        pass
        
    # Geometry
    try:
        if 'Lai' in modelName:
            modelType = 'LaiArnold'
        else:
            raise ValueError("Geometries not available for this model, please contact us")
        if platform.system() == 'Windows':
            geometryDir = os.path.join(repoDir, 'tmp', modelType, 'Geometry')
        else:
            geometryDir = "/tmp/{}/Geometry".format(modelType)
        # If not in cache, download from s3.
        if not os.path.exists(geometryDir):
            os.makedirs(geometryDir, exist_ok=True)
            get_geometries(session_path, modelName=modelName)
        geometryDirEnd = os.path.join(session_path, 'OpenSimData', 'Model', 'Geometry')
        shutil.copytree(geometryDir, geometryDirEnd)
    except:
        pass
    
    # Zip   
    def zipdir(path, ziph):
        # ziph is zipfile handle
        for root, dirs, files in os.walk(path):
            for file in files:
                ziph.write(os.path.join(root, file), 
                           os.path.relpath(os.path.join(root, file), 
                                           os.path.join(path, '..')))    
    session_zip = '{}.zip'.format(session_path)
    if os.path.isfile(session_zip):
        os.remove(session_zip)  
    if zipFolder:
        zipf = zipfile.ZipFile(session_zip, 'w', zipfile.ZIP_DEFLATED)
        zipdir(session_path, zipf)
        zipf.close()
    
    # Write zip as a result to last trial for now
    if writeToDB:
        post_file_to_trial(session_zip,dynamic_ids[-1],tag='session_zip',
                           device_id='all')    