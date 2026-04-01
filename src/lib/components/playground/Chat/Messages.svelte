<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import { onMount } from 'svelte';
	import Message from './Message.svelte';

	const i18n = getI18nContext();

	export let messages: any[] = [];
</script>

<div class="py-3 space-y-3">
	{#each messages as message, idx}
		<Message
			{message}
			{idx}
			onDelete={() => {
				messages = messages.filter((message, messageIdx) => messageIdx !== idx);
			}}
		/>
	{/each}
</div>
