import { useTheme } from "../../hooks/use-theme";
import { Grid, ContactShadows } from "@react-three/drei";

export default function SceneEnvironment() {
	const { theme } = useTheme();
	const isDark = theme === "dark";

	return (
		<>
			{/* Ambient light — soft global illumination */}
			<ambientLight intensity={isDark ? 0.5 : 0.7} />

			{/* Main directional light with shadows */}
			<directionalLight
				position={[5, 8, 5]}
				intensity={isDark ? 1.0 : 1.4}
				castShadow
				shadow-mapSize-width={2048}
				shadow-mapSize-height={2048}
				shadow-camera-far={50}
				shadow-camera-left={-5}
				shadow-camera-right={5}
				shadow-camera-top={5}
				shadow-camera-bottom={-5}
				shadow-bias={-0.0001}
			/>

			{/* Fill light from the opposite side */}
			<directionalLight
				position={[-3, 4, -3]}
				intensity={isDark ? 0.3 : 0.4}
			/>

			{/* Rim light from behind for nice edge highlights */}
			<directionalLight
				position={[0, 3, -5]}
				intensity={isDark ? 0.2 : 0.25}
			/>

			{/* Grid floor — subtle, clean look matching reference */}
			<Grid
				args={[20, 20]}
				position={[0, -0.01, 0]}
				cellSize={0.6}
				cellThickness={0.4}
				cellColor={isDark ? "#333344" : "#c8c8c8"}
				sectionSize={3}
				sectionThickness={0.8}
				sectionColor={isDark ? "#444455" : "#b0b0b0"}
				fadeDistance={18}
				fadeStrength={1.5}
				infiniteGrid
			/>

			{/* Contact shadows for grounded look */}
			<ContactShadows
				position={[0, 0, 0]}
				opacity={isDark ? 0.35 : 0.45}
				scale={10}
				blur={2.5}
				far={4}
			/>

			{/* Background color — light theme: soft warm gray, dark: deep navy */}
			<color
				attach="background"
				args={[isDark ? "#1e1e2e" : "#d4d4d4"]}
			/>

			{/* Subtle fog for depth */}
			<fog
				attach="fog"
				args={[isDark ? "#1e1e2e" : "#d4d4d4", 12, 35]}
			/>
		</>
	);
}
