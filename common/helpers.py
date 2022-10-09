
from typing import List, Dict


def make_chunk_dict(path: str, chunk_name: str, chunk_type: str, clump=None, reference=True, file=True):
	"""
	Create chunk map and chunk reference dictionaries.
	"""
	if clump is not None:
		chunk_name = clump.name

	# Map Chunk
	chunk = dict()
	chunk["Name"] = chunk_name
	chunk["Type"] = chunk_type
	chunk["Path"] = path

	
	if clump is not None:
		chunk_name = clump.models[0]

	# Reference Chunk
	chunk_ref = dict()
	chunk_ref["Name"] = chunk_name
	chunk_ref["Chunk"]: Dict = chunk
	
	if reference:
		return chunk, chunk_ref

	# File Chunk
	filename = ""

	if file:
		if chunk_type == "nuccChunkAnm":
			filename = chunk_name + '.anm'
	
		if chunk_type == "nuccChunkCamera":
			filename = chunk_name + '.camera'

		# File Chunk
		chunk_file = dict()
		chunk_file["File Name"] = filename
		chunk_file["Chunk"]: Dict = chunk

		return chunk_file
	
	else:
		return chunk