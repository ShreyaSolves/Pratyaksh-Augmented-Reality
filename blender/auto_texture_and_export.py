# blender/auto_texture_and_export.py
# Usage:
# blender -b --python blender/auto_texture_and_export.py -- --in outputs/model.glb --out outputs/model_textured.glb
# Optional albedo image blended with vertex colors:
# blender -b --python blender/auto_texture_and_export.py -- --in outputs/model.glb --out outputs/model_textured.glb --albedo textures/fabric.jpg --mix 0.6

import bpy, sys, argparse, os

# -------- arg parsing (after the -- passed to Blender) ----------
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--")+1:]
else:
    argv = []
parser = argparse.ArgumentParser()
parser.add_argument("--in", dest="in_path", required=True, help="Input .glb/.gltf")
parser.add_argument("--out", dest="out_path", required=True, help="Output .glb")
parser.add_argument("--albedo", dest="albedo_path", default=None, help="Optional image to blend into Base Color")
parser.add_argument("--mix", dest="mix_strength", type=float, default=0.5, help="0..1: weight of albedo over vertex colors")
args = parser.parse_args(argv)

# -------- fresh scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)

# -------- import glTF ----------
in_path = os.path.abspath(args.in_path)
assert os.path.isfile(in_path), f"Not found: {in_path}"
bpy.ops.import_scene.gltf(filepath=in_path)

# -------- collect mesh objects ----------
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise RuntimeError("No mesh objects found after import.")

# -------- build or reuse a material ----------
def first_color_attr(obj):
    # Find first color attribute (vertex colors) on mesh
    me = obj.data
    if hasattr(me, "color_attributes") and me.color_attributes:
        return me.color_attributes[0].name
    # Legacy name sometimes appears as "Col"
    return "Col"

# Create one shared material
mat = bpy.data.materials.new("AutoMat")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)

# Nodes
out = nt.nodes.new("ShaderNodeOutputMaterial")
out.location = (500, 0)
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (250, 0)
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

# Vertex Color attribute node
attr = nt.nodes.new("ShaderNodeAttribute")
attr.location = (0, 100)
attr.attribute_name = "COLOR_0"  # glTF default; we'll update per-mesh if needed

# Optional Image Texture
mix_node = None
if args.albedo_path and os.path.isfile(args.albedo_path):
    img = bpy.data.images.load(os.path.abspath(args.albedo_path))
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.location = (0, -150)

    mix_node = nt.nodes.new("ShaderNodeMixRGB")
    mix_node.blend_type = 'MIX'
    mix_node.inputs[0].default_value = max(0.0, min(1.0, args.mix_strength))
    mix_node.location = (120, -20)

    # VertexColor -> Mix Color1, Albedo -> Mix Color2 -> BSDF Base Color
    nt.links.new(attr.outputs["Color"], mix_node.inputs["Color1"])
    nt.links.new(tex.outputs["Color"], mix_node.inputs["Color2"])
    nt.links.new(mix_node.outputs["Color"], bsdf.inputs["Base Color"])
else:
    # VertexColor -> Base Color
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])

# Slightly increase roughness for softer look
bsdf.inputs["Roughness"].default_value = 0.8

# -------- assign material, set correct vertex color attribute, smooth, UV unwrap ----------
for obj in meshes:
    # Assign material
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    # Ensure the Attribute node points to existing color layer if present
    ca_name = first_color_attr(obj)
    # Duplicate node tree per-object so we can set attribute name independently
    obj_mat = mat.copy()
    obj.data.materials[0] = obj_mat
    obj_nt = obj_mat.node_tree
    attr_nodes = [n for n in obj_nt.nodes if n.type == "ATTRIBUTE"]
    if attr_nodes:
        attr_nodes[0].attribute_name = ca_name

    # Shade smooth
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
