'''
    ---------------------------------------------------------------------------
    OpenCap processing: example.py
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
import numpy as np
import utilsKinematics
from utils import download_kinematics

# %% User inputs.
# Specify session id; see end of url in app.opencap.ai/session/<session_id>.
session_id = "4d5c3eb1-1a59-4ea1-9178-d3634610561c"

# Specify trial names in a list; use None to process all trials in a session.
specific_trial_names = ['jump']

# Specify where to download the data.
data_folder = os.path.join("./Data", session_id)

# %% Download data.
trial_names = download_kinematics(session_id, folder=data_folder, trialNames=specific_trial_names)

# %% Process data.
kinematics, center_of_mass = {}, {}
center_of_mass['values'] = {}
for trial_name in trial_names:
    # Create object from class kinematics.
    kinematics[trial_name] = utilsKinematics.kinematics(data_folder, trial_name, lowpass_cutoff_frequency_for_coordinate_values=10)    
    # Get center of mass values, speeds, and accelerations.
    center_of_mass['values'][trial_name] = kinematics[trial_name].get_center_of_mass_values(lowpass_cutoff_frequency=10)
    
print('Maximal center of mass vertical position: {} m'.format(np.round(np.max(center_of_mass['values'][trial_names[0]]['y']), 2)))
