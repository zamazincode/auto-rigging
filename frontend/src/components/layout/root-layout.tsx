import { Outlet } from "react-router";
import Header from "./header";

export default function RootLayout() {
	return (
		<>
			<Header />
			<Outlet />
		</>
	);
}
