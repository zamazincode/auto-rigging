import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Suspense, useRef, useImperativeHandle, forwardRef } from "react";
import * as THREE from "three";
import SceneEnvironment from "./scene-environment";
import type { OrbitControls as OrbitControlsType } from "three-stdlib";
import type { ViewMode } from "../../types";

export interface ModelViewerHandle {
	resetCamera: () => void;
}

interface ModelViewerProps {
	children?: React.ReactNode;
	viewMode?: ViewMode;
}

const ModelViewer = forwardRef<ModelViewerHandle, ModelViewerProps>(
	({ children, viewMode = "orbit" }, ref) => {
		const controlsRef = useRef<OrbitControlsType>(null);

		useImperativeHandle(ref, () => ({
			resetCamera: () => {
				if (controlsRef.current) {
					controlsRef.current.reset();
				}
			},
		}));

		return (
			<Canvas
				shadows
				camera={{
					position: [0, 1.5, 3],
					fov: 50,
					near: 0.1,
					far: 100,
				}}
				gl={{
					antialias: true,
					alpha: false,
					powerPreference: "high-performance",
				}}
				style={{ width: "100%", height: "100%" }}
			>
				<Suspense fallback={null}>
					<SceneEnvironment />
					{children}
				</Suspense>

				<OrbitControls
					ref={controlsRef}
					makeDefault
					enableDamping
					dampingFactor={0.08}
					minDistance={0.5}
					maxDistance={20}
					maxPolarAngle={Math.PI / 2 + 0.1}
					target={[0, 0.8, 0]}
					mouseButtons={{
						LEFT: viewMode === "orbit" ? THREE.MOUSE.ROTATE : THREE.MOUSE.PAN,
						MIDDLE: THREE.MOUSE.DOLLY,
						RIGHT: viewMode === "orbit" ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE,
					}}
				/>
			</Canvas>
		);
	}
);

ModelViewer.displayName = "ModelViewer";

export default ModelViewer;
