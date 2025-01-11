import bpy


from os import path
from collections import defaultdict
from typing import Dict, List

from bpy_extras.io_utils import ExportHelper
from bpy.props import (EnumProperty, StringProperty, BoolProperty)
from bpy.types import Operator, Bone, ActionGroup, FCurve


from ..xfbin.xfbin_lib import *

from .common.helpers import *
from .common.bone_props import *
from .common.armature_props import *
from .common.coordinate_converter import *
from cProfile import Profile
import pstats

from time import perf_counter

class ExportAnmXfbin(Operator, ExportHelper):
	"""Export current collection as XFBIN file"""
	bl_idname = 'export_anm_scene.xfbin'
	bl_label = 'Export animation XFBIN'

	filename_ext = '.xfbin'

	filter_glob: StringProperty(default='*.xfbin', options={'HIDDEN'})

	def collection_callback(self, context):
		items = set()
		active_col = bpy.context.collection

		if active_col:
			items.add((active_col.name, active_col.name, ''))

		items.update([(c.name, c.name, '') for c in bpy.data.collections])

		return list([i for i in items if i[0] != 'Collection'])
	
	def collection_update(self, context):
		pass


	collection: EnumProperty(
		items=collection_callback,
		name='Collection',
		description='The collection to be exported. All animations in the collection will be converted and put in the same XFBIN',
	)

	inject_to_xfbin: BoolProperty(
		name='Inject to an existing XFBIN',
		description='If True, will add (or overwrite) the exportable animations as pages in the selected XFBIN.\n'
		'If False, will create a new XFBIN and overwrite the old file if it exists.\n\n'
		'NOTE: If True, the selected path has to be an XFBIN file that already exists, and that file will be overwritten',
		default=True,
	)

	"""inject_to_clump: BoolProperty(
		name='Inject to an existing Clump',
		description='If True, will add (or overwrite) the Clump animation(s) in the selected ANM in the XFBIN\n'
		'If False, will create a new Clump and overwrite the old file if it exists.\n\n'
		'NOTE: "Inject to existing XFBIN" has to be enabled for this option to take effect\n',					
		default=True,
	)"""

	def draw(self, context):
		layout = self.layout

		layout.label(text='Select a collection to export:')
		layout.prop_search(self, 'collection', bpy.data, 'collections')

		if self.collection:
			inject_row = layout.row()
			inject_row.prop(self, 'inject_to_xfbin')
		

	def execute(self, context):
		import time

		start_time = time.time()
		exporter = AnmXfbinExporter(self, self.filepath, self.as_keywords(ignore=('filter_glob',)))
  
		# Profile the function
		pr = Profile()
		pr.enable()
		exporter.export_collection(context)

		pr.disable()
		pr.print_stats(sort='cumtime')
  
		elapsed_s = "{:.2f}s".format(time.time() - start_time)
		self.report({'INFO'}, f'Finished exporting {exporter.collection.name} in {elapsed_s}')
		return {'FINISHED'}
	
class AnmXfbinExporter:
	xfbin: Xfbin

	def __init__(self, operator: Operator, filepath: str, export_settings: dict):
		self.operator = operator
		self.filepath = filepath
		self.collection: bpy.types.Collection = bpy.data.collections[export_settings.get('collection')]
		self.inject_to_xfbin = export_settings.get('inject_to_xfbin')
		

	
	def export_collection(self, context):
		self.xfbin = Xfbin()
		self.xfbin.version = 121

		if self.inject_to_xfbin:
			if not path.isfile(self.filepath):
				raise Exception(f'Cannot inject XFBIN - File does not exist: {self.filepath}')

			self.xfbin = read_xfbin(self.filepath)
		else:
			self.inject_to_clump = False

		for obj in self.collection.objects:
			if obj.name.startswith(XFBIN_ANMS_OBJ):
				anm_chunks_obj = obj

		anm_chunks_data = anm_chunks_obj.xfbin_anm_chunks_data

		for anm_chunk in anm_chunks_data.anm_chunks:

			page = XfbinPage()
			page.struct_infos.append(NuccStructInfo("", "nuccChunkNull", ""))


			anm_chunk_name = anm_chunk.name.split(' (')[0] if ' (' in anm_chunk.name else anm_chunk.name # Remove suffix if it exists
   
			anm_clumps = self.make_anm_armatures(anm_chunk)

			for clump in anm_clumps:
				page.struct_infos.extend(clump.nucc_struct_infos.get_armature_info())
				page.struct_references.extend(clump.nucc_struct_references)

	
			if anm_chunk.cameras:
				for camera_chunk in anm_chunk.cameras:
					camera = bpy.data.objects[camera_chunk.name]
					camera_name = camera_chunk.name.split(' (')[0] if ' (' in camera_chunk.name else camera_chunk.name # Remove suffix if it exists

					nucc_camera = NuccCamera()
					nucc_camera.struct_info = NuccStructInfo(camera_name, "nuccChunkCamera", camera_chunk.path)
					
					nucc_camera.fov = fov_from_blender(camera.data.sensor_width, camera.data.lens)
					page.structs.append(nucc_camera)
			
			if anm_chunk.lightdircs:
				for light_prop in anm_chunk.lightdircs:
					lightdirc = bpy.data.objects.get(light_prop.name)
					if not lightdirc:
						continue
					lightdirc_name = light_prop.name.split(' (')[0] if ' (' in light_prop.name else light_prop.name

					nucc_lightdirc = NuccLightDirc()
					nucc_lightdirc.struct_info = NuccStructInfo(lightdirc_name, "nuccChunkLightDirc", light_prop.path)

					nucc_lightdirc.color = lightdirc.data.color
					nucc_lightdirc.energy = lightdirc.data.energy
					light_default_rot = lightdirc.matrix_world.to_quaternion().inverted()
					nucc_lightdirc.rotation = [light_default_rot.x, light_default_rot.y, light_default_rot.z, light_default_rot.w]

					page.structs.append(nucc_lightdirc)
			
			if anm_chunk.lightpoints:
				for light_prop in anm_chunk.lightpoints:
					lightpoint = bpy.data.objects.get(light_prop.name)
					if not lightpoint:
						continue
					lightpoint_name = light_prop.name.split(' (')[0] if ' (' in light_prop.name else light_prop.name

					nucc_lightpoint = NuccLightPoint()
					nucc_lightpoint.struct_info = NuccStructInfo(lightpoint_name, "nuccChunkLightPoint", light_prop.path)

					nucc_lightpoint.color = lightpoint.data.color
					nucc_lightpoint.energy = lightpoint.data.energy

					converted_value: List[int] = convert_object_value("location", lightpoint.matrix_world.to_translation().copy()[:]).values
					nucc_lightpoint.location = converted_value

					nucc_lightpoint.radius = lightpoint.data.shadow_soft_size
					
					if lightpoint.data.use_custom_distance:
						nucc_lightpoint.cutoff = lightpoint.data.cutoff_distance
					else:
						nucc_lightpoint.cutoff = 0.0

					page.structs.append(nucc_lightpoint)
			
			if anm_chunk.ambients:
				for light_prop in anm_chunk.ambients:
					ambient_obj = bpy.data.objects.get(light_prop.name)
					if not ambient_obj:
						continue
					ambient_name = light_prop.name.split(' (')[0] if ' (' in light_prop.name else light_prop.name

					nucc_ambient = NuccAmbient()
					nucc_ambient.struct_info = NuccStructInfo(ambient_name, "nuccChunkAmbient", light_prop.path)

					nucc_ambient.color = ambient_obj.data.color
					nucc_ambient.energy = ambient_obj.data.energy

					page.structs.append(nucc_ambient)
			
			
			nucc_anm: NuccAnm = self.make_anm(anm_chunk, anm_clumps, page.struct_infos)
			page.structs.append(nucc_anm)
			

			if self.inject_to_xfbin:
				# Add page or overwrite existing page
				for i, p in enumerate(self.xfbin.pages):
					if any(struct_info.chunk_name == anm_chunk_name for struct_info in p.struct_infos):
						self.xfbin.pages[i] = page
						break
				else:
					self.xfbin.pages.append(page)
			else:
				self.xfbin.pages.append(page)

			
			
		write_xfbin(self.xfbin, self.filepath)


	def make_anm_armatures(self, anm_chunk: XfbinAnmChunkPropertyGroup) -> List[AnmArmature]:
		"""
		Return list of armatures that contain animation data.
		"""
		anm_armatures: List[AnmArmature] = []

		for index, clump_props in enumerate(anm_chunk.anm_clumps):
			arm_obj: Armature = bpy.data.objects.get(clump_props.name)

			if not arm_obj or not arm_obj.animation_data:
				continue

			action_name = anm_chunk.name if index == 0 else arm_obj.animation_data.action.name
			action = bpy.data.actions.get(action_name)

			if action:
				arm_obj.animation_data_create()
				arm_obj.animation_data.action = action
				anm_armatures.append(AnmArmature(arm_obj))

		return anm_armatures


	def make_anm(self, anm_chunk: XfbinAnmChunkPropertyGroup, anm_armatures, struct_infos: List[NuccStructInfo]) -> NuccAnm:
		"""
		Return NuccAnm object from AnmProp object.
		"""

		anm = NuccAnm()

		anm_name = anm_chunk.name.split(' (')[0] if ' (' in anm_chunk.name else anm_chunk.name
		anm.struct_info = NuccStructInfo(f"{anm_name}", "nuccChunkAnm", anm_chunk.path)

		anm.is_looped = anm_chunk.is_looped
		anm.frame_count = anm_chunk.frame_count * 100

		# Combined struct references from all armatures for this animation
		struct_references: List[NuccStructReference] = [ref for armature in anm_armatures for ref in armature.nucc_struct_references]

		anm.clumps.extend(self.make_anm_clump(anm_armatures, struct_references))
		anm.coord_parents.extend(self.make_anm_coords(anm_armatures))
  
		action = bpy.data.actions.get(f'{anm_chunk.name}')
  
		fcurve_dict = {}
  
		for fcurve in action.fcurves:
			if len(fcurve.data_path.split('"')) < 2:
				continue 
			bone_name = fcurve.data_path.split('"')[1]
   
			if not fcurve_dict.get(bone_name):
				fcurve_dict[bone_name] = {
										'location': [None] * 3,
										'rotation_euler': [None] * 3,
										'rotation_quaternion': [None] * 4,
										'scale': [None] * 3,
										'opacity': [None]}

			property_name = fcurve.data_path.split('.')[-1]
			if fcurve_dict[bone_name].get(property_name):
				fcurve_dict[bone_name][property_name][fcurve.array_index] = fcurve

					
		for armature in anm_armatures:
			anm.entries.extend(self.make_coord_entries(armature, struct_references, anm.clumps, fcurve_dict))
			if anm_chunk.export_material_animations:
				anm.entries.extend(self.make_material_entries(armature, struct_references, anm.clumps))


		if anm_chunk.cameras:
			for index, camera_chunk in enumerate(anm_chunk.cameras):
				camera = bpy.data.objects.get(camera_chunk.name)
				if not camera:
					continue
				anm.entries.extend(self.make_camera_entries(camera, index))
				anm.other_entries_indices.append(len(struct_infos) + index)

		if anm_chunk.lightdircs:
			for index, light_prop in enumerate(anm_chunk.lightdircs):
				lightdirc = bpy.data.objects.get(light_prop.name)
				if not lightdirc:
					continue
				anm.entries.extend(self.make_lightdirc_entries(lightdirc, index + len(anm_chunk.cameras)))
				anm.other_entries_indices.append(len(struct_infos) + index + len(anm_chunk.cameras))
		
		if anm_chunk.lightpoints:
			for index, light_prop in enumerate(anm_chunk.lightpoints):
				lightpoint = bpy.data.objects.get(light_prop.name)
				if not lightpoint:
					continue
				anm.entries.extend(self.make_lightpoint_entries(lightpoint, index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs)))
				anm.other_entries_indices.append(len(struct_infos) + index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs))

		if anm_chunk.ambients:
			for index, light_prop in enumerate(anm_chunk.ambients):
				ambient = bpy.data.objects.get(light_prop.name)
				if not ambient:
					continue
				anm.entries.extend(self.make_ambient_entries(ambient, index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs) + len(anm_chunk.lightpoints)))
				anm.other_entries_indices.append(len(struct_infos) + index + len(anm_chunk.cameras) + len(anm_chunk.lightdircs) + len(anm_chunk.lightpoints))

		return anm
			
	def make_anm_clump(self, anm_armatures: List[AnmArmature], struct_references: List[NuccStructReference]) -> List[AnmClump]:
		clumps: List[AnmClump] = list()


		for anm_armature in anm_armatures:
			clump = AnmClump()

			if anm_armature.models:
				clump.clump_index = struct_references.index(NuccStructReference(anm_armature.models[0], NuccStructInfo(anm_armature.name, "nuccChunkClump", anm_armature.chunk_path)))
					
			else:
				clump.clump_index = struct_references.index(NuccStructReference(anm_armature.bones[0].name, NuccStructInfo(anm_armature.name, "nuccChunkClump", anm_armature.chunk_path)))
					
			bone_material_indices: List[int] = list()

			

			bone_indices: List[int] = [struct_references.index(NuccStructReference(bone.name, NuccStructInfo(bone.name, "nuccChunkCoord", anm_armature.chunk_path))) for bone in anm_armature.bones]
			mat_indices: List[int] = [struct_references.index(NuccStructReference(mat, NuccStructInfo(mat, "nuccChunkMaterial", anm_armature.chunk_path))) for mat in anm_armature.materials]
			model_indices: List[int] = [struct_references.index(NuccStructReference(model, NuccStructInfo(model, "nuccChunkModel", anm_armature.chunk_path))) for model in anm_armature.models]

			bone_material_indices.extend([*bone_indices, *mat_indices])


			clump.bone_material_indices = bone_material_indices
			clump.model_indices = model_indices

			clumps.append(clump)

		return clumps


	def make_anm_coords(self, anm_armatures: List[AnmArmature]) -> List[CoordParent]:
		"""
		Return list of CoordParent objects from AnmArmature object.
		"""
		coord_parents: List[CoordParent] = list()

		# Get list of child bones for each bone in armature
		for armature_index, anm_armature in enumerate(anm_armatures):
			armature_obj = anm_armature.armature

			for bone in anm_armature.armature.data.bones:
				if bone.parent:
					parent = AnmCoord(armature_index, anm_armature.bones.index(bone.parent))
					child = AnmCoord(armature_index, anm_armature.bones.index(bone))

					coord_parents.append(CoordParent(parent, child))

				
			# Handle case where bone has constraints
			'''for bone in armature_obj.data.bones:
				if ("Copy Transforms" in anm_armatures[armature_index].armature.pose.bones[bone.name].constraints):
					target_object = anm_armatures[armature_index].armature.pose.bones[bone.name].constraints["Copy Transforms"].target
					parent_armature = next((arm for arm in anm_armatures if arm.armature == target_object), None)
					if parent_armature:
						parent_clump_index = anm_armatures.index(parent_armature)
						parent = AnmCoord(parent_clump_index, parent_armature.bones.index(armature_obj.pose.bones[bone.name].constraints["Copy Transforms"].subtarget))
						child = AnmCoord(armature_index, anm_armature.bones.index(bone.name))

						coord_parents.append(CoordParent(parent, child))'''
			

		return coord_parents


	def make_coord_entries(self, anm_armature: AnmArmature, struct_references: List[NuccStructReference], clumps: List[AnmClump], fcurve_dict) -> List[AnmEntry]:
		def collect_keyframes(curves, default_values, evaluate_fn):
			"""Collect keyframes for given curves with optimized frame processing."""
			keyframes = defaultdict(list)
			all_frame_indices = []

			# Build a frame-to-keyframe map for each curve
			curve_keyframe_maps = []
			for curve in curves:
				if curve:
					frame_values = {kp.co[0]: evaluate_fn(curve, kp.co[0]) for kp in curve.keyframe_points}
					curve_keyframe_maps.append((curve, frame_values))
					all_frame_indices.extend(frame_values.keys())
			
			# Sort all frames only once
			all_frames = sorted(set(all_frame_indices))

			# Initialize the last known values
			last_values = default_values[:]
			frame_values = last_values[:]

			# Iterate over all frames and fill keyframes
			for frame in all_frames:
				for curve, frame_values_map in curve_keyframe_maps:
					if frame in frame_values_map:
						frame_values[curve.array_index] = frame_values_map[frame]

				# Update last_values in place
				last_values[:] = frame_values[:]
				keyframes[int(frame)] = frame_values[:]

			return keyframes


		def create_track_header(track_index, key_format, frame_count):
			"""Create a track header with common properties."""
			header = TrackHeader()
			header.track_index = track_index
			header.key_format = key_format
			header.frame_count = frame_count
			return header

		entries = []
		armature_curves = {bone.name: fcurve_dict.get(bone.name) for bone in anm_armature.armature.data.bones}

		#bone_indices = {bone.name: i for i, bone in enumerate(anm_armature.bones)}

		for bone_name, curves in armature_curves.items():
			if not curves:
				continue
			# Find clump and coordinate indices
			clump_reference_index = struct_references.index(anm_armature.nucc_struct_references[0])
			clump_index = next((i for i, clump in enumerate(clumps) if clump.clump_index == clump_reference_index), None)

			coord_reference_index = struct_references.index(
				NuccStructReference(bone_name, NuccStructInfo(bone_name, "nuccChunkCoord", anm_armature.chunk_path))
			)
			coord_index = next(
				(i for i, coord in enumerate(clumps[clump_index].bone_material_indices) if coord == coord_reference_index), None
			)

			entry = AnmEntry()
			entry.coord = AnmCoord(clump_index, coord_index)
			entry.entry_format = EntryFormat.Coord

			bone = anm_armature.armature.data.bones[bone_name]
			loc, rot, scale = get_edit_matrix(anm_armature.armature, bone).decompose()

			# Create location track
			location_keyframes = collect_keyframes(curves['location'], [0, 0, 0], lambda c, f: c.evaluate(f))
			location_frame_count = len(location_keyframes)
			location_is_multiple = location_frame_count > 1
			location_header = create_track_header(
				0, NuccAnmKeyFormat.Vector3Linear if location_is_multiple else NuccAnmKeyFormat.Vector3Fixed,
				location_frame_count + location_is_multiple
			)
			location_track = Track()
			location_track.keys = [
				convert_bone_value(loc, rot, scale, 'location', location_header, value, frame)
				for frame, value in location_keyframes.items()
			]
			if location_is_multiple:
				location_track.keys.append(NuccAnmKey.Vec3Linear(-1, location_track.keys[-1].values))

			entry.tracks.append(location_track)
			entry.track_headers.append(location_header)

			# Create rotation track
			if any(curves['rotation_quaternion']):
				rotation_keyframes = collect_keyframes(curves['rotation_quaternion'], [1.0, 0.0, 0.0, 0.0], lambda c, f: c.evaluate(f))
				rotation_header = create_track_header(1, NuccAnmKeyFormat.QuaternionLinear, len(rotation_keyframes) + 1)
				rotation_track = Track()
				rotation_track.keys = [
					convert_bone_value(loc, rot, scale, 'rotation_quaternion', rotation_header, value, frame)
					for frame, value in rotation_keyframes.items()
				]
				rotation_track.keys.append(NuccAnmKey.Vec4Linear(-1, rotation_track.keys[-1].values))
				entry.tracks.append(rotation_track)
				entry.track_headers.append(rotation_header)

			elif any(curves['rotation_euler']):
				rotation_keyframes = collect_keyframes(curves['rotation_euler'], [0, 0, 0], lambda c, f: c.evaluate(f))
				rotation_header = create_track_header(1, NuccAnmKeyFormat.EulerXYZFixed, len(rotation_keyframes))
				rotation_track = Track()
				rotation_track.keys = [
					convert_bone_value(loc, rot, scale, 'rotation_euler', rotation_header, value, frame)
					for frame, value in rotation_keyframes.items()
				]

				entry.tracks.append(rotation_track)
				entry.track_headers.append(rotation_header)

			# Create scale track
			if any(curves['scale']):
				scale_keyframes = collect_keyframes(curves['scale'], [1, 1, 1], lambda c, f: c.evaluate(f))
				scale_frame_count = len(scale_keyframes)
				scale_is_multiple = scale_frame_count > 1
				scale_header = create_track_header(
					2, NuccAnmKeyFormat.Vector3Linear if scale_is_multiple else NuccAnmKeyFormat.Vector3Fixed,
					scale_frame_count + scale_is_multiple
				)
				scale_track = Track()
				scale_track.keys = [
					convert_bone_value(loc, rot, scale, 'scale', scale_header, value, frame)
					for frame, value in scale_keyframes.items()
				]
				if scale_is_multiple:
					scale_track.keys.append(NuccAnmKey.Vec3Linear(-1, scale_track.keys[-1].values))

				entry.tracks.append(scale_track)
				entry.track_headers.append(scale_header)

			
			# Create opacity track
			opacity_track = Track()
			if curves['opacity'][0]:
				curve = curves['opacity'][0]
				opacity_track.keys = [NuccAnmKey.FloatLinear(int(kp.co[0] * 100), kp.co[1]) for kp in curve.keyframe_points] 
				opacity_header = create_track_header(3, NuccAnmKeyFormat.FloatLinear, len(opacity_track.keys) + 1)
		
				null_key = NuccAnmKey.FloatLinear(-1, opacity_track.keys[-1].values)
				opacity_track.keys.append(null_key)

				entry.tracks.append(opacity_track)
				entry.track_headers.append(opacity_header)
			else:
				opacity_header = create_track_header(3, NuccAnmKeyFormat.FloatFixed, 1)
				opacity_track.keys = [NuccAnmKey.Float(1)]
				entry.tracks.append(opacity_track)
				entry.track_headers.append(opacity_header)

			entries.append(entry)

		return entries


	def make_material_entries(self, anm_armature: AnmArmature, struct_references: List[NuccStructReference], clumps: List[AnmClump]) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		def get_node_input_default(node_name: str, input_index: int):
			node = nodes.get(node_name)
			if node:
				return node.inputs[input_index].default_value
			return [0, 0, 0]
		

		def get_node_output_default(node_name: str, output_index: int):
			node = nodes.get(node_name)
			if node:
				return node.outputs[output_index].default_value
			return 0
		
  

  
		def create_and_append_track(entry: AnmEntry, track_index: int, key_format: NuccAnmKeyFormat, values: List[float]):
			""" Create helper method since most material entries have the same structure """
			track_header = TrackHeader()
			track_header.track_index = track_index

			
			track_header.key_format = key_format
			track_header.frame_count = len(values)

			track = Track()

			for value in values:
				#converted_value: NuccAnmKey = NuccAnmKey.Float(value)
				track.keys.append(value)

			entry.tracks.append(track)
			entry.track_headers.append(track_header)


		for material_name in anm_armature.materials:
			material = bpy.data.materials.get(material_name)

			if not material:
				continue

			if not material.node_tree.animation_data:
				continue
			
			if not material.node_tree.animation_data.action:
				continue

			
			nodes = material.node_tree.nodes

			u0_location: List[float] = list()
			v0_location: List[float] = list()

			u1_location: List[float] = list()
			v1_location: List[float] = list()
   
			u0_scale: List[float] = list()
			v0_scale: List[float] = list()

			u1_scale: List[float] = list()
			v1_scale: List[float] = list()

			u2_location: List[float] = list()
			v2_location: List[float] = list()
			
			u2_scale: List[float] = list()
			v2_scale: List[float] = list()

			u3_location: List[float] = list()
			v3_location: List[float] = list()

			u3_scale: List[float] = list()
			v3_scale: List[float] = list()

			blend_rate1_values: List[float] = list()
			blend_rate2_values: List[float] = list()
   
			falloff_values: List[float] = list()
			glare_values: List[float] = list()
			alpha_values: List[float] = list()
   
			#get nodes
			nodes = material.node_tree.nodes
   
			existing_nodes = {}

			#get uvOffset0 node
			uv_offset0 = nodes.get("uvOffset0")
			if uv_offset0:
				existing_nodes[uv_offset0] = [None, u0_location, v0_location, u0_scale, v0_scale]
			uv_offset1 = nodes.get("uvOffset1")
			if uv_offset1:
				existing_nodes[uv_offset1] = [u1_location, v1_location, u1_scale, v1_scale]
			uv_offset2 = nodes.get("uvOffset2")
			if uv_offset2:
				existing_nodes[uv_offset2] = [u2_location, v2_location, u2_scale, v2_scale]
			uv_offset3 = nodes.get("uvOffset3")
			if uv_offset3:
				existing_nodes[uv_offset3] = [u3_location, v3_location, u3_scale, v3_scale]
			blend_rate1 = nodes.get("blendRate1")
			if blend_rate1:
				existing_nodes[blend_rate1] = blend_rate1_values
			blend_rate2 = nodes.get("blendRate2")
			if blend_rate2:
				existing_nodes[blend_rate2] = blend_rate2_values
			falloff = nodes.get("falloff")
			if falloff:
				existing_nodes[falloff] = falloff_values
			glare = nodes.get("glare")
			if glare:
				existing_nodes[glare] = glare_values
			alpha = nodes.get("alpha")
			if alpha:
				existing_nodes[alpha] = alpha_values

			for frame in range(context.scene.frame_end + 1):
				context.scene.frame_set(frame)
				for node, curves in existing_nodes.items():
					for i, curve in enumerate(curves):
						if type(node.inputs[i].default_value) == float:
							value = node.inputs[i].default_value
							curve.append(NuccAnmKey.Float(value))


			
			# Value is a (track, track_index) tuple
			material_data_paths = {
				"u0_location": (u0_location, 0),
				"v0_location": (v0_location, 1),
				"u1_location": (u1_location, 2),
				"v1_location": (v1_location, 3),
				"u2_location": (u2_location, 4),
				"v2_location": (v2_location, 5),
   				"u3_location": (u3_location, 6),
				"v3_location": (v3_location, 7),
				"u0_scale": (u0_scale, 8),
				"v0_scale": (v0_scale, 9),
				"u1_scale": (u1_scale, 10),
				"v1_scale": (v1_scale, 11),
				"blend_rate1": (blend_rate1_values, 12),
				"blend_rate2": (blend_rate2_values, 13),
				"falloff": (falloff_values, 14),
				"glare": (glare_values, 15),
				"alpha": (alpha_values, 16),
				"outline_id": (alpha_values, 17),
				"u2_scale": (u2_scale, 18),
				"v2_scale": (v2_scale, 19),
				"u3_scale": (u3_scale, 20),
				"v3_scale": (v3_scale, 21),
			}


			# ------------------- entry -------------------
			clump_reference_index = struct_references.index(anm_armature.nucc_struct_references[0])
			clump_index = next((i for i, clump in enumerate(clumps) if clump.clump_index == clump_reference_index), None)

			material_reference_index = struct_references.index(NuccStructReference(material_name, NuccStructInfo(material_name, "nuccChunkMaterial", anm_armature.chunk_path)))
			material_index = next((i for i, material in enumerate(clumps[clump_index].bone_material_indices) if material == material_reference_index), None)

			entry = AnmEntry()
			entry.coord = AnmCoord(clump_index, material_index)
			entry.entry_format = EntryFormat.Material

			
			for _, (values, track_index) in material_data_paths.items():
				if values:
					create_and_append_track(entry, track_index, NuccAnmKeyFormat.FloatTable, values)
				else:
					# Create a single keyframe for fixed values using the xfbin material props
					if track_index == 4:
						create_and_append_track(entry, track_index, NuccAnmKeyFormat.FloatFixed, [NuccAnmKey.Float(0.0)])
			


			entries.append(entry)

		return entries



	def make_camera_entries(self, camera: bpy.types.Camera, other_index: int) -> List[AnmEntry]:
		entries: List[AnmEntry] = []
		
		if not camera.animation_data or not camera.animation_data.action:
			return entries

		sensor_width = camera.data.sensor_width
  
		cam_fcurves = {
			"location": [{}, {}, {}],
			"rotation_quaternion": [{}, {}, {}, {}],
			"rotation_euler": [{}, {}, {}],
			"lens": {}
		}
		
		location_frames: Set[int] = set()
		quat_frames: Set[int] = set()
		euler_frames: Set[int] = set()
		fov_frames: Set[int] = set()

		fcurve_mapping = {
			"location": (cam_fcurves["location"], location_frames),
			"rotation_quaternion": (cam_fcurves["rotation_quaternion"], quat_frames),
			"rotation_euler": (cam_fcurves["rotation_euler"], euler_frames),
			"lens": (cam_fcurves["lens"], fov_frames)
		}

		for fcurve in camera.animation_data.action.fcurves:
			for path, (target, frame_set) in fcurve_mapping.items():
				if fcurve.data_path.endswith(path):
					for kp in fcurve.keyframe_points:
						if isinstance(target, list):  # For multi-axis data
							target[fcurve.array_index][int(kp.co[0])] = kp.co[1]
						else:  # For single-axis data like lens
							target[int(kp.co[0])] = kp.co[1]
						frame_set.add(int(kp.co[0]))
					break

		def create_tracks(frame_values: Dict[int, List[float]], data_path, key_format, track_index, null_key_type):
			track_header = TrackHeader(track_index=track_index, key_format=key_format)
			track = Track()
			last_values = [0] * len(frame_values[next(iter(frame_values))])

			for frame, values in sorted(frame_values.items()):
				for i, val in enumerate(values):
					if val is not None:
						last_values[i] = val
				converted_value = convert_object_value(sensor_width, data_path, last_values, frame)
				track.keys.append(converted_value)

			if null_key_type == "Vec3Linear":
				null_key = NuccAnmKey.Vec3Linear(-1, track.keys[-1].values)
			elif null_key_type == "Vec4Linear":
				null_key = NuccAnmKey.Vec4Linear(-1, track.keys[-1].values)
			elif null_key_type == "FloatLinear":
				null_key = NuccAnmKey.FloatLinear(-1, track.keys[-1].values)
			else:
				raise ValueError("Unsupported null key type")

			track.keys.append(null_key)
			track_header.frame_count = len(track.keys)
			return track, track_header

		translations = {
			frame: [
				cam_fcurves["location"][i].get(frame, None) for i in range(3)
			] for frame in location_frames
		}

		quaternions = {
			frame: [
				cam_fcurves["rotation_quaternion"][i].get(frame, None) for i in range(4)
			] for frame in quat_frames
		}
  
		eulers = {
			frame: [
				cam_fcurves["rotation_euler"][i].get(frame, None) for i in range(3)
			] for frame in euler_frames
		}

		fov = {
			frame: [value] for frame, value in cam_fcurves["lens"].items()
		}

		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)
		entry.entry_format = EntryFormat.Camera

		if len(location_frames) > 1:
			track, header = create_tracks(translations, "location", NuccAnmKeyFormat.Vector3Linear, 0, "Vec3Linear")
			entry.tracks.append(track)
			entry.track_headers.append(header)

		if len(quat_frames) > 1:
			track, header = create_tracks(quaternions, "rotation_quaternion", NuccAnmKeyFormat.QuaternionLinear, 1, "Vec4Linear")
			entry.tracks.append(track)
			entry.track_headers.append(header)
   
		if len(euler_frames) > 1:
			track, header = create_tracks(eulers, "rotation_euler", NuccAnmKeyFormat.QuaternionLinear, 1, "Vec4Linear")
			entry.tracks.append(track)
			entry.track_headers.append(header)

		if len(fov_frames) > 1:
			track, header = create_tracks(fov, "fov", NuccAnmKeyFormat.FloatLinear, 2, "FloatLinear")
			entry.tracks.append(track)
			entry.track_headers.append(header)

		entries.append(entry)
		return entries

	

	def make_lightdirc_entries(self, lightdirc: bpy.types.Light, other_index: int) -> List[AnmEntry]:
		entries: List[AnmEntry] = []

		light_start, light_end = 0, 0
		rot_start, rot_end = 0, 0
  
		combined_fcurves = []

		
		if lightdirc.data.animation_data:
			if lightdirc.data.animation_data.action:
				light_start, light_end = lightdirc.data.animation_data.action.frame_range
				combined_fcurves += lightdirc.data.animation_data.action.fcurves
		
		if lightdirc.animation_data.action:
			combined_fcurves += lightdirc.animation_data.action.fcurves

			rotation_action = lightdirc.animation_data.action
  
			rot_start, rot_end = rotation_action.frame_range
   
		if len(combined_fcurves) < 1:
			return entries
  
		#check which action has more frames
		frame_end = max(rot_end, light_end)

		context = bpy.context
		light_fcurves = {
			"color": [{}, {}, {}],
			"energy": [{}],
			"rotation_euler": [{}, {}, {}, {}],
			"rotation_quaternion": [{}, {}, {}, {}]
		}

		color_frames: Set[int] = set()
		energy_frames: Set[int] = set()
		rotation_euler_frames: Set[int] = set()
		rotation_quat_frames: Set[int] = set()

		fcurve_mapping = {
			"color": (light_fcurves["color"], color_frames),
			"energy": (light_fcurves["energy"], energy_frames),
			"rotation_euler": (light_fcurves["rotation_euler"], rotation_euler_frames),
			"rotation_quaternion": (light_fcurves["rotation_quaternion"], rotation_quat_frames)
		}

		for fcurve in combined_fcurves:
			for path, (target, frame_set) in fcurve_mapping.items():
				if fcurve.data_path.endswith(path):
					for i in range(int(frame_end + 1)):
						light_fcurves[path][fcurve.array_index][i] = fcurve.evaluate(i)
						frame_set.add(i)
					break
		
		

		def create_light_tracks(frame_values: Dict[int, List[float]], data_path, key_format, track_index):
			track_header = TrackHeader(track_index=track_index, key_format=key_format)
			track = Track()
			last_values = [0] * len(frame_values[next(iter(frame_values))])

			for frame, values in sorted(frame_values.items()):
				for i, val in enumerate(values):
					if val is not None:
						last_values[i] = val
				converted_value = convert_light_values(data_path, last_values, key_format)
				track.keys.append(converted_value)

			#dupe last keyframe
			converted_value = convert_light_values(data_path, last_values)
			track.keys.append(converted_value)

			track_header.frame_count = len(track.keys)
			return track, track_header

		def create_single_frame_track(data_path, key_format, track_index, value):
			single_track_header = TrackHeader(track_index=track_index, key_format=key_format)
			single_track = Track()
			converted_value = convert_light_values(data_path, value, key_format)
			single_track.keys.append(converted_value)
			single_track_header.frame_count = 1
			return single_track, single_track_header

		colors = {frame: [light_fcurves["color"][i].get(frame, None) for i in range(3)] for frame in color_frames}

		energies = {frame: [light_fcurves["energy"][0].get(frame, None)] for frame in energy_frames}

		rotations_euler = {
			frame: [
				light_fcurves["rotation_euler"][i].get(frame, None) for i in range(3)
			] for frame in rotation_euler_frames
		}
  
		rotations_quat = {
			frame: [
				light_fcurves["rotation_quaternion"][i].get(frame, None) for i in range(4)
			] for frame in rotation_quat_frames
		}
  


		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)
		entry.entry_format = EntryFormat.LightDirc

		if len(color_frames) >= 1:
			track, header = create_light_tracks(colors, "color", NuccAnmKeyFormat.ColorRGBTable, 0)
			entry.tracks.append(track)
			entry.track_headers.append(header)
		else:
			# create a single keyframe and take the default value
			track = Track()
			track_header = TrackHeader()
			track_header.track_index = 0
			track_header.key_format = NuccAnmKeyFormat.ColorRGBTable
			
			for i in range(int(frame_end + 2)):
				converted_value = convert_light_values("color", lightdirc.data.color)
				track.keys.append(converted_value)
   
			track_header.frame_count = len(track.keys)
			entry.tracks.append(track)
			entry.track_headers.append(track_header)
   
		if len(energy_frames) >= 1:
			track, header = create_light_tracks(energies, "energy", NuccAnmKeyFormat.FloatTable, 1)
			entry.tracks.append(track)
			entry.track_headers.append(header)
		else:
			# create a single keyframe and take the default value
			track, header = create_single_frame_track("energy", NuccAnmKeyFormat.FloatFixed, 1, [lightdirc.data.energy])
			entry.tracks.append(track)
			entry.track_headers.append(header)
   

		if len(rotation_quat_frames) >= 1:
			track, header = create_light_tracks(rotations_quat, "rotation_quaternion", NuccAnmKeyFormat.QuaternionShortTable, 2)
			entry.tracks.append(track)
			entry.track_headers.append(header)

		elif len(rotation_euler_frames) >= 1:
			track, header = create_light_tracks(rotations_euler, "rotation_euler", NuccAnmKeyFormat.QuaternionShortTable, 2)
			entry.tracks.append(track)
			entry.track_headers.append(header)
		else:
			# create a single keyframe and take the default value
			track = Track()
			track_header = TrackHeader()
			track_header.track_index = 2
			track_header.key_format = NuccAnmKeyFormat.EulerXYZFixed
			
			converted_value = NuccAnmKey.Vec3(tuple(math.radians(x) for x in lightdirc.matrix_world.to_euler()))
			track.keys.append(converted_value)
   
			track_header.frame_count = len(track.keys)
			entry.tracks.append(track)
			entry.track_headers.append(track_header)


		entries.append(entry)
		return entries


	def make_lightpoint_entries(self, lightpoint: bpy.types.Light, other_index: int) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		colors: List[Vector] = list()
		energies: List[float] = list()
		translations: List[Vector] = list()
		radii: List[float] = list()
		cutoffs: List[float] = list()

		# Get the light's color, energy, location, radius, and cutoff for each frame
		for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
			# Last sanity check to see if camera has animation data
			if not lightpoint.animation_data:
				continue

			context.scene.frame_set(frame)

			colors.append(lightpoint.data.color.copy())
			energies.append(lightpoint.data.energy)
			translations.append(lightpoint.matrix_world.to_translation().copy())
			radii.append(lightpoint.data.shadow_soft_size)
			cutoffs.append(lightpoint.data.cutoff_distance if lightpoint.data.use_custom_distance else 0.0)
		

		# ------------------- entry -------------------
		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)
		entry.entry_format = EntryFormat.LightPoint

		# ------------------- color -------------------
		color_track_header = TrackHeader()
		color_track = Track()

		for value in colors:
			color_track_header.track_index = 0
			color_track_header.key_format = NuccAnmKeyFormat.ColorRGBTable
			color_track_header.frame_count = len(colors)

			converted_value: NuccAnmKey = convert_object_value("color", list(map(lambda x: round(x, 2), value[:])))

			color_track.keys.append(converted_value)
		
		
		# Pad color_track.keys with the last value so the length is a multiple of 4
		while len(color_track.keys) % 4 != 0:
			color_track.keys.append(color_track.keys[-1])

		# Update the frame count to reflect the new length
		color_track_header.frame_count = len(color_track.keys)

		entry.tracks.append(color_track)
		entry.track_headers.append(color_track_header)

		# ------------------- energy -------------------
		energy_track_header = TrackHeader()
		energy_track = Track()

		for value in energies:
			energy_track_header.track_index = 1
			energy_track_header.key_format = NuccAnmKeyFormat.FloatTable
			energy_track_header.frame_count = len(energies)

			energy_track.keys.append(NuccAnmKey.Float(value))

		entry.tracks.append(energy_track)
		entry.track_headers.append(energy_track_header)

		# ------------------- location -------------------
		location_track_header = TrackHeader()
		location_track = Track()

		for frame, value in enumerate(translations):
			location_track_header.track_index = 2
			location_track_header.key_format = NuccAnmKeyFormat.Vector3Linear
			location_track_header.frame_count = len(translations) + 1

			converted_value: NuccAnmKey = convert_object_value("location", value[:], frame)

			location_track.keys.append(converted_value)
		
		null_key = NuccAnmKey.Vec3Linear(-1, location_track.keys[-1].values)
		location_track.keys.append(null_key)

		entry.tracks.append(location_track)
		entry.track_headers.append(location_track_header)

		# ------------------- radius -------------------
		radius_track_header = TrackHeader()
		radius_track = Track()

		for value in radii:
			radius_track_header.track_index = 3
			radius_track_header.key_format = NuccAnmKeyFormat.FloatTable
			radius_track_header.frame_count = len(radii)

			radius_track.keys.append(NuccAnmKey.Float(value))

		entry.tracks.append(radius_track)
		entry.track_headers.append(radius_track_header)

		# ------------------- cutoff -------------------
		cutoff_track_header = TrackHeader()
		cutoff_track = Track()

		for value in cutoffs:
			cutoff_track_header.track_index = 4
			cutoff_track_header.key_format = NuccAnmKeyFormat.FloatTable
			cutoff_track_header.frame_count = len(cutoffs)

			cutoff_track.keys.append(NuccAnmKey.Float(value))

		entry.tracks.append(cutoff_track)
		entry.track_headers.append(cutoff_track_header)

		entries.append(entry)


		return entries

	def make_ambient_entries(self, ambient: bpy.types.Light, other_index: int) -> List[AnmEntry]:
		context = bpy.context

		entries: List[AnmEntry] = list()

		colors: List[Vector] = list()
		energies: List[float] = list()

		# Get the light's color and energy for each frame
		for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
			# Last sanity check to see if camera has animation data
			if not ambient.animation_data:
				continue

			context.scene.frame_set(frame)

			colors.append(ambient.data.color.copy())
			energies.append(ambient.data.energy)

		# ------------------- entry -------------------
		entry = AnmEntry()
		entry.coord = AnmCoord(-1, other_index)

		entry.entry_format = EntryFormat.Ambient

		# ------------------- color -------------------
		color_track_header = TrackHeader()
		color_track = Track()

		for value in colors:
			color_track_header.track_index = 0
			color_track_header.key_format = NuccAnmKeyFormat.ColorRGBTable
			color_track_header.frame_count = len(colors)

			converted_value: NuccAnmKey = convert_object_value("color", list(map(lambda x: round(x, 2), value[:])))

			color_track.keys.append(converted_value)
		
		# Pad color_track.keys with the last value so the length is a multiple of 4
		while len(color_track.keys) % 4 != 0:
			color_track.keys.append(color_track.keys[-1])

		# Update the frame count to reflect the new length
		color_track_header.frame_count = len(color_track.keys)

		entry.tracks.append(color_track)
		entry.track_headers.append(color_track_header)


		# ------------------- energy -------------------
		energy_track_header = TrackHeader()
		energy_track = Track()

		for value in energies:
			energy_track_header.track_index = 1
			energy_track_header.key_format = NuccAnmKeyFormat.FloatTable
			energy_track_header.frame_count = len(energies)

			energy_track.keys.append(NuccAnmKey.Float(value))
		
		entry.tracks.append(energy_track)
		entry.track_headers.append(energy_track_header)

		entries.append(entry)


		return entries


		
def menu_export(self, context):
	self.layout.operator(ExportAnmXfbin.bl_idname, text='XFBIN Animation Container (.xfbin)') 