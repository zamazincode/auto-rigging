import { useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

interface PipelineSectionProps {
	id: string;
	index: number;
	title: string;
	description: string;
	children?: React.ReactNode;
	align?: "left" | "right";
}

export default function PipelineSection({
	id,
	index,
	title,
	description,
	children,
	align = "left",
}: PipelineSectionProps) {
	const sectionRef = useRef<HTMLDivElement>(null);

	useGSAP(
		() => {
			gsap.from("[data-section-content]", {
				opacity: 0,
				y: 60,
				duration: 1,
				ease: "power3.out",
				scrollTrigger: {
					trigger: sectionRef.current,
					start: "top 70%",
					end: "top 30%",
					toggleActions: "play none none reverse",
				},
			});
		},
		{ scope: sectionRef }
	);

	return (
		<section
			ref={sectionRef}
			id={id}
			className="relative min-h-screen flex items-center py-20 md:py-32 pointer-events-auto"
		>
			<div className="w-full max-w-[1400px] mx-auto px-4 sm:px-6 md:px-12">
				<div
					data-section-content
					className={`max-w-md sm:max-w-lg md:max-w-xl glass-card ${
						align === "right" ? "ml-auto text-right" : ""
					}`}
				>
					{/* Step number */}
					<div
						className={`inline-flex items-center gap-3 mb-4 ${
							align === "right" ? "flex-row-reverse" : ""
						}`}
					>
						<span className="text-4xl sm:text-5xl md:text-6xl font-bold text-primary/20 select-none">
							{String(index).padStart(2, "0")}
						</span>
						<div
							className={`h-px w-8 sm:w-12 bg-gradient-to-r from-primary/40 to-transparent ${
								align === "right"
									? "bg-gradient-to-l from-primary/40 to-transparent"
									: ""
							}`}
						/>
					</div>

					{/* Title */}
					<h2 className="text-xl sm:text-2xl md:text-3xl lg:text-4xl font-bold tracking-tight mb-3 leading-tight">
						{title}
					</h2>

					{/* Description */}
					<p className="text-xs sm:text-sm md:text-base text-copy-light leading-relaxed mb-6">
						{description}
					</p>

					{/* Optional children */}
					{children && <div>{children}</div>}
				</div>
			</div>
		</section>
	);
}
