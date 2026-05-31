import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import { useTheme } from "../../hooks/use-theme";

interface LandingCanvasProps {
	children: React.ReactNode;
}

export default function LandingCanvas({ children }: LandingCanvasProps) {
	const { theme } = useTheme();
	const isDark = theme === "dark";

	return (
		<div className="fixed inset-0 z-[1]">
			<Canvas
				camera={{
					position: [0, 0, 4],
					fov: 45,
					near: 0.1,
					far: 100,
				}}
				gl={{
					antialias: true,
					alpha: true,
					powerPreference: "high-performance",
				}}
				style={{ width: "100%", height: "100%" }}
			>
				<Suspense fallback={null}>
					{/* Lighting */}
					<ambientLight intensity={isDark ? 0.4 : 0.6} />
					<directionalLight
						position={[5, 8, 5]}
						intensity={isDark ? 1.2 : 1.5}
					/>
					<directionalLight
						position={[-3, 4, -3]}
						intensity={isDark ? 0.25 : 0.35}
					/>
					<directionalLight
						position={[0, 3, -5]}
						intensity={isDark ? 0.15 : 0.2}
					/>

					{/* Fog perfectly matches CSS background */}
					<fog
						key={theme}
						attach="fog"
						args={[isDark ? "#111118" : "#f0f0f0", 15, 40]}
					/>

					{children}
				</Suspense>
			</Canvas>
		</div>
	);
}
