import argparse
import os
import numpy as np
import cv2
import trimesh

def img_to_heightmap_mesh(
    img_path: str,
    out_glb_path: str = "outputs/model.glb",
    target_width: int = 256,
    target_height: int = 256,
    z_scale: float = 0.1,
    invert: bool = False,
    blur_ksize: int = 3
):
    # load
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {img_path}")

    # resize
    img = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_AREA)

    # optional denoise/blur so mesh is smoother
    if blur_ksize > 0:
        img = cv2.GaussianBlur(img, (blur_ksize | 1, blur_ksize | 1), 0)

    # normalize to [0,1]
    depth = img.astype(np.float32) / 255.0
    if invert:
        depth = 1.0 - depth

    # scale to z
    z = depth * z_scale

    h, w = z.shape
    # create grid in x,y
    xs = np.linspace(-0.5, 0.5, w, dtype=np.float32)
    ys = np.linspace(-0.5, 0.5, h, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)

    # vertices (flattened)
    verts = np.column_stack([X.ravel(), -Y.ravel(), z.ravel()])  # -Y so "up" feels natural

    # faces: two tris per quad
    faces = []
    for r in range(h - 1):
        for c in range(w - 1):
            i0 = r * w + c
            i1 = r * w + (c + 1)
            i2 = (r + 1) * w + c
            i3 = (r + 1) * w + (c + 1)
            faces.append([i0, i2, i1])
            faces.append([i1, i2, i3])
    faces = np.array(faces, dtype=np.int64)

    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)

    # simple vertex colors from grayscale
    colors = np.repeat((depth.ravel() * 255).astype(np.uint8)[:, None], 3, axis=1)
    mesh.visual.vertex_colors = np.hstack([colors, np.full((colors.shape[0], 1), 255, dtype=np.uint8)])

    os.makedirs(os.path.dirname(out_glb_path), exist_ok=True)
    mesh.export(out_glb_path)  # writes .glb
    return out_glb_path

def main():
    parser = argparse.ArgumentParser(description="Convert 2D image to heightmap .glb mesh")
    parser.add_argument("--input", "-i", required=True, help="Path to input image (jpg/png)")
    parser.add_argument("--output", "-o", default="outputs/model.glb", help="Path to output .glb")
    parser.add_argument("--width", type=int, default=256, help="Target mesh width in pixels")
    parser.add_argument("--height", type=int, default=256, help="Target mesh height in pixels")
    parser.add_argument("--z-scale", type=float, default=0.12, help="Vertical exaggeration")
    parser.add_argument("--invert", action="store_true", help="Invert depth mapping")
    parser.add_argument("--blur", type=int, default=3, help="Gaussian blur kernel size (odd int, 0=off)")
    args = parser.parse_args()

    out = img_to_heightmap_mesh(
        img_path=args.input,
        out_glb_path=args.output,
        target_width=args.width,
        target_height=args.height,
        z_scale=args.z_scale,
        invert=args.invert,
        blur_ksize=args.blur
    )
    print(f"✅ Exported: {out}")

if __name__ == "__main__":
    main()
