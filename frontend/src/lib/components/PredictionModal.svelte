<script lang="ts">
	import type { PredictionPoint } from '$lib/api/dashboard';

	let {
		open = false,
		predictions30 = [] as PredictionPoint[],
		predictions60 = [] as PredictionPoint[],
		predictions120 = [] as PredictionPoint[],
		modelMae30 = null as number | null,
		modelMae60 = null as number | null,
		modelMae120 = null as number | null,
		modelVersion = '',
		lastBg = null as number | null,
		lastBgTime = ''
	} = $props();

	function formatTime(iso: string): string {
		try {
			return new Date(iso).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
		} catch {
			return '—';
		}
	}

	function horizonLabel(h: number): string {
		const now = new Date();
		const t = new Date(now.getTime() + h * 60_000);
		return `${h} min (${t.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })})`;
	}

	function lastPoint(pts: PredictionPoint[]): PredictionPoint | null {
		return pts.length > 0 ? pts[pts.length - 1] : null;
	}

	function maeHint(mae: number | null): string {
		if (mae === null) return '';
		if (mae < 15) return '🔵 Gute Genauigkeit';
		if (mae < 30) return '🟡 Mittlere Genauigkeit';
		if (mae < 50) return '🟠 Eingeschränkt';
		return '🔴 Ungenau — mit Vorsicht nutzen';
	}
</script>

{#if open}
	<div class="modal-overlay" role="dialog" onclick={() => (open = false)}>
		<div class="modal-content" onclick={(e) => e.stopPropagation()}>
			<button class="close-btn" type="button" onclick={() => (open = false)}>✕</button>

			<h2>BG-Prognose</h2>
			<p class="subtitle">
				Lineare Regression aus {lastBg != null ? `${lastBg} mg/dL` : 'historischen Daten'}
				seit {lastBgTime ? formatTime(lastBgTime) : '—'}
			</p>

			<div class="horizons">
				{#if predictions30.length > 0}
					{@const last = lastPoint(predictions30)}
					<div class="horizon-card">
						<span class="horizon-label">{horizonLabel(30)}</span>
						<span class="horizon-value">{last?.predicted_sgv.toFixed(0) ?? '—'}</span>
						<span class="horizon-range">
							{last?.lower_bound?.toFixed(0) ?? '?'}–{last?.upper_bound?.toFixed(0) ?? '?'} mg/dL
						</span>
						{#if modelMae30 !== null}
							<span class="horizon-mae">MAE {modelMae30.toFixed(1)} mg/dL</span>
							<span class="horizon-hint">{maeHint(modelMae30)}</span>
						{/if}
					</div>
				{/if}
				{#if predictions60.length > 0}
					{@const last = lastPoint(predictions60)}
					<div class="horizon-card">
						<span class="horizon-label">{horizonLabel(60)}</span>
						<span class="horizon-value">{last?.predicted_sgv.toFixed(0) ?? '—'}</span>
						<span class="horizon-range">
							{last?.lower_bound?.toFixed(0) ?? '?'}–{last?.upper_bound?.toFixed(0) ?? '?'} mg/dL
						</span>
						{#if modelMae60 !== null}
							<span class="horizon-mae">MAE {modelMae60.toFixed(1)} mg/dL</span>
							<span class="horizon-hint">{maeHint(modelMae60)}</span>
						{/if}
					</div>
				{/if}
			</div>

			{#if modelVersion}
				<p class="version">Modell: {modelVersion}</p>
			{/if}

			<div class="disclaimer">
				<strong>⚠️ Experimentell</strong>
				<p>
					Die Prognose basiert auf einem statistischen Modell (LinearRegression) und
					ersetzt keine medizinische Beratung. Die Vorhersage berücksichtigt aktuelle
					BG-Werte, Kohlenhydrate und Insulin der letzten Stunden — aber nicht ob
					gerade gegessen oder gespritzt wird. Ein MAE (mittlere Abweichung) von
					z. B. 46 mg/dL bedeutet, dass der tatsächliche Wert im Schnitt 46 mg/dL
					von der Vorhersage abweicht.
				</p>
			</div>
		</div>
	</div>
{/if}

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}

	.modal-content {
		background: var(--color-surface);
		border-radius: var(--radius, 12px);
		padding: 2rem;
		max-width: 460px;
		width: 90%;
		position: relative;
		max-height: 90vh;
		overflow-y: auto;
	}

	.close-btn {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		background: none;
		border: none;
		font-size: 1.2rem;
		cursor: pointer;
		color: var(--color-text-muted);
	}

	h2 {
		margin: 0 0 0.25rem;
		font-size: 1.2rem;
	}

	.subtitle {
		margin: 0 0 1rem;
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.horizons {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.horizon-card {
		background: var(--color-bg, rgba(0, 0, 0, 0.03));
		border-radius: 8px;
		padding: 0.75rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.horizon-label {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.horizon-value {
		font-size: 1.8rem;
		font-weight: 700;
		line-height: 1;
	}

	.horizon-range {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.horizon-mae {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		margin-top: 0.25rem;
	}

	.horizon-hint {
		font-size: 0.85rem;
		font-weight: 600;
	}

	.version {
		font-size: 0.7rem;
		color: var(--color-text-muted);
		text-align: center;
		margin: 0 0 1rem;
	}

	.disclaimer {
		background: rgba(255, 193, 7, 0.12);
		border-radius: 8px;
		padding: 0.75rem 1rem;
		font-size: 0.8rem;
		line-height: 1.4;
		color: var(--color-text);
	}

	.disclaimer strong {
		display: block;
		margin-bottom: 0.25rem;
	}

	.disclaimer p {
		margin: 0;
	}
</style>
