import os
import sys
import bpy
import json
from time import time
from typing import List, Dict
from bpy.types import Armature, Bone
from mathutils import Quaternion, Euler, Vector

directory, filename = os.path.split(os.path.abspath(bpy.context.space_data.text.filepath))
sys.path.append(directory)

from br.br_anm import *
from br.br_camera import Camera
from br.br_lightdirc import LightDirc
from br.br_lightpoint import LightPoint
from br.br_ambient import Ambient

from common.bone_props import *
from common.armature_props import AnmArmature
from common.light_props import get_lights
from common.coordinate_converter import *
from common.helpers import *


is_looped = False # Set to true if your animation should be looped
lightpoint_index = -1

def camera_exists() -> bool:
	""" Return True if Camera exists AND has animation data, and False otherwise."""
	cam = bpy.context.scene.camera

	if cam and cam.animation_data: 
		return True
	else: 
		return False

def light_exists() -> bool:
	"""Returns True if a lightDirc or lightPoint or Ambient object exists, and False otherwise."""
	lights = get_lights()

	for light in lights:
		if light['type'] == "SUN" or light['type'] == "POINT" or light['type'] == "AREA":
			return True
	return False

def get_anm_armatures() -> List[Armature]:
	"""
	Return list of armatures that contain animation data.
	"""
	anm_armatures: List[Armature] = list()

	for obj in bpy.context.selected_objects:
		if obj.type == "ARMATURE":
			armature_obj = bpy.data.objects[obj.name]

			if armature_obj.animation_data:
				anm_armatures.append(armature_obj)

	return anm_armatures

# Animated armature objects which are special objects with .anm properties
animated_armatures = list(map(lambda x: AnmArmature(x), get_anm_armatures()))

def make_mapping_reference(types=False) -> List[str]:
	"""
	Create ExtraMapping Reference list of clump, coord, material, model names for all animated armatures.
	"""
	extra_mapping_reference: List[str] = list()
	extra_mapping_reference_types: List[str] = list()
	
	if types:
		for armature_obj in animated_armatures:
			bones = list(map(lambda x: x + 'nuccChunkCoord', armature_obj.bones))
			materials = list(map(lambda x: x + 'nuccChunkMaterial', armature_obj.materials))
			models = list(map(lambda x: x + 'nuccChunkModel', armature_obj.models))

			extra_mapping_reference_types.extend([armature_obj.models[0] + 'nuccChunkClump', *bones, *materials, *models])
		
		return extra_mapping_reference_types
		
	else:
		for armature_obj in animated_armatures:
			extra_mapping_reference.extend([armature_obj.models[0], *armature_obj.bones, *armature_obj.materials, *armature_obj.models])

		return extra_mapping_reference
		

# Create ExtraMapping Reference list of clump, coord, material, model names for all animated armatures. 
extra_mapping_reference: List[str] = make_mapping_reference()
extra_mapping_reference_types: List[str] = make_mapping_reference(types=True) # With types


def make_clump(armature: AnmArmature, clump_index: int) -> Clump:
	"""
	Create clump struct based on armatures index and bone / model indices.
	"""

	# Get bone material indices from extra mapping reference
	bone_material_indices: List[int]
	model_indices: List[int]

	bones = list(map(lambda x: x + 'nuccChunkCoord', armature.bones))
	materials = list(map(lambda x: x + 'nuccChunkMaterial', armature.materials))
	
	bone_material_map = [*bones, *materials]
	model_map = list(map(lambda x: x + 'nuccChunkModel', armature.models))

	bone_material_indices = [extra_mapping_reference_types.index(bone_material) for bone_material in bone_material_map]
	model_indices = [extra_mapping_reference_types.index(model) for model in model_map]

	clump = Clump(
				clump_index, 
				len(bone_material_indices), 
				len(model_indices), 
				bone_material_indices, 
				model_indices)

	return clump


def make_clumps() -> List[Clump]:
	"""
	Create multiple clump structs based on the animated armatures present.
	"""
	clumps: List[Clump] = list()

	for armature_obj in animated_armatures:
		# Create clump struct and add to list
		clump_index = extra_mapping_reference.index(armature_obj.models[0])
		clump = make_clump(armature_obj, clump_index)
		clumps.append(clump)

	return clumps


def make_coord_parent() -> CoordParent:
	"""
	Create coord parent structs for all animated armatures.
	"""
	anm_coords: List[AnmCoord] = list()

	for index, armature_obj in enumerate(animated_armatures):
		children: List[Bone] = [bone for bone in armature_obj.armature.data.bones if bone.parent] # List of child bones

		for bone in children:
			parent = AnmCoord(index, armature_obj.bones.index(bone.parent.name))
			child = AnmCoord(index, armature_obj.bones.index(bone.name))
			anm_coords.extend([parent, child])

	return CoordParent(anm_coords)


def add_curve(curve_format: AnmCurveFormat, curve_index: int, curve_size: int, frame_count: int, values: List, curve_headers: List[CurveHeader], curves: List[Curve]):
	"""
	Add curve to curve_headers and curves list.
	"""
	curve = Curve(curve_format, values)
	curves.append(curve)
	curve_header = CurveHeader(curve_index, curve_format.value, frame_count, curve_size)
	curve_headers.append(curve_header)

def make_entry_light(light_index: int) -> Entry:
	"""
	Make .anm Entry struct for lightPoint and LightDirc object.. 
	"""
	curve_headers: List[CurveHeader] = list()
	curves: List[Curve] = list()

	light = get_lights()[light_index]

	light_type = light['type']
	light_color_values = light['color']
	light_strength_values = light['strength']
	light_pos_values = light['matrix_world']
	light_rot_values = light['matrix_world_rotation']
	

	if (light_type == "POINT"):
		light_radius_1_values = light['size']
		light_radius_2_values = light['size_2']

		# Combine the color, strength, and rotation values into one list so we can use an index to create the curves
		light_values = {
			'color': light_color_values,
			'strength': light_strength_values,
			'position': light_pos_values,
			'radius_1': light_radius_1_values,
			'radius_2': light_radius_2_values
		}

		# Create curves for each value
		for index, (key, values) in enumerate(light_values.items()):
			if key == 'color':
				converted_values = [[value * 255 for value in sublist] for sublist in light_values[key]]
				chained_values = chain_list(converted_values)
				frame_count = len(converted_values)

				if len(converted_values) % 4 != 0:
					# Pad the list with the last value so the length is a multiple of 4
					chained_values += converted_values[-1] * (4 - len(converted_values) % 4)
					frame_count = len(converted_values) + (4 - len(converted_values) % 4)
				add_curve(AnmCurveFormat.BYTE3, index, 24, frame_count, chained_values, curve_headers, curves)
			
			if key == 'strength':
				converted_values = convert_light_values('light_strength', light_values[key])
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 4, len(converted_values), converted_values, curve_headers, curves)
			
			if key == 'position':
				keyframe_vec3 = dict()
				converted_values = convert_light_values('light_pos', light_pos_values)

				if len(light_pos_values) > 1:
					for frame, value in enumerate(converted_values):
						keyframe_vec3[frame * 100] = value

					keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key

					frame_count = len(light_pos_values) + 1
					add_curve(AnmCurveFormat.INT1_FLOAT3, index, 24, frame_count, keyframe_vec3, curve_headers, curves)
			
			if key == 'radius_1':
				converted_values = convert_light_values('light_radius', light_radius_1_values)
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)

			if key == 'radius_2':
				converted_values = convert_light_values('light_radius', light_radius_2_values)
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)

		# Create the entry
		clump_index = -1
		coord_index = light_index
		entry_format = EntryFormat.LIGHTPOINT # LightPoint
		curve_count = len(curve_headers)

		entry = Entry(clump_index, coord_index, entry_format, curve_count, curve_headers, curves)

		
	if (light_type == "SUN"):
		# Combine the color, strength, and rotation values into one list so we can use an index to create the curves
		light_values = {
			'color': light_color_values,
			'strength': light_strength_values,
			'rotation': light_rot_values
		}

		# Create the curves
		for index, (key, values) in enumerate(light_values.items()):
			if key == 'color':
				converted_values = [[value * 255 for value in sublist] for sublist in light_values[key]]
				chained_values = chain_list(converted_values)
				frame_count = len(converted_values)

				if len(converted_values) % 4 != 0:
					# Pad the list with the last value so the length is a multiple of 4
					chained_values += converted_values[-1] * (4 - len(converted_values) % 4)
					frame_count = len(converted_values) + (4 - len(converted_values) % 4)
				add_curve(AnmCurveFormat.BYTE3, index, 24, frame_count, chained_values, curve_headers, curves)

			if key == 'strength':
				converted_values = convert_light_values('light_strength', light_values[key])
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)
			
			if key == 'rotation':
				if len(light_values[key]) < 2:
					converted_values = convert_light_values('light_rot_euler', light_values[key])
					frame_count = len(converted_values)
					add_curve(AnmCurveFormat.FLOAT3ALT, index, 24, frame_count, converted_values, curve_headers, curves)
				else:
					converted_values = convert_light_values('light_rot', light_values[key])
					frame_count = len(converted_values)
					add_curve(AnmCurveFormat.SHORT4, index, 24, frame_count, converted_values, curve_headers, curves)

		# Create the entry
		clump_index = -1
		coord_index = light_index
		entry_format = EntryFormat.LIGHTDIRECTION
		curve_count = len(curve_headers)

		entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	if (light_type == "AREA"):
		# Combine the color, strength, and rotation values into one list so we can use an index to create the curves
		light_values = {
			'color': light_color_values,
			'strength': light_strength_values
		}

		# Create the curves
		for index, (key, values) in enumerate(light_values.items()):
			if key == 'color':
				converted_values = [[value * 255 for value in sublist] for sublist in light_values[key]]
				chained_values = chain_list(converted_values)
				frame_count = len(converted_values)

				if len(converted_values) % 4 != 0:
					# Pad the list with the last value so the length is a multiple of 4
					chained_values += converted_values[-1] * (4 - len(converted_values) % 4)
					frame_count = len(converted_values) + (4 - len(converted_values) % 4)
				add_curve(AnmCurveFormat.BYTE3, index, 24, frame_count, chained_values, curve_headers, curves)

			if key == 'strength':
				converted_values = convert_light_values('light_strength', light_values[key])
				frame_count = len(converted_values)
				add_curve(AnmCurveFormat.FLOAT1ALT, index, 24, frame_count, converted_values, curve_headers, curves)

		# Create the entry
		clump_index = -1
		coord_index = light_index
		entry_format = EntryFormat.AMBIENT
		curve_count = len(curve_headers)

		entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	return entry


def make_entry_camera() -> Entry:
	"""
	Make .anm Entry struct for camera object. An entry is equivalent to an Action Group in Blender. 
	"""
	curve_headers: List[CurveHeader] = list()
	curves: List[Curve] = list()

	action_cam = bpy.context.scene.camera.animation_data.action
	group_cam = action_cam.groups.get("Action Bake")
	fcurves_cam = group_cam.channels

	data_paths = dict()
	channel_count = len(fcurves_cam)
	channel_values = list()

	loc, rot, sca = bpy.context.scene.camera.matrix_world.decompose()
	
	for i in range(channel_count):
		path = fcurves_cam[i].data_path.rpartition('.')[2]
		keyframes = [int(k) for k in range(len(fcurves_cam[i].keyframe_points))]
		data_paths[path] = len(keyframes) # Add keyframe count

		channel_values.append(list(map(lambda key: fcurves_cam[i].evaluate(key), keyframes)))

	for data_path, keyframe_count in data_paths.items():
		if data_path == 'location':
				keyframe_vec3 = dict()

				values = list(
						map(lambda x, y, z: Vector((x, y, z)), 
						channel_values[0], 
						channel_values[1], 
						channel_values[2]))

				converted_values = convert_to_anm_values('location_camera', values, loc, rot, sca)
				
				if keyframe_count > 1:
					for frame, value in enumerate(converted_values):
						keyframe_vec3[frame * 100] = value
			
					keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
					add_curve(AnmCurveFormat.INT1_FLOAT3, list(data_paths).index(data_path), 12, keyframe_count + 1, keyframe_vec3, curve_headers, curves)
					
				else:
					add_curve(AnmCurveFormat.FLOAT3, list(data_paths).index(data_path), 12, keyframe_count, converted_values, curve_headers, curves)
					
		if data_path == 'rotation_euler':
			if keyframe_count < 2:
				values = list(
					map(lambda x, y, z: Euler(Vector((x, y, z))), 
					channel_values[3], 
					channel_values[4], 
					channel_values[5]))

				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)
				add_curve(AnmCurveFormat.FLOAT3ALT, list(data_paths).index(data_path), 24, len(converted_values), converted_values, curve_headers, curves)

			else:
				quaternion_values = list(map(lambda x: x.to_quaternion(), values))
				converted_values = convert_to_anm_values('rotation_quaternion', quaternion_values, loc, rot, sca)
				add_curve(AnmCurveFormat.SHORT4, list(data_paths).index(data_path), 24, len(converted_values), converted_values, curve_headers, curves)

		if data_path == 'rotation_quaternion':
				values = list(
						map(lambda w, x, y, z: Quaternion((w, x, y, z)), 
						channel_values[3], 
						channel_values[4], 
						channel_values[5], 
						channel_values[6])) 

				converted_values = convert_to_anm_values('rotation_quaternion_camera', values, loc, rot, sca)

				if keyframe_count > 1:
					add_curve(AnmCurveFormat.SHORT4, list(data_paths).index(data_path), 36, len(converted_values), converted_values, curve_headers, curves)
				else:
					euler_values = list(map(lambda x: x.to_euler(), values))
					converted_values = convert_to_anm_values('rotation_quaternion_euler', euler_values, loc, rot, sca)
					add_curve(AnmCurveFormat.FLOAT3ALT, list(data_paths).index(data_path), 24, len(converted_values), converted_values, curve_headers, curves)

	# Add FOV
	keyframe_vec3 = dict()
	values = list()

	for _ in range(keyframe_count):
		values.append(45)
	
	if keyframe_count > 1:
		for frame, value in enumerate(values):
			keyframe_vec3[frame * 100] = value

		keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
		add_curve(AnmCurveFormat.INT1_FLOAT1, 2, 12, keyframe_count + 1, keyframe_vec3, curve_headers, curves)

	clump_index = -1
	coord_index = 0
	entry_format = EntryFormat.CAMERA
	curve_count = len(curve_headers)

	entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	return entry


def make_entry_bone(armature_obj: Armature, bone_name: str, clump_index: int) -> Entry:
	"""
	Make .anm Entry struct. An entry is equivalent to an Action Group in Blender. 
	"""
	action = armature_obj.animation_data.action
	curve_headers: List[CurveHeader] = list()
	curves: List[Curve] = list()

	# Make animated armature object and clump
	animated_armature_obj = AnmArmature(armature_obj)
	clump = make_clump(animated_armature_obj, clump_index)

	bone_material_indices: List[int] = clump.bone_material_indices

	loc, rot, sca = get_edit_matrix(armature_obj, bone_name).decompose()

	group = action.groups.get(bone_name)
	fcurves = group.channels
	
	data_paths = dict()
	
	channel_count = len(fcurves)
	channel_values = list()
	
	for i in range(channel_count):
		path = fcurves[i].data_path.rpartition('.')[2]
		keyframes = [int(k) for k in range(len(fcurves[i].keyframe_points))]
		data_paths[path] = len(keyframes) # Add keyframe count

		channel_values.append(list(map(lambda key: fcurves[i].evaluate(key), keyframes)))


	for data_path, keyframe_count in data_paths.items():
		if data_path == 'location':
				keyframe_vec3 = dict()

				values = list(
						map(lambda x, y, z: Vector((x, y, z)), 
						channel_values[0], 
						channel_values[1], 
						channel_values[2]))

				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)
				print(converted_values)
				
				if keyframe_count > 1:
					for frame, value in enumerate(converted_values):
						keyframe_vec3[frame * 100] = value
			
					keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key
					add_curve(AnmCurveFormat.INT1_FLOAT3, list(data_paths).index(data_path), 12, keyframe_count + 1, keyframe_vec3, curve_headers, curves)

				else:
					add_curve(AnmCurveFormat.FLOAT3, list(data_paths).index(data_path), 12, len(converted_values), converted_values, curve_headers, curves)
					
		if data_path == 'rotation_euler':
			if keyframe_count < 2:
				values = list(
					map(lambda x, y, z: Euler(Vector((x, y, z))), 
					channel_values[3], 
					channel_values[4], 
					channel_values[5]))

				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)
				add_curve(AnmCurveFormat.FLOAT3ALT, list(data_paths).index(data_path), 12, len(converted_values), converted_values, curve_headers, curves)

			else:
				quaternion_values = list(map(lambda x: x.to_quaternion(), values))
				converted_values = convert_to_anm_values('rotation_quaternion', quaternion_values, loc, rot, sca)
				add_curve(AnmCurveFormat.SHORT4, list(data_paths).index(data_path), 12, keyframe_count + 1, converted_values, curve_headers, curves)

		if data_path == 'rotation_quaternion':
				values = list(
						map(lambda w, x, y, z: Quaternion((w, x, y, z)), 
						channel_values[3], 
						channel_values[4], 
						channel_values[5], 
						channel_values[6])) 

				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)

				if keyframe_count > 1:
					add_curve(AnmCurveFormat.SHORT4, list(data_paths).index(data_path), 36, len(converted_values), converted_values, curve_headers, curves)
				else:
					euler_values = list(map(lambda x: x.to_euler(), values))
					converted_values = convert_to_anm_values('rotation_quaternion_euler', euler_values, loc, rot, sca)
					add_curve(AnmCurveFormat.FLOAT3ALT, list(data_paths).index(data_path), 24, len(converted_values), converted_values, curve_headers, curves)

		if data_path == 'scale':
			values = list(
					map(lambda x, y, z: (x, y, z), 
					channel_values[7], 
					channel_values[8], 
					channel_values[9]))

			converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)

			if keyframe_count < 2:
				add_curve(AnmCurveFormat.FLOAT3, list(data_paths).index(data_path), 48, len(converted_values), converted_values, curve_headers, curves)

			else:
				add_curve(AnmCurveFormat.SHORT3, list(data_paths).index(data_path), 48, len(converted_values), converted_values, curve_headers, curves)

				if len(converted_values) % 2 != 0:
					values = list()
					values.append(0)

					curve = Curve(AnmCurveFormat.SHORT3, values)
					curves.append(curve)
	
	# Add toggled visibility curve
	add_curve(AnmCurveFormat.FLOAT1, 3, 12, 1, [1], curve_headers, curves)

	coord_index = bone_material_indices.index(extra_mapping_reference_types.index(group.name + 'nuccChunkCoord'))
	entry_format = EntryFormat.BONE
	curve_count = len(curve_headers)

	entry = Entry(clump_index, coord_index, entry_format.value, curve_count, curve_headers, curves)

	return entry


def make_entries() -> list[Entry]:
	"""
	Make entries for all bones and armatures.
	"""
	entries: List[Entry] = list()

	# Loop over the armature objects and create entries for each bone
	for armature_obj in animated_armatures:
		anm_bones: List[Bone] = armature_obj.anm_bones
		
		for bone in anm_bones:
			e = make_entry_bone(armature_obj.armature, bone.name, animated_armatures.index(armature_obj))
			entries.append(e)

	# If there is a camera in the scene, create an entry for it
	if camera_exists():
		entries.append(make_entry_camera())

	# If there are light objects in the scene, create entries for each of them
	if light_exists():
		lights = get_lights()

		for light in lights:
			if light['type'] in ["SUN", "POINT", "AREA"]:
				entries.append(make_entry_light(lights.index(light)))
	
	return entries


# For debug purposes
def timed(func):
	def inner(*args, **kwargs):
		t0 = time()

		result = func(*args, **kwargs)
		elapsed = time() - t0
		print(f'Animation exported in {elapsed} seconds')

		return result

	return inner


@timed
def make_anm() -> bytearray:
	"""
	Make anm buffer and return it.
	"""
	clumps = make_clumps()
	entries = make_entries()
	coord_parent = make_coord_parent()
	
	entry_count = len(entries)
	clump_count = len(clumps)
	coord_count = len(coord_parent.anm_coords) // 2

	other_entry_count = 0

	if camera_exists():
		other_entry_count += 1

	if light_exists():
		lights = get_lights()

		for light in lights:
			if light['type'] == "SUN":
				other_entry_count += 1
			if light['type'] == "POINT":
				other_entry_count += 1
			if light['type'] == "AREA":
				other_entry_count += 1
	
	# TODO: Get the frame length from the Action itself
	# action = obj.animation_data.action
	# start_frame, end_frame = action.frame_range
	# frame_length = end_frame - start_frame + 1

	frame_length = bpy.context.scene.frame_end


	anm = Anm(frame_length, 1, entry_count, 1, 
					clump_count, other_entry_count, coord_count,
					clumps, coord_parent, entries)

	with BinaryReader(endianness=Endian.BIG) as anm_writer:
		anm_writer.write_struct(anm)

		return anm_writer.buffer()


def make_camera() -> bytearray:
	"""
	Make camera buffer and return it.
	"""
	unk1 = 0
	fov = 45.0

	cam = Camera(unk1, fov)

	with BinaryReader(endianness=Endian.BIG) as cam_writer:
		cam_writer.write_struct(cam)

		return cam_writer.buffer()

def make_lightdirc() -> bytearray:
	"""
	Make lightDirc buffer and return it.
	"""
	unk1 = 0
	unk2 = 0
	unk3 = 0
	unk4 = 0

	unk5 = 0.521569
	unk6 = 0.827451
	unk7 = 1
	unk8 = 1

	unk9 = 0
	unk10 = 0
	unk11 = 0
	unk12 = 0
	
	unk13 = -0.185349
	unk14 = 0.438735
	unk15 = -0.181711
	unk16 = 0.860313

	lightdirc = LightDirc(unk1, unk2, unk3, unk4, unk5, unk6, unk7, unk8, unk9, unk10, unk11,unk12, unk13, unk14, unk15, unk16)

	with BinaryReader(endianness=Endian.BIG) as lightdirc_writer:
		lightdirc_writer.write_struct(lightdirc)

		return lightdirc_writer.buffer()

def make_lightpoint() -> bytearray:
	"""
	Make lightPoint buffer and return it.
	"""
	unk1 = 0
	unk2 = 0
	unk3 = 0
	unk4 = 0

	unk5 = 0.0392157
	unk6 = 0.117647
	unk7 = 1
	unk8 = 0

	unk9 = 0
	unk10 = -23.2275
	unk11 = -183.9
	unk12 = 111.04

	unk13 = 100
	unk14 = 400
	unk15 = 0
	unk16 = 0

	lightpoint = LightPoint(unk1, unk2, unk3, unk4, unk5, unk6, unk7, unk8, unk9, unk10, unk11, unk12, unk13, unk14, unk15, unk16)

	with BinaryReader(endianness=Endian.BIG) as lightpoint_writer:
		lightpoint_writer.write_struct(lightpoint)

		return lightpoint_writer.buffer()

def make_ambient() -> bytearray:
	"""
	Make Ambient buffer and return it.
	"""
	unk1 = 0.290196
	unk2 = 0.494118
	unk3 = 0.611765
	unk4 = 1


	ambient = Ambient(unk1, unk2, unk3, unk4)

	with BinaryReader(endianness=Endian.BIG) as ambient_writer:
		ambient_writer.write_struct(ambient)

		return ambient_writer.buffer()

def write_buffers():
	""" Write buffers to file. """
	export_path = f'{directory}\\Exported Animations'

	action_name = animated_armatures[0].action.name
	
	anm_path = f'{export_path}\\[000] {action_name} (nuccChunkAnm)'
	anm_filename = f'{action_name}.anm'

	if not os.path.exists(anm_path):
		os.makedirs(anm_path)
	
	# Write the ANM file
	with open(f'{anm_path}\\{anm_filename}', 'wb+') as anm:
		anm.write(make_anm())
	
	# Write the CAM file, if a camera exists
	if camera_exists():
		cam_filename = 'camera01'
		with open(f'{anm_path}\\{cam_filename}', 'wb+') as cam:
			cam.write(make_camera())

	# Write the LIGHT files
	if light_exists():
		light_types = {
			"SUN": (".lightdirc", make_lightdirc),
			"POINT": (".lightpoint", make_lightpoint),
			"AREA": (".ambient", make_ambient),
		}

		for i, light in enumerate(get_lights()):
			name = light['name'] + str(i + 1).zfill(2)
			light_type = light['type']
			light_filename = name + light_types[light_type][0]

			with open(f'{anm_path}\\{light_filename}', 'wb+') as light:
				light.write(light_types[light_type][1]())
		

def write_json():
	""" Write page json to file. """
	chunk_maps: List[Dict] = [{"Name": "", "Type": "nuccChunkNull", "Path": ""}]
	chunk_references: List[Dict] = list()
	chunks: List[Dict] = list()

	# Create camera chunks
	if camera_exists():
		cam_path = animated_armatures[0].chunk_path
		cam_name = 'camera01'

		cam_chunk: Dict = make_chunk_dict(cam_path, cam_name, "nuccChunkCamera", reference=False, file=False)
		chunk_maps.append(cam_chunk)

		cam_file_chunk: Dict = make_chunk_dict(cam_path, cam_name, "nuccChunkCamera", reference=False, file=True)
		chunks.append(cam_file_chunk)

	# Create light chunks
	if light_exists():
		for i, light in enumerate(get_lights()):
			if light['type'] == "POINT":
				lightpoint_path = animated_armatures[0].chunk_path
				lightpoint_name = light['name'] + str(i + 1).zfill(2)

				lightpoint_chunk: Dict = make_chunk_dict(lightpoint_path, lightpoint_name, "nuccChunkLightPoint", reference=False, file=False)
				chunk_maps.append(lightpoint_chunk)

				lightpoint_file_chunk: Dict = make_chunk_dict(lightpoint_path, lightpoint_name, "nuccChunkLightPoint", reference=False, file=True)
				chunks.append(lightpoint_file_chunk)
			
			if light['type'] == "SUN":
				lightdirc_path = animated_armatures[0].chunk_path
				lightdirc_name = light['name'] + str(i + 1).zfill(2)

				lightdirc_chunk: Dict = make_chunk_dict(lightdirc_path, lightdirc_name, "nuccChunkLightDirc", reference=False, file=False)
				chunk_maps.append(lightdirc_chunk)

				lightdirc_file_chunk: Dict = make_chunk_dict(lightdirc_path, lightdirc_name, "nuccChunkLightDirc", reference=False, file=True)
				chunks.append(lightdirc_file_chunk)

			if light['type'] == "AREA":
				ambient_path = animated_armatures[0].chunk_path
				ambient_name = light['name'] + str(i + 1).zfill(2)

				ambient_chunk: Dict = make_chunk_dict(ambient_path, ambient_name, "nuccChunkAmbient", reference=False, file=False)
				chunk_maps.append(ambient_chunk)

				ambient_file_chunk: Dict = make_chunk_dict(ambient_path, ambient_name, "nuccChunkAmbient", reference=False, file=True)
				chunks.append(ambient_file_chunk)

	# Create ANM chunk
	if animated_armatures:
		anm_path = animated_armatures[0].chunk_path
		anm_name = animated_armatures[0].action.name

		anm_chunk: Dict = make_chunk_dict(anm_path, anm_name, "nuccChunkAnm", reference=False, file=False)
		chunk_maps.append(anm_chunk)

		anm_file_chunk: Dict = make_chunk_dict(anm_path, anm_name, "nuccChunkAnm", reference=False, file=True)
		chunks.append(anm_file_chunk)
	
	for armature_obj in animated_armatures:
		path = armature_obj.chunk_path

		# Add clump chunk and reference dictionary
		clump_chunk, clump_ref = make_chunk_dict(path, armature_obj.name, "nuccChunkClump", clump=armature_obj)
		chunk_maps.append(clump_chunk)
		chunk_references.append(clump_ref)
		
		# Add coord, material, model chunks and references dictionaries
		for bone_name in armature_obj.bones:
			coord_chunk, coord_ref = make_chunk_dict(path, bone_name, "nuccChunkCoord")
			chunk_maps.append(coord_chunk)
			chunk_references.append(coord_ref)

		for mat_name in armature_obj.materials:
			mat_chunk, mat_ref = make_chunk_dict(path, mat_name, "nuccChunkMaterial")
			chunk_maps.append(mat_chunk)
			chunk_references.append(mat_ref)
		
		for model_name in armature_obj.models:
			model_chunk, model_ref = make_chunk_dict(path, model_name, "nuccChunkModel")
			chunk_maps.append(model_chunk)
			chunk_references.append(model_ref)
		
	page_chunk = make_chunk_dict("", "Page0", "nuccChunkPage", reference=False, file=False)
	chunk_maps.append(page_chunk)

	index_chunk = make_chunk_dict("", "index", "nuccChunkIndex", reference=False, file=False)
	chunk_maps.append(index_chunk)


	page_json = dict()
	page_json['Chunk Maps'] = list(map(lambda x: x, chunk_maps))
	page_json['Chunk References'] = list(map(lambda x: x, chunk_references))
	page_json['Chunks'] = list(map(lambda x: x, chunks))

	export_path = f'{directory}\\Exported Animations'
	page_path = export_path + '\\[000] ' + animated_armatures[0].action.name +' (nuccChunkAnm)'

	if not os.path.exists(page_path):
		os.makedirs(page_path)

	with open(os.path.join(page_path, '_page.json'), 'w', encoding='cp932') as file:
		json.dump(page_json, file, ensure_ascii=False, indent=4)


write_buffers()
write_json()
