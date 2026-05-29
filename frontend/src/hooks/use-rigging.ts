import { useState, useCallback, useRef } from "react";
import type { RiggingState, ProcessingStage } from "../types";
import { processModel } from "../services/api";

const STAGES: ProcessingStage[] = [
	"rendering",
	"classifying",
	"rigging",
	"finalizing",
];

const STAGE_DURATIONS = [3000, 3000, 8000, 2000];

export function useRigging() {
	const [state, setState] = useState<RiggingState>({
		status: "idle",
		file: null,
		previewUrl: null,
		resultUrl: null,
		processingStage: null,
		errorMessage: null,
	});

	const timerRef = useRef<number | null>(null);

	const clearTimers = useCallback(() => {
		if (timerRef.current) {
			clearTimeout(timerRef.current);
			timerRef.current = null;
		}
	}, []);

	const setFile = useCallback((file: File, previewUrl: string) => {
		setState({
			status: "previewing",
			file,
			previewUrl,
			resultUrl: null,
			processingStage: null,
			errorMessage: null,
		});
	}, []);

	const simulateProgress = useCallback(() => {
		let currentStageIdx = 0;

		const nextStage = () => {
			if (currentStageIdx < STAGES.length) {
				setState((s) => ({
					...s,
					processingStage: STAGES[currentStageIdx],
				}));
				
				// Keep cycling the last stage ("finalizing") if actual processing takes longer
				if (currentStageIdx < STAGES.length - 1) {
					timerRef.current = window.setTimeout(nextStage, STAGE_DURATIONS[currentStageIdx]);
					currentStageIdx++;
				}
			}
		};

		nextStage();
	}, []);

	const startProcessing = useCallback(async () => {
		if (!state.file || !state.previewUrl) return;

		clearTimers();
		
		setState((s) => ({
			...s,
			status: "processing",
			errorMessage: null,
		}));

		simulateProgress();

		try {
			const blob = await processModel(state.file);
			
			// Processing successful
			clearTimers();
			const resultUrl = URL.createObjectURL(blob);
			
			setState((s) => ({
				...s,
				status: "completed",
				resultUrl,
				processingStage: null,
			}));
		} catch (error) {
			clearTimers();
			setState((s) => ({
				...s,
				status: "error",
				processingStage: null,
				errorMessage: error instanceof Error ? error.message : "An unknown error occurred",
			}));
		}
	}, [state.file, state.previewUrl, simulateProgress, clearTimers]);

	const reset = useCallback(() => {
		clearTimers();
		if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
		if (state.resultUrl) URL.revokeObjectURL(state.resultUrl);
		
		setState({
			status: "idle",
			file: null,
			previewUrl: null,
			resultUrl: null,
			processingStage: null,
			errorMessage: null,
		});
	}, [state.previewUrl, state.resultUrl, clearTimers]);

	const retry = useCallback(() => {
		if (state.file && state.previewUrl) {
			setState((s) => ({
				...s,
				status: "previewing",
				errorMessage: null,
			}));
		}
	}, [state.file, state.previewUrl]);

	return {
		state,
		setFile,
		startProcessing,
		reset,
		retry,
	};
}
