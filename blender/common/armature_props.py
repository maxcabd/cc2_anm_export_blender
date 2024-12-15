import bpy
from functools import lru_cache

from bpy.types import Armature, Bone, Action
from typing import List

from ...xfbin.xfbin_lib import NuccStructInfo, NuccStructReference


class AnmArmature:
    def __init__(self, arm_obj: Armature):
        self.armature = arm_obj
        self.name = arm_obj.name
        self.chunk_path = arm_obj.xfbin_clump_data.path
        self.action = arm_obj.animation_data.action
        self.bones = list(arm_obj.data.bones)
        self.models = list(self._get_models())
        self.materials = list(self._get_materials())
        self.anm_bones = self._get_anm_bones(self)

        self.nucc_struct_infos = AnmArmatureInfo(self)

    @staticmethod
    @lru_cache(maxsize=None)
    def _get_anm_bones(self) -> List[Bone]:
        """Return the bones displayed in the Action channels."""
        return list({curve.data_path.rpartition('.')[0] for curve in self.action.fcurves})

    def _get_models(self) -> List[str]:
        """Get models attached to the armature."""
        return (model.name for model in self.armature.children if 'lod' not in model.name)

    def _get_materials(self) -> List[str]:
        """Get materials from the armature's models."""
        return {
            slot.material.name
            for model in self.models
            for slot in bpy.data.objects[model].material_slots
        }

    @property
    @lru_cache(maxsize=None)
    def nucc_struct_references(self) -> List[NuccStructReference]:
        """Get NuccStructReferences."""
        coord_references = [NuccStructReference(bone.name, self.nucc_struct_infos.coord_infos[bone])
                            for bone in self.bones]
        mat_references = [NuccStructReference(mat, self.nucc_struct_infos.mat_infos[mat])
                          for mat in self.materials]
        model_references = [NuccStructReference(model, self.nucc_struct_infos.model_infos[model])
                            for model in self.models]

        clump_reference = NuccStructReference(
            self.models[0] if self.models else self.bones[0].name,
            self.nucc_struct_infos.clump_info
        )
        return [clump_reference, *coord_references, *mat_references, *model_references]



class AnmArmatureInfo:
    def __init__(self, armature: AnmArmature):
        self.clump_info = NuccStructInfo(armature.name, "nuccChunkClump", armature.chunk_path)
        self.coord_infos = {bone : NuccStructInfo(bone.name, "nuccChunkCoord", armature.chunk_path) for bone in armature.bones}
        self.model_infos = {model : NuccStructInfo(model, "nuccChunkModel", armature.chunk_path) for model in armature.models}
        self.mat_infos = {mat : NuccStructInfo(mat, "nuccChunkMaterial", armature.chunk_path) for mat in armature.materials}
    
    def get_armature_info(self):
        return [self.clump_info, *self.coord_infos.values(), *self.model_infos.values(), *self.mat_infos.values()]