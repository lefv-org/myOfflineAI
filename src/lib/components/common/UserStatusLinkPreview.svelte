<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import { onMount } from 'svelte';
	import { LinkPreview } from 'bits-ui';

	const i18n = getI18nContext();
	import { getUserInfoById } from '$lib/apis/users';

	import UserStatus from './UserStatus.svelte';

	export let id: any = null;

	export let side: 'left' | 'right' | 'bottom' | 'top' = 'top';
	export let align: 'start' | 'end' | 'center' = 'start';
	export let sideOffset = 6;

	let user: any = null;
	onMount(async () => {
		if (id) {
			user = await getUserInfoById(localStorage.token, id).catch((error) => {
				console.error('Error fetching user by ID:', error);
				return null;
			});
		}
	});
</script>

{#if user}
	<LinkPreview.Portal>
		<LinkPreview.Content
			class="w-[260px] rounded-2xl border border-gray-100  dark:border-gray-800 z-[9999] bg-white dark:bg-gray-850 dark:text-white shadow-lg transition"
			{side}
			{align}
			{sideOffset}
		>
			<UserStatus {user} />
		</LinkPreview.Content>
	</LinkPreview.Portal>
{/if}
