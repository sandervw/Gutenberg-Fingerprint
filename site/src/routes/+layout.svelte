<script>
	// Site shell: navigation, appearance menu, page frame.
	import { onMount } from 'svelte';
	import '../sparse.css';
	import '../wordleaves.css';
	import '../site.css';

	let { children } = $props();

	const themes = ['light', 'dark', 'system'];
	const themeNames = { light: 'Light', dark: 'Dark', system: 'System' };
	let theme = $state('system');
	let menuOpen = $state(false);

	onMount(() => {
		theme = localStorage.getItem('theme') ?? 'system';
	});

	/** Move to the next theme and apply it to the page. */
	function cycleTheme() {
		theme = themes[(themes.indexOf(theme) + 1) % themes.length];
		localStorage.setItem('theme', theme);
		const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
		const systemTheme = prefersDark ? 'dark' : 'light';
		document.documentElement.dataset.theme = theme === 'system' ? systemTheme : theme;
	}

	/** Close the menu when Escape is pressed. */
	function closeOnEscape(event) {
		if (event.key === 'Escape') menuOpen = false;
	}
</script>

<svelte:window onkeydown={closeOnEscape} />

<header class="navbar">
	<a class="navbar-title" href="/">Gufime.com</a>
	<nav>
		<a href="/">Home</a>
		<a href="/works">Works</a>
		<a href="/authors">Authors</a>
		<button class="control" type="button" aria-label="Menu" aria-expanded={menuOpen} onclick={() => (menuOpen = !menuOpen)}>
			&#8942;
		</button>
		{#if menuOpen}
			<div class="menu" role="menu">
				<button class="control" type="button" role="menuitem" onclick={cycleTheme}>
					Appearance: {themeNames[theme]}
				</button>
			</div>
		{/if}
	</nav>
</header>
<main class="page page-text">
	{@render children()}
</main>
