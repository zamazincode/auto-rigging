import { useState, useRef, useCallback } from "react";
import { SUPPORTED_FORMATS, type ViewMode } from "../types";
import ModelViewer, {
	type ModelViewerHandle,
} from "../components/three/model-viewer";
import ModelDisplay from "../components/three/model-display";
import ViewerControls from "../components/three/viewer-controls";
import ProcessingOverlay from "../components/ui/processing-overlay";
import { useRigging } from "../hooks/use-rigging";

export default function Rig() {
	const { state, setFile, startProcessing, reset } = useRigging();
	const [isDragOver, setIsDragOver] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);
	const viewerRef = useRef<ModelViewerHandle>(null);

	const [viewMode, setViewMode] = useState<ViewMode>("orbit");
	const [showSkeleton, setShowSkeleton] = useState(false);

	const isValidFile = useCallback((f: File) => {
		const ext = "." + f.name.split(".").pop()?.toLowerCase();
		return SUPPORTED_FORMATS.includes(ext as any);
	}, []);

	const handleFile = useCallback(
		(f: File) => {
			if (!isValidFile(f)) {
				alert(
					`Unsupported format. Please use: ${SUPPORTED_FORMATS.join(", ")}`,
				);
				return;
			}
			// Create object URL for the 3D model
			const url = URL.createObjectURL(f);
			setFile(f, url);
		},
		[isValidFile, setFile],
	);

	const handleDragOver = useCallback((e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		setIsDragOver(true);
	}, []);

	const handleDragLeave = useCallback((e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		setIsDragOver(false);
	}, []);

	const handleDrop = useCallback(
		(e: React.DragEvent) => {
			e.preventDefault();
			e.stopPropagation();
			setIsDragOver(false);

			const droppedFile = e.dataTransfer.files[0];
			if (droppedFile) handleFile(droppedFile);
		},
		[handleFile],
	);

	const handleInputChange = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			const selected = e.target.files?.[0];
			if (selected) handleFile(selected);
		},
		[handleFile],
	);

	const handleUploadClick = useCallback(() => {
		fileInputRef.current?.click();
	}, []);

	const handleReset = useCallback(() => {
		reset();
		setShowSkeleton(false);
		setViewMode("orbit");
		if (fileInputRef.current) fileInputRef.current.value = "";
	}, [reset]);

	const handleDownload = useCallback(() => {
		if (state.resultUrl && state.file) {
			const a = document.createElement("a");
			a.href = state.resultUrl;
			const nameWithoutExt =
				state.file.name.substring(
					0,
					state.file.name.lastIndexOf("."),
				) || state.file.name;
			a.download = `${nameWithoutExt}_rigged.fbx`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
		}
	}, [state.resultUrl, state.file]);

	return (
		<main className="flex flex-1 overflow-hidden max-sm:flex-col-reverse max-sm:h-fit">
			{/* Left Sidebar — Animations Panel (placeholder) */}
			<aside
				className="w-[280px] min-w-[280px] max-sm:w-full border-r border-border bg-foreground
					flex flex-col overflow-y-auto"
			>
				{/* Sidebar Header */}
				<div className="px-5 py-4 border-b border-border">
					<h2 className="text-sm font-semibold tracking-wide uppercase text-copy-light">
						Animations
					</h2>
				</div>

				{/* Placeholder Content */}
				<div className="flex-1 flex items-center justify-center p-6">
					<div className="text-center space-y-4">
						<div className="mx-auto w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center animate-bounce-subtle">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								width="24"
								height="24"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
								className="lucide lucide-person-standing-icon lucide-person-standing"
							>
								<circle cx="12" cy="5" r="1" />
								<path d="m9 20 3-6 3 6" />
								<path d="m6 8 6 2 6-2" />
								<path d="M12 10v4" />
							</svg>
						</div>
						<div className="space-y-2">
							<p className="text-sm font-medium text-copy">
								Coming Soon
							</p>
							<p className="text-xs text-copy-lighter leading-relaxed">
								Apply pre-built animations to your rigged model.
								This feature is under development.
							</p>
						</div>
						<div
							className="h-1 w-24 mx-auto rounded-full"
							style={{
								background:
									"linear-gradient(90deg, transparent, var(--color-primary-light), transparent)",
								backgroundSize: "200% 100%",
								animation:
									"skeleton-shimmer 1.8s ease-in-out infinite",
							}}
						/>
					</div>
				</div>
			</aside>

			{/* Right Area — 3D Viewport / Upload Zone */}
			<section className="flex-1 relative bg-background flex flex-col">
				{/* Hidden file input */}
				<input
					ref={fileInputRef}
					type="file"
					accept=".obj,.fbx,.glb,.gltf"
					onChange={handleInputChange}
					className="hidden"
				/>

				{state.status !== "idle" && state.file ? (
					/* ===== Model Loaded State (Preview, Processing, Completed) ===== */
					<div className="flex-1 relative flex items-center justify-center">
						{/* Top bar with file info and actions */}
						<div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-3 max-sm:flex-col gap-2">
							<div className="flex items-center gap-3">
								<div className="glass rounded-lg px-3 py-1.5 flex items-center gap-2">
									<svg
										xmlns="http://www.w3.org/2000/svg"
										width="14"
										height="14"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										strokeWidth="2"
										strokeLinecap="round"
										strokeLinejoin="round"
										className="text-primary"
									>
										<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
										<polyline points="14 2 14 8 20 8" />
									</svg>
									<span className="text-xs font-medium text-copy">
										{state.file.name}
									</span>
									<span className="text-xs text-copy-lighter">
										(
										{(
											state.file.size /
											1024 /
											1024
										).toFixed(2)}{" "}
										MB)
									</span>
								</div>
							</div>

							<div className="flex gap-2 h-fit items-stretch">
								{state.status === "previewing" && (
									<button
										disabled
										onClick={startProcessing}
										className="bg-primary hover:bg-primary-light text-foreground 
											px-4 py-1.5 rounded-lg text-sm font-semibold shadow-lg shadow-primary/20
											transition-all duration-200 active:scale-95 flex items-center gap-2 h-full "
									>
										<span>Auto-Rig</span>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											width="16"
											height="16"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											stroke-width="2"
											stroke-linecap="round"
											stroke-linejoin="round"
											className="lucide lucide-bone-icon lucide-bone"
										>
											<path d="M17 10c.7-.7 1.69 0 2.5 0a2.5 2.5 0 1 0 0-5 .5.5 0 0 1-.5-.5 2.5 2.5 0 1 0-5 0c0 .81.7 1.8 0 2.5l-7 7c-.7.7-1.69 0-2.5 0a2.5 2.5 0 0 0 0 5c.28 0 .5.22.5.5a2.5 2.5 0 1 0 5 0c0-.81-.7-1.8 0-2.5Z" />
										</svg>
									</button>
								)}

								<div className="fixed bottom-4 right-4 bg-error flex items-center justify-center p-4 rounded-full text-foreground text-xs animate-bounce-subtle duration-1000">
									<p className="max-w-64 text-center">
										The server is currently inactive. So,
										Auto-Rig button is not active now.
									</p>
								</div>

								{state.status === "completed" && (
									<button
										onClick={handleDownload}
										className="bg-primary hover:bg-primary-light text-primary-content 
											px-4 py-1.5 rounded-lg text-sm font-semibold shadow-lg shadow-primary/20
											transition-all duration-200 active:scale-95 flex items-center gap-2 h-full"
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											width="16"
											height="16"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											strokeWidth="2"
											strokeLinecap="round"
											strokeLinejoin="round"
										>
											<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
											<polyline points="7 10 12 15 17 10" />
											<line
												x1="12"
												y1="15"
												x2="12"
												y2="3"
											/>
										</svg>
										<span>Download FBX</span>
									</button>
								)}

								<button
									onClick={handleReset}
									disabled={state.status === "processing"}
									className="glass rounded-lg px-3 py-1.5 text-xs font-medium
										text-copy-light hover:text-copy hover:bg-foreground/80
										transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
								>
									Upload New
								</button>
							</div>
						</div>

						{/* 3D Viewport */}
						<div className="absolute inset-0">
							<ModelViewer ref={viewerRef} viewMode={viewMode}>
								<ModelDisplay
									url={
										state.status === "completed"
											? state.resultUrl!
											: state.previewUrl!
									}
									fileName={
										state.status === "completed"
											? "rigged.fbx"
											: state.file.name
									}
									showSkeleton={showSkeleton}
								/>
							</ModelViewer>
						</div>

						{/* Viewer Controls */}
						<ViewerControls
							viewMode={viewMode}
							showSkeleton={showSkeleton}
							onViewModeChange={setViewMode}
							onToggleSkeleton={() => setShowSkeleton((s) => !s)}
							onResetCamera={() =>
								viewerRef.current?.resetCamera()
							}
						/>

						{/* Processing Overlay */}
						{state.status === "processing" && (
							<ProcessingOverlay stage={state.processingStage} />
						)}

						{/* Error Overlay */}
						{state.status === "error" && (
							<div className="absolute inset-0 z-50 glass-strong flex items-center justify-center animate-fade-in">
								<div className="w-full max-w-sm p-6 rounded-3xl bg-foreground shadow-2xl border border-error/20 flex flex-col items-center text-center">
									<div className="w-12 h-12 rounded-full bg-error/10 flex items-center justify-center text-error mb-4">
										<svg
											xmlns="http://www.w3.org/2000/svg"
											width="24"
											height="24"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											strokeWidth="2"
											strokeLinecap="round"
											strokeLinejoin="round"
										>
											<circle cx="12" cy="12" r="10" />
											<line
												x1="12"
												y1="8"
												x2="12"
												y2="12"
											/>
											<line
												x1="12"
												y1="16"
												x2="12.01"
												y2="16"
											/>
										</svg>
									</div>
									<p className="text-sm font-semibold text-copy mb-2">
										Rigging Failed
									</p>
									<p className="text-xs text-copy-light mb-6">
										{state.errorMessage ||
											"An unexpected error occurred during processing."}
									</p>
									<div className="flex w-full gap-3">
										<button
											onClick={handleReset}
											className="flex-1 py-2 rounded-xl text-sm font-medium text-copy-light bg-background hover:text-copy hover:bg-border transition-colors"
										>
											Cancel
										</button>
										<button
											onClick={startProcessing}
											className="flex-1 py-2 rounded-xl text-sm font-semibold text-error-content bg-error hover:opacity-90 transition-opacity"
										>
											Try Again
										</button>
									</div>
								</div>
							</div>
						)}
					</div>
				) : (
					/* ===== Upload Zone State ===== */
					<div className="flex-1 flex items-center justify-center p-8">
						<div
							onDragOver={handleDragOver}
							onDragLeave={handleDragLeave}
							onDrop={handleDrop}
							onClick={handleUploadClick}
							className={`
								relative w-full max-w-xl aspect-[4/3] rounded-2xl
								border-2 border-dashed cursor-pointer
								flex flex-col items-center justify-center gap-5
								transition-all duration-300 ease-out
								${
									isDragOver
										? "border-primary bg-primary/5 scale-[1.02] shadow-lg shadow-primary/10"
										: "border-border hover:border-primary-light hover:bg-foreground/50"
								}
							`}
						>
							{/* Upload Icon */}
							<div
								className={`
									w-20 h-20 rounded-2xl flex items-center justify-center
									transition-all duration-300
									${isDragOver ? "bg-primary/15 scale-110" : "bg-foreground"}
								`}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									width="36"
									height="36"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									strokeWidth="1.5"
									strokeLinecap="round"
									strokeLinejoin="round"
									className={`transition-colors duration-300 ${
										isDragOver
											? "text-primary"
											: "text-copy-lighter"
									}`}
								>
									<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
									<polyline points="17 8 12 3 7 8" />
									<line x1="12" y1="3" x2="12" y2="15" />
								</svg>
							</div>

							{/* Text */}
							<div className="text-center space-y-2">
								<p className="text-sm font-medium text-copy">
									{isDragOver
										? "Drop your model here"
										: "Drag & drop your 3D model"}
								</p>
								<p className="text-xs text-copy-lighter">
									or click to browse files
								</p>
							</div>

							{/* Format badges */}
							<div className="flex items-center gap-2">
								{SUPPORTED_FORMATS.map((fmt) => (
									<span
										key={fmt}
										className="px-2.5 py-1 rounded-md text-[10px] font-semibold uppercase tracking-wider
											bg-foreground text-copy-light border border-border"
									>
										{fmt.replace(".", "")}
									</span>
								))}
							</div>

							{/* Drag-over ring effect */}
							{isDragOver && (
								<div className="absolute inset-0 rounded-2xl border-2 border-primary/30 animate-pulse-glow pointer-events-none" />
							)}
						</div>
					</div>
				)}
			</section>
		</main>
	);
}
