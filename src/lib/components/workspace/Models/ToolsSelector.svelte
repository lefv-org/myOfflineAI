<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import Checkbox from '$lib/components/common/Checkbox.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { onMount } from 'svelte';

	export let tools: any[] = [];

	let _tools: any = {};

	export let selectedToolIds: any[] = [];

	const i18n = getI18nContext();

	onMount(() => {
		_tools = tools.reduce((acc, tool) => {
			acc[tool.id] = {
				...tool,
				selected: selectedToolIds.includes(tool.id)
			};

			return acc;
		}, {});
	});
</script>

<div>
	<div class="flex w-full justify-between mb-1">
		<div class=" self-center text-xs font-medium text-gray-500">{$i18n.t('Tools')}</div>
	</div>

	<div class="flex flex-col mb-1">
		{#if tools.length > 0}
			<div class=" flex items-center flex-wrap">
				{#each Object.keys(_tools) as tool, toolIdx}
					<div class=" flex items-center gap-2 mr-3">
						<div class="self-center flex items-center">
							<Checkbox
								state={_tools[tool].selected ? 'checked' : 'unchecked'}
								on:change={(e) => {
									_tools[tool].selected = e.detail === 'checked';
									selectedToolIds = Object.keys(_tools).filter((t) => _tools[t].selected);
								}}
							/>
						</div>

						<Tooltip content={_tools[tool]?.meta?.description ?? _tools[tool].id}>
							<div class=" py-0.5 text-sm w-full capitalize font-medium">
								{_tools[tool].name}
							</div>
						</Tooltip>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<div class=" text-xs dark:text-gray-700">
		{$i18n.t('To select toolkits here, add them to the "Tools" workspace first.')}
	</div>
</div>
