# Auto-Rigging Pipeline

---

# Table of Contents

1. [Fundamentals](#1-fundamentals)
2. [Codebase Architecture](#2-codebase-architecture)
3. [Humanoid Auto-Rigging Pipeline](#3-humanoid-auto-rigging-pipeline)
4. [Quadruped Auto-Rigging Pipeline](#4-quadruped-auto-rigging-pipeline)
5. [Mathematical Foundations](#5-mathematical-foundations)
6. [Skinning Theory](#6-skinning-theory)
7. [Practical Examples](#7-practical-examples)

---

# 1. Fundamentals

## 1.1 What Is a Mesh?

A **mesh** is the 3D shape of a character or object. It is made of three building blocks:

- **Vertices (points):** Individual points in 3D space, each defined by coordinates `(x, y, z)`.
- **Edges:** Lines connecting two vertices.
- **Faces (polygons):** Flat surfaces enclosed by three or more edges (usually triangles or quads).

```
    Vertex A (0, 1, 0)
       /\
      /  \
     /    \       ← This triangle is one "face"
    /______\
Vertex B    Vertex C
(−1,0,0)    (1, 0, 0)
```

A humanoid character mesh might contain 5,000–100,000 vertices. Each vertex stores its position in **world space** — a global coordinate system where:

| Axis | Direction (This Codebase) |
| ---- | ------------------------- |
| X    | Left ↔ Right              |
| Y    | Front ↔ Back              |
| Z    | Down ↔ Up (height)        |

### Bounding Box

A **bounding box** is the smallest axis-aligned box that completely encloses the mesh. It gives us quick measurements:

```
        ┌─────────────┐ ← max (x_max, y_max, z_max)
       /|            /|
      / |           / |
     /  |          /  |   height = z_max − z_min
    ┌─────────────┐   |   width  = x_max − x_min
    |   |         |   |   depth  = y_max − y_min
    |   └─────────|───┘
    |  /          |  /
    | /           | /
    └─────────────┘ ← min (x_min, y_min, z_min)
```

**In our code** (`common/mesh_utils.py`):

```python
def get_world_bbox(obj):
    world_pts = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [p.x for p in world_pts]
    ys = [p.y for p in world_pts]
    zs = [p.z for p in world_pts]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))
```

`obj.matrix_world` is a 4×4 transformation matrix that converts the object's local coordinates into world coordinates.

---

## 1.2 What Is a Skeleton / Armature?

A **skeleton** (called **armature** in Blender) is an invisible structure placed inside the mesh that controls how it moves. Think of it like the bones inside a puppet — when you move a bone, the mesh deforms around it.

```
           [Head]
             |
           [Neck]
             |
  [L.Arm]─[Chest]─[R.Arm]
             |
           [Spine]
             |
           [Hips]
          /      \
     [L.Leg]     [R.Leg]
        |          |
    [L.Foot]    [R.Foot]
```

---

## 1.3 Bones and Joints

A **bone** is a rigid segment defined by two points:

- **Head:** The starting point (closer to the body's root)
- **Tail:** The ending point

A **joint** is the connection point between two bones (where one bone's tail meets the next bone's head).

```
  Head ●━━━━━━━━━━━● Tail/Head ●━━━━━━━━━━━● Tail
       upper_arm          ↑          forearm
                        Joint
                      (elbow)
```

Bones form a **parent-child hierarchy**. When a parent bone moves, all its children move with it. This is called **forward kinematics**.

---

## 1.4 Rigging vs. Skinning

| Concept      | What It Does                                                                         | Analogy                                    |
| ------------ | ------------------------------------------------------------------------------------ | ------------------------------------------ |
| **Rigging**  | Creating the skeleton and placing bones inside the mesh                              | Building a puppet's internal frame         |
| **Skinning** | Connecting each mesh vertex to one or more bones so the mesh deforms when bones move | Attaching the puppet's fabric to its frame |

**Rigging** comes first (build the skeleton), then **skinning** connects the mesh to it.

---

## 1.5 Forward Kinematics (FK) vs. Inverse Kinematics (IK)

### Forward Kinematics (FK)

You rotate each bone manually, starting from the root. The final position of the end effector (e.g., hand) is **calculated** from all the rotations above it.

```
Shoulder rotates 30° → Elbow rotates 45° → Wrist ends up at position P
```

### Inverse Kinematics (IK)

You specify WHERE the end effector should be, and the algorithm **calculates** the rotations of all bones in the chain to reach that target.

```
"Put the hand at position P" → Algorithm solves shoulder and elbow angles
```

**In this codebase**, the `solve_two_bone_ik()` function in `common/fitting_utils.py` uses analytical 2-bone IK to calculate the position of middle joints (elbows and knees) given the start and end positions of a limb chain.

---

## 1.6 Vertex Weights

A **vertex weight** is a number between 0.0 and 1.0 that determines how much a specific bone influences a specific vertex.

- Weight `1.0` = the vertex follows that bone 100%
- Weight `0.5` = the vertex follows that bone 50%
- Weight `0.0` = the bone has no effect on this vertex

Each vertex can be influenced by multiple bones. All weights for a vertex must sum to 1.0 (**weight normalization**).

```
Example: Vertex near the elbow
  upper_arm bone: weight = 0.4  (40% influence)
  forearm bone:   weight = 0.6  (60% influence)
  Total:                    1.0  ✓ (normalized)
```

### Weight Normalization Formula

Given raw weights `w₁, w₂, ..., wₙ` for a vertex:

```
normalized_wᵢ = wᵢ / (w₁ + w₂ + ... + wₙ)

Example: w1 = 0.3, w2 = 0.5 w3 = 0.4
  w_total = 0.3 + 0.5 + 0.4 = 1.2
  w1_normalized = 0.3 / 1.2 = 0.250
  w2_normalized = 0.5 / 1.2 = 0.417
  w3_normalized = 0.4 / 1.2 = 0.333
  w_total_normalized = 0.250 + 0.417 + 0.333 = 1.0
```

---

## 1.7 Coordinate Systems and Transformations

### World Space vs. Local Space

- **World space:** The global coordinate system. All objects share it.
- **Local space:** Each object has its own origin and orientation.

To convert between them, we use the object's **transformation matrix** (`matrix_world`), a 4×4 matrix:

```
┌                         ┐
│ Rx·Sx  Ry·Sx  Rz·Sx  Tx │    R = rotation components
│ Rx·Sy  Ry·Sy  Rz·Sy  Ty │    S = scale components
│ Rx·Sz  Ry·Sz  Rz·Sz  Tz │    T = translation components
│   0      0      0     1 │
└                         ┘
```

**World position** = `matrix_world @ local_position`
**Local position** = `matrix_world.inverted() @ world_position`

This conversion is used extensively in our code:

```python
# From fitting_utils.py — converting bone positions
to_local = rig.matrix_world.inverted()
shoulder_l = to_local @ shoulder_l_w  # world → rig local
```

### Translation, Rotation, and Scale

| Transform   | What It Does                   | Mathematical Operation         |
| ----------- | ------------------------------ | ------------------------------ |
| Translation | Moves an object                | `P' = P + T`                   |
| Rotation    | Spins an object around an axis | `P' = R × P` (matrix multiply) |
| Scale       | Grows or shrinks               | `P' = S × P`                   |

---

# 2. Codebase Architecture

## 2.1 Directory Structure

```
backend/blender_scripts/
├── common/                  ← Shared utilities (used by both pipelines)
│   ├── __init__.py          ← Module documentation
│   ├── mesh_utils.py        ← Bounding box, dimensions, vertex helpers
│   ├── profile_analysis.py  ← Cross-section slicing and extrema detection
│   ├── blender_utils.py     ← Scene management, rig loading
│   ├── mesh_processing.py   ← Mesh cleanup, voxel proxy creation
│   └── fitting_utils.py     ← 2-Bone IK solver, raycast centering, chain ratios
│
├── humanoid/                ← Humanoid-specific pipeline
│   ├── analyzer.py          ← Pose detection, anatomical landmark detection
│   └── rigging.py           ← Bone fitting, regional scaling, main pipeline
│
├── quadruped/               ← Quadruped-specific pipeline
│   ├── analyzer.py          ← Quadruped landmark detection (Y-axis profiling)
│   └── rigging.py           ← Quadruped bone fitting, regional scaling, main pipeline
│
└── tools/
    └── inspect_rig.py       ← Debug utility to print bone hierarchy

backend/templates/
├── human_rig_A.blend        ← Pre-built humanoid skeleton (A-Pose)
├── human_rig_T.blend        ← Pre-built humanoid skeleton (T-Pose)
└── quadruped_rig.blend      ← Pre-built quadruped skeleton (34 bones)
```

## 2.2 Data Flow Between Modules

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MAIN PIPELINE                                 │
│  (humanoid/rigging.py::auto_rig_advanced  OR                        │
│   quadruped/rigging.py::auto_rig_quadruped)                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. blender_utils.pick_target_mesh()     → Find the mesh             │
│  2. mesh_processing.preprocess_mesh()    → Clean the mesh            │
│  3. mesh_processing.create_voxel_proxy() → Simplify for analysis     │
│  4. analyzer.detect_*_landmarks()        → Find body landmarks       │
│     └── profile_analysis.build_profile() → Slice the mesh            │
│     └── profile_analysis.find_local_extrema() → Find key points      │
│  5. blender_utils.append_custom_rig()    → Load template skeleton    │
│  6. fitting.fit_bones_to_anatomy()       → Position bones            │
│     └── fitting_utils.solve_two_bone_ik()→ Calculate joint positions  │
│  7. fitting_utils.extract_chain_ratios() → Get template proportions  │
│  8. apply_regional_scaling()             → Preserve proportions       │
│  9. fitting_utils.refine_bones_with_raycast() → Center in mesh       │
│ 10. mesh_processing.cleanup_proxy()      → Remove proxy              │
│ 11. Blender ARMATURE_AUTO                → Auto-weight skinning      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## 2.3 Key Classes and Functions

| Module               | Function                       | Purpose                                   |
| -------------------- | ------------------------------ | ----------------------------------------- |
| `mesh_utils`         | `get_world_bbox()`             | Calculate bounding box in world space     |
| `mesh_utils`         | `get_mesh_dimensions()`        | Get height and 3D size of mesh            |
| `mesh_utils`         | `get_world_verts()`            | Get all vertices in world coordinates     |
| `mesh_utils`         | `lerp_vec(a, b, t)`            | Linear interpolation between two points   |
| `profile_analysis`   | `build_profile()`              | Slice mesh along axis into cross-sections |
| `profile_analysis`   | `smooth_profile()`             | Moving average filter for noise reduction |
| `profile_analysis`   | `find_local_extrema()`         | Detect significant peaks and valleys      |
| `blender_utils`      | `pick_target_mesh()`           | Select the mesh to rig                    |
| `blender_utils`      | `append_custom_rig()`          | Load template armature from .blend file   |
| `mesh_processing`    | `preprocess_mesh()`            | Remove doubles, fix normals               |
| `mesh_processing`    | `create_voxel_proxy()`         | Create simplified voxel copy              |
| `fitting_utils`      | `solve_two_bone_ik()`          | Analytical 2-bone IK solver               |
| `fitting_utils`      | `refine_bones_with_raycast()`  | Center bones inside mesh volume           |
| `fitting_utils`      | `extract_chain_ratios()`       | Extract bone length proportions           |
| `humanoid/analyzer`  | `detect_humanoid_pose()`       | Detect T-Pose vs A-Pose                   |
| `humanoid/analyzer`  | `detect_humanoid_landmarks()`  | Find neck, shoulder, hip, etc.            |
| `humanoid/rigging`   | `fit_bones_to_anatomy()`       | Position humanoid bones                   |
| `humanoid/rigging`   | `apply_regional_scaling()`     | Preserve template bone ratios             |
| `humanoid/rigging`   | `auto_rig_advanced()`          | Main humanoid pipeline entry point        |
| `quadruped/analyzer` | `detect_quadruped_landmarks()` | Find chest, hip, neck for animals         |
| `quadruped/rigging`  | `fit_quadruped_bones()`        | Position quadruped bones                  |
| `quadruped/rigging`  | `auto_rig_quadruped()`         | Main quadruped pipeline entry point       |

# 3. Humanoid Auto-Rigging Pipeline

The humanoid pipeline is the main entry point: `humanoid/rigging.py::auto_rig_advanced()`. Below is every step explained in full detail.

## 3.1 Overview Flowchart

```
┌─────────────────┐
│ 1. Find Mesh    │  blender_utils.pick_target_mesh()
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. Apply       │  bpy.ops.object.transform_apply()
│   Transforms    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. Preprocess   │  mesh_processing.preprocess_mesh()
│    Mesh         │  - Remove duplicate vertices
└────────┬────────┘  - Fix normals, dissolve degenerate faces
         ▼
┌─────────────────┐
│ 4. Create Voxel │  mesh_processing.create_voxel_proxy()
│    Proxy        │  - Simplify mesh for analysis
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. Detect Pose  │  analyzer.detect_humanoid_pose()
│  (T or A Pose)  │  - Cross-section width ratio analysis
└────────┬────────┘
         ▼
┌─────────────────┐
│ 6. Load Template│  blender_utils.append_custom_rig()
│    Skeleton     │  - Choose T-pose or A-pose template
└────────┬────────┘
         ▼
┌─────────────────┐
│ 7. Scale Rig    │  Uniform scaling: mesh_height / rig_height × 0.92
└────────┬────────┘
         ▼
┌─────────────────┐
│ 8. Extract      │  fitting_utils.extract_chain_ratios()
│    Template     │  - Save bone proportions before fitting
│    Ratios       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 9. Fit Bones    │  rigging.fit_bones_to_anatomy()
│    to Anatomy   │  - Detect landmarks on proxy
│                 │  - Position each bone to match mesh
└────────┬────────┘
         ▼
┌─────────────────┐
│10. Regional     │  rigging.apply_regional_scaling()
│   Scaling + IK  │  - Restore template proportions
│                 │  - 2-Bone IK for elbows/knees
└────────┬────────┘
         ▼
┌─────────────────┐
│11. Raycast      │  fitting_utils.refine_bones_with_raycast()
│   Refinement    │  - Center bones inside mesh volume
└────────┬────────┘
         ▼
┌─────────────────┐
│12. Cleanup      │  mesh_processing.cleanup_proxy()
│    Proxy        │
└────────┬────────┘
         ▼
┌─────────────────┐
│13. Skinning     │  bpy.ops.object.parent_set(type='ARMATURE_AUTO')
│   (Auto-Weights)│  - Blender's heat-map based auto-weighting
└─────────────────┘
```

---

## 3.2 Step 1 — Target Mesh Selection

**WHY:** The system needs to identify which 3D object in the Blender scene should be rigged.

**WHAT:** `pick_target_mesh()` in `common/blender_utils.py` selects the mesh.

**HOW:**

1. Check if the user has manually selected an active object. If it's a mesh, use it.
2. Otherwise, find ALL mesh objects in the scene.
3. Calculate the **volume** of each mesh's bounding box: `volume = width × depth × height`.
4. Return the mesh with the largest volume (the character, not small props).

```python
def mesh_volume_world(obj):
    _, dims = get_mesh_dimensions(obj)
    return dims.x * dims.y * dims.z   # width × depth × height

return max(meshes, key=mesh_volume_world)
```

---

## 3.3 Step 2 — Transform Application

**WHY:** The mesh might have been rotated or scaled in Object mode. If rotation/scale aren't "applied," the mesh's local coordinates won't match its visual position.

**WHAT:** `bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)` bakes the rotation and scale into the vertex data.

**HOW:** After applying, the object's scale becomes `(1, 1, 1)` and rotation becomes `(0, 0, 0)`, but vertex positions in world space remain unchanged.

---

## 3.4 Step 3 — Mesh Preprocessing

**WHY:** Raw meshes from 3D modeling software often have problems:

- **Duplicate vertices:** Two vertices at the same position waste computation and cause errors.
- **Inconsistent normals:** Some face normals may point inward, confusing algorithms.
- **Degenerate faces:** Zero-area faces that cause division-by-zero errors.

**WHAT:** `preprocess_mesh()` in `common/mesh_processing.py` fixes all three.

**HOW:**

```python
bpy.ops.mesh.remove_doubles(threshold=0.0001)      # Merge vertices within 0.1mm
bpy.ops.mesh.normals_make_consistent(inside=False)  # All normals face outward
bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)  # Remove zero-area faces
```

---

## 3.5 Step 4 — Voxel Proxy Creation

**WHY:** Character meshes often have complex details — armor, belts, weapons, hair. These details create noise in anatomical analysis. A voxel proxy creates a **simplified, smooth version** of the mesh.

**WHAT:** `create_voxel_proxy()` in `common/mesh_processing.py` creates a copy of the mesh and applies a **Voxel Remesh** modifier.

**HOW:**

1. Duplicate the target mesh.
2. Calculate voxel size based on mesh height: `voxel_size = max(0.02, mesh_height × 0.018)`.
3. Apply a VOXEL remesh modifier — this converts the mesh into a grid of small cubes (voxels), then reconstructs a smooth surface from them.

```
Original Mesh          Voxel Proxy
(with armor, belt)     (smooth blob)
     ╔══╗                  ┌──┐
    ╔╝  ╚╗                ┌┘  └┐
    ║ ▓▓ ║   ──────→      │    │
    ╠════╣                 │    │
    ║    ║                 │    │
    ╚╗  ╔╝                 └┐  ┌┘
     ╚══╝                  └──┘
```

The voxel proxy is used for:

- Landmark detection (the analyzer reads the proxy)
- Raycast centering (bones are centered inside the proxy)

After rigging, the proxy is deleted.

---

## 3.6 Step 5 — Pose Detection (T-Pose vs. A-Pose)

**WHY:** The template skeleton must match the mesh's pose. If the character has arms straight out (T-Pose), we load the T-Pose template. If arms are at 45° angles (A-Pose), we load the A-Pose template.

**WHAT:** `detect_humanoid_pose()` in `humanoid/analyzer.py` uses cross-section width analysis.

**HOW:**

1. Build a cross-section profile by slicing the mesh along the Z axis (height) into 60 slices.
2. For each slice, measure the **X-width** (left-to-right extent).
3. Smooth the width values with a moving average filter (window=5).
4. Compare the **upper body width** (60%–85% height) to the **waist width** (40%–55% height).

```
T-Pose:                    A-Pose:
shoulder/arm width         shoulder width
is VERY wide               is moderately wide

  ─────────────             ──────────
      ████                    ████
     ██████                  ██████
████████████████             ████████
████████████████              ██████
      ████                    ████
      ████                    ████
     ██████                  ██████
```

**Decision logic:**

```python
ratio = shoulder_width / waist_width

if ratio > 2.5:
    return 'T_POSE'    # Arms extend far beyond body → T-Pose
else:
    return 'A_POSE'    # Arms closer to body → A-Pose
```

---

## 3.7 Step 6 — Template Skeleton Loading

**WHY:** Instead of generating a skeleton from scratch, we use a pre-built, professionally designed armature as a starting point. This template already has correct bone hierarchy, naming conventions, and constraint setups.

**WHAT:** `append_custom_rig()` in `common/blender_utils.py` loads the appropriate `.blend` file.

**HOW:**

1. Select template based on pose: `human_rig_A.blend` or `human_rig_T.blend`.
2. Use Blender's `wm.append` to import the "Armature" object from the template file.
3. If that fails, load ALL objects from the file and find the one with type `ARMATURE`.

### Humanoid Bone Hierarchy (Template)

```
spine (root/sacrum)
├── spine.001
│   ├── spine.002
│   │   ├── spine.003
│   │   │   ├── spine.004
│   │   │   │   ├── spine.005 (neck)
│   │   │   │   │   └── spine.006 (head)
│   │   │   │   ├── shoulder.L
│   │   │   │   │   └── upper_arm.L
│   │   │   │   │       └── forearm.L
│   │   │   │   │           └── hand.L
│   │   │   │   ├── shoulder.R
│   │   │   │   │   └── upper_arm.R
│   │   │   │   │       └── forearm.R
│   │   │   │   │           └── hand.R
│   │   │   │   ├── breast.L
│   │   │   │   └── breast.R
├── pelvis.L
│   └── thigh.L
│       └── shin.L
│           └── foot.L
│               └── toe.L
├── pelvis.R
│   └── thigh.R
│       └── shin.R
│           └── foot.R
│               └── toe.R
```

---

## 3.8 Step 7 — Uniform Scaling

**WHY:** The template skeleton is designed at a standard size. The user's mesh could be any size — from a 2cm chibi figure to a 200cm realistic human. We need to scale the skeleton to match.

**WHAT:** Calculate a scale factor and apply it uniformly to all three axes.

**HOW:**

```python
scale_factor = (mesh_height / rig_height) × 0.92
scale_factor = clamp(scale_factor, 0.20, 8.00)
custom_rig.scale = (scale_factor, scale_factor, scale_factor)
```

- The `× 0.92` multiplier makes the rig slightly smaller than the mesh so bones sit inside the mesh volume rather than poking through the surface.
- Clamping to `[0.20, 8.00]` prevents extreme scaling from broken measurements.

After scaling, `transform_apply(scale=True)` bakes the scale into bone positions.

---

## 3.9 Step 8 — Template Ratio Extraction

**WHY:** Every bone in the template has carefully designed proportions (e.g., upper_arm is 40% of the total arm length, forearm is 35%, hand is 25%). After we reposition bones to match the mesh anatomy, we want to restore these proportions.

**WHAT:** `extract_chain_ratios()` in `common/fitting_utils.py` records the ratio of each bone's length relative to its chain total.

**HOW:**

```python
# For each bone chain (e.g., arm = [upper_arm, forearm, hand]):
lengths = [bone_length(bone) for bone in chain]
total = sum(lengths)
for i, bone in enumerate(chain):
    ratios[bone_name] = lengths[i] / total
```

**Example output:**

```
arms_upper_arm.L = 0.40   (40% of total arm)
arms_forearm.L   = 0.35   (35% of total arm)
arms_hand.L      = 0.25   (25% of total arm)
legs_thigh.L     = 0.52   (52% of total leg)
legs_shin.L      = 0.48   (48% of total leg)
```

---

## 3.10 Step 9 — Anatomical Landmark Detection

**WHY:** To position the skeleton bones correctly inside the mesh, we need to know WHERE key anatomical features are: neck, shoulders, waist, hips, knees, etc.

**WHAT:** `detect_humanoid_landmarks()` in `humanoid/analyzer.py` performs cross-section profiling to find these landmarks.

### 3.10.1 Cross-Section Profiling

The mesh is sliced horizontally (along Z) into 80 slices. For each slice, we measure the **X-width** (left-right extent).

```
Slice 79 (top):   ──██──          width = small (head top)
Slice 72:         ─████─          width = medium (head)
Slice 66:         ──██──          width = small (NECK ← minimum!)
Slice 60:         ████████        width = large (shoulders)
Slice 50:         ──████──        width = medium (waist ← minimum!)
Slice 42:         ─██████─        width = large (hips ← maximum!)
Slice 30:         ──██──          width = small (legs)
Slice 10:         ──██──          width = small (ankles)
Slice 0 (bottom): ─████─          width = medium (feet)
```

### 3.10.2 Signal Processing — Smoothing

Raw width values are noisy due to mesh detail. We apply a **moving average filter**:

```python
def smooth_profile(values, window=5):
    half = window // 2
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        smoothed[i] = sum(values[lo:hi]) / (hi - lo)
```

**Example** (window=3):

```
Raw:      [4, 8, 6, 2, 7, 5, 3]
Smoothed: [6, 6, 5.3, 5, 4.7, 5, 4]
           ↑ avg(4,8) = 6
              ↑ avg(4,8,6) = 6
                 ↑ avg(8,6,2) = 5.3
```

### 3.10.3 Local Extrema Detection

**Local minima** (valleys) = anatomical narrowing points (neck, waist).
**Local maxima** (peaks) = anatomical widening points (shoulders, hips).

A **prominence filter** ensures we only detect significant features, not small noise bumps:

```python
# A minimum is significant if it's at least 8% of the total range deeper
# than the surrounding maxima
min_prominence = (max(values) - min(values)) × 0.08
```

### 3.10.4 Landmark Identification

Each landmark is found using a specific strategy:

| Landmark     | Strategy                                                               | Search Region       |
| ------------ | ---------------------------------------------------------------------- | ------------------- |
| **Neck**     | Deepest local minimum in upper 35%                                     | Slices 65%–100%     |
| **Shoulder** | Anatomical estimate (neck − 2.5% height) + nearby local max validation | ±8% around estimate |
| **Waist**    | Narrowest local minimum between shoulder and hip                       | Slices 43%–shoulder |
| **Hip**      | Widest local maximum below waist                                       | Slices 30%–waist    |
| **Crotch**   | Width drops below 65% of hip width (legs split from body)              | Below hip           |
| **Knee**     | Biased midpoint: `ankle + (crotch − ankle) × 0.55`                     | Calculated          |
| **Ankle**    | `ground + height × 3.5%`                                               | Calculated          |

### 3.10.5 Left/Right Vertex Separation

After finding Z-levels, vertices at each landmark's height are split into left and right groups:

```python
center_x = median(all_x_values)   # Robust center (median, not mean)
offset = total_height × 0.01      # Dead zone around center

left_verts  = [v for v in band if v.x > center_x + offset]
right_verts = [v for v in band if v.x < center_x - offset]
```

### 3.10.6 Dynamic Inset Calculation

**Shoulder inset** determines how far inward the shoulder joint sits relative to the outermost shoulder point:

```python
torso_shoulder_width = waist_width × 1.3
shoulder_inset = clamp(torso_shoulder_width / shoulder_full_width, 0.55, 0.90)
```

This ensures the shoulder joint is inside the body, not at the skin surface.

---

## 3.11 Step 10 — Bone Fitting (Positioning)

**WHY:** The template skeleton was loaded at a generic position. Now we need to move every bone to match the specific mesh's anatomy.

**WHAT:** `fit_bones_to_anatomy()` in `humanoid/rigging.py` repositions all bones in Edit Mode.

**HOW:**

The function works in Blender's **Edit Mode** where bone head/tail positions can be directly modified.

### 3.11.1 Hybrid Z-Level System

Cross-section Z values are used but **clamped** to anatomical safety ranges:

```python
def clamp_z(value, min_pct, max_pct):
    lo = z_min + mesh_height × min_pct
    hi = z_min + mesh_height × max_pct
    return clamp(value, lo, hi)

shoulder_z = clamp_z(cross_section_shoulder, 0.78, 0.84)  # Must be 78%-84% of height
neck_z     = clamp_z(cross_section_neck,     0.82, 0.90)  # Must be 82%-90% of height
knee_z     = clamp_z(cross_section_knee,     0.24, 0.32)  # Must be 24%-32% of height
```

### 3.11.2 Spine Chain Construction

The spine is divided into 7 bones, distributed linearly from sacrum to head:

```
spine.006 ── head center (neck_z + 45% of remaining height)
spine.005 ── neck_z
spine.004 ── shoulder_z (top of torso)    ← 5 segments evenly
spine.003 ── ...                              distributed from
spine.002 ── ...                              spine_root to
spine.001 ── ...                              shoulder_z
spine     ── spine_root_z (sacrum)

spine_step = (shoulder_z − spine_root_z) / 5.0
```

### 3.11.3 Limb Positioning

**Shoulders:** Positioned at shoulder_z, with X offset from center using the calculated inset ratio.

**Elbows:** Interpolated at 52% between shoulder and wrist positions, with a slight lateral offset for natural bend:

```python
wrist_l = lerp(shoulder_l, hand_l, 0.82)     # Wrist at 82% along arm
elbow_l = lerp(shoulder_l, wrist_l, 0.52)    # Elbow at 52% of shoulder→wrist
elbow_l.x += abs(wrist_l.x - shoulder_l.x) × 0.08  # Slight outward offset
```

**Hips:** Positioned using waist width:

```python
hip_half_width = waist_width × 0.45
hip_half_width = clamp(hip_half_width, mesh_h × 0.04, mesh_h × 0.08)
hip_l = Vector(center_x + hip_half_width, torso_y, hip_joint_z)
```

**Knees:** Placed directly below hips (same X), at the calculated knee_z.

**Feet/Toes:** Foot bone points forward (−Y direction), toe extends further:

```python
foot_forward_len = mesh_height × 0.04
toe_len = mesh_height × 0.025
```

---

## 3.12 Step 11 — Regional Scaling with IK

**WHY:** Step 10 positioned bones using simple interpolation (e.g., elbow at 52% of arm length). This ignores the template's carefully designed bone proportions. Regional scaling restores those proportions while keeping the anchor points (shoulder, hand, hip, ankle) fixed.

**WHAT:** `apply_regional_scaling()` in `humanoid/rigging.py` uses the template ratios extracted in Step 8 and analytically solves for joint positions using 2-Bone IK.

**HOW:**

### 3.12.1 Arm Chain

```
Given:
  arm_start = shoulder joint (FIXED)
  arm_end   = hand tip (FIXED)
  total_dist = distance(arm_start, arm_end)

From template ratios:
  len_upper = total_dist × r_upper  (e.g., 0.40)
  len_fore  = total_dist × r_fore   (e.g., 0.35)
  len_hand  = total_dist × r_hand   (e.g., 0.25)

Step 1: Find wrist position
  wrist = arm_end + normalize(arm_start − arm_end) × len_hand

Step 2: Solve elbow with 2-Bone IK
  elbow = solve_two_bone_ik(arm_start, wrist, len_upper, len_fore, pole_dir)
```

### 3.12.2 The 2-Bone IK Solver

This is the mathematical heart of the system. Located in `common/fitting_utils.py`.

**Problem:** Given two bones of lengths `L₁` and `L₂` connected at a middle joint, with the start and end positions fixed, find the middle joint position.

```
    Start ●─────── L₁ ───────● Middle (unknown)
                                \
                                 L₂
                                  \
                                   ● End
```

**Solution using the Law of Cosines:**

The start, middle, and end points form a triangle. We know all three side lengths:

- Side `a` = L₂ (second bone)
- Side `b` = dist (distance from start to end)
- Side `c` = L₁ (first bone)

```
cos(A) = (L₁² + dist² − L₂²) / (2 × L₁ × dist)
```

Where `A` is the angle at the start point between the direction to the end and the direction to the middle joint.

```python
def solve_two_bone_ik(start, end, len1, len2, pole_direction):
    direction = end - start
    dist = direction.length

    # Edge case: bones can't reach
    if dist >= len1 + len2:
        t = len1 / (len1 + len2)
        return start + direction * t    # Stretch along line

    # Normal case: Law of Cosines
    cos_angle = (len1² + dist² - len2²) / (2 × len1 × dist)
    cos_angle = clamp(cos_angle, -1.0, 1.0)
    angle = acos(cos_angle)

    dir_n = direction.normalized()

    # Gram-Schmidt: make pole perpendicular to bone direction
    pole_proj = pole_direction - dir_n × dot(pole_direction, dir_n)
    pole_proj.normalize()

    # Calculate middle joint position
    mid = start + dir_n × (len1 × cos(angle)) + pole_proj × (len1 × sin(angle))
    return mid
```

**Step-by-step numerical example:**

```
Given:
  start = (0, 0, 5)     ← shoulder
  end   = (3, 0, 5)     ← wrist
  len1  = 1.8            ← upper arm
  len2  = 1.5            ← forearm
  pole  = (0, 1, 0)     ← elbow bends backward

Calculations:
  dist = |end − start| = |(3,0,0)| = 3.0
  cos(A) = (1.8² + 3.0² − 1.5²) / (2 × 1.8 × 3.0)
         = (3.24 + 9.0 − 2.25) / 10.8
         = 9.99 / 10.8
         = 0.925
  A = acos(0.925) = 0.3898 radians (22.3°)

  dir_n = (1, 0, 0)
  pole_proj = (0, 1, 0) − (1,0,0) × 0 = (0, 1, 0)  ← already perpendicular

  mid = (0,0,5) + (1,0,0) × (1.8 × 0.925) + (0,1,0) × (1.8 × 0.380)
      = (0,0,5) + (1.665, 0, 0) + (0, 0.684, 0)
      = (1.665, 0.684, 5.0)  ← elbow position
```

### 3.12.3 Pole Direction

The **pole direction** controls which way the joint bends:

- **Arms:** `pole = (±0.1, 1.0, −0.3)` → elbows bend backward and slightly down
- **Legs:** `pole = (0.0, −1.0, 0.0)` → knees bend forward

### 3.12.4 Spine Redistribution

The spine is redistributed using template ratios while keeping the total spine length unchanged:

```python
# For each spine bone, calculate its proportional Z position:
cumulative = 0
for ratio in segment_ratios:
    cumulative += ratio / total_ratio
    z_point = z_start + total_z × cumulative
```

---

## 3.13 Step 12 — Raycast Refinement

**WHY:** After fitting and IK solving, some bones might not be centered within the mesh volume. They could be shifted too far forward, backward, or sideways. Raycast refinement ensures each bone sits in the volumetric center.

**WHAT:** `refine_bones_with_raycast()` in `common/fitting_utils.py` shoots rays through the voxel proxy to find the mesh center at each bone point.

**HOW:**

### 3.13.1 Bidirectional Raycast Centering

For each bone point, two rays are cast in opposite directions along an axis:

```
Ray 1 (positive direction)     Ray 2 (negative direction)
         ──────→ ● ←──────
         hit_p   ↑   hit_n
                 │
          center = (hit_p + hit_n) / 2
```

```python
def raycast_find_center(proxy, point, axis, dist=5.0):
    hit_p, loc_p = raycast_world(proxy, point - axis × dist, axis)    # Ray from left
    hit_n, loc_n = raycast_world(proxy, point + axis × dist, -axis)   # Ray from right

    if hit_p and hit_n:
        return (loc_p + loc_n) / 2.0    # Average = center
```

### 3.13.2 Raycast World-Space Conversion

Raycasting requires converting between world space and object local space:

```python
def raycast_world(obj, origin, direction):
    matrix_inv = obj.matrix_world.inverted()
    origin_local = matrix_inv @ origin           # World → Local
    dir_local = (matrix_inv.to_3x3() @ direction).normalized()

    hit, loc_local, normal, face_idx = obj.ray_cast(origin_local, dir_local)

    if hit:
        return True, obj.matrix_world @ loc_local  # Local → World
```

### 3.13.3 What Gets Centered

| Bone Type   | Centering Axis | Why                                |
| ----------- | -------------- | ---------------------------------- |
| Spine bones | Y (front-back) | Center spine in the torso depth    |
| Limb chains | Y (front-back) | Center arms/legs in the limb depth |
| Pelvis      | Y (front-back) | Center pelvis connection           |

### 3.13.4 Chain Connection Consistency

After raycast refinement, some bone connections may break (tail of parent ≠ head of child). The system repairs these:

```python
for (src_name, src_pt, dst_name, dst_pt) in chain_connections:
    # e.g., shoulder.L tail must equal upper_arm.L head
    value = src_bone.tail
    dst_bone.head = value   # Force connection
```

---

## 3.14 Step 13 — Skinning (Auto-Weights)

**WHY:** The skeleton is now positioned inside the mesh, but the mesh doesn't "know" about the bones yet. Skinning creates the vertex-to-bone weight mapping.

**WHAT:** Blender's built-in `ARMATURE_AUTO` operator performs heat-map-based automatic weight assignment.

**HOW:**

1. Select the mesh AND the armature.
2. Set the armature as active.
3. Call `parent_set(type='ARMATURE_AUTO')`.

Blender's algorithm:

1. For each bone, generate a **heat field** that radiates from the bone outward.
2. Vertices closer to a bone get higher weights for that bone.
3. Heat cannot pass through the mesh surface (so the chest bone doesn't affect back vertices).
4. Weights are automatically normalized so each vertex's weights sum to 1.0.

**Fallback:** If auto-weights fail (common with non-watertight meshes), the system tries `ARMATURE_NAME`, which assigns weights based on vertex group naming.

# 4. Quadruped Auto-Rigging Pipeline

The quadruped pipeline: `quadruped/rigging.py::auto_rig_quadruped()`.

## 4.1 Humanoid vs. Quadruped — Key Differences

| Aspect         | Humanoid                         | Quadruped                                        |
| -------------- | -------------------------------- | ------------------------------------------------ |
| Orientation    | Vertical (Z = height)            | Horizontal (Y = length)                          |
| Primary axis   | Z (slicing along height)         | Y (slicing along body length)                    |
| Legs           | 2 legs, symmetric L/R            | 4 legs: front pair + rear pair                   |
| Spine          | Vertical (7 bones)               | Horizontal (12 bones: tail + body + neck + head) |
| Pose detection | T-Pose vs A-Pose                 | Not needed (single template)                     |
| Template       | `human_rig_A.blend` or `T.blend` | `quadruped_rig.blend` (34 bones)                 |
| Scale basis    | Height (Z)                       | Body length (Y)                                  |

## 4.2 Quadruped Bone Hierarchy

```
spine.004 (ROOT — pelvis/hip center)
│
├── TAIL (Y+ direction, away from head)
│   spine.003 → spine.002 → spine.001 → spine
│
├── BODY + NECK + HEAD (Y− direction, toward head)
│   spine.005 → spine.006 → spine.007 (body/torso)
│   → spine.008 → spine.009 → spine.010 (neck)
│   → spine.011 (head/skull)
│
├── REAR LEGS
│   ├── pelvis.L → thigh.L → shin.L → foot.L → toe.L
│   └── pelvis.R → thigh.R → shin.R → foot.R → toe.R
│
├── FRONT LEGS
│   ├── shoulder.L → front_thigh.L → front_shin.L → front_foot.L → front_toe.L
│   └── shoulder.R → front_thigh.R → front_shin.R → front_foot.R → front_toe.R
│
└── breast.L / breast.R (chest/ribcage)
```

## 4.3 Pipeline Flowchart

```
┌─────────────────┐
│ 1. Find Mesh    │  Same as humanoid
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. Preprocess   │  Same as humanoid
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. Voxel Proxy  │  Same as humanoid
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. Load Template│  quadruped_rig.blend (single template)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. Scale by     │  scale = mesh_length_Y / rig_length_Y × 0.92
│    Body Length   │  (NOT height — quadrupeds are wider than tall)
└────────┬────────┘
         ▼
┌─────────────────┐
│ 6. Extract      │  Chain ratios for front_legs, rear_legs, spine
│    Ratios       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 7. Detect       │  Y-axis cross-section profiling
│    Landmarks    │  Find chest, waist, hip, neck, head, tail
└────────┬────────┘
         ▼
┌─────────────────┐
│ 8. Fit Bones    │  Position all 34 bones
└────────┬────────┘
         ▼
┌─────────────────┐
│ 9. Regional     │  2-Bone IK for all 4 legs
│    Scaling      │
└────────┬────────┘
         ▼
┌─────────────────┐
│10. Raycast      │  X-axis only (not Z — would pull spine down)
│    Refinement   │
└────────┬────────┘
         ▼
┌─────────────────┐
│11. Cleanup +    │  Same as humanoid
│    Skinning     │
└─────────────────┘
```

## 4.4 Quadruped Landmark Detection

`quadruped/analyzer.py::detect_quadruped_landmarks()` slices along the **Y axis** (body length).

### Y-Axis Cross-Section Profile

```
       HEAD    NECK    CHEST   WAIST    HIP     TAIL
        ↓       ↓       ↓       ↓       ↓       ↓
width:  ██     ███    █████    ███    █████     █
        ↑               ↑       ↑       ↑
      small           max #1   min    max #2
      (snout)        (front   (narrow (rear
                      body)    waist)  body)

Y axis: ←────────────────────────────────────────→
      y_min (nose)                          y_max (tail tip)
```

**Algorithm:**

1. Build profile along Y with 80 slices, measuring X-width at each slice.
2. Find **two width maxima**: front half = chest, rear half = hip.
3. Find **minimum between them** = waist.
4. From chest, scan toward head (decreasing Y) until width drops below 55% = neck.
5. Tail = y_max, Head = y_min.

```python
# Split profile in half
mid = n // 2
front_maxs = [m for m in local_maxs if m < mid + 5]   # Chest candidates
rear_maxs  = [m for m in local_maxs if m >= mid - 5]   # Hip candidates

chest_idx = max(front_maxs, key=lambda i: width[i])    # Widest in front
hip_idx   = max(rear_maxs,  key=lambda i: width[i])    # Widest in rear
```

### Leg Position Detection

Legs are detected by finding vertices near the ground at chest and hip Y-coordinates:

```python
# Rear feet: low vertices near hip Y-coordinate
rear_feet = [v for v in verts
             if v.z < ground_z + body_height × 0.08        # Near ground
             and abs(v.y - hip_y) < body_length × 0.20]    # Near hip

# Split into left and right
rf_left  = [v for v in rear_feet if v.x > center_x]
rf_right = [v for v in rear_feet if v.x < center_x]
```

## 4.5 Quadruped Bone Fitting

`fit_quadruped_bones()` in `quadruped/rigging.py` positions all bones.

### 4.5.1 Root Placement (spine.004)

The root bone is placed between chest and hip, biased by `SPINE_ROOT_Y_RATIO = 0.45`:

```python
root_y = lerp(chest_y, hip_y, 0.45)    # 45% from chest toward hip
root_pos = Vector(center_x, root_y, spine_z_line)
```

`spine_z_line` = top of mesh minus 8% of body height (slightly below the back surface).

### 4.5.2 Tail Chain

4 bones distributed linearly from root toward tail tip:

```python
for i, name in enumerate(["spine.003", "spine.002", "spine.001", "spine"]):
    t_start = i / 4
    t_end = (i + 1) / 4
    bone.head = lerp(hip_position, tail_end, t_start)
    bone.tail = lerp(hip_position, tail_end, t_end)
```

### 4.5.3 Body, Neck, and Head Chains

- **Body** (spine.005–007): Root → Chest, 3 segments
- **Neck** (spine.008–010): Chest → Neck base, 3 segments
- **Head** (spine.011): Neck base → Head position, 1 bone

All use linear interpolation (`lerp_vec`) for even distribution.

### 4.5.4 Rear Legs

```
                    hip_pos (thigh.head)
                   ╱
                  ╱  thigh bone
                 ╱
    knee_pos ───●  (stifle joint — bends FORWARD, −Y)
                 \
                  \ shin bone
                   \
    ankle_pos ──────● (hock — 20% above ground)
                    |
                    | foot bone
                    |
    toe_pos ────────● (on ground)
```

**Knee bend:** The knee (stifle) is offset forward:

```python
knee_pos = lerp(hip_pos, ankle_pos, 0.50)
knee_pos.y -= body_length × 0.08    # Push forward (−Y)
```

**Ankle height:** `ground_z + body_height × 0.20`

### 4.5.5 Front Legs

Front legs have an extra bone — the **shoulder (scapula)**:

```
    shoulder_pos (scapula top, above spine)
        |
        | shoulder bone
        |
    sh_bottom (humerus head, below spine)
       ╱
      ╱  front_thigh bone
     ╱
    f_knee ── (elbow — bends BACKWARD, +Y)
     \
      \ front_shin bone
       \
    f_ankle (20% above ground)
        |
    f_toe (ground level)
```

**Front knee/elbow bend direction is OPPOSITE to rear:**

```python
f_knee.y += body_length × 0.08    # Push backward (+Y)
```

This is anatomically correct — in quadrupeds, rear knees (stifles) bend forward while front elbows bend backward.

### 4.5.6 Balance and Center of Mass

The system handles balance through:

1. **Symmetric placement:** Left/right bones mirror across `center_x`.
2. **Root at body center:** `spine.004` sits at the weighted center (45% from chest to hip).
3. **Spine follows back surface:** `spine_z_line = spine_z − body_height × 0.08`.

## 4.6 Quadruped Regional Scaling

Same principle as humanoid but with **4 leg chains** instead of 2 arms + 2 legs.

**Rear legs:** Pole direction = `(0, −1, 0)` → stifle bends forward.
**Front legs:** Pole direction = `(0, +1, 0)` → elbow bends backward.

Both add a 5% length buffer for bend room:

```python
l_th = dist × r_th × 1.05    # 5% extra for natural bend
l_sn = dist × r_sn × 1.05
```

## 4.7 Quadruped Raycast Refinement

**Critical difference from humanoid:** Only X-axis raycast is performed.

**WHY:** In quadrupeds, Z-axis raycasting would pull the spine downward into the belly cavity. The spine should stay near the back surface, not at the volumetric center.

```python
# Only center bones left-right (X axis)
for bone in ["shoulder", "front_thigh", "front_shin", ...]:
    center = raycast_find_center(proxy, bone.head, Vector(1,0,0))
    if center:
        bone.head.x = center.x

# Spine bones: force to center_x = 0 (perfect symmetry)
for spine_bone in spine_chain:
    bone.head.x = 0.0
    bone.tail.x = 0.0
```

---

# 5. Mathematical Foundations

## 5.1 Linear Interpolation (Lerp)

Used extensively for positioning bones between two known points.

```
lerp(A, B, t) = A + (B − A) × t

When t = 0: result = A
When t = 0.5: result = midpoint
When t = 1: result = B
```

**Vector form** (implemented in `mesh_utils.py`):

```python
def lerp_vec(a, b, t):
    return a + (b - a) * t
    # Equivalent to: Vector(a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t, a.z+(b.z-a.z)*t)
```

## 5.2 The Law of Cosines (2-Bone IK Foundation)

For a triangle with sides a, b, c and angle A opposite to side a:

```
a² = b² + c² − 2bc × cos(A)

Rearranged:
cos(A) = (b² + c² − a²) / (2bc)
```

In our 2-Bone IK:

- `b` = L₁ (first bone length)
- `c` = dist (distance from start to end)
- `a` = L₂ (second bone length)

## 5.3 Gram-Schmidt Orthogonalization

Used in the IK solver to ensure the pole direction is perpendicular to the bone chain direction:

```
Given: direction d, pole vector p
Goal: find p' perpendicular to d

p' = p − d × (p · d)    (subtract the component of p along d)
p' = normalize(p')
```

This ensures the middle joint bends in a plane perpendicular to the bone chain.

## 5.4 Transformation Matrices

### 5.4.1 Translation Matrix

```
┌ 1  0  0  tx ┐     ┌ x ┐     ┌ x + tx ┐
│ 0  1  0  ty │  ×  │ y │  =  │ y + ty │
│ 0  0  1  tz │     │ z │     │ z + tz │
└ 0  0  0   1 ┘     └ 1 ┘     └   1   ┘
```

### 5.4.2 Scale Matrix

```
┌ sx  0  0  0 ┐     ┌ x ┐     ┌ sx·x ┐
│  0 sy  0  0 │  ×  │ y │  =  │ sy·y │
│  0  0 sz  0 │     │ z │     │ sz·z │
└  0  0  0  1 ┘     └ 1 ┘     └  1   ┘
```

### 5.4.3 World ↔ Local Conversion

```python
# The code uses matrix_world extensively:
world_position = obj.matrix_world @ local_position
local_position = obj.matrix_world.inverted() @ world_position

# For directions (no translation), use the 3×3 submatrix:
world_dir = (obj.matrix_world.to_3x3() @ local_dir).normalized()
```

## 5.5 Euler Angles and Quaternions

### Euler Angles

Three rotation values (X, Y, Z) applied in sequence. Simple but suffer from **gimbal lock** — when two axes align, one degree of freedom is lost.

### Quaternions

Four-component representation `(w, x, y, z)` that avoids gimbal lock. Used internally by Blender for bone rotations.

```
q = w + xi + yj + zk
|q| = √(w² + x² + y² + z²) = 1  (unit quaternion)

Rotation by angle θ around axis (ax, ay, az):
w = cos(θ/2)
x = ax × sin(θ/2)
y = ay × sin(θ/2)
z = az × sin(θ/2)
```

**This codebase** primarily works with bone head/tail positions rather than rotations, so quaternions are handled internally by Blender.

---

# 6. Skinning Theory

## 6.1 Linear Blend Skinning (LBS)

The most common skinning method. Each vertex's final position is a weighted average of where each influencing bone would place it:

```
v' = Σᵢ wᵢ × Mᵢ × M⁻¹ᵢ_bind × v

Where:
  v  = original vertex position
  v' = deformed vertex position
  wᵢ = weight of bone i (0 to 1, all weights sum to 1)
  Mᵢ = current world transform of bone i
  M⁻¹ᵢ_bind = inverse of bone i's transform at bind time
```

### Step-by-Step Example

```
Vertex v at position (2, 0, 3)
Influenced by:
  Bone A (weight 0.6): rotated 30° → would move v to (2.23, 0, 2.60)
  Bone B (weight 0.4): rotated 0°  → would keep v at (2, 0, 3)

Final position:
  v' = 0.6 × (2.23, 0, 2.60) + 0.4 × (2, 0, 3)
     = (1.338, 0, 1.56) + (0.8, 0, 1.2)
     = (2.138, 0, 2.76)
```

### LBS Artifact: "Candy Wrapper" Effect

When a bone rotates 180°, LBS collapses the mesh volume because it averages positions linearly. This creates a pinched appearance at twist joints (like the forearm).

## 6.2 Dual Quaternion Skinning (DQS)

DQS solves the candy wrapper problem by blending bone transformations as **dual quaternions** instead of matrices:

```
A dual quaternion: q̂ = q₀ + εq₁
Where:
  q₀ = rotation quaternion
  q₁ = translation quaternion = ½ × t × q₀
  ε² = 0 (dual number property)
```

DQS preserves volume during blending but can create slight bulging artifacts. Blender supports both methods.

**Note:** This codebase uses Blender's built-in `ARMATURE_AUTO` which defaults to LBS. The skinning formula choice is made at the Blender engine level, not in the Python scripts.

## 6.3 Weight Normalization

All bone weights for a single vertex must sum to 1.0:

```
Given raw weights: w₁=0.3, w₂=0.5, w₃=0.4
Sum = 1.2

Normalized:
  w₁' = 0.3/1.2 = 0.250
  w₂' = 0.5/1.2 = 0.417
  w₃' = 0.4/1.2 = 0.333
  Sum = 1.000 ✓
```

---

# 7. Practical Examples

## 7.1 Complete Bone Hierarchy — Humanoid Example

```
BONE NAME          HEAD POSITION        TAIL POSITION        LENGTH
─────────────────────────────────────────────────────────────────────
spine              (0, 0.1, 0.95)       (0, 0.1, 1.05)       0.10
spine.001          (0, 0.1, 1.05)       (0, 0.1, 1.15)       0.10
spine.002          (0, 0.1, 1.15)       (0, 0.1, 1.25)       0.10
spine.003          (0, 0.1, 1.25)       (0, 0.1, 1.35)       0.10
spine.004          (0, 0.1, 1.35)       (0, 0.1, 1.45)       0.10
spine.005 (neck)   (0, 0.1, 1.45)       (0, 0.1, 1.55)       0.10
spine.006 (head)   (0, 0.1, 1.55)       (0, 0.1, 1.70)       0.15
shoulder.L         (0, 0.1, 1.45)       (0.12, 0.1, 1.45)    0.12
upper_arm.L        (0.12, 0.1, 1.45)    (0.38, 0.1, 1.42)    0.26
forearm.L          (0.38, 0.1, 1.42)    (0.60, 0.1, 1.40)    0.22
hand.L             (0.60, 0.1, 1.40)    (0.72, 0.1, 1.39)    0.12
pelvis.L           (0, 0.1, 0.95)       (0.08, 0.1, 0.88)    0.10
thigh.L            (0.08, 0.1, 0.88)    (0.08, 0.05, 0.50)   0.38
shin.L             (0.08, 0.05, 0.50)   (0.08, 0.1, 0.08)    0.42
foot.L             (0.08, 0.1, 0.08)    (0.08, 0.03, 0.04)   0.08
```

## 7.2 Example Vertex Weight Calculation

```
Vertex at position (0.35, 0.1, 1.42) — near the elbow

Blender's heat-map auto-weighting assigns:
  upper_arm.L: 0.45  (close to upper arm bone)
  forearm.L:   0.52  (close to forearm bone)
  shoulder.L:  0.03  (far from shoulder, tiny influence)
  Total:       1.00  ✓

When upper_arm.L rotates 45°:
  This vertex moves 45% with upper_arm and 52% with forearm,
  creating a smooth bend at the elbow.
```

## 7.3 Example Transformation Matrix

```
Rig at position (0, 0, 0), scale (1.5, 1.5, 1.5), no rotation:

matrix_world =
┌ 1.5   0    0    0  ┐
│  0   1.5   0    0  │
│  0    0   1.5   0  │
└  0    0    0    1  ┘

Bone head in local space: (0.08, 0.1, 0.88)

World position = matrix_world @ (0.08, 0.1, 0.88, 1)
               = (0.12, 0.15, 1.32)

After transform_apply(scale=True):
  matrix_world becomes identity
  Bone head becomes (0.12, 0.15, 1.32) in local space
  World position unchanged
```

## 7.4 Cross-Section Analysis — Numerical Walkthrough

```
Mesh height: 1.80m (z_min=0.0, z_max=1.80)
80 slices → each slice = 0.0225m tall

Slice 66 (pos=1.498): width_x = 0.14  ← NECK (local minimum)
Slice 62 (pos=1.408): width_x = 0.42  ← SHOULDER (local maximum)
Slice 44 (pos=1.003): width_x = 0.28  ← WAIST (local minimum)
Slice 38 (pos=0.868): width_x = 0.38  ← HIP (local maximum)

Neck at 83.2% of height ✓ (within 82%-90% clamp)
Shoulder at 78.2% ✓ (within 78%-84% clamp)

Crotch detection:
  Scanning below hip (slice 38), width drops:
  Slice 35: width = 0.36 (95% of hip width 0.38)
  Slice 32: width = 0.30 (79% of hip width)
  Slice 30: width = 0.24 (63% of hip width) ← BELOW 65% threshold
  → Crotch Z = slice 30 position = 0.688m
```

---

# 8. Summary — How Humanoid and Quadruped Pipelines Differ in Code

| Pipeline Step        | Humanoid Code                | Quadruped Code                       |
| -------------------- | ---------------------------- | ------------------------------------ |
| Entry point          | `auto_rig_advanced()`        | `auto_rig_quadruped()`               |
| Analyzer             | `humanoid/analyzer.py`       | `quadruped/analyzer.py`              |
| Profile axis         | Z (vertical slicing)         | Y (horizontal slicing)               |
| Pose detection       | `detect_humanoid_pose()`     | Not needed                           |
| Template selection   | T-Pose or A-Pose             | Single template                      |
| Scale calculation    | `mesh_height / rig_height`   | `mesh_length_Y / rig_length_Y`       |
| Bone fitting         | `fit_bones_to_anatomy()`     | `fit_quadruped_bones()`              |
| Regional scaling     | `apply_regional_scaling()`   | `apply_quadruped_regional_scaling()` |
| IK pole (arms/front) | `(±0.1, 1.0, −0.3)` backward | `(0, +1, 0)` backward                |
| IK pole (legs/rear)  | `(0, −1, 0)` forward         | `(0, −1, 0)` forward                 |
| Raycast axes         | X and Y                      | X only                               |
| Raycast config       | `_humanoid_bone_config()`    | Custom inline                        |

### Shared Code (common/)

Both pipelines share 100% of:

- `mesh_utils.py` — geometry calculations
- `profile_analysis.py` — cross-section engine
- `blender_utils.py` — scene management
- `mesh_processing.py` — preprocessing and voxel proxy
- `fitting_utils.py` — IK solver, raycast, chain ratios

This modular architecture means improvements to the shared code benefit both pipelines simultaneously.
