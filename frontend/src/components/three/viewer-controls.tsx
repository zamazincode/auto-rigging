import type { ViewMode } from "../../types";

interface ViewerControlsProps {
	viewMode: ViewMode;
	showSkeleton: boolean;
	onViewModeChange: (mode: ViewMode) => void;
	onToggleSkeleton: () => void;
	onResetCamera: () => void;
}

interface ControlButton {
	id: string;
	label: string;
	icon: React.ReactNode;
	onClick: () => void;
	isActive?: boolean;
}

export default function ViewerControls({
	viewMode,
	showSkeleton,
	onViewModeChange,
	onToggleSkeleton,
	onResetCamera,
}: ViewerControlsProps) {
	const buttons: ControlButton[] = [
		{
			id: "orbit",
			label: "Orbit",
			icon: (
				<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
					<path d="M21.5 2v6h-6" />
					<path d="M21.34 15.57a10 10 0 1 1-.57-8.38" />
				</svg>
			),
			onClick: () => onViewModeChange("orbit"),
			isActive: viewMode === "orbit",
		},
		{
			id: "pan",
			label: "Pan",
			icon: (
				<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
					<path d="M5 9l-3 3 3 3" />
					<path d="M9 5l3-3 3 3" />
					<path d="M15 19l-3 3-3-3" />
					<path d="M19 9l3 3-3 3" />
					<line x1="2" y1="12" x2="22" y2="12" />
					<line x1="12" y1="2" x2="12" y2="22" />
				</svg>
			),
			onClick: () => onViewModeChange("pan"),
			isActive: viewMode === "pan",
		},
		{
			id: "reset",
			label: "Reset View",
			icon: (
				<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
					<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
					<polyline points="9 22 9 12 15 12 15 22" />
				</svg>
			),
			onClick: onResetCamera,
		},
		{
			id: "skeleton",
			label: "Skeleton",
			icon: (
				<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
					{/* Simple bone icon */}
					<circle cx="12" cy="4" r="2" />
					<line x1="12" y1="6" x2="12" y2="14" />
					<line x1="12" y1="10" x2="8" y2="7" />
					<line x1="12" y1="10" x2="16" y2="7" />
					<line x1="12" y1="14" x2="8" y2="18" />
					<line x1="12" y1="14" x2="16" y2="18" />
					<circle cx="8" cy="18.5" r="1.5" />
					<circle cx="16" cy="18.5" r="1.5" />
				</svg>
			),
			onClick: onToggleSkeleton,
			isActive: showSkeleton,
		},
	];

	return (
		<div className="absolute bottom-4 left-4 z-10 flex items-center gap-1 glass rounded-xl px-1.5 py-1.5">
			{buttons.map((btn, index) => (
				<div key={btn.id} className="flex items-center">
					{/* Divider before reset button */}
					{index === 2 && (
						<div className="w-px h-5 bg-border mx-1" />
					)}
					<button
						onClick={btn.onClick}
						title={btn.label}
						className={`
							w-8 h-8 rounded-lg flex items-center justify-center
							transition-all duration-200
							${
								btn.isActive
									? "bg-primary/15 text-primary"
									: "text-copy-lighter hover:text-copy hover:bg-foreground/60"
							}
						`}
					>
						{btn.icon}
					</button>
				</div>
			))}
		</div>
	);
}
