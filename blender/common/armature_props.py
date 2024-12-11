import bpy
from functools import lru_cache

from bpy.types import Armature, Bone, Action
from typing import List

from ...xfbin.xfbin_lib import NuccStructInfo, NuccStructReference


class AnmArmature:
    armature: Armature

    def __init__(self, arm_obj: Armature):
        self.armature = arm_obj
        self.name = arm_obj.name
        self.chunk_path = arm_obj.xfbin_clump_data.path
        self.action = arm_obj.animation_data.action
        self.anm_bones = self.get_anm_bones()
        self.models = self.get_models()
        self.bones = list(arm_obj.data.bones)
        self.materials = self.get_materials()
        
        self.nucc_struct_infos = AnmArmatureInfo(self)


    def get_anm_bones(self) -> List[Bone]:
        """
        Return the bones displayed in the Action channels.
        """
        action = self.armature.animation_data.action

        anm_bones = {}

        for curve in action.fcurves:
            if curve.data_path.rpartition('.')[0]:
                anm_bones[curve.data_path.rpartition(
                    '.')[0]] = curve.data_path.rpartition('.')[0]
        return list(anm_bones)

    def get_models(self) -> List[str]:
        models = [
            model.name for model in self.armature.children if 'lod' not in model.name]
        return models

    def get_materials(self) -> List[str]:
        materials = {
            slot.material.name
            for model in self.models
            for slot in bpy.data.objects[model].material_slots
        }
        return list(materials)


    @property
    @lru_cache(maxsize=None)
    def nucc_struct_references(self) -> List[NuccStructReference]:
        """
        Return list of NuccStructReference objects that reference the armature's bones, models, materials, etc for animation.
        """
        struct_references: List[NuccStructReference] = list()
        
        coord_infos = self.nucc_struct_infos.coord_infos
        mat_infos = self.nucc_struct_infos.mat_infos
        model_infos = self.nucc_struct_infos.model_infos
        clump_info = self.nucc_struct_infos.clump_info
        
        coord_references = [NuccStructReference(bone.name, coord_infos[bone]) for bone in self.bones]
        mat_references = [NuccStructReference(mat, mat_infos[mat]) for mat in self.materials]
        model_references = [NuccStructReference(model, model_infos[model]) for model in self.models]
        
        if self.models:
            clump_reference = NuccStructReference(self.models[0], clump_info)
        else:
            clump_reference = NuccStructReference(self.bones[0].name, clump_info)
        struct_references.extend([clump_reference, *coord_references, *mat_references, *model_references])
        return struct_references

    def make_extra_clump_references(self, reference_anm_armature: Armature, reference_anm_armature_name: str) -> List[NuccStructReference]:
        struct_references: List[NuccStructReference] = list()
        coord_references: List[NuccStructReference] = list()
        model_references: List[NuccStructReference] = list()
        mat_references: List[NuccStructReference] = list()

        for bone in self.bones:
            coord_info = [x for x in reference_anm_armature.nucc_struct_infos if x.chunk_name == bone and x.chunk_type == "nuccChunkCoord"][0]
            coord_references.append(NuccStructReference(bone, coord_info))

        for mat in self.materials:
            mat_info = [x for x in reference_anm_armature.nucc_struct_infos if x.chunk_name == mat and x.chunk_type == "nuccChunkMaterial"][0]
            mat_references.append(NuccStructReference(mat, mat_info))

        for model in self.models:
            model_info = [x for x in reference_anm_armature.nucc_struct_infos if x.chunk_name == model and x.chunk_type == "nuccChunkModel"][0]
            model_references.append(NuccStructReference(model, model_info))

        clump_info = [x for x in reference_anm_armature.nucc_struct_infos if x.chunk_name ==
                      reference_anm_armature.name][0]

        if reference_anm_armature.models:
            clump_reference = NuccStructReference(
                reference_anm_armature.models[0], clump_info)
        else:
            clump_reference = NuccStructReference(
                reference_anm_armature.bones[0], clump_info)

        struct_references.extend(
            [clump_reference, *coord_references, *mat_references, *model_references])

        return struct_references


class AnmArmatureInfo:
    def __init__(self, armature: AnmArmature):
        self.clump_info = NuccStructInfo(armature.name, "nuccChunkClump", armature.chunk_path)
        self.coord_infos = {bone : NuccStructInfo(bone.name, "nuccChunkCoord", armature.chunk_path) for bone in armature.bones}
        self.model_infos = {model : NuccStructInfo(model, "nuccChunkModel", armature.chunk_path) for model in armature.models}
        self.mat_infos = {mat : NuccStructInfo(mat, "nuccChunkMaterial", armature.chunk_path) for mat in armature.materials}
    
    def get_armature_info(self):
        return [self.clump_info, *self.coord_infos.values(), *self.model_infos.values(), *self.mat_infos.values()]