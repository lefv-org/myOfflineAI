<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import { createEventDispatcher } from 'svelte';
	;
	const i18n = getI18nContext();

	import TagItem from './TagItem.svelte';
	const dispatch = createEventDispatcher();

	export let tags: any[] = [];
	export let disabled = false;
</script>

{#each tags as tag}
	<TagItem
		{tag}
		{disabled}
		onDelete={() => {
			dispatch('delete', tag.name);
		}}
	/>
{/each}
