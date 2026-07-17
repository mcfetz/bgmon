<script lang="ts">
	import type { StatsData, PredictionPoint } from '$lib/api/dashboard';
	import { DASHBOARD_STAT_TILES, type DashboardStatTile } from '$lib/dashboardTiles';
	import TirModal from './TirModal.svelte';
	import DailyScoreModal from './DailyScoreModal.svelte';
	import BadgeModal from './BadgeModal.svelte';
	import StreakModal from './StreakModal.svelte';
	import PredictionModal from './PredictionModal.svelte';

	const DEFAULT_VISIBLE_TILES: readonly DashboardStatTile[] = DASHBOARD_STAT_TILES;

	function ignoreStatTile(_tile: DashboardStatTile): void {}

	let {
		stats = null as StatsData | null,
		thresholds = { criticalLow: 54, low: 70, high: 180, criticalHigh: 250 },
		predictions = [] as PredictionPoint[],
		predictions30 = [] as PredictionPoint[],
		predictions60 = [] as PredictionPoint[],
		predictions120 = [] as PredictionPoint[],
		modelMae30 = null as number | null,
		modelMae60 = null as number | null,
		modelMae120 = null as number | null,
		modelVersion = '',
		lastBg = null as number | null,
		lastBgTime = '',
		visibleTiles = DEFAULT_VISIBLE_TILES,
		editMode = false,
		onToggleTile = ignoreStatTile,
	} = $props();

	let tirModalOpen = $state(false);
	let dailyScoreModalOpen = $state(false);
	let badgeModalOpen = $state(false);
	let streakModalOpen = $state(false);
	let predictionModalOpen = $state(false);
	let gmiModalOpen = $state(false);

	function formatStreakHM(intervals: number | null | undefined): string {
		const v = intervals ?? 0;
		const totalMin = v * 15;
		const h = Math.floor(totalMin / 60);
		const m = totalMin % 60;
		return `${h}:${String(m).padStart(2, '0')}`;
	}

	function gmiColor(gmi: number | null | undefined): string {
		if (gmi == null) return 'var(--color-text-muted)';
		if (gmi < 5.7) return '#22c55e';
		if (gmi < 6.5) return '#eab308';
		return '#ef4444';
	}

	function gmiLabel(gmi: number | null | undefined): string {
		if (gmi == null) return '';
		if (gmi < 5.7) return 'Normal';
		if (gmi < 6.5) return 'Prädiabetes';
		return 'Diabetes-Bereich';
	}

	function shouldRenderStatTile(tile: DashboardStatTile): boolean {
		if (editMode) return true;
		return visibleTiles.includes(tile);
	}
</script>

	<div class="stats-grid" class:editing={editMode}>
		{#if shouldRenderStatTile('daily-score')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('daily-score')}>
	<button class="stat-card clickable" type="button" onclick={() => (dailyScoreModalOpen = true)}>
		<span class="label">Heute ⭐</span>
		<span class="value">{stats?.daily_score?.total ?? 0}</span>
		<span class="unit">Punkte · Level {stats?.daily_score?.level ?? 1}</span>
		<div class="level-bar">
			<div class="level-bar-fill" style="width: {stats?.daily_score?.progress ?? 0}%"></div>
		</div>
		{#if stats?.daily_score?.breakdown && stats.daily_score.breakdown.length > 0}
			<span class="streak-date">{stats.daily_score.breakdown.length} Belohnungen</span>
		{:else}
			<span class="streak-date">Noch keine Punkte heute</span>
		{/if}
	</button>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('daily-score')} aria-label={visibleTiles.includes('daily-score') ? 'Heute ausblenden' : 'Heute einblenden'} onclick={() => onToggleTile('daily-score')}>
						<span>{visibleTiles.includes('daily-score') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}

		{#if shouldRenderStatTile('prediction')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('prediction')}>
	<button class="stat-card clickable" type="button" onclick={() => (predictionModalOpen = true)}>
		<span class="label">Prognose +30min</span>
		{#if predictions30.length > 0}
			{@const last = predictions30[predictions30.length - 1]}
			<span class="value">{last.predicted_sgv.toFixed(0)}</span>
			<span class="unit">
				{#if last.lower_bound != null && last.upper_bound != null}
					{last.lower_bound.toFixed(0)}–{last.upper_bound.toFixed(0)} mg/dL
				{:else}
					mg/dL
				{/if}
				{#if modelMae30 !== null}
					<span class="mae-label">±{modelMae30.toFixed(0)}</span>
				{/if}
			</span>
		{:else}
			<span class="value">—</span>
			<span class="unit">Keine Prognose</span>
		{/if}
	</button>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('prediction')} aria-label={visibleTiles.includes('prediction') ? 'Prognose ausblenden' : 'Prognose einblenden'} onclick={() => onToggleTile('prediction')}>
						<span>{visibleTiles.includes('prediction') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}

		{#if shouldRenderStatTile('tir')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('tir')}>
	<button
		class="stat-card clickable"
		class:good={!(stats?.tir_percent != null && stats.tir_percent < 50)}
		type="button"
		onclick={() => (tirModalOpen = true)}
	>
		<span class="label">Time in Range</span>
		<span class="value">{stats?.tir_percent ?? '—'}<span class="unit">%</span></span>
		<div class="tir-bar">
			<div class="tir-segment below" style="width: {stats?.tir_below ?? 0}%"></div>
			<div class="tir-segment range" style="width: {stats?.tir_percent ?? 0}%"></div>
			<div class="tir-segment above" style="width: {stats?.tir_above ?? 0}%"></div>
		</div>
	</button>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('tir')} aria-label={visibleTiles.includes('tir') ? 'Time in Range ausblenden' : 'Time in Range einblenden'} onclick={() => onToggleTile('tir')}>
						<span>{visibleTiles.includes('tir') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}

		{#if shouldRenderStatTile('streak')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('streak')}>
	<button class="stat-card clickable" type="button" onclick={() => (streakModalOpen = true)}>
		<span class="label">Streak 🏆</span>
		<span class="value">{formatStreakHM(stats?.best_streak_hours ?? stats?.streak_hours ?? 0)}</span
		>
		<span class="unit">h:mm</span>
	</button>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('streak')} aria-label={visibleTiles.includes('streak') ? 'Streak ausblenden' : 'Streak einblenden'} onclick={() => onToggleTile('streak')}>
						<span>{visibleTiles.includes('streak') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}

		{#if shouldRenderStatTile('min-mean-max')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('min-mean-max')}>
	<div class="stat-card">
		<span class="label">Min / Ø / Max</span>
		<span class="value">
			{stats?.min ?? '—'} / {stats?.mean ?? '—'} / {stats?.max ?? '—'}
		</span>
		<span class="unit">mg/dL</span>
	</div>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('min-mean-max')} aria-label={visibleTiles.includes('min-mean-max') ? 'Min Mittelwert Max ausblenden' : 'Min Mittelwert Max einblenden'} onclick={() => onToggleTile('min-mean-max')}>
						<span>{visibleTiles.includes('min-mean-max') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}

		{#if shouldRenderStatTile('badges')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('badges')}>
	<button class="stat-card clickable" type="button" onclick={() => (badgeModalOpen = true)}>
		<span class="label">Badges 🏅</span>
		<span class="value">
			{stats?.achievements?.filter((a) => a.unlocked).length ?? 0}/{stats?.achievements?.length ??
				0}
		</span>
		<span class="unit">freigeschaltet</span>
	</button>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('badges')} aria-label={visibleTiles.includes('badges') ? 'Badges ausblenden' : 'Badges einblenden'} onclick={() => onToggleTile('badges')}>
						<span>{visibleTiles.includes('badges') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}

		{#if shouldRenderStatTile('gmi')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('gmi')}>
	<button class="stat-card clickable" type="button" onclick={() => (gmiModalOpen = true)}>
		<span class="label">GMI (eA1c)</span>
		<span class="value" style="color: {gmiColor(stats?.gmi)}">{stats?.gmi ?? '—'}</span>
		<span class="unit">% · {gmiLabel(stats?.gmi)}</span>
	</button>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('gmi')} aria-label={visibleTiles.includes('gmi') ? 'GMI ausblenden' : 'GMI einblenden'} onclick={() => onToggleTile('gmi')}>
						<span>{visibleTiles.includes('gmi') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}

		{#if shouldRenderStatTile('readings')}
			<div class="stat-card-wrapper" class:inactive={editMode && !visibleTiles.includes('readings')}>
	<div class="stat-card">
		<span class="label">Messwerte</span>
		<span class="value">{stats?.readings ?? 0}</span>
		<span class="unit">Stk.</span>
	</div>
				{#if editMode}
					<button class="card-edit-overlay" type="button" aria-pressed={visibleTiles.includes('readings')} aria-label={visibleTiles.includes('readings') ? 'Messwerte ausblenden' : 'Messwerte einblenden'} onclick={() => onToggleTile('readings')}>
						<span>{visibleTiles.includes('readings') ? 'Aktiv' : 'Ausgeblendet'}</span>
					</button>
				{/if}
			</div>
		{/if}
	</div>

<TirModal bind:open={tirModalOpen} {stats} />
<DailyScoreModal
	bind:open={dailyScoreModalOpen}
	score={stats?.daily_score ?? null}
	weekly={stats?.weekly_scores ?? []}
/>
<BadgeModal bind:open={badgeModalOpen} achievements={stats?.achievements ?? []} />
<StreakModal
	bind:open={streakModalOpen}
	bestStreakHours={stats?.best_streak_hours ?? 0}
	bestStreakAchievedAt={stats?.best_streak_achieved_at ?? null}
	currentStreakHours={stats?.streak_hours ?? 0}
	streakStartedAt={stats?.streak_started_at ?? null}
/>
<PredictionModal
	bind:open={predictionModalOpen}
	{predictions30}
	{predictions60}
	{predictions120}
	{modelMae30}
	{modelMae60}
	{modelMae120}
	{modelVersion}
	{lastBg}
	{lastBgTime}
/>

{#if gmiModalOpen}
	<div class="modal-overlay" role="dialog" onclick={() => (gmiModalOpen = false)}>
		<div class="modal-content" onclick={(e) => e.stopPropagation()}>
			<button class="close-btn" type="button" onclick={() => (gmiModalOpen = false)}>✕</button>
			<h2>GMI — Glucose Management Indicator</h2>
			<p class="gmi-desc">
				Der GMI ist ein aus CGM-Daten berechneter Schätzwert, der dem
				laborbestimmten HbA1c ähnelt. Er wird aus deinem durchschnittlichen
				Blutzucker der letzten Wochen berechnet.
			</p>
			<div class="gmi-ranges">
				<div class="gmi-range"><span class="dot" style="background:#22c55e"></span> &lt;5,7% — Normal</div>
				<div class="gmi-range"><span class="dot" style="background:#eab308"></span> 5,7–6,5% — Prädiabetes</div>
				<div class="gmi-range"><span class="dot" style="background:#ef4444"></span> &gt;6,5% — Diabetes-Bereich</div>
			</div>
			<p class="gmi-formula">Formel: GMI (%) = 3,31 + 0,02392 × ∅-Blutzucker (mg/dL)</p>
		</div>
	</div>
{/if}

<style>
	.stats-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		grid-auto-rows: 1fr;
		gap: var(--spacing-md);
	}


	.stat-card-wrapper {
		display: flex;
		position: relative;
		min-width: 0;
	}

	.stat-card-wrapper.inactive {
		opacity: 0.45;
	}

	.card-edit-overlay {
		position: absolute;
		inset: 0;
		z-index: 10;
		display: flex;
		align-items: flex-start;
		justify-content: flex-end;
		padding: var(--spacing-xs);
		border: 2px solid rgba(var(--color-primary-rgb), 0.65);
		border-radius: var(--radius);
		background: transparent;
		color: var(--color-primary);
		box-shadow: inset 0 0 0 999px rgba(var(--color-primary-rgb), 0.06);
	}

	.card-edit-overlay[aria-pressed='false'] {
		border-color: var(--color-border-default);
		color: var(--color-text-muted);
		box-shadow: inset 0 0 0 999px var(--color-border-subtle);
	}

	.card-edit-overlay span {
		padding: var(--spacing-xs) var(--spacing-sm);
		border-radius: var(--radius-pill);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
		font-size: 0.75rem;
		font-weight: 700;
	}

	.card-edit-overlay:focus-visible {
		outline: 3px solid rgba(var(--color-primary-rgb), 0.45);
		outline-offset: 2px;
	}

	.stat-card {
		flex: 1;
		background: var(--color-surface);
		border-radius: var(--radius);
		padding: var(--spacing-md);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-xs);
	}

	@media (max-width: 640px) {
		.stats-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	.stat-card.clickable {
		border: none;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
		transition:
			transform 0.1s,
			box-shadow 0.15s;
	}

	.stat-card.clickable:hover {
		transform: translateY(-1px);
		background: rgba(var(--color-primary-rgb), 0.08);
		box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.25);
	}

	.stat-card.clickable:active {
		transform: translateY(0);
	}

	.label {
		color: var(--color-text-muted);
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.value {
		font-size: 1.6rem;
		font-weight: 700;
		color: var(--color-text);
		line-height: 1;
	}

	.unit {
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	.mae-label {
		display: inline-block;
		margin-left: 0.4rem;
		padding: 0.1rem 0.35rem;
		border-radius: 4px;
		background: rgba(255, 193, 7, 0.15);
		font-size: 0.7rem;
		font-weight: 600;
		color: #b8860b;
	}

	.tir-bar {
		display: flex;
		height: 8px;
		border-radius: 4px;
		overflow: hidden;
		margin-top: var(--spacing-xs);
	}

	.tir-segment.below {
		background: var(--color-target-low);
	}

	.tir-segment.range {
		background: var(--color-success);
	}

	.tir-segment.above {
		background: var(--color-target-high);
	}

	.streak-date {
		font-size: 0.7rem;
		color: var(--color-text-muted);
		font-style: italic;
	}

	.level-bar {
		height: 6px;
		background: var(--color-border);
		border-radius: 3px;
		overflow: hidden;
		margin-top: 2px;
	}

	.level-bar-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--color-primary), var(--color-primary));
		border-radius: 3px;
		transition: width 0.3s ease;
	}

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
		max-width: 400px;
		width: 90%;
		position: relative;
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

	.gmi-desc {
		font-size: 0.9rem;
		line-height: 1.5;
		color: var(--color-text);
		margin: 0.75rem 0 1rem;
	}

	.gmi-ranges {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.gmi-range {
		font-size: 0.9rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.dot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		display: inline-block;
	}

	.gmi-formula {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		font-style: italic;
		margin: 0;
	}
</style>
