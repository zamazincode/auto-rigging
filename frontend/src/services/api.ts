export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";


export async function processModel(file: File): Promise<Blob> {
	const formData = new FormData();
	formData.append("file", file);

	const response = await fetch(`${API_BASE}/rigging/process`, {
		method: "POST",
		body: formData,
	});

	if (!response.ok) {
		const errorData = await response.json().catch(() => null);
		throw new Error(
			errorData?.detail ||
			`Processing failed with status ${response.status}`,
		);
	}

	return response.blob();
}
