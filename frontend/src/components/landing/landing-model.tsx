import { useRef, useEffect, useCallback } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
	getConfig,
	lerpValues,
	SECTION_IDS,
	type SectionAnimValues,
} from "../../config/scroll-anim-config";
import { createDissolveMaterial } from "./dissolve-material";

gsap.registerPlugin(ScrollTrigger);

interface LandingModelProps {
	onLoaded?: () => void;
	contentReady?: boolean;
}

export default function LandingModel({
	onLoaded,
	contentReady,
}: LandingModelProps) {
	const groupRef = useRef<THREE.Group>(null);
	const triggersRef = useRef<ScrollTrigger[]>([]);
	const timeRef = useRef(0);

	const humanGltf = useGLTF("/human.glb");
	const quadrupedGltf = useGLTF("/quadruped.glb");

	// Dissolve materials
	const humanDissolveRef = useRef<THREE.ShaderMaterial | null>(null);
	const quadDissolveRef = useRef<THREE.ShaderMaterial | null>(null);

	// Animation target
	const target = useRef<SectionAnimValues>({
		...getConfig().hero.start,
	});

	// Section activity tracking
	const classifyActive = useRef(false);
	const dissolveTime = useRef(0);
	const downloadActive = useRef(false);
	const skeletonGroupRef = useRef<THREE.Group | null>(null);
	
	// Used to instantly snap model to correct position on initial load/refresh
	const snapToTarget = useRef(true);

	// Setup models + dissolve materials
	useEffect(() => {
		const humanScene = humanGltf.scene;
		const quadScene = quadrupedGltf.scene;

		const humanMat = createDissolveMaterial({
			baseColor: "#c77d6a",
			edgeColor: "#00ffcc",
			edgeWidth: 0.06,
		});
		const quadMat = createDissolveMaterial({
			baseColor: "#c77d6a",
			edgeColor: "#ff6600",
			edgeWidth: 0.06,
		});

		humanDissolveRef.current = humanMat;
		quadDissolveRef.current = quadMat;

		humanScene.traverse((child) => {
			if (child instanceof THREE.Mesh) {
				child.material = humanMat;
				child.castShadow = true;
				child.receiveShadow = true;
			}
		});

		quadScene.traverse((child) => {
			if (child instanceof THREE.Mesh) {
				child.material = quadMat;
				child.castShadow = true;
				child.receiveShadow = true;
			}
		});

		// Both models normalized to SAME height
		normalizeScene(humanScene, 2.5);
		normalizeScene(quadScene, 2.5);

		// Quadruped starts fully dissolved (invisible)
		quadMat.uniforms.uProgress.value = 1.0;
		quadScene.visible = true;
	}, [humanGltf.scene, quadrupedGltf.scene]);

	// Notify parent
	const notifyLoaded = useCallback(() => {
		onLoaded?.();
	}, [onLoaded]);
	useEffect(() => {
		notifyLoaded();
	}, [notifyLoaded]);

	// ScrollTrigger setup — triggers when section reaches center of viewport
	useEffect(() => {
		if (!contentReady) return;

		const timer = setTimeout(() => {
			triggersRef.current.forEach((t) => t.kill());
			triggersRef.current = [];
			ScrollTrigger.refresh();

			const config = getConfig();
			const triggers: ScrollTrigger[] = [];
			const animTriggers: ScrollTrigger[] = [];

			const updateTarget = () => {
				if (animTriggers.length === 0) return;
				let activeIndex = -1;
				for (let i = 0; i < animTriggers.length; i++) {
					if (animTriggers[i].progress > 0) {
						activeIndex = i;
					}
				}

				if (activeIndex === -1) {
					Object.assign(target.current, config.hero.start);
				} else {
					const t = animTriggers[activeIndex];
					// activeIndex 0 is upload (SECTION_IDS[1])
					const id = SECTION_IDS[activeIndex + 1];
					const sectionConfig = config[id];
					Object.assign(
						target.current,
						lerpValues(sectionConfig.start, sectionConfig.end, t.progress)
					);
				}
			};

			for (const id of SECTION_IDS) {
				if (id === "hero") continue;

				const el = document.querySelector(`#${id}`);
				if (!el) continue;

				// Position animation: triggers as section comes into center
				const st = ScrollTrigger.create({
					trigger: el,
					start: "top 80%",
					end: "center center",
					scrub: 0.8,
					onUpdate: updateTarget,
				});
				
				animTriggers.push(st);
				triggers.push(st);
			}

			// Force initial evaluation
			updateTarget();

			// Dissolve activation — only when classify is centered
			const classifyEl = document.querySelector("#classify");
			if (classifyEl) {
				triggers.push(
					ScrollTrigger.create({
						trigger: classifyEl,
						start: "top 20%",
						end: "bottom 50%",
						onEnter: () => {
							if (humanDissolveRef.current) gsap.killTweensOf(humanDissolveRef.current.uniforms.uProgress);
							if (quadDissolveRef.current) gsap.killTweensOf(quadDissolveRef.current.uniforms.uProgress);
							classifyActive.current = true;
							dissolveTime.current = 0;
						},
						onLeave: () => {
							classifyActive.current = false;
							resetDissolve();
						},
						onEnterBack: () => {
							if (humanDissolveRef.current) gsap.killTweensOf(humanDissolveRef.current.uniforms.uProgress);
							if (quadDissolveRef.current) gsap.killTweensOf(quadDissolveRef.current.uniforms.uProgress);
							classifyActive.current = true;
							dissolveTime.current = 0;
						},
						onLeaveBack: () => {
							classifyActive.current = false;
							resetDissolve();
						},
					}),
				);
			}

			// Skeleton activation — only when download is centered
			const downloadEl = document.querySelector("#download");
			if (downloadEl) {
				triggers.push(
					ScrollTrigger.create({
						trigger: downloadEl,
						start: "top 60%",
						end: "bottom 40%",
						onEnter: () => {
							downloadActive.current = true;
						},
						onLeave: () => {
							downloadActive.current = false;
						},
						onEnterBack: () => {
							downloadActive.current = true;
						},
						onLeaveBack: () => {
							downloadActive.current = false;
						},
					}),
				);
			}

			triggersRef.current = triggers;

			// Turn off snapping 500ms after triggers are set up
			setTimeout(() => {
				snapToTarget.current = false;
			}, 500);
		}, 200);

		return () => {
			clearTimeout(timer);
			triggersRef.current.forEach((t) => t.kill());
			triggersRef.current = [];
		};
	}, [contentReady]);

	function resetDissolve() {
		if (humanDissolveRef.current) {
			gsap.to(humanDissolveRef.current.uniforms.uProgress, {
				value: 0,
				duration: 1.2,
				ease: "power2.inOut",
			});
		}
		if (quadDissolveRef.current) {
			gsap.to(quadDissolveRef.current.uniforms.uProgress, {
				value: 1,
				duration: 1.2,
				ease: "power2.inOut",
			});
		}
	}

	// Render loop
	useFrame((state, delta) => {
		timeRef.current += delta;
		const t = target.current;
		const group = groupRef.current;

		const lerpPos = snapToTarget.current ? 1 : 0.08;

		if (group) {
			const floatY =
				Math.sin(timeRef.current * 0.8) * 0.04 * t.floatIntensity;
			const floatScale =
				1 + Math.sin(timeRef.current * 1.2) * 0.008 * t.floatIntensity;

			group.position.x += (t.posX - group.position.x) * lerpPos;
			group.position.y += (t.posY + floatY - group.position.y) * lerpPos;
			group.position.z += (t.posZ - group.position.z) * lerpPos;
			
			if (snapToTarget.current) {
				group.rotation.y = t.rotY;
			} else {
				group.rotation.y += (t.rotY - group.rotation.y) * 0.06;
			}
			
			const targetScale = t.scale * floatScale;
			group.scale.setScalar(
				group.scale.x + (targetScale - group.scale.x) * lerpPos,
			);
		}

		// Camera is now fixed, no updates here.

		// === Dissolve cycling (smooth, 7 second cycle) ===
		if (classifyActive.current) {
			dissolveTime.current += delta;
			const cycle = 7; // total cycle duration
			const dissolveLen = 2.5; // how long the dissolve transition takes
			const holdLen = 1.0; // how long to hold each form
			const cycleT = dissolveTime.current % cycle;

			let humanP: number;
			let quadP: number;

			if (cycleT < dissolveLen) {
				// Human dissolves out → Quadruped appears
				const raw = cycleT / dissolveLen;
				const p = smoothstep(raw);
				humanP = p;
				quadP = 1 - p;
			} else if (cycleT < dissolveLen + holdLen) {
				// Hold quadruped
				humanP = 1;
				quadP = 0;
			} else if (cycleT < dissolveLen * 2 + holdLen) {
				// Quadruped dissolves out → Human appears
				const raw = (cycleT - dissolveLen - holdLen) / dissolveLen;
				const p = smoothstep(raw);
				humanP = 1 - p;
				quadP = p;
			} else {
				// Hold human
				humanP = 0;
				quadP = 1;
			}

			if (humanDissolveRef.current)
				humanDissolveRef.current.uniforms.uProgress.value = humanP;
			if (quadDissolveRef.current)
				quadDissolveRef.current.uniforms.uProgress.value = quadP;
		}

		// === Custom Thick Skeleton in download section ===
		if (downloadActive.current) {
			if (!skeletonGroupRef.current) {
				const boneGroup = new THREE.Group();
				
				const boneMat = new THREE.MeshStandardMaterial({
					color: 0x00ffff,
					emissive: 0x0088cc,
					emissiveIntensity: 1.0,
					roughness: 0.2,
					metalness: 0.8,
					depthTest: false,
					transparent: true,
					opacity: 0.95
				});

				const sphereGeom = new THREE.SphereGeometry(0.012, 8, 8);
				const cylinderGeom = new THREE.CylinderGeometry(0.015, 0.005, 1, 8);
				cylinderGeom.translate(0, 0.5, 0); // Base at origin
				cylinderGeom.rotateX(Math.PI / 2); // Point along +Z

				humanGltf.scene.traverse((child) => {
					if (child.type === "Bone") {
						const bone = child as THREE.Bone;
						
						// Create joint sphere
						const joint = new THREE.Mesh(sphereGeom, boneMat);
						joint.renderOrder = 999;
						joint.userData.isCustomBone = true;
						bone.add(joint);

						// Create bone segments
						bone.children.forEach((c) => {
							if (c.type === "Bone") {
								const length = c.position.length();
								if (length > 0.001) {
									const seg = new THREE.Mesh(cylinderGeom, boneMat);
									seg.scale.set(1, 1, length);
									
									const dir = c.position.clone().normalize();
									const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir);
									seg.quaternion.copy(q);
									
									seg.renderOrder = 999;
									seg.userData.isCustomBone = true;
									bone.add(seg);
								}
							}
						});
					}
				});
				
				boneGroup.userData = { boneMat, sphereGeom, cylinderGeom };
				state.scene.add(boneGroup);
				skeletonGroupRef.current = boneGroup;

				humanGltf.scene.traverse((child) => {
					if (child instanceof THREE.Mesh && !child.userData.isCustomBone) {
						const m = child.material as THREE.ShaderMaterial;
						if (m.wireframe !== undefined) m.wireframe = false;
					}
				});
			}
		} else {
			if (skeletonGroupRef.current) {
				humanGltf.scene.traverse((child) => {
					if (child.type === "Bone") {
						const toRemove = child.children.filter((c) => c.userData.isCustomBone);
						toRemove.forEach((c) => child.remove(c));
					}
				});

				const { boneMat, sphereGeom, cylinderGeom } = skeletonGroupRef.current.userData;
				boneMat.dispose();
				sphereGeom.dispose();
				cylinderGeom.dispose();

				state.scene.remove(skeletonGroupRef.current);
				skeletonGroupRef.current = null;
			}
		}
	});

	return (
		<group
			ref={groupRef}
			position={[target.current.posX, 0, 0]}
			rotation={[0, target.current.rotY, 0]}
		>
			<primitive object={humanGltf.scene} />
			<primitive object={quadrupedGltf.scene} />
		</group>
	);
}

// === Helpers ===

/** Smooth easing for dissolve transitions */
function smoothstep(t: number): number {
	t = Math.max(0, Math.min(1, t));
	return t * t * (3 - 2 * t);
}

function normalizeScene(scene: THREE.Object3D, targetHeight: number) {
	const box = new THREE.Box3().setFromObject(scene);
	const size = box.getSize(new THREE.Vector3());
	const maxDim = Math.max(size.x, size.y, size.z);
	if (maxDim > 0) {
		const s = targetHeight / maxDim;
		scene.scale.set(s, s, s);
	}
	scene.updateMatrixWorld(true);
	const scaledBox = new THREE.Box3().setFromObject(scene);
	const scaledCenter = scaledBox.getCenter(new THREE.Vector3());
	scene.position.x -= scaledCenter.x;
	scene.position.z -= scaledCenter.z;
	scene.position.y -= scaledBox.min.y;
}

useGLTF.preload("/human.glb");
useGLTF.preload("/quadruped.glb");
