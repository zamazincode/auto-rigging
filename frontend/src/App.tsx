import { Route, Routes } from "react-router";
import RootLayout from "./components/layout/root-layout";
import Home from "./pages/home";

function App() {
	return (
		<Routes>
			<Route element={<RootLayout />}>
				<Route index element={<Home />} />
				<Route path="rig" element={<Rig />} />
			</Route>
		</Routes>
	);
}

export default App;
