export type ViewMode = "orbit" | "pan";
export type ThemeMode = "light" | "dark";
export type SupportedFormat = ".obj" | ".fbx" | ".glb" | ".gltf";

export type ProcessingStage =
	| "rendering"
	| "classifying"
	| "rigging"
	| "finalizing";

export type RiggingStatus =
	| "idle"
	| "previewing"
	| "uploading"
	| "processing"
	| "completed"
	| "error";

export interface RiggingState {
	status: RiggingStatus;
	file: File | null;
	previewUrl: string | null;
	resultUrl: string | null;
	processingStage: ProcessingStage | null;
	errorMessage: string | null;
}

export const SUPPORTED_FORMATS: SupportedFormat[] = [
	".obj",
	".fbx",
	".glb",
	".gltf",
];

export const PROCESSING_STAGE_LABELS: Record<ProcessingStage, string> = {
	rendering: "Taking renders from multiple angles...",
	classifying: "AI is analyzing your model...",
	rigging: "Building skeleton & applying skin weights...",
	finalizing: "Preparing your rigged model...",
};
