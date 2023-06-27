'''
    ---------------------------------------------------------------------------
    OpenCap processing: utilsProcessing.py
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
import logging
import opensim
import numpy as np
from scipy import signal
import matplotlib.pyplot as plt
from utils import storage_to_dataframe

def lowPassFilter(time, data, lowpass_cutoff_frequency, order=4):
    
    fs = 1/np.round(np.mean(np.diff(time)),16)
    wn = lowpass_cutoff_frequency/(fs/2)
    sos = signal.butter(order/2, wn, btype='low', output='sos')
    dataFilt = signal.sosfiltfilt(sos, data, axis=0)

    return dataFilt

# %% Segment squats.
def segmentSquats(ikFilePath, pelvis_ty=None, timeVec=None, visualize=False,
                  filter_pelvis_ty=True, cutoff_frequency=4, height=.2):
    
    # Extract pelvis_ty if not given.
    if pelvis_ty is None and timeVec is None:
        ikResults = storage_to_dataframe(ikFilePath,headers={'pelvis_ty'})
        timeVec = ikResults['time']
        if filter_pelvis_ty:
            from utilsOpenSimAD import filterNumpyArray
            pelvis_ty = filterNumpyArray(
                ikResults['pelvis_ty'].to_numpy(), timeVec.to_numpy(), 
                cutoff_frequency=cutoff_frequency)
        else:
            pelvis_ty = ikResults['pelvis_ty']    
    dt = timeVec[1] - timeVec[0]

    # Identify minimums.
    pelvSignal = np.array(-pelvis_ty - np.min(-pelvis_ty))
    pelvSignalPos = np.array(pelvis_ty - np.min(pelvis_ty))
    idxMinPelvTy,_ = signal.find_peaks(pelvSignal,distance=.7/dt,height=height)
    
    # Find the max adjacent to all of the minimums.
    minIdxOld = 0
    startFinishInds = []
    for i, minIdx in enumerate(idxMinPelvTy):
        if i<len(idxMinPelvTy)-1:
            nextIdx = idxMinPelvTy[i+1]
        else:
            nextIdx = len(pelvSignalPos)
        startIdx = np.argmax(pelvSignalPos[minIdxOld:minIdx]) + minIdxOld
        endIdx = np.argmax(pelvSignalPos[minIdx:nextIdx]) + minIdx
        startFinishInds.append([startIdx,endIdx])
        minIdxOld = np.copy(minIdx)
    startFinishTimes = [timeVec[i].tolist() for i in startFinishInds]
    
    if visualize:
        plt.figure()     
        plt.plot(-pelvSignal)
        for c_v, val in enumerate(startFinishInds):
            plt.plot(val, -pelvSignal[val], marker='o', markerfacecolor='k',
                     markeredgecolor='none', linestyle='none',
                     label='Squatting phase')
            if c_v == 0:
                plt.legend()
        plt.xlabel('Frames')
        plt.ylabel('Position [m]')
        plt.title('Vertical pelvis position')
        plt.draw()
    
    return startFinishTimes

# %% Segment sit-to-stands.
'''
 Three time intervals are returned:
     - risingTimes: rising phase.
     - risingTimesDelayedStart: rising phase from delayed start to exclude
        time interval when there is contact with the chair.
     - risingSittingTimesDelayedStartPeriodicEnd: rising and sitting phases
         from delayed start to corresponding periodic end in terms of
         vertical pelvis position.     
'''
def segmentSTS(ikFilePath, pelvis_ty=None, timeVec=None, velSeated=0.3,
               velStanding=0.15, visualize=False, filter_pelvis_ty=True, 
               cutoff_frequency=4, delay=0.1):
    
    # Extract pelvis_ty if not given.
    if pelvis_ty is None and timeVec is None:
        ikResults = storage_to_dataframe(ikFilePath,headers={'pelvis_ty'})
        timeVec = ikResults['time']
        if filter_pelvis_ty:
            from utilsOpenSimAD import filterNumpyArray
            pelvis_ty = filterNumpyArray(
                ikResults['pelvis_ty'].to_numpy(), timeVec.to_numpy(), 
                cutoff_frequency=cutoff_frequency)
        else:
            pelvis_ty = ikResults['pelvis_ty']
    dt = timeVec[1] - timeVec[0]
    
    # Identify minimum.
    pelvSignal = np.array(pelvis_ty - np.min(pelvis_ty))
    pelvVel = np.diff(pelvSignal,append=0)/dt
    idxMaxPelvTy,_ = signal.find_peaks(pelvSignal,distance=.9/dt,height=.2,
                                prominence=.2)
    
    # Find the max adjacent to all of the minimums.
    maxIdxOld = 0
    startFinishInds = []
    for i, maxIdx in enumerate(idxMaxPelvTy):     
        # Find velocity peak to left of pelv_ty peak.
        vels = pelvVel[maxIdxOld:maxIdx]
        velPeak,peakVals = signal.find_peaks(vels,distance=.9/dt,height=.2) 
        velPeak = velPeak[np.argmax(peakVals['peak_heights'])] + maxIdxOld        
        velsLeftOfPeak = np.flip(pelvVel[maxIdxOld:velPeak])
        velsRightOfPeak = pelvVel[velPeak:]        
        # Trace left off the pelv_ty peak and find first index where
        # velocity<velSeated m/s.
        slowingIndLeft = np.argwhere(velsLeftOfPeak<velSeated)[0]
        startIdx = velPeak - slowingIndLeft
        slowingIndRight = np.argwhere(velsRightOfPeak<velStanding)[0]
        endIdx = velPeak + slowingIndRight
        startFinishInds.append([startIdx[0],endIdx[0]])
        maxIdxOld = np.copy(maxIdx)
    risingTimes = [timeVec[i].tolist() for i in startFinishInds]  
        
    # We add a delay to make sure we do not simulate part of the motion
    # involving chair contact; this is not modeled.        
    sf = 1/np.round(np.mean(np.round(timeVec.to_numpy()[1:] - 
                                     timeVec.to_numpy()[:-1],2)),16)
    startFinishIndsDelay = []
    for i in startFinishInds:
        c_i = []
        for c_j, j in enumerate(i):
            if c_j == 0:
                c_i.append(j + int(delay*sf))
            else:
                c_i.append(j)
        startFinishIndsDelay.append(c_i)
    risingTimesDelayedStart = [
        timeVec[i].tolist() for i in startFinishIndsDelay]
    
    # Segment periodic STS by identifying when the pelvis_ty value from the
    # standing phase best matches that from the sitting phase.
    startFinishIndsDelayPeriodic = []
    for val in startFinishIndsDelay:
        pelvVal_up = pelvSignal[val[0]]
        # Find next index when pelvis_ty is lower than this value.
        val_down = (np.argwhere(pelvSignal[val[0]+1:] < pelvVal_up)[0][0])
        # Add trimmed part.
        val_down += (val[0]+1)
        # Select val_down or val_down-1 based on best match with pelvVal_up.
        if (np.abs(pelvSignal[val_down] - pelvVal_up) > 
            np.abs(pelvSignal[val_down-1] - pelvVal_up)):
            val_down -= 1
        startFinishIndsDelayPeriodic.append([val[0], val_down])
    risingSittingTimesDelayedStartPeriodicEnd = [
        timeVec[i].tolist() for i in startFinishIndsDelayPeriodic]
    
    if visualize:        
        plt.figure()     
        plt.plot(pelvSignal)
        for c_v, val in enumerate(startFinishInds):
            plt.plot(val, pelvSignal[val], marker='o', markerfacecolor='k',
                     markeredgecolor='none', linestyle='none', 
                     label='Rising phase')
            val2 = startFinishIndsDelay[c_v][0]
            plt.plot(val2, pelvSignal[val2], marker='o',
                     markerfacecolor='r', markeredgecolor='none',
                     linestyle='none', label='Delayed start')
            val3 = startFinishIndsDelayPeriodic[c_v][1]
            plt.plot(val3, pelvSignal[val3], marker='o',
                     markerfacecolor='g', markeredgecolor='none',
                     linestyle='none', 
                     label='Periodic end corresponding to delayed start')
            if c_v == 0:
                plt.legend()
        plt.xlabel('Frames')
        plt.ylabel('Position [m]')
        plt.title('Vertical pelvis position')
        plt.tight_layout()
        plt.draw()
    
    return (risingTimes, risingTimesDelayedStart, 
            risingSittingTimesDelayedStartPeriodicEnd)

# %% Generate model with adjusted muscle wrapping to prevent unrealistic
# wrapping giving rise to bad muscle-tendon lengths and moment arms. Changes
# are made for the gmax1, iliacus, and psoas. Changes are documented in
# modelAdjustment.log.
def adjustMuscleWrapping(
        baseDir, dataDir, subject, poseDetector='DefaultPD', 
        cameraSetup='DefaultModel', 
        OpenSimModel="LaiUhlrich2022",
        overwrite=False):
    
    # Paths
    osDir = os.path.join(dataDir, subject, 'OpenSimData')
    pathModelFolder = os.path.join(osDir, 'Model')
    pathUnscaledModel = os.path.join(baseDir, 'OpenSimPipeline', 'Models',
                                     OpenSimModel + '.osim')
    pathScaledModel = os.path.join(pathModelFolder,
                                   OpenSimModel + '_scaled.osim')
    pathOutputModel = os.path.join(pathModelFolder,
                                   OpenSimModel + '_scaled_adjusted.osim')
    
    if overwrite is False and os.path.exists(pathOutputModel):
        return
        
    # Set up logging.
    logPath = os.path.join(pathModelFolder,'modelAdjustment.log')
    if os.path.exists(logPath):
        os.remove(logPath)
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.shutdown()
    logging.basicConfig(filename=logPath,format='%(message)s',
                        level=logging.INFO)
    
    # Load models.
    opensim.Logger.setLevelString('error')
    unscaledModel = opensim.Model(pathUnscaledModel)
    scaledModel = opensim.Model(pathScaledModel)    
    scaledBodySet = scaledModel.getBodySet()
    
    # Poses that often cause problems.
    pose_gmax = [
        [['hip_flexion_r',90],['hip_adduction_r',-26], ['hip_rotation_r',40]]]    
    coord_gmax = 'hip_flexion_r'
    
    # generic model doesn't wrap beyond 32deg abd.
    pose_hipFlexors = [
        [['hip_flexion_r',-30],['hip_adduction_r',-32],['hip_rotation_r',-36]],
        [['hip_flexion_r',-30],['hip_adduction_r',-50],['hip_rotation_r',0]],
        [['hip_flexion_r',-30],['hip_adduction_r',30],['hip_rotation_r',0]]] 
    coord_hipFlexors = 'hip_flexion_r'
    
    # Gmax1 - shrink wrap cyl radius.
    momentArmsGmax_unscaled = getMomentArms(
        unscaledModel,pose_gmax,'glmax1_r',coord_gmax)
    momentArmsGmax_scaled = getMomentArms(
        scaledModel,pose_gmax,'glmax1_r',coord_gmax)    
    # Get wrapping surface.
    pelvis = scaledBodySet.get('pelvis')
    gmaxWrap = opensim.WrapCylinder.safeDownCast(
        pelvis.getWrapObjectSet().get('Gmax1_at_pelvis_r'))
    radius = gmaxWrap.get_radius()
    originalRadius = np.copy(radius)
    
    for iPose,(momentArmGmax_scaled,momentArmGmax_unscaled) in enumerate(zip(momentArmsGmax_scaled,momentArmsGmax_unscaled)): 
        if np.abs(momentArmGmax_scaled) < np.max([0.5* np.abs(momentArmGmax_unscaled), 0.008]): # This constant came from 100 scaled models
            originalBadMomentArm = np.copy(momentArmGmax_scaled)            
            while np.abs(momentArmGmax_scaled) <= np.abs(originalBadMomentArm) and radius > 0.002:
                gmaxWrap.set_radius(radius-0.002) 
                momentArmGmax_scaled = getMomentArms(scaledModel,pose_gmax,'glmax1_r',coord_gmax)[iPose]
                radius = gmaxWrap.get_radius()                
            if radius > 0.5*originalRadius:
                outputStr = '-For pose #{}, scaled gmax1 moment arm was {:.3f}. Unscaled was {:.3f}. Reduced R&L wrap radius from {:.3f} to {:.3f}, which increased the moment arm back to {:.3f}.'.format(
                              iPose, originalBadMomentArm,momentArmGmax_unscaled,
                              originalRadius,radius,momentArmGmax_scaled)
                print(outputStr)
                logging.info(outputStr)
                # Set the left side as well.
                opensim.WrapCylinder.safeDownCast(pelvis.getWrapObjectSet().get('Gmax1_at_pelvis_l')).set_radius(radius)        
            else:
                outputStr = '-For pose #{}, couldn''t restore glmax1 moment arm by shrinking radius by 1/2. Model unchanged.'.format(iPose)
                print(outputStr)
                logging.info(outputStr)
                gmaxWrap.set_radius(float(originalRadius))        
            scaledModel.initSystem()       
        else:
            outputStr = '-For pose #{}, scaled gmax1 moment arm was {:.3f}. Unscaled was {:.3f}. No adjustements made.'.format(
                         iPose,np.abs(momentArmGmax_scaled),np.abs(momentArmGmax_unscaled))
            print(outputStr)
            logging.info(outputStr)
    
    # Iliacus - change path points to engage wrap cylinder.
    momentArms_unscaled = getMomentArms(
        unscaledModel,pose_hipFlexors,'iliacus_r',coord_hipFlexors)
    momentArms_scaled = getMomentArms(
        scaledModel,pose_hipFlexors,'iliacus_r',coord_hipFlexors)    
    # Get path point locations.
    muscle = scaledModel.getMuscles().get('iliacus_r')
    pathPoints = muscle.get_GeometryPath().getPathPointSet()
    point1 = opensim.PathPoint.safeDownCast(pathPoints.get(1))
    loc1Vec = point1.get_location()
    point2 = opensim.PathPoint.safeDownCast(pathPoints.get(2))
    loc2Vec = point2.get_location()    
    original_loc1 = [loc1Vec[i] for i in range(3)]
    original_loc2 = [loc2Vec[i] for i in range(3)]
    # Get wrap cyl.        
    wrapCyl = opensim.WrapCylinder.safeDownCast(
        pelvis.getWrapObjectSet().get('IL_at_brim_r'))
    radius = wrapCyl.get_radius()
    originalRadius = np.copy(radius)
    previousRadius = np.copy(radius)
    
    for iPose,(momentArm_scaled,momentArm_unscaled) in enumerate(zip(momentArms_scaled,momentArms_unscaled)):
        if np.abs(momentArm_scaled) < np.max([0.7* np.abs(momentArm_unscaled) , 0.015]):             
            # Get path point locations.
            muscle = scaledModel.getMuscles().get('iliacus_r')
            pathPoints = muscle.get_GeometryPath().getPathPointSet()
            point1 = opensim.PathPoint.safeDownCast(pathPoints.get(1))
            loc1Vec = point1.get_location()
            point2 = opensim.PathPoint.safeDownCast(pathPoints.get(2))
            loc2Vec = point2.get_location()            
            originalBadMomentArm = np.copy(momentArm_scaled)                           
            while np.abs(momentArm_scaled) <= np.max([0.7* np.abs(momentArm_unscaled) , 0.015]) and (np.abs(loc1Vec[0]-original_loc1[0]) < 0.015 and np.abs(loc2Vec[1]-original_loc2[1]) <0.015):
                loc1Vec[0] += 0.002 # Move the 1st (pelvis) path point forward
                loc2Vec[1] -= 0.002 # move the 2nd (femur) path point down
                point1.set_location(loc1Vec)
                point2.set_location(loc2Vec)        
                momentArm_scaled = getMomentArms(scaledModel,pose_hipFlexors,'iliacus_r',coord_hipFlexors)[iPose]          
            while np.abs(momentArm_scaled) <= np.max([0.7* np.abs(momentArm_unscaled) , 0.015]) and radius>0.7*originalRadius: # above approach did not succeed, drop the cyl radius some
                wrapCyl.set_radius(radius-0.002) 
                momentArm_scaled = getMomentArms(scaledModel,pose_hipFlexors,'iliacus_r',coord_hipFlexors)[iPose]
                pelvis = scaledBodySet.get('pelvis')
                radius = wrapCyl.get_radius()
            if np.abs(momentArm_scaled) > np.max([0.7* np.abs(momentArm_unscaled) , 0.015]): # succeeded
                # Set the left side as well.
                muscle = scaledModel.getMuscles().get('iliacus_l')
                pathPoints = muscle.get_GeometryPath().getPathPointSet()        
                point1 = opensim.PathPoint.safeDownCast(pathPoints.get(1))
                loc1Vec_l = point1.get_location()
                loc1Vec_l[0] = loc1Vec[0]
                point1.set_location(loc1Vec_l)                
                point2 = opensim.PathPoint.safeDownCast(pathPoints.get(2))
                loc2Vec_l = point2.get_location()
                loc2Vec_l[1] = loc2Vec[1]
                point2.set_location(loc2Vec_l)                
                if radius<previousRadius:
                    radiusStr = ', and after moving points by 1.5±0.2cm wasn''t enough, reduced R&L iliacus wrap radius from {:.3f} to {:.3f}'.format(
                    originalRadius,radius)
                    # set the left side as well.
                    opensim.WrapCylinder.safeDownCast(pelvis.getWrapObjectSet().get('IL_at_brim_l')).set_radius(radius)
                else:
                    radiusStr = ''
                previousRadius = np.copy(radius)    
                outputStr = '-For pose #{}, moved iliacus pelvis path point xpos forward from {:.3f} to {:.3f}, and femur iliacus path point ypos down from {:.3f} to {:.3f}'.format(
                    iPose,original_loc1[0],loc1Vec[0],original_loc2[1],loc2Vec[1]) + radiusStr + '. Restored moment arm from {:.3f} to {:.3f}.'.format(
                      originalBadMomentArm,momentArm_scaled)
                print(outputStr)
                logging.info(outputStr)
            else:
                outputStr = '-For pose #{}, couldn''t restore iliacus moment arm by moving path points by 2cm. Model unchanged.'.format(iPose)
                print(outputStr)
                logging.info(outputStr)                
                point1.set_location(original_loc1)
                point2.set_location(original_loc2)            
            scaledModel.initSystem()
        else:
            outputStr = '-For pose #{}, scaled iliacus moment arm was {:.3f}. Unscaled was {:.3f}. No adjustements made.'.format(
                  iPose,np.abs(momentArm_scaled),np.abs(momentArm_unscaled))
            print(outputStr)
            logging.info(outputStr)
    
    # Psoas - change path points to engage wrap cylinder.
    momentArms_unscaled = getMomentArms(
        unscaledModel,pose_hipFlexors,'psoas_r',coord_hipFlexors)
    momentArms_scaled = getMomentArms(
        scaledModel,pose_hipFlexors,'psoas_r',coord_hipFlexors)    
    # Get path point locations 
    muscle = scaledModel.getMuscles().get('psoas_r')
    pathPoints = muscle.get_GeometryPath().getPathPointSet()
    point1 = opensim.PathPoint.safeDownCast(pathPoints.get(1))
    loc1Vec = point1.get_location()
    point2 = opensim.PathPoint.safeDownCast(pathPoints.get(2))
    loc2Vec = point2.get_location()    
    original_loc1 = [loc1Vec[i] for i in range(3)]
    original_loc2 = [loc2Vec[i] for i in range(3)]
    # Get wrap cyl         
    wrapCyl = opensim.WrapCylinder.safeDownCast(
        pelvis.getWrapObjectSet().get('PS_at_brim_r'))
    radius = wrapCyl.get_radius()
    originalRadius = np.copy(radius)
    previousRadius = np.copy(radius)
    
    for iPose,(momentArm_scaled,momentArm_unscaled) in enumerate(zip(momentArms_scaled,momentArms_unscaled)):
        if np.abs(momentArm_scaled) < np.max([0.7* np.abs(momentArm_unscaled), 0.015]):            
            # Get path point locations.
            muscle = scaledModel.getMuscles().get('psoas_r')
            pathPoints = muscle.get_GeometryPath().getPathPointSet()
            point1 = opensim.PathPoint.safeDownCast(pathPoints.get(1))
            loc1Vec = point1.get_location()
            point2 = opensim.PathPoint.safeDownCast(pathPoints.get(2))
            loc2Vec = point2.get_location()
            originalBadMomentArm = np.copy(momentArm_scaled)               
            while np.abs(momentArm_scaled) <= np.max([0.7* np.abs(momentArm_unscaled), 0.015]) and (np.abs(loc1Vec[0]-original_loc1[0]) < 0.015 and np.abs(loc2Vec[1]-original_loc2[1]) < 0.015):
                loc1Vec[0] += 0.002 # Move the 1st (pelvis) path point forward
                loc2Vec[1] -= 0.002 # move the 2nd (femur) path point down
                point1.set_location(loc1Vec)
                point2.set_location(loc2Vec)        
                momentArm_scaled = getMomentArms(scaledModel,pose_hipFlexors,'psoas_r',coord_hipFlexors)[iPose]            
            while np.abs(momentArm_scaled) <= np.max([0.7* np.abs(momentArm_unscaled) , 0.015]) and radius>0.7*originalRadius: #above approach did not succeed, drop the cyl radius some
                wrapCyl.set_radius(radius-0.002) 
                momentArm_scaled = getMomentArms(scaledModel,pose_hipFlexors,'psoas_r',coord_hipFlexors)[iPose]
                pelvis = scaledBodySet.get('pelvis')
                radius = wrapCyl.get_radius()
            if np.abs(momentArm_scaled) > np.max([0.7* np.abs(momentArm_unscaled) , 0.015]): # succeeded
                # set the left side as well.
                muscle = scaledModel.getMuscles().get('psoas_l')
                pathPoints = muscle.get_GeometryPath().getPathPointSet()        
                point1 = opensim.PathPoint.safeDownCast(pathPoints.get(1))
                loc1Vec_l = point1.get_location()
                loc1Vec_l[0] = loc1Vec[0]
                point1.set_location(loc1Vec_l)
                point2 = opensim.PathPoint.safeDownCast(pathPoints.get(2))
                loc2Vec_l = point2.get_location()
                loc2Vec_l[1] = loc2Vec[1]
                point2.set_location(loc2Vec_l)
                if radius<previousRadius:
                    radiusStr = ', and after moving points by 1.5±0.2cm wasn''t enough, reduced R&L psoas wrap radius from {:.3f} to {:.3f}'.format(
                    originalRadius,radius)
                    # set the left side as well.
                    opensim.WrapCylinder.safeDownCast(pelvis.getWrapObjectSet().get('PS_at_brim_l')).set_radius(radius)
                else:
                    radiusStr = ''
                previousRadius = np.copy(radius)   
                outputStr = '-For pose #{}, moved psoas pelvis path point xpos forward from {:.3f} to {:.3f}, and femur psoas path point ypos down from {:.3f} to {:.3f}'.format(
                    iPose,original_loc1[0],loc1Vec[0],original_loc2[1],loc2Vec[1]) + radiusStr + '. Restored moment arm from {:.3f} to {:.3f}.'.format(
                      originalBadMomentArm,momentArm_scaled)
                print(outputStr)
                logging.info(outputStr)                   
            else:
                outputStr = '-For pose #{}, couldn''t restore psoas moment arm by moving path points by 2cm. Model unchanged.'.format(iPose)
                print(outputStr)
                logging.info(outputStr)                
                point1.set_location(opensim.Vec3(original_loc1))
                point2.set_location(opensim.Vec3(original_loc2))          
            scaledModel.initSystem()           
        else:
            outputStr = '-For pose #{}, scaled psoas moment arm was {:.3f}. Unscaled was {:.3f}. No adjustements made.'.format(
                  iPose,np.abs(momentArm_scaled),np.abs(momentArm_unscaled))
            print(outputStr)
            logging.info(outputStr)
    
    scaledModel.printToXML(pathOutputModel)
    logging.shutdown()
    
# %% Pose the models and get moment arms.
def getMomentArms(model, poses, muscleName, coordinateForMomentArm):
    state = model.initSystem()
    coords = model.getCoordinateSet()
    muscleSet = model.getMuscles()
    coordForMA = coords.get(coordinateForMomentArm)
    momentArms = []
    for i, pose in enumerate(poses):        
        for coordVal in pose:
            coords.get(coordVal[0]).setValue(state,np.deg2rad(coordVal[1]))
        momentArms.append(
            muscleSet.get(muscleName).computeMomentArm(state,coordForMA))
        
    return momentArms

# %% Generate model with contacts.
def generateModelWithContacts(
        dataDir, subject, poseDetector='DefaultPD', cameraSetup='DefaultModel',
        OpenSimModel="LaiUhlrich2022",
        setPatellaMasstoZero=True, overwrite=False):
    
    # %% Process settings.
    osDir = os.path.join(dataDir, subject, 'OpenSimData')
    # pathModelFolder = os.path.join(osDir, poseDetector, cameraSetup, 'Model')
    pathModelFolder = os.path.join(osDir, 'Model')
    suffix_MA = '_adjusted'
    outputModelFileName = (OpenSimModel + "_scaled" + suffix_MA)
    pathOutputFiles = os.path.join(pathModelFolder, outputModelFileName)
    pathOutputModel = pathOutputFiles + "_contacts.osim"
    
    if overwrite is False and os.path.exists(pathOutputModel):
        return
        
    # %% Add contact spheres to the scaled model.
    # The parameters of the foot-ground contacts are based on previous work. We
    # scale the contact sphere locations based on foot dimensions.
    reference_contact_spheres = {
        "s1_r": {"radius": 0.032, "location": np.array([0.0019011578840796601,   -0.01,  -0.00382630379623308]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_r"},
        "s2_r": {"radius": 0.032, "location": np.array([0.14838639994206301,     -0.01,  -0.028713422052654002]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_r"},
        "s3_r": {"radius": 0.032, "location": np.array([0.13300117060705099,     -0.01,  0.051636247344956601]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_r"},
        "s4_r": {"radius": 0.032, "location": np.array([0.066234666199163503,    -0.01,  0.026364160674169801]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_r"},
        "s5_r": {"radius": 0.032, "location": np.array([0.059999999999999998,    -0.01,  -0.018760308461917698]), "orientation": np.array([0, 0, 0]), "socket_frame": "toes_r" },
        "s6_r": {"radius": 0.032, "location": np.array([0.044999999999999998,    -0.01,  0.061856956754965199]), "orientation": np.array([0, 0, 0]), "socket_frame": "toes_r" },
        "s1_l": {"radius": 0.032, "location": np.array([0.0019011578840796601,   -0.01,  0.00382630379623308]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_l"},
        "s2_l": {"radius": 0.032, "location": np.array([0.14838639994206301,     -0.01,  0.028713422052654002]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_l"},
        "s3_l": {"radius": 0.032, "location": np.array([0.13300117060705099,     -0.01,  -0.051636247344956601]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_l"},
        "s4_l": {"radius": 0.032, "location": np.array([0.066234666199163503,    -0.01,  -0.026364160674169801]), "orientation": np.array([0, 0, 0]), "socket_frame": "calcn_l"},
        "s5_l": {"radius": 0.032, "location": np.array([0.059999999999999998,    -0.01,  0.018760308461917698]), "orientation": np.array([0, 0, 0]), "socket_frame": "toes_l" },
        "s6_l": {"radius": 0.032, "location": np.array([0.044999999999999998,    -0.01,  -0.061856956754965199]), "orientation": np.array([0, 0, 0]), "socket_frame": "toes_l" }}      
    reference_scale_factors = {"calcn_r": np.array([0.91392399999999996, 0.91392399999999996, 0.91392399999999996]),
                               "toes_r":  np.array([0.91392399999999996, 0.91392399999999996, 0.91392399999999996]),
                               "calcn_l": np.array([0.91392399999999996, 0.91392399999999996, 0.91392399999999996]),
                               "toes_l":  np.array([0.91392399999999996, 0.91392399999999996, 0.91392399999999996])}
    reference_contact_half_space = {"name": "floor", "location": np.array([0, 0, 0]),"orientation": np.array([0, 0, -np.pi/2]), "frame": "ground"}
    stiffness = 1000000
    dissipation = 2.0
    static_friction = 0.8
    dynamic_friction = 0.8
    viscous_friction = 0.5
    transition_velocity = 0.2
    
    # Add contact spheres and SmoothSphereHalfSpaceForces.
    opensim.Logger.setLevelString('error')
    model = opensim.Model(pathOutputFiles + ".osim")   
    bodySet = model.get_BodySet()
    
    # ContactHalfSpace.
    if reference_contact_half_space["frame"] == "ground":
        contact_half_space_frame = model.get_ground()
    else:
        raise ValueError('Not yet supported.')    
    contactHalfSpace = opensim.ContactHalfSpace(
        opensim.Vec3(reference_contact_half_space["location"]),
        opensim.Vec3(reference_contact_half_space["orientation"]),
        contact_half_space_frame, reference_contact_half_space["name"])
    contactHalfSpace.connectSocket_frame(contact_half_space_frame)
    model.addContactGeometry(contactHalfSpace)
    
    # ContactSpheres and SmoothSphereHalfSpaceForces.
    for ref_contact_sphere in reference_contact_spheres:    
        # ContactSpheres.
        body = bodySet.get(reference_contact_spheres[ref_contact_sphere]["socket_frame"])
        # Scale location based on attached_geometry scale_factors.      
        # We don't scale the y_position.
        attached_geometry = body.get_attached_geometry(0)
        c_scale_factors = attached_geometry.get_scale_factors().to_numpy() 
        c_ref_scale_factors = reference_scale_factors[reference_contact_spheres[ref_contact_sphere]["socket_frame"]]
        scale_factors = c_ref_scale_factors / c_scale_factors        
        scale_factors[1] = 1        
        scaled_location = reference_contact_spheres[ref_contact_sphere]["location"] / scale_factors
        c_contactSphere = opensim.ContactSphere(
            reference_contact_spheres[ref_contact_sphere]["radius"],
            opensim.Vec3(scaled_location), body, ref_contact_sphere)
        c_contactSphere.connectSocket_frame(body)
        model.addContactGeometry(c_contactSphere)
        
        # SmoothSphereHalfSpaceForces.
        SmoothSphereHalfSpaceForce = opensim.SmoothSphereHalfSpaceForce(
            "SmoothSphereHalfSpaceForce_" + ref_contact_sphere, 
            c_contactSphere, contactHalfSpace)
        SmoothSphereHalfSpaceForce.set_stiffness(stiffness)
        SmoothSphereHalfSpaceForce.set_dissipation(dissipation)
        SmoothSphereHalfSpaceForce.set_static_friction(static_friction)
        SmoothSphereHalfSpaceForce.set_dynamic_friction(dynamic_friction)
        SmoothSphereHalfSpaceForce.set_viscous_friction(viscous_friction)
        SmoothSphereHalfSpaceForce.set_transition_velocity(transition_velocity)        
        SmoothSphereHalfSpaceForce.connectSocket_half_space(contactHalfSpace)
        SmoothSphereHalfSpaceForce.connectSocket_sphere(c_contactSphere)
        model.addForce(SmoothSphereHalfSpaceForce)
    
    # We do not use the patella in the dynamic simulations. The reason is that
    # the patella only matters for the muscle-tendon lengths and moment arms,
    # but since we approximate those with polynomials, the patella is useless.
    # We therefore remove it, since otherwise we would have to deal with
    # kinematic constraints that would make things unecessarily complicated.
    # We remove it when building the external function, and here we set its
    # mass to zero such that we can make an apple-to-apple comparison when
    # checking that the outputs from the external function match the results
    # from ID ran with the model (with a mass set to 0, the patella will not
    # influence ID).
    if setPatellaMasstoZero:
        for i in range(bodySet.getSize()):        
            c_body = bodySet.get(i)
            c_body_name = c_body.getName()            
            if (c_body_name == 'patella_l' or c_body_name == 'patella_r'):
                c_body.set_mass(0.)
                c_body.set_inertia(opensim.Vec6(0))
        
    model.finalizeConnections
    model.initSystem()
    model.printToXML(pathOutputModel)

