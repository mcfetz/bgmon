<script lang="ts">
	import {
		fmtDuration,
		progressPct,
		stageLabel,
		stageUnit,
		type MlProgress
	} from '#lib/mlProgress.js';

	let { progress }: { progress: MlProgress } = $props();

	const pct = $derived(progressPct(progress));
	const unit = $derived(stageUnit(progress.stage));
</script>

<div class="ml-progress">
	<div class="ml-progress-head">
		<span class="ml-progress-stage">
			{stageLabel(progress.stage)}
			{#if unit && progress.total > 0}
				({progress.done}/{progress.total} {unit})
			{/if}
		</span>
		<span class="ml-progress-pct">{pct}%</span>
	</div>
	<div
		class="ml-progress-track"
		role="progressbar"
		aria-valuenow={pct}
		aria-valuemin="0"
		aria-valuemax="100"
	>
		<div class="ml-progress-fill" style="width: {pct}%"></div>
	</div>
	<p class="ml-progress-meta">
		Läuft seit {fmtDuration(progress.elapsed_s)}
		{#if progress.eta_s != null && progress.eta_s > 0}
			· noch ca. {fmtDuration(progress.eta_s)}
		{/if}
	</p>
</div>

<style>
	.ml-progress {
		margin-top: 0.75rem;
	}

	.ml-progress-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--spacing-sm);
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.ml-progress-stage {
		color: var(--color-text);
	}

	.ml-progress-pct {
		font-variant-numeric: tabular-nums;
		flex-shrink: 0;
	}

	.ml-progress-track {
		height: 6px;
		margin-top: 0.35rem;
		background: var(--color-border);
		border-radius: 3px;
		overflow: hidden;
	}

	.ml-progress-fill {
		height: 100%;
		background: var(--color-primary);
		border-radius: 3px;
		transition: width 0.4s ease;
	}

	.ml-progress-meta {
		margin: 0.35rem 0 0;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}
</style>
