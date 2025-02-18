import importlib.util

blender_loader = importlib.util.find_spec('bpy')

bl_info = {
    "name": "CyberConnect2 ANM XFBIN File Export",
    "author": "Dei, TheLeonX, Al-Hydra",
    "version": (1, 0, 5),
    "blender": (4, 2, 0),
    "location": "File > Export",
    "description": "Export XFBIN animation files found in CyberConnect2 Naruto Storm and JoJo games.",
    "warning": "",
    "category": "Export",
}

if blender_loader:
    from .blender.addon import *
