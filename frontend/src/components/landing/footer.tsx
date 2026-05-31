import { Link } from "react-router";

export default function Footer() {
	return (
		<footer className="relative border-t border-border bg-foreground/90 backdrop-blur-xl pointer-events-auto">
			{/* Gradient top border */}
			<div
				className="absolute top-0 left-0 right-0 h-px"
				style={{
					background:
						"linear-gradient(90deg, transparent, var(--color-primary), var(--color-secondary), transparent)",
				}}
			/>

			<div className="max-w-[1400px] mx-auto px-4 sm:px-6 md:px-12 py-10 md:py-16">
				<div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-4 gap-6 md:gap-12">
					{/* Brand column */}
					<div className="col-span-2 md:col-span-1">
						<Link
							to="/"
							className="inline-flex items-center gap-2 font-semibold text-lg mb-3"
						>
							<span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
								AutoRig
							</span>
						</Link>
						<p className="text-xs sm:text-sm text-copy-lighter leading-relaxed max-w-xs">
							Open-source auto-rigging pipeline powered by AI
							classification and automated bone fitting.
						</p>
					</div>

					{/* Product */}
					<div>
						<h3 className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-copy-light mb-3">
							Product
						</h3>
						<ul className="space-y-2">
							<li>
								<Link
									to="/"
									className="text-xs sm:text-sm text-copy-lighter hover:text-copy transition-colors"
								>
									Home
								</Link>
							</li>
							<li>
								<Link
									to="/rig"
									className="text-xs sm:text-sm text-copy-lighter hover:text-copy transition-colors"
								>
									Start Rigging
								</Link>
							</li>
						</ul>
					</div>

					{/* Resources */}
					<div>
						<h3 className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-copy-light mb-3">
							Resources
						</h3>
						<ul className="space-y-2">
							<li>
								<a
									href="https://github.com/zamazincode/auto-rigging"
									target="_blank"
									rel="noopener noreferrer"
									className="text-xs sm:text-sm text-copy-lighter hover:text-copy transition-colors"
								>
									GitHub
								</a>
							</li>
							<li>
								<a
									href="https://github.com/zamazincode/auto-rigging/blob/main/RIGGING_PIPELINE.md"
									target="_blank"
									rel="noopener noreferrer"
									className="text-xs sm:text-sm text-copy-lighter hover:text-copy transition-colors"
								>
									Documentation
								</a>
							</li>
						</ul>
					</div>

					{/* Tech stack — hidden on very small screens */}
					<div className="hidden sm:block">
						<h3 className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-copy-light mb-3">
							Built With
						</h3>
						<ul className="space-y-2">
							<li className="text-xs sm:text-sm text-copy-lighter">
								Blender & Python
							</li>
							<li className="text-xs sm:text-sm text-copy-lighter">
								TensorFlow / ML
							</li>
							<li className="text-xs sm:text-sm text-copy-lighter">
								React & Three.js
							</li>
						</ul>
					</div>
				</div>

				{/* Bottom bar */}
				<div className="mt-8 sm:mt-12 pt-5 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-3">
					<p className="text-[10px] sm:text-xs text-copy-lighter">
						© {new Date().getFullYear()} AutoRig. Open source under
						MIT License.
					</p>
					<p className="text-[10px] sm:text-xs text-copy-lighter">
						Built with ❤️ by{" "}
						<a
							href="https://github.com/zamazincode"
							target="_blank"
							rel="noopener noreferrer"
							className="text-primary hover:text-primary-light transition-colors"
						>
							zamazincode
						</a>
					</p>
				</div>
			</div>
		</footer>
	);
}
