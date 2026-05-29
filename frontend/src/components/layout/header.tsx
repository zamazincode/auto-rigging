import { Link, useLocation } from "react-router";
import ThemeToggle from "../ui/theme-toggle";

const NAV_LINKS = [
	{ to: "/", label: "Home" },
	{ to: "/rig", label: "Rig" },
] as const;

export default function Header() {
	const location = useLocation();

	return (
		<header
			className="sticky top-0 z-50 glass-strong"
		>
			<div className="flex items-center justify-between h-14 px-6 max-w-[1600px] mx-auto">
				{/* Logo */}
				<Link
					to="/"
					className="flex items-center gap-2 font-semibold text-lg tracking-tight
						hover:opacity-80 transition-opacity"
				>
					{/* Bone icon as logo */}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="22"
						height="22"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						strokeWidth="2"
						strokeLinecap="round"
						strokeLinejoin="round"
						className="text-primary"
					>
						<path d="M18.6 9.82c-.52-.52-1.17-.76-1.84-.76-.44 0-.88.12-1.27.35l-4.03 4.03c-.55-.2-1.14-.3-1.72-.3-1.34 0-2.61.52-3.56 1.47a5.04 5.04 0 0 0 0 7.12 5.04 5.04 0 0 0 7.12 0 5.04 5.04 0 0 0 1.17-5.28l4.03-4.03c.47-.79.47-1.8-.05-2.33l.15-.27z" />
						<path d="M14.5 3.5a5.04 5.04 0 0 0-7.12 0 5.04 5.04 0 0 0 0 7.12c.38.38.81.67 1.27.88l4.03-4.03c.2.55.3 1.14.3 1.72 0 .44-.06.88-.17 1.3" />
					</svg>
					<span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
						AutoRig
					</span>
				</Link>

				{/* Navigation */}
				<nav className="flex items-center gap-1">
					{NAV_LINKS.map((link) => {
						const isActive =
							link.to === "/"
								? location.pathname === "/"
								: location.pathname.startsWith(link.to);

						return (
							<Link
								key={link.to}
								to={link.to}
								className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200
									${
										isActive
											? "text-primary bg-primary/10"
											: "text-copy-light hover:text-copy hover:bg-background/60"
									}`}
							>
								{link.label}
							</Link>
						);
					})}

					{/* Divider */}
					<div className="w-px h-5 bg-border mx-2" />

					{/* Theme Toggle */}
					<ThemeToggle />
				</nav>
			</div>
		</header>
	);
}
