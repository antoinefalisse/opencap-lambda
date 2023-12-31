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

from flask import Flask, request
from flask_restful import Resource, Api

from utilsKinematics import Kinematics
from utils import download_kinematics


app = Flask(__name__)
api = Api(app)


class Function(Resource):
    def post(self):
        if 'session_id' not in request.json:
            return {'error': '`session_id` is required.'}, 400
        if 'specific_trial_names' not in request.json:
            return {'error': '`specific_trial_names` is required.'}, 400
        
        # %% User inputs.
        # Specify session id; see end of url in app.opencap.ai/session/<session_id>.
        # session_id = "bd61b3a6-813d-411c-8067-92315b3d4e0d"
        session_id = request.json['session_id']
        # Specify trial names in a list; use None to process all trials in a session.
        # specific_trial_names = ['test']
        specific_trial_names = request.json['specific_trial_names']
        data_folder = os.path.join("./Data", session_id)
        # %% Download data.
        trial_names, modelName = download_kinematics(
            session_id, folder=data_folder, trialNames=specific_trial_names
        )
        # %% Process data.
        kinematics, center_of_mass = {}, {}
        center_of_mass['values'] = {}
        for trial_name in trial_names:
            # Create object from class kinematics.
            kinematics[trial_name] = Kinematics(
                data_folder,
                trial_name,
                modelName=modelName,
                lowpass_cutoff_frequency_for_coordinate_values=10
            )    
            # Get center of mass values, speeds, and accelerations.
            center_of_mass['values'][trial_name] = kinematics[trial_name].get_center_of_mass_values(lowpass_cutoff_frequency=10)
            
        max_center_of_mass = np.round(np.max(center_of_mass['values'][trial_names[0]]['y']), 2)
        return {'message': f'Maximal center of mass vertical position: {max_center_of_mass} m'}, 200


api.add_resource(Function, '/2015-03-31/functions/function/invocations')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
