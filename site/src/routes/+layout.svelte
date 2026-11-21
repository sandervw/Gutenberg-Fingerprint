<script>
	// Site shell: wood sign, theme switch, and the sheet with breadcrumbs.
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

	const section = $derived(sections.find((candidate) => page.url.pathname.startsWith(candidate.path)));
	const crumbs = $derived(breadcrumbsFor(page.url.pathname, page.status));

	onMount(() => {
		theme = localStorage.getItem('theme') ?? 'system';
	});

	/** Breadcrumb trail after Home. */
	function breadcrumbsFor(pathname, status) {
		if (status === 404) return [{ name: 'Page Not Found' }];
		const owner = sections.find((candidate) => pathname.startsWith(candidate.path));
		if (!owner) return [];
		const isDetail = pathname.replace(/\/$/, '') !== owner.path;
		if (!isDetail) return [{ name: owner.name }];
		return [{ name: owner.name, href: owner.path }, { name: owner.detail }];
	}

	/** Store the chosen theme and apply it to the page. */
	function chooseTheme(chosen) {
		theme = chosen;
		localStorage.setItem('theme', chosen);
		const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
		const systemTheme = prefersDark ? 'dark' : 'light';
		document.documentElement.dataset.theme = chosen === 'system' ? systemTheme : chosen;
	}
</script>

<svg class="svg-defs" aria-hidden="true" focusable="false">
	<defs>
		<filter id="edge-worn" x="-3%" y="-3%" width="106%" height="106%">
			<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="4" seed="5" result="noise" />
			<feDisplacementMap in="SourceGraphic" in2="noise" scale="16" xChannelSelector="R" yChannelSelector="G" />
		</filter>
		<filter id="chisel" x="-5%" y="-25%" width="110%" height="150%">
			<feTurbulence type="fractalNoise" baseFrequency="0.22" numOctaves="2" seed="6" result="noise" />
			<feDisplacementMap in="SourceGraphic" in2="noise" scale="4" result="chipped" />
			<feOffset in="chipped" dx="0" dy="1.5" result="dropped" />
			<feComponentTransfer in="dropped" result="faded"><feFuncA type="linear" slope="0.5" /></feComponentTransfer>
			<feColorMatrix in="faded" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="shadow" />
			<feMerge><feMergeNode in="shadow" /><feMergeNode in="chipped" /></feMerge>
		</filter>
		<pattern id="dither" width="4" height="4" patternUnits="userSpaceOnUse">
			<rect x="0" y="0" width="2" height="2" style="fill: var(--sheet-base)" />
			<rect x="2" y="2" width="2" height="2" style="fill: var(--sheet-base)" />
		</pattern>
	</defs>
</svg>

<div class="desk">
	<header class="sign">
		<a class="brand" href="/">Gufime.com</a>
		<div class="sign-end">
			<nav aria-label="Site">
				<a href="/" aria-current={page.url.pathname === '/' ? 'page' : undefined}>Home</a>
				{#each sections as link (link.path)}
					<a href={link.path} aria-current={section === link ? 'page' : undefined}>{link.name}</a>
				{/each}
			</nav>
			<div class="theme-switch" role="group" aria-label="Theme">
				{#each themes as name (name)}
					<button type="button" aria-pressed={theme === name} onclick={() => chooseTheme(name)}>{themeNames[name]}</button>
				{/each}
			</div>
		</div>
	</header>

	<main class="sheet">
		<div class="sheet-bg" aria-hidden="true"></div>
		<article>
			<nav class="breadcrumbs" aria-label="Breadcrumb">
				<a href="/">Home</a>
				{#each crumbs as crumb (crumb.name)}
					<span aria-hidden="true">›</span>
					{#if crumb.href}
						<a href={crumb.href}>{crumb.name}</a>
					{:else}
						<span aria-current="page">{crumb.name}</span>
					{/if}
				{/each}
			</nav>
			{@render children()}
		</article>
	</main>
</div>
