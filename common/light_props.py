import bpy
import math
import os

from bpy.types import Collection
from typing import List


def get_lights():
    """Get all lights in the scene and return a list of dictionaries with the light data."""
    
    lights = list()
    light_objects = list()

    for light in bpy.data.objects:
        if light.type == "LIGHT":
            lights.append(light)


    for i, light in enumerate(lights):
        sce = bpy.context.scene

        light_dict = dict()

        light_dict['type'] = light.data.type
        light_dict['name'] = light.data.name

        if light.data.type == 'POINT':
            light_frame_size = []
            light_frame_2_size = []

            for f in range(sce.frame_start, sce.frame_end + 1):
                sce.frame_set(f)
                light_frame_size.append(light.data.shadow_soft_size)
                light_frame_2_size.append(light.data.cutoff_distance)

            light_dict['size'] = light_frame_size
            light_dict['size_2'] = light_frame_2_size
            
        light_frame_energy = []
        light_color = []
        light_frame_pos = []
        light_frame_rot = []

        for f in range(sce.frame_start, sce.frame_end + 1):
            sce.frame_set(f)
            light_frame_energy.append(light.data.energy)
            light_frame_color = []
            light_frame_color.append(round(light.data.color.r, 2))
            light_frame_color.append(round(light.data.color.g, 2))
            light_frame_color.append(round(light.data.color.b, 2))
            light_color.append(light_frame_color)

            matrix = get_light_matrix(light)
            light_frame_pos.append(matrix['matrix_world'])
            light_frame_rot.append(matrix['matrix_world_rotation'])

        light_dict['color'] = light_color
        light_dict['strength'] = light_frame_energy
        light_dict['matrix_world'] = light_frame_pos
        light_dict['matrix_world_rotation'] = light_frame_rot
        
        light_objects.append(light_dict)


    return light_objects



def get_light_matrix(light_obj):
    d = dict()
    if hasattr(light_obj, "matrix_world"):
        d["matrix_world"] = light_obj.matrix_world.to_translation().copy()        
        d["matrix_world_rotation"] = light_obj.matrix_world.to_quaternion().copy()    
    return d