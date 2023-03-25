import bpy
import math
import os

from bpy.types import Collection
from typing import List


def get_lights():
    """
    Get all lights in the scene and return a list of dictionaries with the light data.
    """
    
    light_objects: List = list()

    for i, light in enumerate(bpy.data.lights):
        objects = bpy.context.scene.objects.keys()
        sce = bpy.context.scene

        if light.name in objects:
            light_dict = dict()

            light_dict['type'] = light.type
            light_dict['name'] = light.name
   
            if light.type == 'POINT':
                light_frame_size = []
                light_frame_2_size = []

                for f in range(sce.frame_start, sce.frame_end + 1):
                    sce.frame_set(f)
                    light_frame_size.append(light.shadow_soft_size)
                    light_frame_2_size.append(light.cutoff_distance)

                light_dict['size'] = light_frame_size
                light_dict['size_2'] = light_frame_2_size
                
            light_frame_energy = []
            light_color = []
            light_frame_pos = []
            light_frame_rot = []

            for f in range(sce.frame_start, sce.frame_end + 1):
                sce.frame_set(f)
                light_frame_energy.append(light.energy)
                light_frame_color = []
                light_frame_color.append(round(light.color.r, 2))
                light_frame_color.append(round(light.color.g, 2))
                light_frame_color.append(round(light.color.b, 2))
                light_color.append(light_frame_color)

                matrix = get_lights_matrix(bpy.context.scene)
                light_frame_pos.append(matrix[i]['matrix_world'])
                light_frame_rot.append(matrix[i]['matrix_world_rotation'])
    
            light_dict['color'] = light_color
            light_dict['strength'] = light_frame_energy
            light_dict['matrix_world'] = light_frame_pos
            light_dict['matrix_world_rotation'] = light_frame_rot
            
            light_objects.append(light_dict)


    return light_objects


def get_lights_matrix(col):
    if not hasattr(col, "objects"):
        return []

    def to_dict(light):
        d = dict()
        if hasattr(light, "matrix_world"):
            d["matrix_world"] = light.matrix_world.to_translation().copy()        
            d["matrix_world_rotation"] = light.matrix_world.to_quaternion().copy()    
        return d

    return [to_dict(o) for o in col.objects if o.type == 'LIGHT']
