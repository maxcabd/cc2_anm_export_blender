from bpy.types import Armature, Bone, Action
from typing import List

from ...xfbin.xfbin_lib import NuccStructInfo, NuccStructReference


class AnmArmature:
	armature: Armature

	def __init__(self, arm_obj):
		self.armature = arm_obj
	
	@property
	def name(self) -> str:
		if ' [C]' in self.armature.name:
			return self.armature.name.removesuffix(' [C]')
		else:
			return self.armature.name

	@property
	def chunk_path(self) -> str:
		return self.armature.xfbin_clump_data.path
	
	@property
	def action(self) -> Action:
		return self.armature.animation_data.action
	

	@property
	def anm_bones(self) -> List[Bone]:
		"""
		Return the bones displayed in the Action channels. 
		"""
		action = self.armature.animation_data.action
		anm_bones = list()

		for curve in action.fcurves:
			data_path = curve.data_path.rpartition('.')[0]
			if (data_path is not ""):
				bone = self.armature.path_resolve(data_path)
				anm_bones.append(bone)

		return list(dict.fromkeys(anm_bones)) # Get unique keys and return as list
	
	@property
	def bones(self) -> List[str]:
		bones = self.armature.data.bones

		return [bone.name for bone in bones  if not 'lod' in bone.name]
	

	@property
	def materials(self) -> List[str]:
		materials = self.armature.xfbin_clump_data.materials

		return sorted([mat.name for mat in materials if not 'lod' in mat.name])
		
	@property
	def models(self) -> List[str]:
		models = self.armature.xfbin_clump_data.models
		
		return [model.name for model in models if not 'lod' in model.name]
	
	@property
	def nucc_struct_infos(self) -> List[NuccStructInfo]:
		struct_infos: List[NuccStructInfo] = list()

		coord_infos: List[NuccStructInfo] = list()
		model_infos: List[NuccStructInfo] = list()
		mat_infos: List[NuccStructInfo] = list()


		clump_info = NuccStructInfo(self.name, "nuccChunkClump", self.chunk_path)

		for bone in self.bones:
			coord_info = NuccStructInfo(bone, "nuccChunkCoord", self.chunk_path)
			coord_infos.append(coord_info)

		for model in self.models:
			model_info = NuccStructInfo(model, "nuccChunkModel", self.chunk_path)
			model_infos.append(model_info)

		for mat in self.materials:
			mat_info = NuccStructInfo(mat, "nuccChunkMaterial", self.chunk_path)
			mat_infos.append(mat_info)

	
		struct_infos.extend([clump_info, *coord_infos, *model_infos, *mat_infos])

		return struct_infos


		

	@property
	def nucc_struct_references(self) -> List[NuccStructReference]:
		"""
		Return list of NuccStructReference objects that reference the armature's bones, models, materials, etc for animation.
		"""
		struct_references: List[NuccStructReference] = list()

		coord_references: List[NuccStructReference] = list()
		model_references: List[NuccStructReference] = list()
		mat_references: List[NuccStructReference] = list()

		for bone in self.bones:
			coord_info = [x for x in self.nucc_struct_infos if x.chunk_name == bone and x.chunk_type == "nuccChunkCoord"][0]
			coord_references.append(NuccStructReference(bone, coord_info))

		for model in self.models:
			model_info = [x for x in self.nucc_struct_infos if x.chunk_name == model and x.chunk_type == "nuccChunkModel"][0]
			model_references.append(NuccStructReference(model, model_info))
		
		for mat in self.materials:
			mat_info = [x for x in self.nucc_struct_infos if x.chunk_name == mat and x.chunk_type == "nuccChunkMaterial"][0]
			mat_references.append(NuccStructReference(mat, mat_info))
		


		clump_info = [x for x in self.nucc_struct_infos if x.chunk_name == self.name][0]

		if self.models:
			clump_reference = NuccStructReference(self.models[0], clump_info)
			

		else:
			clump_reference = NuccStructReference(self.bones[0], clump_info)
			

		struct_references.extend([clump_reference, *coord_references, *model_references, *mat_references])

		return struct_references		