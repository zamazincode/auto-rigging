import { useRef } from "react";
import { Link } from "react-router";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

export default function HeroSection() {
	const sectionRef = useRef<HTMLDivElement>(null);

	useGSAP(
		() => {
			const tl = gsap.timeline({ delay: 0.3 });

			tl.from("[data-hero-badge]", {
				opacity: 0,
				y: 20,
				duration: 0.6,
				ease: "power3.out",
			})
				.from(
					"[data-hero-heading]",
					{ opacity: 0, y: 40, duration: 0.8, ease: "power3.out" },
					"-=0.3"
				)
				.from(
					"[data-hero-paragraph]",
					{ opacity: 0, y: 30, duration: 0.7, ease: "power3.out" },
					"-=0.4"
				)
				.from(
					"[data-hero-buttons]",
					{ opacity: 0, y: 20, duration: 0.6, ease: "power3.out" },
					"-=0.3"
				)
				.from(
					"[data-hero-scroll]",
					{ opacity: 0, duration: 0.8, ease: "power2.out" },
					"-=0.2"
				);
		},
		{ scope: sectionRef }
	);

	return (
		<section
			ref={sectionRef}
			id="hero"
			className="relative mt-24 flex items-center pointer-events-auto"
		>
			<div className="w-full max-w-[1400px] mx-auto px-4 sm:px-6 md:px-12 py-20">
				<div className="max-w-md sm:max-w-lg md:max-w-xl glass-card">
					{/* Badge */}
					<div
						data-hero-badge
						className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 mb-5"
					>
						<div className="w-2 h-2 rounded-full bg-primary animate-pulse-glow" />
						<span className="text-[10px] sm:text-xs font-semibold text-primary uppercase tracking-wider">
							Open Source Auto-Rigging
						</span>
					</div>

					{/* Heading */}
					<h1
						data-hero-heading
						className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.1] tracking-tight mb-4 sm:mb-6"
					>
						Auto-Rig Your{" "}
						<span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
							3D Models
						</span>
					</h1>

					{/* Paragraph */}
					<p
						data-hero-paragraph
						className="text-sm sm:text-base md:text-lg text-copy-light leading-relaxed mb-8 sm:mb-10"
					>
						Upload any humanoid or quadruped mesh and get a
						production-ready rigged model in seconds. Powered by AI
						classification and automated bone fitting.
					</p>

					{/* Buttons */}
					<div
						data-hero-buttons
						className="flex flex-col sm:flex-row items-stretch sm:items-start gap-3"
					>
						<Link
							to="/rig"
							className="inline-flex items-center justify-center gap-2 px-5 sm:px-6 py-3 rounded-xl
								bg-primary hover:bg-primary-light text-primary-content
								text-sm font-semibold shadow-lg shadow-primary/20
								transition-all duration-200 active:scale-95"
						>
							<span>Start Rigging</span>
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

						<a
							href="https://github.com/zamazincode/auto-rigging"
							target="_blank"
							rel="noopener noreferrer"
							className="inline-flex items-center justify-center gap-2 px-5 sm:px-6 py-3 rounded-xl
								border border-border hover:border-primary/40 text-copy-light hover:text-copy
								text-sm font-semibold transition-all duration-200"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								width="18"
								height="18"
								viewBox="0 0 24 24"
								fill="currentColor"
							>
								<path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
							</svg>
							<span>View on GitHub</span>
						</a>
					</div>
				</div>
			</div>

			{/* Scroll hint */}
			<div
				data-hero-scroll
				className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-copy-lighter"
			>
				<span className="text-[10px] uppercase tracking-[0.2em]">
					Scroll
				</span>
				<div className="w-5 h-8 rounded-full border-2 border-copy-lighter/30 flex justify-center pt-1.5">
					<div className="w-1 h-2 rounded-full bg-copy-lighter/50 animate-bounce-subtle" />
				</div>
			</div>
		</section>
	);
}
