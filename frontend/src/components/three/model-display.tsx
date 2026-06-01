import { useEffect, useRef, useMemo } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";

interface ModelDisplayProps {
	url: string;
	fileName: string;
	showSkeleton?: boolean;
}

// Default clay-like material (salmon tone matching reference image)
function createDefaultMaterial() {
	return new THREE.MeshStandardMaterial({
		color: new THREE.Color("#c77d6a"),
		roughness: 0.7,
		metalness: 0.05,
	});
}

// Auto-center and scale the model to fit viewport
function normalizeModel(object: THREE.Object3D) {
	// Reset any existing transforms on the object
	object.updateMatrixWorld(true);

	// Step 1: Compute initial bounding box
	const box = new THREE.Box3().setFromObject(object);
	const size = box.getSize(new THREE.Vector3());
	const center = box.getCenter(new THREE.Vector3());

	// Step 2: Scale to fit ~2 units tall
	const maxDim = Math.max(size.x, size.y, size.z);
	if (maxDim > 0) {
		const scale = 2 / maxDim;
		object.scale.multiplyScalar(scale);
	}

	// Step 3: Recompute bounding box AFTER scaling
	object.updateMatrixWorld(true);
	const scaledBox = new THREE.Box3().setFromObject(object);
	const scaledCenter = scaledBox.getCenter(new THREE.Vector3());

	// Step 4: Center horizontally (X, Z) and place feet at Y=0
	object.position.x -= scaledCenter.x;
	object.position.z -= scaledCenter.z;
	object.position.y -= scaledBox.min.y;
}

// Force-apply a visible material to ALL meshes.
// Many models use materials that are invisible in our scene (wrong color,
// transparent, unlit, or normals are flipped). This ensures every model
// is clearly visible with a consistent clay-like look.
function forceApplyMaterial(object: THREE.Object3D) {
	const defaultMat = createDefaultMaterial();
	// Double-sided rendering handles models with flipped normals
	defaultMat.side = THREE.DoubleSide;

	object.traverse((child) => {
		if (child instanceof THREE.Mesh) {
			child.material = defaultMat;
			child.castShadow = true;
			child.receiveShadow = true;
		}
	});
}

function getFileExtension(fileName: string): string {
	return fileName.split(".").pop()?.toLowerCase() || "";
}

export default function ModelDisplay({
	url,
	fileName,
	showSkeleton = false,
}: ModelDisplayProps) {
	const groupRef = useRef<THREE.Group>(null);
	const skeletonHelperRef = useRef<THREE.SkeletonHelper | null>(null);
	const { scene } = useThree();

	const fileExt = useMemo(() => getFileExtension(fileName), [fileName]);

	// Load model
	useEffect(() => {
		const group = groupRef.current;
		if (!group) return;

		// Clear previous model
		while (group.children.length > 0) {
			group.remove(group.children[0]);
		}

		// Remove old skeleton helper
		if (skeletonHelperRef.current) {
			scene.remove(skeletonHelperRef.current);
			skeletonHelperRef.current = null;
		}

		const onModelLoaded = (object: THREE.Object3D) => {
			forceApplyMaterial(object);
			normalizeModel(object);
			group.add(object);
		};

		const onError = (error: unknown) => {
			console.error("Failed to load model:", error);
		};

		switch (fileExt) {
			case "fbx": {
				const loader = new FBXLoader();
				loader.load(url, onModelLoaded, undefined, onError);
				break;
			}
			case "glb":
			case "gltf": {
				const loader = new GLTFLoader();
				loader.load(
					url,
					(gltf) => onModelLoaded(gltf.scene),
					undefined,
					onError
				);
				break;
			}
			case "obj": {
				const loader = new OBJLoader();
				loader.load(url, onModelLoaded, undefined, onError);
				break;
			}
			default:
				console.error(`Unsupported format: .${fileExt}`);
		}

		return () => {
			// Cleanup on unmount
			while (group.children.length > 0) {
				group.remove(group.children[0]);
			}
			if (skeletonHelperRef.current) {
				scene.remove(skeletonHelperRef.current);
				skeletonHelperRef.current = null;
			}
		};
	}, [url, fileExt, scene]);

	// Skeleton helper toggle
	useEffect(() => {
		const group = groupRef.current;
		if (!group) return;

		// Remove old skeleton helper
		if (skeletonHelperRef.current) {
			scene.remove(skeletonHelperRef.current);
			skeletonHelperRef.current = null;
		}

		if (showSkeleton) {
			// Create a skeleton helper for the entire group
			// This automatically finds all THREE.Bone objects within the hierarchy
			const helper = new THREE.SkeletonHelper(group);
			
			// Style the bones so they are highly visible
			const mat = helper.material as THREE.LineBasicMaterial;
			mat.linewidth = 3;
			mat.color = new THREE.Color("#00ffcc"); // Bright cyan
			mat.depthTest = false; // Render on top of meshes
			mat.transparent = true;
			
			scene.add(helper);
			skeletonHelperRef.current = helper;

			// Make meshes wireframe when showing skeleton
			group.traverse((child) => {
				if (child instanceof THREE.Mesh) {
					if (Array.isArray(child.material)) {
						child.material.forEach((mat) => {
							if (mat) {
								mat.wireframe = true;
								mat.needsUpdate = true;
							}
						});
					} else if (child.material) {
						child.material.wireframe = true;
						child.material.needsUpdate = true;
					}
				}
			});
		} else {
			// Restore solid mesh
			group.traverse((child) => {
				if (child instanceof THREE.Mesh) {
					if (Array.isArray(child.material)) {
						child.material.forEach((mat) => {
							if (mat) {
								mat.wireframe = false;
								mat.needsUpdate = true;
							}
						});
					} else if (child.material) {
						child.material.wireframe = false;
						child.material.needsUpdate = true;
					}
				}
			});
		}
	}, [showSkeleton, scene, url]);

	return <group ref={groupRef} />;
}
