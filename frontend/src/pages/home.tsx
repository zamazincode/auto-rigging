import { useState, useCallback } from "react";
import SmoothScroll from "../components/landing/smooth-scroll";
import LoadingScreen from "../components/landing/loading-screen";
import LandingCanvas from "../components/landing/landing-canvas";
import LandingModel from "../components/landing/landing-model";
import HeroSection from "../components/landing/sections/hero-section";
import PipelineSection from "../components/landing/sections/pipeline-section";
import Footer from "../components/landing/footer";
import { Link } from "react-router";

const PIPELINE_SECTIONS = [
	{
		id: "upload",
		title: "Upload Your Model",
		description:
			"Simply drag and drop your 3D model in FBX, GLB, OBJ, or GLTF format. Our system accepts meshes of any complexity — from low-poly game characters to high-detail sculpts.",
		align: "left" as const,
	},
	{
		id: "render",
		title: "Multi-Angle Rendering",
		description:
			"Four orthographic renders are automatically captured from front, back, left, and right views. These images provide the visual data our AI needs to understand your model's anatomy.",
		align: "right" as const,
	},
	{
		id: "classify",
		title: "AI Classification",
		description:
			"Our trained machine learning model analyzes the renders to classify your mesh as either humanoid or quadruped. This determines which rigging template and bone structure to apply.",
		align: "left" as const,
	},
	{
		id: "template",
		title: "Template Skeleton",
		description:
			"A pre-built armature template with correct bone hierarchy and naming conventions is loaded and uniformly scaled to match your model's dimensions.",
		align: "right" as const,
	},
	{
		id: "fitting",
		title: "Precision Bone Fitting",
		description:
			"Cross-section profiling detects anatomical landmarks — neck, shoulders, hips, knees. Bones are repositioned using bounding box analysis, IK solving, and raycast refinement to sit perfectly inside the mesh.",
		align: "left" as const,
	},
	{
		id: "weighting",
		title: "Automatic Skin Weighting",
		description:
			"Each vertex is assigned influence weights to nearby bones using Blender's heat-map based auto-weighting. This ensures natural deformation when the skeleton moves.",
		align: "right" as const,
	},
	{
		id: "download",
		title: "Download & Use",
		description:
			"Your fully rigged model is exported as FBX, ready to import into any 3D application — Blender, Unity, Unreal Engine, or Maya. Start animating immediately.",
		align: "left" as const,
	},
];

export default function Home() {
	const [modelsLoaded, setModelsLoaded] = useState(false);
	const [loadingDone, setLoadingDone] = useState(false);

	const handleModelsLoaded = useCallback(() => {
		setModelsLoaded(true);
	}, []);

	const handleLoadingComplete = useCallback(() => {
		setLoadingDone(true);
	}, []);

	return (
		<>
			{/* Loading screen overlay — z-[100] above everything */}
			{!loadingDone && (
				<LoadingScreen
					isLoaded={modelsLoaded}
					onComplete={handleLoadingComplete}
				/>
			)}

			{/* 3D Canvas — fixed background layer */}
			<LandingCanvas>
				<LandingModel onLoaded={handleModelsLoaded} contentReady={loadingDone} />
			</LandingCanvas>

			{/* Scrollable content — always in DOM */}
			<SmoothScroll>
				<div className="relative z-[2] pointer-events-none">
					{/* Hero */}
					<HeroSection />

					{/* Pipeline steps */}
					{PIPELINE_SECTIONS.map((section, i) => (
						<PipelineSection
							key={section.id}
							id={section.id}
							index={i + 1}
							title={section.title}
							description={section.description}
							align={section.align}
						>
							{section.id === "download" && (
								<Link
									to="/rig"
									className="inline-flex items-center gap-2 px-6 py-3 rounded-xl
										bg-primary hover:bg-primary-light text-foreground
										text-sm font-semibold shadow-lg shadow-primary/20
										transition-all duration-200 active:scale-95"
								>
									<span>Try It Now</span>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										width="18"
										height="18"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										strokeWidth="2"
										strokeLinecap="round"
										strokeLinejoin="round"
									>
										<path d="M5 12h14" />
										<path d="M12 5l7 7-7 7" />
									</svg>
								</Link>
							)}
						</PipelineSection>
					))}

					{/* Footer */}
					<Footer />
				</div>
			</SmoothScroll>
		</>
	);
}
