<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	;

	const i18n = getI18nContext();

	export let noteId: string;
	export let href: string;
</script>

<!-- Notes feature removed; render as static label -->
<span class="inline-flex items-center px-2 py-0.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs text-gray-500">
	{$i18n.t('Note')}
</span>
