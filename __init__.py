import importlib.util

blender_loader = importlib.util.find_spec('bpy')

bl_info = {
    "name": "CyberConnect2 ANM XFBIN File Export",
    "author": "Dei, TheLeonX",
    "version": (1, 0, 1),
    "blender": (3, 6, 0),
    "location": "File > Export",
    "description": "Export XFBIN animation files found in CyberConnect2 Naruto Storm and JoJo games.",
    "warning": "",
    "category": "Export",
}

if blender_loader:
    from .blender.addon import *