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
	const renderActive = useRef(false);
	const renderTime = useRef(0);
	const cameraGroupRef = useRef<THREE.Group | null>(null);
	const classifyActive = useRef(false);
	const dissolveTime = useRef(0);
	const templateActive = useRef(false);
	const fittingActive = useRef(false);
	const weightingActive = useRef(false);
	const downloadActive = useRef(false);

	const skeletonGroupRef = useRef<THREE.Group | null>(null);
	const skeletonLerp = useRef(0); // 0 = misaligned (template), 1 = aligned (fitting/download)

	// Idle animation state (Step 7)
	const idleTime = useRef(0);
	const idleProgress = useRef(0); // 0=T-pose, 1=idle
	const savedBoneRotations = useRef<Map<string, THREE.Euler>>(new Map());
	const readySpriteRef = useRef<THREE.Sprite | null>(null);

	// Used to instantly snap model to correct position on initial load/refresh
	const snapToTarget = useRef(true);

	// Setup models + dissolve materials
	useEffect(() => {
		const humanScene = humanGltf.scene;
		const quadScene = quadrupedGltf.scene;

		const humanMat = createDissolveMaterial({
			baseColor: "#c8e0dc",
			edgeColor: "#354b47",
			edgeWidth: 0.06,
		});
		const quadMat = createDissolveMaterial({
			baseColor: "#c8e0dc",
			edgeColor: "#544a69",
			edgeWidth: 0.06,
		});

		humanDissolveRef.current = humanMat;
		quadDissolveRef.current = quadMat;

		const standardHumanMat = new THREE.MeshStandardMaterial({
			color: "#c8e0dc",
			roughness: 0.4,
			metalness: 0.1,
		});

		humanScene.traverse((child) => {
			if (child instanceof THREE.Mesh || child.type === "SkinnedMesh") {
				(child as THREE.Mesh).material = humanMat;
				child.userData.dissolveMat = humanMat;
				child.userData.standardMat = standardHumanMat;
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

		// Setup weight paint bones for human model
		const weightBones: THREE.Bone[] = [];
		humanScene.traverse((child) => {
			if (child.type === "Bone") weightBones.push(child as THREE.Bone);
		});

		// Pick 6 evenly spaced or key bones (e.g. head, chest, hands, feet)
		// We'll just pick 6 spread out across the array
		const selectedBones = [];
		const numBones = Math.min(6, weightBones.length);
		for (let i = 0; i < numBones; i++) {
			selectedBones.push(
				weightBones[
					Math.floor(
						(i / Math.max(1, numBones - 1)) *
							(weightBones.length - 1),
					)
				],
			);
		}

		// Find the main mesh to convert world positions to mesh local space
		let mainMesh: THREE.Mesh | null = null;
		humanScene.traverse((child) => {
			if (!mainMesh && child instanceof THREE.Mesh) mainMesh = child;
		});

		const targetMesh = mainMesh as THREE.Mesh | null;
		if (targetMesh) {
			const meshInverse = targetMesh.matrixWorld.clone().invert();
			const colors = [
				new THREE.Color(1.0, 0.0, 0.0), // Red
				new THREE.Color(1.0, 0.5, 0.0), // Orange
				new THREE.Color(1.0, 1.0, 0.0), // Yellow
				new THREE.Color(0.0, 1.0, 0.0), // Green
				new THREE.Color(0.0, 0.5, 1.0), // Blue
				new THREE.Color(0.5, 0.0, 1.0), // Purple
			];

			const positionsArray = humanMat.uniforms.uBonePositions
				.value as THREE.Vector3[];
			const colorsArray = humanMat.uniforms.uBoneColors
				.value as THREE.Color[];

			selectedBones.forEach((bone, i) => {
				if (!bone) return;
				const wp = new THREE.Vector3();
				bone.getWorldPosition(wp);
				const lp = wp.applyMatrix4(meshInverse);
				positionsArray[i].copy(lp);
				colorsArray[i].copy(colors[i % colors.length]);
			});
		}

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
			// ScrollTrigger.refresh();

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
						lerpValues(
							sectionConfig.start,
							sectionConfig.end,
							t.progress,
						),
					);

					// Clamp: once download trigger is fully done, freeze at its end position
					if (id === "download" && t.progress >= 1) {
						Object.assign(target.current, config.download.end);
					}
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

			// Moved here
			ScrollTrigger.refresh();

			// Force initial evaluation
			updateTarget();

			// Render section — orbiting cameras
			const renderEl = document.querySelector("#render");
			if (renderEl) {
				triggers.push(
					ScrollTrigger.create({
						trigger: renderEl,
						start: "top 60%",
						end: "bottom 40%",
						onEnter: () => {
							renderActive.current = true;
							renderTime.current = 0;
						},
						onLeave: () => {
							renderActive.current = false;
						},
						onEnterBack: () => {
							renderActive.current = true;
							renderTime.current = 0;
						},
						onLeaveBack: () => {
							renderActive.current = false;
						},
					}),
				);
			}

			// Dissolve activation — only when classify is centered
			const classifyEl = document.querySelector("#classify");
			if (classifyEl) {
				triggers.push(
					ScrollTrigger.create({
						trigger: classifyEl,
						start: "top 20%",
						end: "bottom 50%",
						onEnter: () => {
							if (humanDissolveRef.current)
								gsap.killTweensOf(
									humanDissolveRef.current.uniforms.uProgress,
								);
							if (quadDissolveRef.current)
								gsap.killTweensOf(
									quadDissolveRef.current.uniforms.uProgress,
								);
							classifyActive.current = true;
							dissolveTime.current = 0;
						},
						onLeave: () => {
							classifyActive.current = false;
							resetDissolve();
						},
						onEnterBack: () => {
							if (humanDissolveRef.current)
								gsap.killTweensOf(
									humanDissolveRef.current.uniforms.uProgress,
								);
							if (quadDissolveRef.current)
								gsap.killTweensOf(
									quadDissolveRef.current.uniforms.uProgress,
								);
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

			// Template skeleton activation
			const templateEl = document.querySelector("#template");
			if (templateEl) {
				triggers.push(
					ScrollTrigger.create({
						trigger: templateEl,
						start: "top 40%",
						end: "bottom 40%",
						onEnter: () => {
							templateActive.current = true;
						},
						onLeave: () => {
							templateActive.current = false;
						},
						onEnterBack: () => {
							templateActive.current = true;
						},
						onLeaveBack: () => {
							templateActive.current = false;
						},
					}),
				);
			}

			// Fitting skeleton activation
			const fittingEl = document.querySelector("#fitting");
			if (fittingEl) {
				triggers.push(
					ScrollTrigger.create({
						trigger: fittingEl,
						start: "top 60%",
						end: "bottom 40%",
						onEnter: () => {
							fittingActive.current = true;
						},
						onLeave: () => {
							fittingActive.current = false;
						},
						onEnterBack: () => {
							fittingActive.current = true;
						},
						onLeaveBack: () => {
							fittingActive.current = false;
						},
					}),
				);
			}

			// Weighting activation
			const weightingEl = document.querySelector("#weighting");
			if (weightingEl) {
				triggers.push(
					ScrollTrigger.create({
						trigger: weightingEl,
						start: "top 60%",
						end: "bottom 40%",
						onEnter: () => {
							weightingActive.current = true;
						},
						onLeave: () => {
							weightingActive.current = false;
						},
						onEnterBack: () => {
							weightingActive.current = true;
						},
						onLeaveBack: () => {
							weightingActive.current = false;
						},
					}),
				);
			}

			// Download activation
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

		// === Orbiting cameras in render section ===
		if (renderActive.current) {
			renderTime.current += delta;
			if (!cameraGroupRef.current) {
				const camGroup = new THREE.Group();

				// Camera body material
				const camBodyMat = new THREE.MeshStandardMaterial({
					color: 0x555566,
					metalness: 0.9,
					roughness: 0.3,
				});
				const lensMat = new THREE.MeshStandardMaterial({
					color: 0x222233,
					metalness: 0.8,
					roughness: 0.1,
					emissive: 0x0066ff,
					emissiveIntensity: 0.3,
				});
				const laserMat = new THREE.LineBasicMaterial({
					color: 0x00ffcc,
					transparent: true,
					opacity: 0.6,
				});

				// Shared geometries
				const bodyGeom = new THREE.BoxGeometry(0.12, 0.08, 0.08);
				const lensGeom = new THREE.CylinderGeometry(
					0.025,
					0.03,
					0.05,
					12,
				);
				lensGeom.rotateX(Math.PI / 2);

				for (let i = 0; i < 4; i++) {
					const camMesh = new THREE.Group();

					// Body
					const body = new THREE.Mesh(bodyGeom, camBodyMat);
					camMesh.add(body);

					// Lens (front)
					const lens = new THREE.Mesh(lensGeom, lensMat);
					lens.position.z = -0.065;
					camMesh.add(lens);

					// Laser line from camera to model center
					const laserGeom = new THREE.BufferGeometry().setFromPoints([
						new THREE.Vector3(0, 0, 0),
						new THREE.Vector3(0, 0, 1), // will be updated each frame
					]);
					const laser = new THREE.Line(laserGeom, laserMat);
					laser.userData.isLaser = true;
					camMesh.add(laser);

					camMesh.userData.orbitIndex = i;
					camGroup.add(camMesh);
				}

				camGroup.userData = {
					camBodyMat,
					lensMat,
					laserMat,
					bodyGeom,
					lensGeom,
				};
				state.scene.add(camGroup);
				cameraGroupRef.current = camGroup;
			}

			// Animate orbiting cameras
			const camGroup = cameraGroupRef.current;
			if (camGroup && group) {
				const modelCenter = new THREE.Vector3();
				group.getWorldPosition(modelCenter);
				modelCenter.y += 1.0; // aim at chest height

				const orbitRadius = 2.0;
				const orbitSpeed = 0.4; // radians per second
				const baseAngle = renderTime.current * orbitSpeed;

				camGroup.children.forEach((camMesh, idx) => {
					const angle = baseAngle + (idx * Math.PI) / 2;
					const x = modelCenter.x + Math.cos(angle) * orbitRadius;
					const z = modelCenter.z + Math.sin(angle) * orbitRadius;
					const y =
						modelCenter.y +
						Math.sin(renderTime.current * 0.7 + idx) * 0.15;

					camMesh.position.set(x, y, z);
					camMesh.lookAt(modelCenter);

					// Update laser line endpoint
					camMesh.children.forEach((child) => {
						if (
							child.userData.isLaser &&
							child instanceof THREE.Line
						) {
							const laserGeom =
								child.geometry as THREE.BufferGeometry;
							const worldToLocal = camMesh.matrixWorld
								.clone()
								.invert();
							const localTarget = modelCenter
								.clone()
								.applyMatrix4(worldToLocal);
							const positions = laserGeom.attributes.position;
							positions.setXYZ(
								1,
								localTarget.x,
								localTarget.y,
								localTarget.z,
							);
							positions.needsUpdate = true;
						}
					});

					// Fade in
					const fadeIn = Math.min(1, renderTime.current * 2);
					camMesh.scale.setScalar(fadeIn);
				});
			}
		} else {
			if (cameraGroupRef.current) {
				const { camBodyMat, lensMat, laserMat, bodyGeom, lensGeom } =
					cameraGroupRef.current.userData;
				camBodyMat.dispose();
				lensMat.dispose();
				laserMat.dispose();
				bodyGeom.dispose();
				lensGeom.dispose();
				// Dispose laser geometries
				cameraGroupRef.current.children.forEach((camMesh) => {
					camMesh.children.forEach((child) => {
						if (child instanceof THREE.Line) {
							child.geometry.dispose();
						}
					});
				});
				state.scene.remove(cameraGroupRef.current);
				cameraGroupRef.current = null;
			}
		}

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

		// === Unified Skeleton (Template, Fitting) ===
		const skeletonActive = templateActive.current || fittingActive.current;

		if (skeletonActive) {
			// Determine target lerp based on section
			// template = 0 (misaligned), fitting/download = 1 (aligned)
			const targetLerp = templateActive.current ? 0 : 1;
			// Smoothly animate the lerp value
			skeletonLerp.current +=
				(targetLerp - skeletonLerp.current) * (delta * 4.0);

			if (!skeletonGroupRef.current) {
				const boneGroup = new THREE.Group();

				const boneMat = new THREE.MeshStandardMaterial({
					color: 0xffffff, // will be updated per frame
					emissive: 0xffffff,
					emissiveIntensity: 0.8,
					roughness: 0.2,
					metalness: 0.8,
					depthTest: false,
					transparent: true,
					opacity: 0.95,
				});

				const sphereGeom = new THREE.SphereGeometry(0.015, 8, 8);
				const cylinderGeom = new THREE.CylinderGeometry(
					0.018,
					0.006,
					1,
					8,
				);
				cylinderGeom.translate(0, 0.5, 0); // Base at origin
				cylinderGeom.rotateX(Math.PI / 2); // Point along +Z

				// First pass: Calculate model center for distortion
				const boneWorldPositions: THREE.Vector3[] = [];
				group!.updateMatrixWorld(true);
				humanGltf.scene.traverse((child) => {
					if (child.type === "Bone") {
						const wp = new THREE.Vector3();
						child.getWorldPosition(wp);
						boneWorldPositions.push(wp);
					}
				});
				const modelCenter = new THREE.Vector3();
				if (boneWorldPositions.length > 0) {
					boneWorldPositions.forEach((p) => modelCenter.add(p));
					modelCenter.divideScalar(boneWorldPositions.length);
				}

				// Second pass: Create custom bones
				humanGltf.scene.traverse((child) => {
					if (child.type === "Bone") {
						const bone = child as THREE.Bone;

						// Calculate distorted local position for this joint
						const worldPos = new THREE.Vector3();
						bone.getWorldPosition(worldPos);

						const distortedWorld = worldPos.clone();
						const dx = distortedWorld.x - modelCenter.x;
						distortedWorld.x = modelCenter.x + dx * 1.45;
						// Random deterministic offset based on bone name length/chars
						const seed = bone.name.length;
						distortedWorld.y += Math.sin(seed * 123) * 0.15;
						distortedWorld.z += Math.cos(seed * 321) * 0.08;

						// Convert distorted world to bone local space
						const boneInverse = bone.matrixWorld.clone().invert();
						const distortedLocal =
							distortedWorld.applyMatrix4(boneInverse);

						// Create joint sphere
						const joint = new THREE.Mesh(sphereGeom, boneMat);
						joint.renderOrder = 999;
						joint.userData = { isCustomBone: true, distortedLocal };
						bone.add(joint);

						// Create bone segments pointing to children
						bone.children.forEach((c) => {
							if (c.type === "Bone") {
								const childBone = c as THREE.Bone;

								// Calculate child's distorted world position
								const cWorldPos = new THREE.Vector3();
								childBone.getWorldPosition(cWorldPos);

								const cDistortedWorld = cWorldPos.clone();
								const cdx = cDistortedWorld.x - modelCenter.x;
								cDistortedWorld.x = modelCenter.x + cdx * 1.45;
								const cSeed = childBone.name.length;
								cDistortedWorld.y +=
									Math.sin(cSeed * 123) * 0.15;
								cDistortedWorld.z +=
									Math.cos(cSeed * 321) * 0.08;

								// Child's distorted position in THIS bone's local space
								const childDistortedLocal =
									cDistortedWorld.applyMatrix4(boneInverse);

								const seg = new THREE.Mesh(
									cylinderGeom,
									boneMat,
								);
								seg.renderOrder = 999;
								seg.userData = {
									isCustomBone: true,
									isSegment: true,
									childDistortedLocal,
									childCorrectLocal:
										childBone.position.clone(),
								};
								joint.add(seg); // Add segment to joint so it moves with the joint's offset!
							}
						});
					}
				});

				boneGroup.userData = { boneMat, sphereGeom, cylinderGeom };
				state.scene.add(boneGroup);
				skeletonGroupRef.current = boneGroup;
			}

			// Update skeleton animation each frame
			if (skeletonGroupRef.current) {
				const { boneMat } = skeletonGroupRef.current.userData;
				const lerp = skeletonLerp.current;

				// Interpolate color: Orange (template) to Cyan (fitting)
				const orange = new THREE.Color(0xff9500);
				const cyan = new THREE.Color(0x00ffff);
				boneMat.color.lerpColors(orange, cyan, lerp);

				const orangeEmissive = new THREE.Color(0xcc6600);
				const cyanEmissive = new THREE.Color(0x0088cc);
				boneMat.emissive.lerpColors(orangeEmissive, cyanEmissive, lerp);

				// Update bone positions and segments
				humanGltf.scene.traverse((child) => {
					if (child.type === "Bone") {
						const bone = child as THREE.Bone;
						bone.children.forEach((joint) => {
							if (
								joint.userData.isCustomBone &&
								!joint.userData.isSegment
							) {
								// Interpolate joint position
								const distLocal = joint.userData
									.distortedLocal as THREE.Vector3;
								joint.position.lerpVectors(
									distLocal,
									new THREE.Vector3(0, 0, 0),
									lerp,
								);

								// Update segments attached to this joint
								joint.children.forEach((seg) => {
									if (seg.userData.isSegment) {
										const cDistLocal = seg.userData
											.childDistortedLocal as THREE.Vector3;
										const cCorrLocal = seg.userData
											.childCorrectLocal as THREE.Vector3;

										// Calculate where the child is currently located in bone space
										const currentChildLocal =
											new THREE.Vector3().lerpVectors(
												cDistLocal,
												cCorrLocal,
												lerp,
											);

										// Segment points from joint (which is at joint.position) to child (currentChildLocal)
										// Since segment is a child of joint, its local space origin is joint.position.
										// So we need the vector from joint.position to currentChildLocal
										const dir = currentChildLocal
											.clone()
											.sub(joint.position);
										const length = dir.length();

										if (length > 0.001) {
											seg.scale.set(1, 1, length);
											const q =
												new THREE.Quaternion().setFromUnitVectors(
													new THREE.Vector3(0, 0, 1),
													dir.normalize(),
												);
											seg.quaternion.copy(q);
											seg.visible = true;
										} else {
											seg.visible = false;
										}
									}
								});
							}
						});
					}
				});

				// Update model opacity
				// template = 0.4 opacity, fitting/download = 1.0 opacity
				humanGltf.scene.traverse((child) => {
					if (
						child instanceof THREE.Mesh &&
						!child.userData.isCustomBone
					) {
						const m = child.material as THREE.ShaderMaterial;
						const currentOpacity = 0.4 + 0.6 * lerp;

						if (m.uniforms?.uAlpha)
							m.uniforms.uAlpha.value = currentOpacity;
						else if ("opacity" in m) {
							m.transparent = currentOpacity < 1.0;
							(m as any).opacity = currentOpacity;
						}
					}
				});
			}
		} else {
			// Cleanup skeleton
			if (skeletonGroupRef.current) {
				humanGltf.scene.traverse((child) => {
					if (child.type === "Bone") {
						const toRemove = child.children.filter(
							(c) => c.userData.isCustomBone,
						);
						toRemove.forEach((c) => child.remove(c));
					}
				});

				const { boneMat, sphereGeom, cylinderGeom } =
					skeletonGroupRef.current.userData;
				boneMat.dispose();
				sphereGeom.dispose();
				cylinderGeom.dispose();
				state.scene.remove(skeletonGroupRef.current);
				skeletonGroupRef.current = null;
				skeletonLerp.current = 0;

				// Restore model opacity
				humanGltf.scene.traverse((child) => {
					if (
						child instanceof THREE.Mesh &&
						!child.userData.isCustomBone
					) {
						const m = child.material as THREE.ShaderMaterial;
						if (m.uniforms?.uAlpha) m.uniforms.uAlpha.value = 1.0;
						else if ("opacity" in m) {
							m.transparent = false;
							(m as any).opacity = 1.0;
						}
					}
				});
			}
		}

		// === Weight Paint Animation ===
		if (humanDissolveRef.current) {
			const targetWeight = weightingActive.current ? 1.0 : 0.0;
			const currentWeight =
				humanDissolveRef.current.uniforms.uWeightProgress.value;
			humanDissolveRef.current.uniforms.uWeightProgress.value +=
				(targetWeight - currentWeight) * (delta * 3.0);
		}

		// === Step 7: Idle Animation (Download section) ===
		if (downloadActive.current) {
			idleTime.current += delta;

			// Switch to standard skinning material
			humanGltf.scene.traverse((child) => {
				if (
					(child instanceof THREE.Mesh ||
						child.type === "SkinnedMesh") &&
					child.userData.standardMat
				) {
					if (
						(child as THREE.Mesh).material !==
						child.userData.standardMat
					) {
						(child as THREE.Mesh).material =
							child.userData.standardMat;
					}
				}
			});

			// Ease in the idle pose over ~2 seconds
			idleProgress.current = Math.min(
				1,
				idleProgress.current + delta * 0.5,
			);
			const p = smoothstep(idleProgress.current);

			// Save original rotations on first frame
			if (savedBoneRotations.current.size === 0) {
				humanGltf.scene.traverse((child) => {
					if (child.type === "Bone") {
						savedBoneRotations.current.set(
							child.name,
							child.rotation.clone(),
						);
					}
				});
			}

			const time = idleTime.current;

			humanGltf.scene.traverse((child) => {
				if (child.type !== "Bone") return;
				const bone = child as THREE.Bone;
				const name = bone.name.toLowerCase();
				const saved = savedBoneRotations.current.get(bone.name);
				if (!saved) return;

				// Breathing — subtle chest/spine movement
				if (
					name.includes("spine") ||
					name.includes("chest") ||
					name.includes("torso")
				) {
					const breathe = Math.sin(time * 1.8) * 0.015 * p;
					bone.rotation.x = saved.x + breathe;
					bone.rotation.z =
						saved.z + Math.sin(time * 0.7) * 0.008 * p;
				}

				// Head — gentle look around
				if (name.includes("head") || name.includes("neck")) {
					bone.rotation.y = saved.y + Math.sin(time * 0.5) * 0.04 * p;
					bone.rotation.x = saved.x + Math.sin(time * 0.8) * 0.02 * p;
				}

				// Upper arms — loop up and down
				if (
					name.includes("upperarm") ||
					name.includes("upper_arm") ||
					name.includes("arm.l") ||
					name.includes("arm.r") ||
					name.includes("shoulder")
				) {
					const armLower = 0.15 * p;
					// Add a looping sine wave for the up/down motion
					const loopMotion = Math.sin(time * 2.5) * 0.6 * p;
					if (
						name.includes("left") ||
						name.includes(".l") ||
						name.includes("_l")
					) {
						bone.rotation.z = saved.z + armLower - loopMotion;
					} else {
						bone.rotation.z = saved.z - armLower + loopMotion;
					}
				}

				// Forearms — bend with the loop
				if (
					name.includes("forearm") ||
					name.includes("lower_arm") ||
					name.includes("lowerarm")
				) {
					const loopBend = Math.abs(Math.sin(time * 2.5)) * 0.5 * p;
					bone.rotation.y = saved.y + 0.3 * p + loopBend;
					bone.rotation.x = saved.x + Math.sin(time * 1.2) * 0.02 * p;
				}

				// Hips — very subtle sway
				if (name.includes("hip") || name.includes("pelvis")) {
					bone.rotation.y =
						saved.y + Math.sin(time * 0.4) * 0.015 * p;
				}

				// Legs — very slight knee bend
				if (
					name.includes("thigh") ||
					name.includes("upper_leg") ||
					name.includes("upperleg")
				) {
					bone.rotation.x = saved.x + 0.05 * p;
				}
			});
		} else {
			// Switch back to dissolve material
			humanGltf.scene.traverse((child) => {
				if (
					(child instanceof THREE.Mesh ||
						child.type === "SkinnedMesh") &&
					child.userData.dissolveMat
				) {
					if (
						(child as THREE.Mesh).material !==
						child.userData.dissolveMat
					) {
						(child as THREE.Mesh).material =
							child.userData.dissolveMat;
					}
				}
			});

			// Cleanup Ready sprite
			if (readySpriteRef.current) {
				const sprite = readySpriteRef.current;
				sprite.material.dispose();
				sprite.material.map?.dispose();
				group?.remove(sprite);
				readySpriteRef.current = null;
			}

			// Restore original bone rotations when leaving download section
			if (idleProgress.current > 0) {
				idleProgress.current = Math.max(
					0,
					idleProgress.current - delta * 2.0,
				);
				const p = smoothstep(idleProgress.current);

				if (savedBoneRotations.current.size > 0) {
					humanGltf.scene.traverse((child) => {
						if (child.type !== "Bone") return;
						const saved = savedBoneRotations.current.get(
							child.name,
						);
						if (!saved) return;
						// Lerp back to saved rotation
						child.rotation.x += (saved.x - child.rotation.x) * 0.1;
						child.rotation.y += (saved.y - child.rotation.y) * 0.1;
						child.rotation.z += (saved.z - child.rotation.z) * 0.1;
					});

					if (p <= 0.01) {
						// Snap to exact original and clear
						humanGltf.scene.traverse((child) => {
							if (child.type !== "Bone") return;
							const saved = savedBoneRotations.current.get(
								child.name,
							);
							if (saved) child.rotation.copy(saved);
						});
						savedBoneRotations.current.clear();
						idleTime.current = 0;
						idleProgress.current = 0;
					}
				}
			}
		}
	});

	return (
		<group
			ref={groupRef}
			position={[
				target.current.posX,
				target.current.posY,
				target.current.posZ,
			]}
			rotation={[0, target.current.rotY, 0]}
			scale={target.current.scale}
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
