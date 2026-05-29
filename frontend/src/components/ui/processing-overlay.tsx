import { type ProcessingStage } from "../../types";
import { PROCESSING_STAGE_LABELS } from "../../types";

interface ProcessingOverlayProps {
	stage: ProcessingStage | null;
}

const STAGES: ProcessingStage[] = [
	"rendering",
	"classifying",
	"rigging",
	"finalizing",
];

export default function ProcessingOverlay({ stage }: ProcessingOverlayProps) {
	if (!stage) return null;

	const currentIndex = STAGES.indexOf(stage);
	const progressPercent = Math.max(
		10,
		((currentIndex + 1) / STAGES.length) * 100
	);

	return (
		<div className="absolute inset-0 z-40 glass-strong flex items-center justify-center animate-fade-in">
			<div className="w-full max-w-sm p-8 rounded-3xl bg-foreground/90 shadow-2xl border border-border backdrop-blur-xl flex flex-col items-center text-center">
				{/* Skeleton SVG animation */}
				<div className="relative w-32 h-32 mb-8 flex items-center justify-center">
					{/* Glowing background blob */}
					<div className="absolute inset-0 bg-primary/20 rounded-full blur-2xl animate-pulse-glow" />

					{/* Drawing skeleton */}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 100 100"
						className="w-full h-full text-primary drop-shadow-[0_0_8px_rgba(var(--color-primary),0.8)] relative z-10"
					>
						<g
							fill="none"
							stroke="currentColor"
							strokeWidth="3"
							strokeLinecap="round"
							strokeLinejoin="round"
							className="animate-draw-stroke"
							style={{ strokeDasharray: 400, strokeDashoffset: 0 }}
						>
							{/* Head */}
							<circle cx="50" cy="15" r="8" />
							{/* Spine */}
							<path d="M50 23 v 30" />
							{/* Shoulders & Arms */}
							<path d="M35 30 L 50 25 L 65 30" />
							<path d="M35 30 L 20 40 L 15 55" />
							<path d="M65 30 L 80 40 L 85 55" />
							{/* Pelvis & Legs */}
							<path d="M40 53 L 50 58 L 60 53" />
							<path d="M40 53 L 35 75 L 35 90" />
							<path d="M60 53 L 65 75 L 65 90" />
						</g>
						{/* Joints (dots) */}
						<g fill="currentColor" className="animate-fade-in" style={{ animationDelay: "1.5s", animationFillMode: "both" }}>
							<circle cx="50" cy="25" r="2.5" />
							<circle cx="35" cy="30" r="2.5" />
							<circle cx="65" cy="30" r="2.5" />
							<circle cx="20" cy="40" r="2" />
							<circle cx="80" cy="40" r="2" />
							<circle cx="40" cy="53" r="2.5" />
							<circle cx="60" cy="53" r="2.5" />
							<circle cx="35" cy="75" r="2" />
							<circle cx="65" cy="75" r="2" />
						</g>
					</svg>
				</div>

				{/* Progress Track */}
				<div className="w-full h-1.5 bg-background rounded-full mb-6 overflow-hidden">
					<div
						className="h-full bg-primary transition-all duration-700 ease-out"
						style={{ width: `${progressPercent}%` }}
					/>
				</div>

				{/* Stage indicator dots */}
				<div className="flex items-center gap-3 mb-6">
					{STAGES.map((s, idx) => {
						const isPast = idx < currentIndex;
						const isCurrent = idx === currentIndex;
						
						return (
							<div
								key={s}
								className={`
									w-2.5 h-2.5 rounded-full transition-all duration-300
									${isPast ? "bg-primary scale-100 opacity-80" : ""}
									${isCurrent ? "bg-primary scale-125 animate-pulse-glow" : ""}
									${!isPast && !isCurrent ? "bg-border scale-100" : ""}
								`}
							/>
						);
					})}
				</div>

				{/* Text */}
				<div className="h-12 flex flex-col justify-center">
					<p className="text-sm font-semibold text-copy animate-fade-in key={stage}">
						{PROCESSING_STAGE_LABELS[stage]}
					</p>
					<p className="text-xs text-copy-lighter mt-1">
						Please wait, this may take a minute...
					</p>
				</div>
			</div>
		</div>
	);
}
