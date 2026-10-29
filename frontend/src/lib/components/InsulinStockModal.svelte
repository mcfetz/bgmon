<script lang="ts">
	import type {
		InsulinStockInfo,
		NeedleStockInfo,
		SensorStockInfo,
		StatsData
	} from '#lib/api/dashboard.js';

	let {
		open = $bindable(false),
		info = null as StatsData['insulin_stock']
	}: {
		open?: boolean;
		info?: StatsData['insulin_stock'];
	} = $props();

	function close() {
		open = false;
	}

	function formatCountDate(iso: string | null | undefined): string {
		if (!iso) return '—';
		const d = new Date(iso);
		if (Number.isNaN(d.getTime())) return '—';
		return d.toLocaleDateString('de-DE', {
			day: '2-digit',
			month: '2-digit',
			year: 'numeric'
		});
	}

	function formatDays(value: number | null | undefined): string {
		return value == null ? '—' : String(value);
	}

	function formatUnits(value: number | null | undefined): string {
		return value == null ? '—' : String(value);
	}

	function formatCount(value: number | null | undefined): string {
		return value == null ? '—' : String(value);
	}
</script>

{#if open}
	<button class="sm-backdrop" type="button" onclick={close} aria-label="Schließen"></button>
	<div class="sm-modal" role="dialog" aria-modal="true" aria-label="Insulin-Vorrat">
		<header class="sm-header">
			<h2>Vorrat 📦</h2>
			<button class="close-btn" type="button" onclick={close} aria-label="Schließen">×</button>
		</header>

		<div class="sm-body">
			{#if !info?.bolus?.configured && !info?.basal?.configured && !info?.needles?.configured && !info?.sensors?.configured}
				<p class="sm-empty">
					Kein Bestand hinterlegt. Lege ihn unter <em>Einstellungen → Faktoren</em> an, um den Vorrat
					zu verfolgen.
				</p>
			{:else}
				{#each ['bolus', 'basal'] as const as key (key)}
					{@const item = info?.[key] as InsulinStockInfo | null}
					{@const label = key === 'bolus' ? 'Schnellinsulin' : 'Basalinsulin'}
					{@const icon = key === 'bolus' ? '💉' : '🧴'}
					{#if item}
						<section class="sm-section" class:low={item.low_stock}>
							<div class="sm-section-head">
								<h3 class="sm-section-title">{icon} {label}</h3>
								{#if item.configured && item.low_stock}
									<span class="sm-low-badge">Nachschub besorgen</span>
								{/if}
							</div>

							{#if item.configured}
								<div class="sm-value-row">
									<span class="sm-value" class:low={item.low_stock}
										>{formatDays(item.days_left)}</span
									>
									<span class="sm-unit">Tage</span>
								</div>

								<ul class="sm-details">
									<li>
										<span class="sm-detail-label">Rechnerisch verbleibend</span>
										<span class="sm-detail-value">{formatUnits(item.effective_stock)} U</span>
									</li>
									<li>
										<span class="sm-detail-label">Gezählt (Bestand)</span>
										<span class="sm-detail-value"
											>{formatUnits(item.stock_units)} U · {formatCountDate(
												item.stock_set_at
											)}</span
										>
									</li>
									<li>
										<span class="sm-detail-label">Verbrauch seit Zählen</span>
										<span class="sm-detail-value">{formatUnits(item.consumed_since_set_at)} U</span>
									</li>
									<li>
										<span class="sm-detail-label">Verbrauch (14-Tage-Ø)</span>
										<span class="sm-detail-value">~{formatUnits(item.usage_per_day)} U/Tag</span>
									</li>
									<li>
										<span class="sm-detail-label">Warnschwelle</span>
										<span class="sm-detail-value">unter {item.low_stock_days} Tagen</span>
									</li>
								</ul>
							{:else}
								<p class="sm-empty">
									Bestand nicht konfiguriert — unter <em>Einstellungen → Faktoren</em> hinterlegen.
								</p>
							{/if}
						</section>
					{/if}
				{/each}

				{#if info?.needles}
					{@const needles = info.needles as NeedleStockInfo}
					<section class="sm-section" class:low={needles.low_stock}>
						<div class="sm-section-head">
							<h3 class="sm-section-title">🧷 Spritzenköpfe</h3>
							{#if needles.configured && needles.low_stock}
								<span class="sm-low-badge">Nachschub besorgen</span>
							{/if}
						</div>

						{#if needles.configured}
							<div class="sm-value-row">
								<span class="sm-value" class:low={needles.low_stock}
									>{formatDays(needles.days_left)}</span
								>
								<span class="sm-unit">Tage</span>
							</div>

							<ul class="sm-details">
								<li>
									<span class="sm-detail-label">Rechnerisch verbleibend</span>
									<span class="sm-detail-value">{formatCount(needles.effective_stock)} Stk.</span>
								</li>
								<li>
									<span class="sm-detail-label">Gezählt (Bestand)</span>
									<span class="sm-detail-value"
										>{formatCount(needles.stock_units)} Stk. · {formatCountDate(
											needles.stock_set_at
										)}</span
									>
								</li>
								<li>
									<span class="sm-detail-label">Verbrauch seit Zählen</span>
									<span class="sm-detail-value"
										>{formatCount(needles.consumed_since_set_at)} Stk.</span
									>
								</li>
								<li>
									<span class="sm-detail-label">Verbrauch (14-Tage-Ø)</span>
									<span class="sm-detail-value"
										>~{formatCount(needles.avg_daily_injections)} Stk./Tag</span
									>
								</li>
								<li>
									<span class="sm-detail-label">Warnschwelle</span>
									<span class="sm-detail-value">unter {needles.low_stock_days} Tagen</span>
								</li>
							</ul>
						{:else}
							<p class="sm-empty">
								Bestand nicht konfiguriert — unter <em>Einstellungen → Faktoren</em> hinterlegen.
							</p>
						{/if}
					</section>
				{/if}

				{#if info?.sensors}
					{@const sensors = info.sensors as SensorStockInfo}
					<section class="sm-section" class:low={sensors.low_stock}>
						<div class="sm-section-head">
							<h3 class="sm-section-title">📡 Sensoren</h3>
							{#if sensors.configured && sensors.low_stock}
								<span class="sm-low-badge">Nachschub besorgen</span>
							{/if}
						</div>

						{#if sensors.configured}
							<div class="sm-value-row">
								<span class="sm-value" class:low={sensors.low_stock}
									>{formatDays(sensors.days_left)}</span
								>
								<span class="sm-unit">Tage</span>
							</div>

							<ul class="sm-details">
								<li>
									<span class="sm-detail-label">Rechnerisch verbleibend</span>
									<span class="sm-detail-value">{formatCount(sensors.effective_stock)} Stk.</span>
								</li>
								<li>
									<span class="sm-detail-label">Gezählt (Bestand)</span>
									<span class="sm-detail-value"
										>{formatCount(sensors.stock_units)} Stk. · {formatCountDate(
											sensors.stock_set_at
										)}</span
									>
								</li>
								<li>
									<span class="sm-detail-label">Verbraucht seit Zählen</span>
									<span class="sm-detail-value"
										>{formatCount(sensors.consumed_since_set_at)} Stk.</span
									>
								</li>
								<li>
									<span class="sm-detail-label">Nutzungsdauer</span>
									<span class="sm-detail-value"
										>~{formatCount(sensors.lifetime_days ?? 14)} Tage/Sensor</span
									>
								</li>
								<li>
									<span class="sm-detail-label">Warnschwelle</span>
									<span class="sm-detail-value">unter {sensors.low_stock_days} Tagen</span>
								</li>
							</ul>
						{:else}
							<p class="sm-empty">
								Bestand nicht konfiguriert — unter <em>Einstellungen → Faktoren</em> hinterlegen.
							</p>
						{/if}
					</section>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<style>
	.sm-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 201;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		appearance: none;
		-webkit-appearance: none;
		color: transparent;
		outline: none;
	}

	.sm-backdrop:hover,
	.sm-backdrop:focus,
	.sm-backdrop:focus-visible,
	.sm-backdrop:active {
		background: rgba(0, 0, 0, 0.5);
		outline: none;
		box-shadow: none;
	}

	.sm-modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		background: var(--color-surface);
		border-radius: var(--radius);
		width: 90vw;
		max-width: 480px;
		max-height: 85vh;
		overflow-y: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
		z-index: 202;
	}

	.sm-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-md);
		border-bottom: 1px solid var(--color-border);
	}

	.sm-header h2 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--color-text);
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: 1.5rem;
		cursor: pointer;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius);
	}

	.close-btn:hover {
		background: var(--color-bg);
		color: var(--color-text);
	}

	.sm-body {
		padding: var(--spacing-md);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.sm-section {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-xs);
		padding: var(--spacing-sm);
		background: rgba(var(--color-primary-rgb), 0.08);
		border-radius: var(--radius);
	}

	.sm-section.low {
		background: rgba(239, 68, 68, 0.12);
	}

	.sm-section-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.sm-section-title {
		margin: 0;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.sm-low-badge {
		font-size: 0.7rem;
		font-weight: 700;
		color: #ef4444;
	}

	.sm-value-row {
		display: flex;
		align-items: baseline;
		gap: var(--spacing-xs);
	}

	.sm-value {
		font-size: 2.4rem;
		font-weight: 700;
		color: var(--color-primary);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	.sm-value.low {
		color: #ef4444;
	}

	.sm-unit {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.sm-details {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--spacing-xs);
	}

	.sm-details li {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}

	.sm-detail-label {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.sm-detail-value {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text);
		font-variant-numeric: tabular-nums;
	}

	.sm-empty {
		margin: 0;
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}
</style>
