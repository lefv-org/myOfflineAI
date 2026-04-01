<script>
	import { getI18nContext } from '$lib/i18n';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';

	import Dashboard from './Analytics/Dashboard.svelte';

	const i18n = getI18nContext();

	let loaded = false;

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
		}
		loaded = true;
	});
</script>

{#if loaded}
	<div class="w-full h-full pb-2 px-[16px]">
		<Dashboard />
	</div>
{/if}
