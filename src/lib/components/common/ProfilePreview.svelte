<script lang="ts">
	import { getI18nContext } from '$lib/i18n';
	import { LinkPreview } from 'bits-ui';
	;

	const i18n = getI18nContext();
	import UserStatus from './UserStatus.svelte';
	import UserStatusLinkPreview from './UserStatusLinkPreview.svelte';

	export let user: any = null;

	export let align: 'start' | 'end' | 'center' = 'center';
	export let side: 'left' | 'right' | 'bottom' | 'top' = 'right';
	export let sideOffset = 8;

	let openPreview = false;
</script>

<LinkPreview.Root openDelay={0} closeDelay={200} bind:open={openPreview}>
	<LinkPreview.Trigger class="flex items-center">
		<button
			type="button"
			class=" cursor-pointer no-underline! font-normal!"
			on:click={() => {
				openPreview = !openPreview;
			}}
		>
			<slot />
		</button>
	</LinkPreview.Trigger>

	<UserStatusLinkPreview id={user?.id} {side} {align} {sideOffset} />
</LinkPreview.Root>
