<script lang="ts">
	import { goto } from '$app/navigation';
	import { setAuthToken } from '$lib/auth';

	let email = $state('');
	let password = $state('');
	let loading = $state(false);
	let error = $state('');

	async function login() {
		loading = true;
		error = '';
		try {
			const res = await fetch('/api/auth/login', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password })
			});
			if (res.ok) {
				const data = await res.json();
				setAuthToken(data.token);
				goto('/');
			} else {
				const err = await res.json();
				error = err.error || 'Login fehlgeschlagen';
			}
		} catch {
			error = 'Netzwerkfehler';
		}
		loading = false;
	}
</script>

<div class="login">
	<h1>bgmon</h1>
	<form
		onsubmit={(e) => {
			e.preventDefault();
			login();
		}}
	>
		<div class="field">
			<label for="email">E-Mail</label>
			<input id="email" type="email" bind:value={email} required />
		</div>
		<div class="field">
			<label for="password">Passwort</label>
			<input id="password" type="password" bind:value={password} required />
		</div>
		{#if error}
			<div class="error">{error}</div>
		{/if}
		<button type="submit" disabled={loading}>
			{loading ? 'Anmelden...' : 'Anmelden'}
		</button>
	</form>
</div>

<style>
	.login {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 100vh;
		gap: var(--spacing-lg);
		padding: var(--spacing-md);
	}

	.login h1 {
		font-size: 2rem;
		color: var(--color-primary);
		margin: 0;
	}

	form {
		display: flex;
		flex-direction: column;
		gap: var(--spacing-md);
		width: 100%;
		max-width: 320px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.field label {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.field input {
		padding: var(--spacing-sm);
		font-size: 1rem;
		background: var(--color-surface);
		color: var(--color-text);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
	}

	button {
		padding: var(--spacing-sm);
		font-size: 1rem;
		background: var(--color-primary);
		color: var(--color-primary-contrast, #fff);
		border: none;
		border-radius: var(--radius);
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error {
		color: #f87171;
		font-size: 0.9rem;
		text-align: center;
	}
</style>
