<script lang="ts">
	type Breakdown = { label: string; points: number; count?: number };
	type DailyScore = {
		total: number;
		level: number;
		progress: number;
		breakdown: Breakdown[];
	} | null;
	type WeekDay = { date: string; total: number; is_today: boolean };

	let {
		open = $bindable(false),
		score = null as DailyScore,
		weekly = [] as WeekDay[]
	}: {
		open?: boolean;
		score?: DailyScore;
		weekly?: WeekDay[];
	} = $props();

	function close() {
		open = false;
	}

	function getScoreColor(s: number): string {
		if (s >= 50) return 'rgba(var(--color-primary-rgb), 0.7)';
		if (s >= 30) return 'rgba(var(--color-primary-rgb), 0.45)';
		if (s >= 15) return 'rgba(var(--color-primary-rgb), 0.25)';
		if (s > 0) return 'rgba(var(--color-primary-rgb), 0.1)';
		return 'var(--color-border)';
	}

	const dayNames = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

	const tips = $derived.by(() => {
		if (!score) return [];
		const earned = new Set(score.breakdown.map((b) => b.label));
		const out: { icon: string; text: string; points: string }[] = [];

		if (
			!earned.has('Einträge erfasst') ||
			(score.breakdown.find((b) => b.label === 'Einträge erfasst')?.count ?? 0) < 5
		) {
			out.push({
				icon: '🥪',
				text: 'Erfasse mehrere Mahlzeiten und Insulin-Dosen',
				points: '+2 pro Eintrag'
			});
		}
		if (!earned.has('Alle 3 Typen')) {
			out.push({ icon: '💉', text: 'Erfasse auch dein Basal-Insulin heute', points: '+10' });
		}
		if (!earned.has('Pünktlich (< 15 Min)')) {
			out.push({
				icon: '⏱️',
				text: 'Protokolliere Insulin innerhalb 15 Min nach dem Essen',
				points: '+3 pro Treffer'
			});
		}
		if (!earned.has('TIR ≥ 80%') && !earned.has('TIR ≥ 90%')) {
			out.push({
				icon: '🎯',
				text: 'Bleib im grünen Bereich — Ziel: 80% TIR',
				points: '+15 (90%: +25)'
			});
		} else if (earned.has('TIR ≥ 80%') && !earned.has('TIR ≥ 90%')) {
			out.push({ icon: '🎯', text: 'Noch besser: 90% TIR für extra Punkte', points: '+10 mehr' });
		}
		if (!earned.has('Streak-Meilensteine')) {
			out.push({
				icon: '🏆',
				text: 'Halte deinen Streak — jede 15 Min gibt Punkte',
				points: '+1 pro Meilenstein'
			});
		} else {
			out.push({ icon: '🔥', text: 'Streak läuft — weiter so!', points: '+1 alle 15 Min' });
		}
		if (!earned.has('Neuer Rekord!')) {
			out.push({ icon: '⭐', text: 'Schlage deinen persönlichen Streak-Rekord', points: '+20' });
		}
		return out;
	});
</script>

{#if open}
	<button class="ds-modal-backdrop" type="button" onclick={close} aria-label="Schließen"></button>
	<div class="ds-modal" role="dialog" aria-modal="true" aria-label="Heute-Punkte">
		<header class="ds-header">
			<h2>Heute ⭐</h2>
			<button class="close-btn" type="button" onclick={close} aria-label="Schließen">×</button>
		</header>

		<div class="ds-body">
			<div class="ds-score-big">
				<span class="ds-score-value">{score?.total ?? 0}</span>
				<span class="ds-score-label">Punkte · Level {score?.level ?? 1}</span>
			</div>

			<div class="level-bar">
				<div class="level-bar-fill" style="width: {score?.progress ?? 0}%"></div>
			</div>

			{#if weekly.length > 0}
				<h3 class="ds-section">Diese Woche</h3>
				<div class="week-grid">
					{#each dayNames as dayName, i}
						{@const d = weekly[i]}
						<div class="week-day" class:today={d?.is_today}>
							<span class="day-name">{dayName}</span>
							<span class="day-score" style="background: {getScoreColor(d?.total ?? 0)}">
								{d?.total ?? 0}
							</span>
						</div>
					{/each}
				</div>
			{/if}

			{#if score?.breakdown && score.breakdown.length > 0}
				<h3 class="ds-section">Heute erreicht</h3>
				<ul class="breakdown-list">
					{#each score.breakdown as b}
						<li>
							<span class="bd-label">
								{b.label}
								{#if b.count !== undefined}<span class="bd-count">×{b.count}</span>{/if}
							</span>
							<span class="bd-points">+{b.points}</span>
						</li>
					{/each}
				</ul>
			{/if}

			{#if tips.length > 0}
				<h3 class="ds-section">Noch mehr Punkte holen</h3>
				<ul class="tips-list">
					{#each tips as t}
						<li>
							<span class="tip-icon">{t.icon}</span>
							<span class="tip-text">{t.text}</span>
							<span class="tip-points">{t.points}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>
{/if}

<style>
	.ds-modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 100;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		appearance: none;
		-webkit-appearance: none;
		color: transparent;
		outline: none;
	}

	.ds-modal-backdrop:hover,
	.ds-modal-backdrop:focus,
	.ds-modal-backdrop:focus-visible,
	.ds-modal-backdrop:active {
		background: rgba(0, 0, 0, 0.5);
		outline: none;
		box-shadow: none;
	}

	.ds-modal {
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
		z-index: 101;
	}

	.ds-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-md);
		border-bottom: 1px solid var(--color-border);
	}

	.ds-header h2 {
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

	.ds-body {
		padding: var(--spacing-md);
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
	}

	.ds-score-big {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
	}

	.ds-score-value {
		font-size: 3rem;
		font-weight: 700;
		color: var(--color-primary);
		line-height: 1;
	}

	.ds-score-label {
		font-size: 0.85rem;
		color: var(--color-text-muted);
	}

	.level-bar {
		height: 8px;
		background: var(--color-border);
		border-radius: 4px;
		overflow: hidden;
	}

	.level-bar-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--color-primary), var(--color-primary));
		border-radius: 4px;
		transition: width 0.3s ease;
	}

	.ds-section {
		margin: 0;
		font-size: 0.8rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.week-grid {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 4px;
	}

	.week-day {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		padding: 4px 0;
		border-radius: 4px;
	}

	.week-day.today {
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
	}

	.day-name {
		font-size: 0.65rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
	}

	.day-score {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text);
		padding: 2px 6px;
		border-radius: 4px;
		min-width: 28px;
		text-align: center;
	}

	.breakdown-list,
	.tips-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.breakdown-list li {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--spacing-xs) var(--spacing-sm);
		background: rgba(var(--color-primary-rgb), 0.08);
		border-radius: var(--radius);
		font-size: 0.85rem;
	}

	.bd-label {
		color: var(--color-text);
	}

	.bd-count {
		color: var(--color-text-muted);
		font-size: 0.75rem;
		margin-left: 4px;
	}

	.bd-points {
		color: var(--color-primary);
		font-weight: 600;
	}

	.tips-list li {
		display: flex;
		align-items: center;
		gap: var(--spacing-sm);
		padding: var(--spacing-xs) var(--spacing-sm);
		background: var(--color-bg);
		border-radius: var(--radius);
		font-size: 0.85rem;
	}

	.tip-icon {
		font-size: 1.1rem;
		flex-shrink: 0;
	}

	.tip-text {
		flex: 1;
		color: var(--color-text);
	}

	.tip-points {
		color: var(--color-text-muted);
		font-size: 0.75rem;
		flex-shrink: 0;
	}
</style>
