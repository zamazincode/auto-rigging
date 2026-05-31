import { useEffect, useRef } from "react";
import Lenis from "lenis";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

interface SmoothScrollProps {
	children: React.ReactNode;
}

export default function SmoothScroll({ children }: SmoothScrollProps) {
	const lenisRef = useRef<Lenis | null>(null);
	const progressRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const lenis = new Lenis({
			duration: 1.2,
			easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
			touchMultiplier: 2,
		});

		lenisRef.current = lenis;

		// Sync Lenis scroll with GSAP ScrollTrigger
		lenis.on("scroll", ScrollTrigger.update);

		gsap.ticker.add((time) => {
			lenis.raf(time * 1000);
		});
		gsap.ticker.lagSmoothing(0);

		// Scroll progress bar
		if (progressRef.current) {
			ScrollTrigger.create({
				trigger: document.documentElement,
				start: "top top",
				end: "bottom bottom",
				scrub: 0.3,
				onUpdate: (self) => {
					if (progressRef.current) {
						progressRef.current.style.transform = `scaleX(${self.progress})`;
					}
				},
			});
		}

		return () => {
			lenis.destroy();
			gsap.ticker.remove(lenis.raf);
			ScrollTrigger.getAll().forEach((t) => t.kill());
		};
	}, []);

	return (
		<>
			{/* Scroll progress bar */}
			<div ref={progressRef} className="scroll-progress" style={{ transform: "scaleX(0)" }} />
			{children}
		</>
	);
}
