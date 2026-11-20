<script>
	// Site shell: header, sidebar, breadcrumbs, page contents, appearance menu.
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import '../site.css';

	let { children } = $props();

	const themes = ['light', 'dark', 'system'];
	const themeNames = { light: 'Light', dark: 'Dark', system: 'System' };
	const sections = [
		{ path: '/authors', name: 'Authors', detail: 'Author Summary' },
		{ path: '/works', name: 'Works', detail: 'Work Detail' }
	];
	let theme = $state('system');
	let menuOpen = $state(false);
	let drawerOpen = $state(false);
	let headings = $state([]);

	const section = $derived(sections.find((candidate) => page.url.pathname.startsWith(candidate.path)));
	const crumbs = $derived(breadcrumbsFor(page.url.pathname, page.status));

	onMount(() => {
		theme = localStorage.getItem('theme') ?? 'system';
		headings = [...document.querySelectorAll('main h2')].map((heading) => {
			heading.id = heading.textContent.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-');
			return { id: heading.id, text: heading.textContent.trim() };
		});
	});

	/** Breadcrumb trail after Home, as Evidence showed it. */
	function breadcrumbsFor(pathname, status) {
		if (status === 404) return [{ name: 'Page Not Found' }];
		const owner = sections.find((candidate) => pathname.startsWith(candidate.path));
		if (!owner) return [];
		const isDetail = pathname.replace(/\/$/, '') !== owner.path;
		if (!isDetail) return [{ name: owner.name }];
		return [{ name: owner.name, href: owner.path }, { name: owner.detail }];
	}

	/** Move to the next theme and apply it to the page. */
	function cycleTheme() {
		theme = themes[(themes.indexOf(theme) + 1) % themes.length];
		localStorage.setItem('theme', theme);
		const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
		const systemTheme = prefersDark ? 'dark' : 'light';
		document.documentElement.dataset.theme = theme === 'system' ? systemTheme : theme;
	}

	/** Close the menu and drawer when Escape is pressed. */
	function closeOnEscape(event) {
		if (event.key !== 'Escape') return;
		menuOpen = false;
		drawerOpen = false;
	}
</script>

<svelte:window onkeydown={closeOnEscape} />

{#snippet navLinks()}
	<div class="nav-links">
		<a class="nav-home" href="/" aria-current={page.url.pathname === '/' ? 'page' : undefined}>Home</a>
		{#each sections as link (link.path)}
			<a href={link.path} aria-current={section === link ? 'page' : undefined}>{link.name}</a>
		{/each}
	</div>
{/snippet}

<header class="site-header">
	<div class="header-inner">
		<div class="header-start">
			<button class="icon-button sidebar-button" type="button" onclick={() => (drawerOpen = true)}>
				<span class="sr-only">Open sidebar</span>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
					<path d="M4 6h16M4 12h16M4 18h16" />
				</svg>
			</button>
			<a class="logo" href="/">Gufime.com</a>
		</div>
		<div class="menu-anchor">
			<button
				class="icon-button menu-button"
				type="button"
				aria-label="Menu"
				aria-expanded={menuOpen}
				onclick={() => (menuOpen = !menuOpen)}
			>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					<circle cx="5" cy="12" r="1" />
					<circle cx="12" cy="12" r="1" />
					<circle cx="19" cy="12" r="1" />
				</svg>
			</button>
			{#if menuOpen}
				<div class="menu" role="menu">
					<button class="menu-item" type="button" role="menuitem" onclick={cycleTheme}>
						Appearance <span>{themeNames[theme]}</span>
					</button>
				</div>
			{/if}
		</div>
	</div>
</header>

{#if drawerOpen}
	<div class="drawer" role="dialog" aria-modal="true" aria-label="Site navigation">
		<div class="drawer-top">
			<a class="logo" href="/">Gufime.com</a>
			<button class="icon-button" type="button" onclick={() => (drawerOpen = false)}>
				<span class="sr-only">Close sidebar</span>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
					<path d="M18 6 6 18M6 6l12 12" />
				</svg>
			</button>
		</div>
		<nav aria-label="Site">{@render navLinks()}</nav>
	</div>
{/if}

<div class="shell">
	<aside class="sidebar">
		<nav aria-label="Site">{@render navLinks()}</nav>
	</aside>
	<main>
		<nav class="breadcrumbs" aria-label="Breadcrumb">
			<a href="/">Home</a>
			{#each crumbs as crumb (crumb.name)}
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
				{#if crumb.href}
					<a href={crumb.href}>{crumb.name}</a>
				{:else}
					<span aria-current="page">{crumb.name}</span>
				{/if}
			{/each}
		</nav>
		<article>
			{@render children()}
		</article>
	</main>
	<aside class="contents">
		{#if headings.length > 0}
			<nav aria-label="On this page">
				<span>On this page</span>
				{#each headings as heading (heading.id)}
					<a href="#{heading.id}">{heading.text}</a>
				{/each}
			</nav>
		{/if}
	</aside>
</div>
