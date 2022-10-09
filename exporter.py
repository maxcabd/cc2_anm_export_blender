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
from common.bone_props import *
from common.armature_props import *
from common.coordinate_converter import *
from common.helpers import *



is_looped = False # Set to true if your animation should be looped


def camera_exists() -> bool:
	""" Return true if Camera exists AND has animation data."""
	cam = bpy.context.scene.camera

	if cam and cam.animation_data: 
		return True
	else: 
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

					curve = Curve(AnmCurveFormat.INT1_FLOAT3, keyframe_vec3)
					curves.append(curve)

					curve_header = CurveHeader(
											list(data_paths).index(data_path), 
											AnmCurveFormat.INT1_FLOAT3.value, 
											keyframe_count + 1,  # Add 1 more to frame count for null key
											12)
					curve_headers.append(curve_header)
				else:
					curve = Curve(AnmCurveFormat.FLOAT3, converted_values)
					curves.append(curve)

					curve_header = CurveHeader(
									list(data_paths).index(data_path), 
									AnmCurveFormat.FLOAT3.value, 
									len(converted_values), 
									12)
					curve_headers.append(curve_header)

					
		if data_path == 'rotation_euler':
			if keyframe_count < 2:
				values = list(
					map(lambda x, y, z: Euler(Vector((x, y, z))), 
					channel_values[3], 
					channel_values[4], 
					channel_values[5]))

				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)

				curve = Curve(AnmCurveFormat.FLOAT3ALT, converted_values)
				curves.append(curve)

				curve_header = CurveHeader(
										list(data_paths).index(data_path), 
										AnmCurveFormat.FLOAT3ALT.value, 
										len(converted_values), 
										24)
				curve_headers.append(curve_header)
			else:
				quaternion_values = list(map(lambda x: x.to_quaternion(), values))
				converted_values = convert_to_anm_values('rotation_quaternion', quaternion_values, loc, rot, sca)

				curve = Curve(AnmCurveFormat.SHORT4, converted_values)
				curves.append(curve)
				curve_header = CurveHeader(
										list(data_paths).index(data_path), 
										AnmCurveFormat.SHORT4.value, 
										len(converted_values), 
										24)
				curve_headers.append(curve_header)

		if data_path == 'rotation_quaternion':
				values = list(
						map(lambda w, x, y, z: Quaternion((w, x, y, z)), 
						channel_values[3], 
						channel_values[4], 
						channel_values[5], 
						channel_values[6])) 

				converted_values = convert_to_anm_values('rotation_quaternion_camera', values, loc, rot, sca)

				if keyframe_count > 1:
					curve = Curve(AnmCurveFormat.SHORT4, converted_values)
					curves.append(curve)

					curve_header = CurveHeader(
									list(data_paths).index(data_path), 
									AnmCurveFormat.SHORT4.value, 
									len(converted_values), 
									36)
					curve_headers.append(curve_header)
				else:
					euler_values = list(map(lambda x: x.to_euler(), values))
					converted_values = convert_to_anm_values('rotation_quaternion_euler', euler_values, loc, rot, sca)

					curve = Curve(AnmCurveFormat.FLOAT3ALT, converted_values)
					curves.append(curve)

					curve_header = CurveHeader(
									list(data_paths).index(data_path), 
									AnmCurveFormat.FLOAT3ALT.value, 
									len(converted_values), 
									24)
					curve_headers.append(curve_header)
	

	# Add FOV
	keyframe_vec3 = dict()
	values = list()

	for _ in range(keyframe_count):
		values.append(45)
	
	if keyframe_count > 1:
		for frame, value in enumerate(values):
			keyframe_vec3[frame * 100] = value

		keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key

		curve = Curve(AnmCurveFormat.INT1_FLOAT1, keyframe_vec3)
		curves.append(curve)
		curve_header = CurveHeader(
								2, 
								AnmCurveFormat.INT1_FLOAT1.value, 
								keyframe_count + 1,  # Add 1 more to frame count for null key
								12)
		curve_headers.append(curve_header)

	clump_index = -1
	coord_index = 0
	entry_format = 2 # Camera
	curve_count = len(curve_headers)

	entry = Entry(clump_index, coord_index, entry_format, curve_count, curve_headers, curves)

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
				
				if keyframe_count > 1:
					for frame, value in enumerate(converted_values):
						keyframe_vec3[frame * 100] = value
			
					keyframe_vec3.update({-1: [*keyframe_vec3.values()][-1]}) # Add null key

					curve = Curve(AnmCurveFormat.INT1_FLOAT3, keyframe_vec3)
					curves.append(curve)

					curve_header = CurveHeader(list(data_paths).index(data_path), 
											AnmCurveFormat.INT1_FLOAT3.value, 
											keyframe_count + 1,  # Add 1 more to frame count for null key
											12)
					curve_headers.append(curve_header)
				else:
					curve = Curve(AnmCurveFormat.FLOAT3, converted_values)
					curves.append(curve)

					curve_header = CurveHeader(list(data_paths).index(data_path), 
									AnmCurveFormat.FLOAT3.value, 
									len(converted_values), 
									12)
					curve_headers.append(curve_header)

					
		if data_path == 'rotation_euler':
			if keyframe_count < 2:
				values = list(
					map(lambda x, y, z: Euler(Vector((x, y, z))), 
					channel_values[3], 
					channel_values[4], 
					channel_values[5]))

				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)
				curve = Curve(AnmCurveFormat.FLOAT3ALT, converted_values)
				curves.append(curve)

				curve_header = CurveHeader(list(data_paths).index(data_path), 
										AnmCurveFormat.FLOAT3ALT.value, 
										len(converted_values), 
										24)
				curve_headers.append(curve_header)
			else:
				quaternion_values = list(map(lambda x: x.to_quaternion(), values))
				converted_values = convert_to_anm_values('rotation_quaternion', quaternion_values, loc, rot, sca)
				
				curve = Curve(AnmCurveFormat.SHORT4, converted_values)
				curves.append(curve)

				curve_header = CurveHeader(list(data_paths).index(data_path), 
										AnmCurveFormat.SHORT4.value, 
										len(converted_values), 
										24)
				curve_headers.append(curve_header)

		if data_path == 'rotation_quaternion':
				values = list(
						map(lambda w, x, y, z: Quaternion((w, x, y, z)), 
						channel_values[3], 
						channel_values[4], 
						channel_values[5], 
						channel_values[6])) 

				converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)

				if keyframe_count > 1:
					curve = Curve(AnmCurveFormat.SHORT4, converted_values)
					curves.append(curve)

					curve_header = CurveHeader(
									list(data_paths).index(data_path), 
									AnmCurveFormat.SHORT4.value, 
									len(converted_values), 
									36)
					curve_headers.append(curve_header)
				else:
					euler_values = list(map(lambda x: x.to_euler(), values))
					converted_values = convert_to_anm_values('rotation_quaternion_euler', euler_values, loc, rot, sca)

					curve = Curve(AnmCurveFormat.FLOAT3ALT, converted_values)
					curves.append(curve)

					curve_header = CurveHeader(
									list(data_paths).index(data_path), 
									AnmCurveFormat.FLOAT3ALT.value, 
									len(converted_values), 
									24)
					curve_headers.append(curve_header)

		if data_path == 'scale':
			values = list(
					map(lambda x, y, z: (x, y, z), 
					channel_values[7], 
					channel_values[8], 
					channel_values[9]))

			converted_values = convert_to_anm_values(data_path, values, loc, rot, sca)

			if keyframe_count < 2:
				curve = Curve(AnmCurveFormat.FLOAT3, converted_values)
				curves.append(curve)
				curve_header = CurveHeader(
									list(data_paths).index(data_path), 
									AnmCurveFormat.FLOAT3.value, 
									len(converted_values), 
									48)
				curve_headers.append(curve_header)
			else:
				curve = Curve(AnmCurveFormat.SHORT3, converted_values)
				curves.append(curve)

				curve_header = CurveHeader(
									list(data_paths).index(data_path), 
									AnmCurveFormat.SHORT3.value, 
									len(converted_values), 
									48)
				curve_headers.append(curve_header)

				if len(converted_values) % 2 != 0:
					values = list()
					values.append(0)

					curve = Curve(AnmCurveFormat.SHORT3, values)
					curves.append(curve)
	
	# Add toggled
	values = list()
	values.append(1)
	curve = Curve(AnmCurveFormat.FLOAT1, values)
	curves.append(curve)
	curve_header = CurveHeader(3, AnmCurveFormat.FLOAT1.value, 1, 12)
	curve_headers.append(curve_header)

	coord_index = bone_material_indices.index(extra_mapping_reference_types.index(group.name + 'nuccChunkCoord'))
	entry_format = 1 # Bone
	curve_count = len(curve_headers)

	entry = Entry(clump_index, coord_index, entry_format, curve_count, curve_headers, curves)

	return entry


def make_entries() -> list[Entry]:
	"""
	Make entries for all bones and armatures.
	"""
	entries: List[Entry] = list()

	for armature_obj in animated_armatures:
		anm_bones: List[Bone] = armature_obj.anm_bones
		
		for bone in anm_bones:
			e = make_entry_bone(armature_obj.armature, bone.name, animated_armatures.index(armature_obj))
			entries.append(e)

	if camera_exists():
		entries.append(make_entry_camera())

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
	other_entry_count = 0
	loop = 0

	if camera_exists():
		other_entry_count += 1
		

	coord_count = len(coord_parent.anm_coords) // 2

	frame_length = bpy.context.scene.frame_end

	if is_looped:
		loop = 1

	anm = Anm(frame_length, 1, entry_count, loop, 
					clump_count, other_entry_count, coord_count,
					clumps, coord_parent, entries)

	with BinaryReader(endianness=Endian.BIG) as anm_writer:
		anm_writer.write_struct(anm)

		return anm_writer.buffer()


def make_camera() -> bytearray:
	"""
	Make camera buffer and return it.
	"""
	unk = 0
	fov = 45.0

	cam = Camera(unk, fov)

	with BinaryReader(endianness=Endian.BIG) as cam_writer:
		cam_writer.write_struct(cam)

		return cam_writer.buffer()

# TODO: Add support for LightDir chunks
	

def write_buffers():
	""" Write buffers to file. """
	export_path = f'{directory}\\exported_anm'

	if not os.path.exists(export_path):
		os.makedirs(export_path)
	
	action_name = animated_armatures[0].action.name
	
	anm_path = f'{export_path}\\[000] {action_name} (nuccChunkAnm)'
	anm_filename = f'{action_name}.anm'

	if not os.path.exists(anm_path):
		os.makedirs(anm_path)
		
	with open(f'{anm_path}\\{anm_filename}', 'wb+') as anm:
		anm.write(make_anm())
	
	if camera_exists():
		cam_filename = "camera01.camera"
		with open(f'{anm_path}\\{cam_filename}', 'wb+') as cam:
			cam.write(make_camera())

def write_json():
	""" Write page json to file. """
	chunk_maps: List[Dict] = [{"Name": "", "Type": "nuccChunkNull", "Path": ""}]
	chunk_references: List[Dict] = list()
	chunks: List[Dict] = list()


	if camera_exists():
		cam_path = animated_armatures[0].chunk_path
		cam_name = "camera01"

		cam_chunk: Dict = make_chunk_dict(cam_path, cam_name, "nuccChunkCamera", reference=False, file=False)
		chunk_maps.append(cam_chunk)

		cam_file_chunk: Dict = make_chunk_dict(cam_path, cam_name, "nuccChunkCamera", reference=False, file=True)
		chunks.append(cam_file_chunk)

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

	export_path = f'{directory}\\exported_anm'
	page_path = export_path + '\\[000] ' + animated_armatures[0].action.name +' (nuccChunkAnm)'

	if not os.path.exists(page_path):
		os.makedirs(page_path)

	with open(os.path.join(page_path, '_page.json'), 'w', encoding='cp932') as file:
		json.dump(page_json, file, ensure_ascii=False, indent=4)


write_buffers()
write_json()
