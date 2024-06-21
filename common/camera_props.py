import bpy
import math
import numpy as np

def get_matrix_camera():
    camera = bpy.context.scene.camera
    d = dict()
    if hasattr(camera, "matrix_world"):
        d["matrix_world"] = camera.matrix_world.to_translation().copy()        
        d["matrix_world_rotation"] = camera.matrix_world.to_quaternion().copy()    
    return d

def get_camera():
    """Get all lights in the scene and return a list of dictionaries with the light data."""
    
    camera_dict = dict()
    if bpy.context.scene.camera is not None:
        camera = bpy.data.cameras[bpy.context.scene.camera.data.name]
        sce = bpy.context.scene
        camera_dict['name'] = bpy.context.scene.camera.data.name
        camera_frame_pos = []
        camera_frame_rot = []
        camera_frame_FOV = []

        for f in range(sce.frame_start, sce.frame_end + 1):
            sce.frame_set(f)
            matrix = get_matrix_camera()
            camera_frame_pos.append(matrix['matrix_world'])
            camera_frame_rot.append(matrix['matrix_world_rotation'])
            camera_frame_FOV.append((2*np.arctan((0.5*camera.sensor_width)/camera.lens)*180)/math.pi)
            
            
        camera_dict['FOV'] = camera_frame_FOV
        camera_dict['matrix_world'] = camera_frame_pos
        camera_dict['matrix_world_rotation'] = camera_frame_rot


    return camera_dict

