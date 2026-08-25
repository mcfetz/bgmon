<script lang="ts">
	import type { DailyProfile } from '$lib/api/report';

	let { profiles }: { profiles: DailyProfile[] } = $props();

	const chartW = 200;
	const chartH = 60;
	const pad = { top: 5, right: 5, bottom: 15, left: 5 };
	const innerW = chartW - pad.left - pad.right;
	const innerH = chartH - pad.top - pad.bottom;

	const LOW = 70;
	const HIGH = 180;
	const Y_MIN = 0;
	const Y_MAX = 350;

	function scaleX(minutes: number): number {
		return pad.left + (minutes / (24 * 60)) * innerW;
	}
	function scaleY(v: number): number {
		return pad.top + innerH - ((v - Y_MIN) / (Y_MAX - Y_MIN)) * innerH;
	}
</script>

<div class="daily-grid">
	{#each profiles as profile}
		<div class="day-card">
			<div class="day-header">
				<span class="day-weekday">{profile.weekday}</span>
				<span class="day-date">{profile.date.slice(8)}.{profile.date.slice(5, 7)}</span>
				{#if profile.avg !== null}
					<span class="day-avg">{profile.avg} mg/dL</span>
				{/if}
			</div>
			<svg viewBox="0 0 {chartW} {chartH}" class="day-svg">
				<!-- Target range -->
				<rect
					x={pad.left}
					y={scaleY(HIGH)}
					width={innerW}
					height={scaleY(LOW) - scaleY(HIGH)}
					fill="#dcfce7"
					opacity="0.4"
				/>
				<!-- 70 line -->
				<line x1={pad.left} y1={scaleY(LOW)} x2={pad.left + innerW} y2={scaleY(LOW)}
					stroke="#f97316" stroke-width="0.5" stroke-dasharray="2,2" />
				<!-- 180 line -->
				<line x1={pad.left} y1={scaleY(HIGH)} x2={pad.left + innerW} y2={scaleY(HIGH)}
					stroke="#eab308" stroke-width="0.5" stroke-dasharray="2,2" />
				<!-- Glucose line -->
				{#if profile.readings.length > 1}
					<polyline
						points={profile.readings
							.map(([time, sgv]) => {
								const [h, m] = time.split(':').map(Number);
								const x = scaleX(h * 60 + m);
								const y = scaleY(sgv);
								return `${x},${y}`;
							})
							.join(' ')}
						fill="none"
						stroke="#1d4ed8"
						stroke-width="1.2"
					/>
				{/if}
			</svg>
			<div class="day-footer">
				{#if profile.carbs_total !== null}
					<span class="day-carbs">🍞 {profile.carbs_total}g</span>
				{/if}
				{#if profile.insulin_total !== null}
					<span class="day-insulin">💉 {profile.insulin_total}U</span>
				{/if}
				{#if profile.hypo_events > 0}
					<span class="day-hypo">⚠ {profile.hypo_events}</span>
				{/if}
			</div>
		</div>
	{/each}
</div>

<style>
	.daily-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 0.5rem;
	}
	.day-card {
		border: 1px solid var(--color-border, #e5e7eb);
		border-radius: 6px;
		padding: 0.4rem;
		background: var(--color-surface, #fff);
	}
	.day-header {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.75rem;
		margin-bottom: 0.2rem;
	}
	.day-weekday {
		font-weight: 700;
	}
	.day-date {
		color: var(--color-text-muted, #666);
	}
	.day-avg {
		margin-left: auto;
		font-weight: 600;
	}
	.day-svg {
		width: 100%;
		height: auto;
	}
	.day-footer {
		display: flex;
		gap: 0.5rem;
		font-size: 0.7rem;
		margin-top: 0.2rem;
		color: var(--color-text-muted, #666);
	}
	.day-hypo {
		color: #dc2626;
		font-weight: 600;
	}
</style>
