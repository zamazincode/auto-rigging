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
				<a
					href="/"
					className="flex items-center gap-2 font-semibold text-lg tracking-tight
						hover:opacity-80 transition-opacity"
				>
					<img src="/icon.svg" alt="logo" width={20} height={20} />
					<span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
						ZamaRig
					</span>
				</a>

				{/* Navigation */}
				<nav className="flex items-center gap-1">
					{NAV_LINKS.map((link) => {
						const isActive =
							link.to === "/"
								? location.pathname === "/"
								: location.pathname.startsWith(link.to);

						if (link.to === "/") {
							return (
								<a
									key={link.to}
									href={link.to}
									className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200
										${isActive
											? "text-primary bg-primary/10"
											: "text-copy-light hover:text-copy hover:bg-background/60"
										}`}
								>
									{link.label}
								</a>
							);
						}

						return (
							<Link
								key={link.to}
								to={link.to}
								className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200
									${isActive
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
